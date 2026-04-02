from __future__ import annotations

import requests


def ollama_evaluate(
    ocr_text: str,
    url: str = "http://localhost:11434/api/generate",
    model: str = "llama3.2",
    timeout: float = 120.0,
) -> str:
    prompt = (
        "Based on the following text recognized from the user's screen, "
        "briefly describe what they appear to be doing (task focus, apps/context if obvious). "
        "If the text is empty or useless, say so.\n\n---\n"
        + ocr_text[:12000]
    )
    r = requests.post(
        url,
        json={"model": model, "prompt": prompt, "stream": False},
        timeout=timeout,
    )
    r.raise_for_status()
    data = r.json()
    return str(data.get("response", "")).strip()
