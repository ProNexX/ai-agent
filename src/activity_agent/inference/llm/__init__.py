"""Vision LLM helpers. Heavy imports (e.g. ``requests``) load on first attribute access."""

from __future__ import annotations

__all__ = [
    "build_activity_json_prompt",
    "clip_ocr_text",
    "ollama_evaluate",
    "openai_compatible_evaluate",
]


def __getattr__(name: str):
    if name == "build_activity_json_prompt":
        from activity_agent.inference.llm.prompt import build_activity_json_prompt

        return build_activity_json_prompt
    if name == "clip_ocr_text":
        from activity_agent.inference.llm.prompt import clip_ocr_text

        return clip_ocr_text
    if name == "ollama_evaluate":
        from activity_agent.inference.llm.ollama import ollama_evaluate

        return ollama_evaluate
    if name == "openai_compatible_evaluate":
        from activity_agent.inference.llm.openai_compatible import openai_compatible_evaluate

        return openai_compatible_evaluate
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
