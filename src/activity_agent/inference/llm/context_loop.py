from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from activity_agent.inference.llm.ollama import ollama_json_completion
from activity_agent.inference.llm.openai_compatible import openai_compatible_json_completion
from activity_agent.inference.llm.prompt import (
    build_activity_json_prompt_enriched,
    build_context_requests_prompt,
    ocr_limit_for_requests,
    parse_context_requests,
)

LlmProvider = Literal["openai_compatible", "ollama"]


def run_activity_llm_context_loop(
    provider: LlmProvider,
    image_paths: Sequence[Path],
    active_windows: Sequence[str],
    ocr_per_screen: Sequence[str],
    desktop_context_section: str,
    system_load_section: str,
    *,
    past_verified_solutions_section: str,
    openai_api_key: str = "",
    openai_base_url: str = "https://api.openai.com/v1",
    openai_planner_model: str = "",
    openai_final_model: str = "gpt-4o-mini",
    ollama_url: str = "http://localhost:11434/api/chat",
    ollama_planner_model: str = "",
    ollama_final_model: str = "llava",
    timeout: float = 180.0,
    planner_max_tokens: int = 256,
    final_max_tokens: int = 1024,
    max_image_side: int = 2048,
    openai_json_mode: bool = True,
) -> str:
    """Planner pass (minimal text + images) then final activity JSON."""
    n = len(image_paths)
    if len(ocr_per_screen) != n:
        raise ValueError("ocr_per_screen length must match image_paths")

    planner_prompt = build_context_requests_prompt(n, active_windows)

    if provider == "openai_compatible":
        key = str(openai_api_key).strip()
        if not key:
            raise ValueError("openai_api_key is empty")
        planner_model = openai_planner_model or openai_final_model
        plan_raw = openai_compatible_json_completion(
            planner_prompt,
            image_paths,
            api_key=key,
            base_url=openai_base_url,
            model=planner_model,
            timeout=timeout,
            max_tokens=planner_max_tokens,
            max_image_side=max_image_side,
            json_mode=openai_json_mode,
        )
        requests = parse_context_requests(plan_raw)
        ocr_limit = ocr_limit_for_requests(requests)
        past_block = ""
        if "past_verified_solutions" in requests and past_verified_solutions_section.strip():
            past_block = past_verified_solutions_section.strip()
        final_prompt = build_activity_json_prompt_enriched(
            n,
            active_windows,
            ocr_per_screen,
            desktop_context_section=desktop_context_section,
            system_load_section=system_load_section,
            past_solutions_section=past_block,
            ocr_clip_limit=ocr_limit,
        )
        return openai_compatible_json_completion(
            final_prompt,
            image_paths,
            api_key=key,
            base_url=openai_base_url,
            model=openai_final_model,
            timeout=timeout,
            max_tokens=final_max_tokens,
            max_image_side=max_image_side,
            json_mode=openai_json_mode,
        )

    if provider == "ollama":
        planner_model = ollama_planner_model or ollama_final_model
        plan_raw = ollama_json_completion(
            planner_prompt,
            image_paths,
            url=ollama_url,
            model=planner_model,
            timeout=timeout,
            max_tokens=planner_max_tokens,
            max_image_side=max_image_side,
        )
        requests = parse_context_requests(plan_raw)
        ocr_limit = ocr_limit_for_requests(requests)
        past_block = ""
        if "past_verified_solutions" in requests and past_verified_solutions_section.strip():
            past_block = past_verified_solutions_section.strip()
        final_prompt = build_activity_json_prompt_enriched(
            n,
            active_windows,
            ocr_per_screen,
            desktop_context_section=desktop_context_section,
            system_load_section=system_load_section,
            past_solutions_section=past_block,
            ocr_clip_limit=ocr_limit,
        )
        return ollama_json_completion(
            final_prompt,
            image_paths,
            url=ollama_url,
            model=ollama_final_model,
            timeout=timeout,
            max_tokens=final_max_tokens,
            max_image_side=max_image_side,
        )

    raise ValueError(f"unknown llm_provider: {provider!r}")
