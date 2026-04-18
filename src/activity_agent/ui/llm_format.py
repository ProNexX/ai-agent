from __future__ import annotations

import json
from typing import Any

from activity_agent.inference.llm.json_fence import strip_json_fence


def short_ts(iso: str) -> str:
    s = iso.strip()
    if "T" in s:
        s = s.replace("T", " ", 1)
    return s[:19] if len(s) >= 19 else s


def preview_text(text: str, n: int = 72) -> str:
    t = " ".join(text.strip().split())
    if len(t) <= n:
        return t
    return t[: n - 1] + "…"


def format_llm_activity_json(raw: str) -> tuple[str, str]:
    """Return (human summary, pretty JSON or raw fallback)."""
    stripped = strip_json_fence(raw)
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

    def _bullet_list(title: str, val: Any) -> str:
        line = [title, "-" * max(len(title), 3)]
        if isinstance(val, list):
            if not val:
                line.append("  (none)")
            else:
                for item in val:
                    if isinstance(item, dict):
                        line.append("  •")
                        for dk, dv in item.items():
                            if isinstance(dv, (dict, list)):
                                line.append(f"    {dk}: {json.dumps(dv, ensure_ascii=False)}")
                            else:
                                line.append(f"    {dk}: {dv}")
                    else:
                        line.append(f"  • {item}")
        elif val is None or val == "":
            line.append("  (none)")
        else:
            line.append(f"  {val}")
        return "\n".join(line)

    for key, title in (
        ("tasks", "Tasks"),
        ("distractions", "Distractions"),
        ("problems", "Problems"),
    ):
        sections.append(_bullet_list(title, data.get(key, [])))

    sections.append(
        _bullet_list("Problem solutions", data.get("problem_solutions", [])),
    )

    extra = {
        k: v
        for k, v in data.items()
        if k
        not in ("tasks", "distractions", "problems", "problem_solutions")
    }
    if extra:
        sections.append("Other fields\n------------")
        sections.append(json.dumps(extra, indent=2, ensure_ascii=False))

    summary = "\n\n".join(sections).strip() + "\n"
    pretty = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    return summary, pretty


def llm_tree_preview(raw: str, n: int = 80) -> str:
    try:
        data = json.loads(strip_json_fence(raw))
        if isinstance(data, dict):
            tasks = data.get("tasks")
            if isinstance(tasks, list) and tasks:
                return preview_text(str(tasks[0]), n)
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return preview_text(raw, n)
