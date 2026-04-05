from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Literal

from activity_agent.collectors.screenshot.collector import ScreenshotCapture
from activity_agent.config_local import load_local_config
from activity_agent.inference.llm import ollama_evaluate, openai_compatible_evaluate
from activity_agent.inference.ocr import image_to_text
from activity_agent.storage.db import (
    SavedPipelineRow,
    connect,
    init_schema,
    insert_pipeline_result,
    load_row,
)

NotifyFn = Callable[[SavedPipelineRow], None]

LlmProvider = Literal["openai_compatible", "ollama"]


def _pick_str(
    kw: str | None,
    cfg: dict,
    cfg_key: str,
    default: str = "",
) -> str:
    if kw is not None and str(kw).strip():
        return str(kw).strip()
    v = cfg.get(cfg_key)
    if v is not None and str(v).strip():
        return str(v).strip()
    return default


def _pick_provider(cfg: dict, kw: LlmProvider | None) -> LlmProvider:
    if kw is not None:
        return kw
    v = cfg.get("llm_provider")
    if v in ("openai_compatible", "ollama"):
        return v
    return "openai_compatible"


def _pick_int(kw: int | None, cfg: dict, cfg_key: str, default: int) -> int:
    if kw is not None:
        return int(kw)
    if cfg_key in cfg and cfg[cfg_key] is not None:
        return int(cfg[cfg_key])
    return default


def _pick_float(kw: float | None, cfg: dict, cfg_key: str, default: float) -> float:
    if kw is not None:
        return float(kw)
    if cfg_key in cfg and cfg[cfg_key] is not None:
        return float(cfg[cfg_key])
    return default


def _pick_bool(kw: bool | None, cfg: dict, cfg_key: str, default: bool) -> bool:
    if kw is not None:
        return bool(kw)
    if cfg_key in cfg and cfg[cfg_key] is not None:
        return bool(cfg[cfg_key])
    return default


def _pick_optional_int(kw: int | None, cfg: dict, cfg_key: str) -> int | None:
    if kw is not None:
        return int(kw)
    if cfg_key in cfg:
        v = cfg[cfg_key]
        if v is None:
            return None
        return int(v)
    return None


def process_capture(
    captures: Sequence[ScreenshotCapture],
    active_windows: Sequence[str],
    *,
    db_path: Path | None = None,
    llm_provider: LlmProvider | None = None,
    openai_api_key: str | None = None,
    openai_base_url: str | None = None,
    openai_model: str | None = None,
    openai_max_tokens: int | None = None,
    openai_json_mode: bool | None = None,
    ollama_url: str | None = None,
    ollama_model: str | None = None,
    ollama_max_tokens: int | None = None,
    llm_timeout: float | None = None,
    max_image_side: int | None = None,
    on_saved: NotifyFn | None = None,
) -> SavedPipelineRow:
    cfg = load_local_config()
    eff_db = db_path
    if eff_db is None:
        p = cfg.get("db_path")
        eff_db = Path(p) if p else Path("data") / "agent.db"
    provider = _pick_provider(cfg, llm_provider)

    if not captures:
        raise ValueError("captures must not be empty")
    group_ids = {c.group_id for c in captures}
    if len(group_ids) != 1:
        raise ValueError("all captures must share the same group_id")
    group_id = captures[0].group_id
    paths = [c.path for c in captures]
    ordered = sorted(captures, key=lambda c: c.monitor_index)
    paths_ordered = [c.path for c in ordered]

    ocr_per_screen = [image_to_text(p) for p in paths_ordered]
    ocr_combined = "\n\n".join(
        f"--- monitor {i + 1} ---\n{t}" for i, t in enumerate(ocr_per_screen)
    )

    timeout = _pick_float(llm_timeout, cfg, "llm_timeout", 180.0)
    img_side_opt = _pick_optional_int(max_image_side, cfg, "max_image_side")

    if provider == "openai_compatible":
        key = _pick_str(openai_api_key, cfg, "openai_api_key")
        if not key:
            raise ValueError(
                "openai_api_key is missing; set it in local.config.json or pass openai_api_key="
            )
        base = _pick_str(
            openai_base_url,
            cfg,
            "openai_base_url",
            "https://api.openai.com/v1",
        )
        model = _pick_str(
            openai_model,
            cfg,
            "openai_model",
            "gpt-4o-mini",
        )
        img_side = img_side_opt if img_side_opt is not None else 2048
        llm_out = openai_compatible_evaluate(
            paths_ordered,
            active_windows,
            ocr_per_screen,
            api_key=key,
            base_url=base,
            model=model,
            timeout=timeout,
            max_tokens=_pick_int(openai_max_tokens, cfg, "openai_max_tokens", 1024),
            max_image_side=img_side,
            json_mode=_pick_bool(openai_json_mode, cfg, "openai_json_mode", True),
        )
    elif provider == "ollama":
        url = _pick_str(
            ollama_url,
            cfg,
            "ollama_url",
            "http://localhost:11434/api/chat",
        )
        model = _pick_str(ollama_model, cfg, "ollama_model", "llava")
        img_side = img_side_opt if img_side_opt is not None else 1280
        llm_out = ollama_evaluate(
            paths_ordered,
            active_windows,
            ocr_per_screen,
            url=url,
            model=model,
            timeout=timeout,
            max_tokens=_pick_int(ollama_max_tokens, cfg, "ollama_max_tokens", 512),
            max_image_side=img_side,
        )
    else:
        raise ValueError(f"unknown llm_provider: {provider!r}")

    image_path = "|".join(str(p) for p in paths_ordered)
    captured_at = captures[0].captured_at

    conn = connect(eff_db)
    init_schema(conn)
    row_id = insert_pipeline_result(
        conn,
        capture_id=group_id,
        image_path=image_path,
        ocr_text=ocr_combined,
        llm_text=llm_out,
        captured_at=captured_at,
    )
    row = load_row(conn, row_id)
    conn.close()
    if row is None:
        raise RuntimeError("failed to read saved row")
    if on_saved is not None:
        on_saved(row)
    for p in paths:
        p.unlink(missing_ok=True)
    return row
