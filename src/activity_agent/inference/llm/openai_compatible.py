from __future__ import annotations

import base64
import io
from collections.abc import Sequence
from pathlib import Path
from urllib.parse import urlparse

import requests

from activity_agent.inference.llm.prompt import build_activity_json_prompt

_DEFAULT_MAX_IMAGE_SIDE = 2048


def _chat_completions_url(base_url: str) -> str:
    raw = (base_url or "").strip().rstrip("/")
    if not raw:
        raw = "https://api.openai.com/v1"
    if raw.endswith("/chat/completions"):
        return raw
    p = urlparse(raw) if "://" in raw else urlparse("https://" + raw)
    scheme = p.scheme or "https"
    netloc = p.netloc
    path = (p.path or "").rstrip("/")
    if path == "":
        path = "/v1"
    elif not path.endswith("/v1"):
        path = f"{path}/v1"
    base = f"{scheme}://{netloc}{path}"
    return f"{base}/chat/completions"


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


def openai_compatible_evaluate(
    image_paths: Sequence[Path],
    active_windows: Sequence[str],
    ocr_per_screen: Sequence[str],
    *,
    api_key: str,
    base_url: str = "https://api.openai.com/v1",
    model: str = "gpt-4o-mini",
    timeout: float = 180.0,
    max_tokens: int = 1024,
    max_image_side: int = _DEFAULT_MAX_IMAGE_SIDE,
    json_mode: bool = True,
) -> str:
    api_key = str(api_key).strip()
    if not api_key:
        raise ValueError("api_key is empty")
    n = len(image_paths)
    if len(ocr_per_screen) != n:
        raise ValueError("ocr_per_screen length must match image_paths")
    prompt = build_activity_json_prompt(n, active_windows, ocr_per_screen)
    content: list[dict[str, object]] = [{"type": "text", "text": prompt}]
    for p in image_paths:
        data = _png_bytes_for_model(p.resolve(), max_image_side)
        b64 = base64.standard_b64encode(data).decode("ascii")
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64}"},
            }
        )
    url = _chat_completions_url(base_url)
    payload: dict[str, object] = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    r = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=timeout,
    )
    try:
        data = r.json()
    except Exception:
        return ""
    choices = data.get("choices") or []
    if not choices:
        return ""
    msg = choices[0].get("message") or {}
    return str(msg.get("content", "")).strip()
