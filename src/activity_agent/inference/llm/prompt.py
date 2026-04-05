from __future__ import annotations

from collections.abc import Sequence

_OCR_PER_SCREEN_MAX = 5000


def clip_ocr_text(text: str, limit: int = _OCR_PER_SCREEN_MAX) -> str:
    t = text.strip()
    if len(t) <= limit:
        return t
    return t[: limit - 1] + "..."


def build_activity_json_prompt(
    num_screens: int,
    active_windows: Sequence[str],
    ocr_per_screen: Sequence[str],
) -> str:
    if len(ocr_per_screen) != num_screens:
        raise ValueError("ocr_per_screen length must match num_screens")
    monitor_note = (
        "Images are one per monitor in order (first image = monitor 1)."
        if num_screens > 1
        else "Single monitor image."
    )
    ocr_blocks = []
    for i, raw in enumerate(ocr_per_screen):
        clipped = clip_ocr_text(raw)
        ocr_blocks.append(f"--- OCR monitor {i + 1} ---\n{clipped or '(no text detected)'}")
    ocr_section = "\n\n".join(ocr_blocks)
    titles = "\n".join(f"- {t}" for t in active_windows[:80]) or "(none listed)"
    schema_hint = (
        '{"tasks":["short string",...],'
        '"distractions":["short string",...],'
        '"problems":["short string",...]}'
    )
    return (
        f"{monitor_note}\n\n"
        "Window titles (may be incomplete):\n"
        f"{titles}\n\n"
        "OCR text extracted per monitor (may have errors; use with the images):\n"
        f"{ocr_section}\n\n"
        "Respond with ONLY valid JSON. No markdown code fences, no explanation before or after. "
        f"Use this exact shape (arrays of strings; use [] when none): {schema_hint}\n"
        "tasks: work the user appears focused on. "
        "distractions: off-task or interrupting context. "
        "problems: errors, blockers, confusion, or struggle visible from screen or OCR."
    )
