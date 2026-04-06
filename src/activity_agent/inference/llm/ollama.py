from __future__ import annotations

import base64
import io
from collections.abc import Sequence
from pathlib import Path

import requests

from activity_agent.inference.llm.prompt import build_activity_json_prompt

_DEFAULT_MAX_IMAGE_SIDE = 1280

def _png_bytes_for_model(path: Path, max_side: int) -> bytes:
    raw = path.read_bytes()
    try:
        from PIL import Image
    except ModuleNotFoundError:
        return raw
    with Image.open(io.BytesIO(raw)) as im:
        w, h = im.size
        if max(w, h) <= max_side:
            return raw
        scale = max_side / max(w, h)
        nw, nh = int(w * scale), int(h * scale)
        rgb = im.convert("RGB").resize((nw, nh), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        rgb.save(buf, format="PNG")
        return buf.getvalue()

def ollama_evaluate(
    image_paths: Sequence[Path],
    active_windows: Sequence[str],
    ocr_per_screen: Sequence[str],
    desktop_context_section: str = "",
    system_load_section: str = "",
    url: str = "http://localhost:11434/api/chat",
    model: str = "llava",
    timeout: float = 120.0,
    *,
    max_tokens: int = 512,
    max_image_side: int = _DEFAULT_MAX_IMAGE_SIDE,
) -> str:
    n = len(image_paths)
    if len(ocr_per_screen) != n:
        raise ValueError("ocr_per_screen length must match image_paths")
    prompt = build_activity_json_prompt(
        n,
        active_windows,
        ocr_per_screen,
        desktop_context_section=desktop_context_section,
        system_load_section=system_load_section,
    )
    images_b64: list[str] = []
    for p in image_paths:
        data = _png_bytes_for_model(p.resolve(), max_image_side)
        images_b64.append(base64.b64encode(data).decode("ascii"))
    r = requests.post(
        url,
        json={
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": images_b64,
                }
            ],
            "stream": False,
            "format": "json",
            "options": {"num_predict": max_tokens},
        },
        timeout=timeout,
    )
    r.raise_for_status()
    data = r.json()
    msg = data.get("message") or {}
    return str(msg.get("content", "")).strip()
