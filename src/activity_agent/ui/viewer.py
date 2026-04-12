from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any

from activity_agent.config_local import load_local_config
from activity_agent.core.models import PipelineResultRecord
from activity_agent.storage.db import (
    connect,
    fetch_pipeline_result,
    init_schema,
    list_pipeline_results,
)


def _resolve_db_path(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit.resolve()
    cfg = load_local_config()
    p = cfg.get("db_path")
    return Path(p).resolve() if p else (Path.cwd() / "data" / "agent.db").resolve()


def _short_ts(iso: str) -> str:
    s = iso.strip()
    if "T" in s:
        s = s.replace("T", " ", 1)
    return s[:19] if len(s) >= 19 else s


def _preview(text: str, n: int = 72) -> str:
    t = " ".join(text.strip().split())
    if len(t) <= n:
        return t
    return t[: n - 1] + "…"


def _strip_json_fence(s: str) -> str:
    t = s.strip()
    if not t.startswith("```"):
        return t
    t = re.sub(r"^```(?:json)?\s*", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s*```\s*$", "", t)
    return t.strip()


def _format_llm_activity_json(raw: str) -> tuple[str, str]:
    stripped = _strip_json_fence(raw)
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError:
        return (
            "LLM output is not valid JSON. See the Raw tab for the full text.\n",
            raw,
        )
    if not isinstance(data, dict):
        pretty = json.dumps(data, indent=2, ensure_ascii=False)
        return pretty + "\n", pretty + "\n"

    sections: list[str] = []
    for key, title in (
        ("tasks", "Tasks"),
        ("distractions", "Distractions"),
        ("problems", "Problems"),
    ):
        val = data.get(key, [])
        line = [title, "-" * max(len(title), 3)]
        if isinstance(val, list):
            if not val:
                line.append("  (none)")
            else:
                for item in val:
                    line.append(f"  • {item}")
        elif val is None or val == "":
            line.append("  (none)")
        else:
            line.append(f"  {val}")
        sections.append("\n".join(line))

    extra = {k: v for k, v in data.items() if k not in ("tasks", "distractions", "problems")}
    if extra:
        sections.append("Other fields\n------------")
        sections.append(json.dumps(extra, indent=2, ensure_ascii=False))

    summary = "\n\n".join(sections).strip() + "\n"
    pretty = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    return summary, pretty


def _llm_tree_preview(raw: str, n: int = 80) -> str:
    try:
        data = json.loads(_strip_json_fence(raw))
        if isinstance(data, dict):
            tasks = data.get("tasks")
            if isinstance(tasks, list) and tasks:
                return _preview(str(tasks[0]), n)
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return _preview(raw, n)


def _run_app(db_path: Path) -> None:
    try:
        import tkinter as tk
        from tkinter import messagebox, ttk
        from tkinter.scrolledtext import ScrolledText
    except ImportError as e:
        raise SystemExit(
            "The results viewer needs tkinter. On Linux install your distro's tk binding "
            "(e.g. Arch/CachyOS: sudo pacman -S tk; Debian/Ubuntu: sudo apt install python3-tk)."
        ) from e

    class _ResultsApp:
        def __init__(self, path: Path) -> None:
            self._db_path = path
            self._conn: sqlite3.Connection | None = None

            self.root = tk.Tk()
            self.root.title("Activity agent — pipeline results")
            self.root.minsize(720, 480)
            self.root.geometry("960x640")

            outer = ttk.Frame(self.root, padding=8)
            outer.pack(fill=tk.BOTH, expand=True)

            toolbar = ttk.Frame(outer)
            toolbar.pack(fill=tk.X, pady=(0, 8))
            self._path_var = tk.StringVar(value=str(path))
            ttk.Label(toolbar, textvariable=self._path_var, wraplength=560).pack(
                side=tk.LEFT, fill=tk.X, expand=True
            )
            ttk.Button(toolbar, text="Refresh", command=self._reload_list).pack(
                side=tk.RIGHT, padx=(8, 0)
            )

            hpaned = ttk.PanedWindow(outer, orient=tk.HORIZONTAL)
            hpaned.pack(fill=tk.BOTH, expand=True)

            left = ttk.Frame(hpaned, width=300)
            hpaned.add(left, weight=0)

            tree_frame = ttk.Frame(left)
            tree_frame.pack(fill=tk.BOTH, expand=True)
            scroll_y = ttk.Scrollbar(tree_frame)
            scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
            self._tree = ttk.Treeview(
                tree_frame,
                columns=("id", "captured", "capture_id", "preview"),
                show="headings",
                yscrollcommand=scroll_y.set,
                height=18,
            )
            scroll_y.config(command=self._tree.yview)
            self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            self._tree.heading("id", text="ID")
            self._tree.heading("captured", text="Worked at")
            self._tree.heading("capture_id", text="Capture ID")
            self._tree.heading("preview", text="First task / preview")
            self._tree.column("id", width=48, stretch=False)
            self._tree.column("captured", width=150, stretch=False)
            self._tree.column("capture_id", width=120, stretch=False)
            self._tree.column("preview", width=200, stretch=True)
            self._tree.bind("<<TreeviewSelect>>", self._on_select)

            right = ttk.Frame(hpaned)
            hpaned.add(right, weight=1)

            meta = ttk.LabelFrame(right, text="Row", padding=6)
            meta.pack(fill=tk.X, pady=(0, 6))
            self._meta_var = tk.StringVar(value="Select a row.")
            ttk.Label(
                meta,
                textvariable=self._meta_var,
                justify=tk.LEFT,
                wraplength=520,
            ).pack(anchor=tk.W, fill=tk.X)

            ocr_lab = ttk.LabelFrame(right, text="OCR", padding=4)
            ocr_lab.pack(fill=tk.BOTH, expand=True, pady=(0, 6))
            self._ocr = ScrolledText(ocr_lab, height=10, wrap=tk.WORD, state=tk.DISABLED)
            self._ocr.pack(fill=tk.BOTH, expand=True)

            llm_lab = ttk.LabelFrame(right, text="LLM", padding=4)
            llm_lab.pack(fill=tk.BOTH, expand=True)
            self._llm_nb = ttk.Notebook(llm_lab)
            self._llm_nb.pack(fill=tk.BOTH, expand=True)
            sum_tab = ttk.Frame(self._llm_nb, padding=2)
            raw_tab = ttk.Frame(self._llm_nb, padding=2)
            self._llm_nb.add(sum_tab, text="Summary")
            self._llm_nb.add(raw_tab, text="Raw")
            self._llm_summary = ScrolledText(sum_tab, height=10, wrap=tk.WORD, state=tk.DISABLED)
            self._llm_summary.pack(fill=tk.BOTH, expand=True)
            self._llm_raw = ScrolledText(raw_tab, height=10, wrap=tk.WORD, state=tk.DISABLED)
            self._llm_raw.pack(fill=tk.BOTH, expand=True)

            self.root.protocol("WM_DELETE_WINDOW", self._on_close)

            self._open_db()

        def _open_db(self) -> None:
            try:
                self._db_path.parent.mkdir(parents=True, exist_ok=True)
                self._conn = connect(self._db_path)
                init_schema(self._conn)
            except OSError as e:
                messagebox.showerror("Database", str(e), parent=self.root)
                self.root.after(100, self.root.destroy)
                return
            self._path_var.set(str(self._db_path))
            self._reload_list()

        def _on_close(self) -> None:
            if self._conn is not None:
                self._conn.close()
                self._conn = None
            self.root.destroy()

        def _set_text(self, widget: Any, content: str) -> None:
            widget.configure(state=tk.NORMAL)
            widget.delete("1.0", tk.END)
            widget.insert(tk.END, content)
            widget.configure(state=tk.DISABLED)

        def _clear_detail(self) -> None:
            self._meta_var.set("Select a row.")
            self._set_text(self._ocr, "")
            self._set_text(self._llm_summary, "")
            self._set_text(self._llm_raw, "")

        def _reload_list(self) -> None:
            if self._conn is None:
                return
            self._clear_detail()
            for iid in self._tree.get_children():
                self._tree.delete(iid)
            try:
                rows = list_pipeline_results(self._conn, limit=500)
            except sqlite3.Error as e:
                messagebox.showerror("Query failed", str(e), parent=self.root)
                return
            for rec in rows:
                self._tree.insert(
                    "",
                    "end",
                    iid=str(rec.id),
                    values=(
                        str(rec.id),
                        _short_ts(rec.worked_at),
                        _preview(rec.capture_id, 36),
                        _llm_tree_preview(rec.llm_text, 80),
                    ),
                )

        def _show_record(self, rec: PipelineResultRecord) -> None:
            meta = (
                f"Worked at (session): {_short_ts(rec.worked_at)}  ({rec.worked_at})\n"
                f"Screen capture UTC: {rec.captured_at}\n"
                f"Saved to DB: {rec.processed_at}\n"
                f"id={rec.id}\n"
                f"capture_id={rec.capture_id}\n"
                f"image_path={rec.image_path}"
            )
            self._meta_var.set(meta)
            self._set_text(self._ocr, rec.ocr_text)
            summary, raw = _format_llm_activity_json(rec.llm_text)
            self._set_text(self._llm_summary, summary)
            self._set_text(self._llm_raw, raw)

        def _on_select(self, _event: object | None = None) -> None:
            if self._conn is None:
                return
            sel = self._tree.selection()
            if not sel:
                self._clear_detail()
                return
            try:
                rid = int(sel[0])
            except ValueError:
                return
            rec = fetch_pipeline_result(self._conn, rid)
            if rec is None:
                self._clear_detail()
                return
            self._show_record(rec)

        def run(self) -> None:
            self.root.mainloop()

    _ResultsApp(db_path).run()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Browse pipeline_results in SQLite")
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="SQLite file (default: db_path from local.config.json or data/agent.db)",
    )
    args = parser.parse_args(argv)
    _run_app(_resolve_db_path(args.db))
    return 0


if __name__ == "__main__":
    sys.exit(main())
