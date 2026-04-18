from __future__ import annotations

import json
from collections.abc import Sequence

from activity_agent.inference.llm.json_fence import strip_json_fence

_OCR_PER_SCREEN_MAX = 5000
_OCR_PER_SCREEN_FULL = 15000

# IDs the planner may return in `context_requests` (machine-fulfilled only).
# Desktop/focus and system load are always included in the final analysis step.
FULFILLABLE_CONTEXT_REQUEST_IDS: tuple[str, ...] = (
    "full_ocr",
    "past_verified_solutions",
)

# Shared rules so the model does not treat passive UI chrome as "distractions".
_OCR_LABEL_GUIDANCE = (
    "How to use OCR vs labels: OCR often includes passive browser or app chrome "
    "(bookmark bar, tab titles, sidebars, toolbars, address bar, menus, system tray) "
    "that is visible even while the user is focused on legitimate work. "
    "Do NOT list bookmarks, tab labels, or other static chrome as distractions unless "
    "they clearly show the user is engaged with off-task content in the main viewport "
    "(e.g. the focused tab or central pane is social media, games, or shopping while "
    "work tools are only in the background). "
    "Infer tasks from the foreground window, the main reading/editing area in the image, "
    "and window titles; treat peripheral OCR lines as context, not automatic distractions. "
    "distractions: only concrete off-task engagement you can justify from primary content "
    "or focus, not mere presence of navigational text. "
    "Use an empty distractions array when the user appears on-task.\n\n"
)


def parse_context_requests(raw: str) -> set[str]:
    try:
        data = json.loads(strip_json_fence(raw))
    except json.JSONDecodeError:
        return set()
    if not isinstance(data, dict):
        return set()
    req = data.get("context_requests")
    if not isinstance(req, list):
        return set()
    allowed = set(FULFILLABLE_CONTEXT_REQUEST_IDS)
    out: set[str] = set()
    for item in req:
        if isinstance(item, str) and item in allowed:
            out.add(item)
    return out


def clip_ocr_text(text: str, limit: int = _OCR_PER_SCREEN_MAX) -> str:
    t = text.strip()
    if len(t) <= limit:
        return t
    return t[: limit - 1] + "..."

def build_activity_json_prompt(
    num_screens: int,
    active_windows: Sequence[str],
    ocr_per_screen: Sequence[str],
    desktop_context_section: str = "",
    system_load_section: str = "",
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
    ctx = (desktop_context_section or "").strip()
    context_block = (
        f"System / input / focus context:\n{ctx}\n\n" if ctx else ""
    )
    load = (system_load_section or "").strip()
    load_block = f"System load snapshot:\n{load}\n\n" if load else ""
    schema_hint = (
        '{"tasks":["short string",...],'
        '"distractions":["short string",...],'
        '"problems":["short string",...]}'
    )
    return (
        f"{monitor_note}\n\n"
        f"{context_block}"
        f"{load_block}"
        "Window titles (may be incomplete):\n"
        f"{titles}\n\n"
        "OCR text extracted per monitor (may have errors; use with the images):\n"
        f"{ocr_section}\n\n"
        f"{_OCR_LABEL_GUIDANCE}"
        "Respond with ONLY valid JSON. No markdown code fences, no explanation before or after. "
        f"Use this exact shape (arrays of strings; use [] when none): {schema_hint}\n"
        "tasks: work the user appears focused on (main content / foreground activity). "
        "distractions: only justified off-task engagement, not bookmark bars or passive UI text alone. "
        "problems: errors, blockers, confusion, or struggle visible from screen or OCR."
    )


def build_context_requests_prompt(
    num_screens: int,
    active_windows: Sequence[str],
) -> str:
    """First-pass prompt: screenshots attached separately; minimal text context."""
    monitor_note = (
        "Images are one per monitor in order (first image = monitor 1)."
        if num_screens > 1
        else "Single monitor image."
    )
    titles = "\n".join(f"- {t}" for t in active_windows[:80]) or "(none listed)"
    ids_list = ", ".join(f'"{x}"' for x in FULFILLABLE_CONTEXT_REQUEST_IDS)
    return (
        f"{monitor_note}\n\n"
        "You will receive a full activity analysis prompt in a follow-up step. "
        "Right now, only window titles (below) are provided as text — no OCR and "
        "no prior user-confirmed fixes. The next step always adds desktop/focus context, "
        "system load, and clipped OCR.\n\n"
        "Window titles (may be incomplete):\n"
        f"{titles}\n\n"
        "Decide which **optional extra text** would most improve your eventual analysis. "
        "You cannot request new screenshots.\n\n"
        "Respond with ONLY valid JSON. No markdown fences. Shape:\n"
        '{"context_requests":["id",...],"rationale":"short string"}\n'
        f"Each id must be one of: {ids_list}\n"
        "Use an empty array if the defaults will be enough.\n"
        "full_ocr: use less-truncated OCR in the next step (longer text per monitor).\n"
        "past_verified_solutions: include user-confirmed fixes from earlier sessions.\n"
    )


def build_activity_json_prompt_enriched(
    num_screens: int,
    active_windows: Sequence[str],
    ocr_per_screen: Sequence[str],
    desktop_context_section: str = "",
    system_load_section: str = "",
    *,
    extra_sections: str = "",
    past_solutions_section: str = "",
    ocr_clip_limit: int = _OCR_PER_SCREEN_MAX,
) -> str:
    """Final activity prompt with optional blocks and problem/solution schema."""
    if len(ocr_per_screen) != num_screens:
        raise ValueError("ocr_per_screen length must match num_screens")
    monitor_note = (
        "Images are one per monitor in order (first image = monitor 1)."
        if num_screens > 1
        else "Single monitor image."
    )
    ocr_blocks = []
    for i, raw in enumerate(ocr_per_screen):
        clipped = clip_ocr_text(raw, limit=ocr_clip_limit)
        ocr_blocks.append(f"--- OCR monitor {i + 1} ---\n{clipped or '(no text detected)'}")
    ocr_section = "\n\n".join(ocr_blocks)
    titles = "\n".join(f"- {t}" for t in active_windows[:80]) or "(none listed)"
    ctx = (desktop_context_section or "").strip()
    context_block = (
        f"System / input / focus context:\n{ctx}\n\n" if ctx else ""
    )
    load = (system_load_section or "").strip()
    load_block = f"System load snapshot:\n{load}\n\n" if load else ""
    extra = (extra_sections or "").strip()
    extra_block = f"{extra}\n\n" if extra else ""
    past = (past_solutions_section or "").strip()
    past_block = f"{past}\n\n" if past else ""
    schema_hint = (
        '{"tasks":["short string",...],'
        '"distractions":["short string",...],'
        '"problems":["short string",...],'
        '"problem_solutions":['
        '{"problem":"short string","suggested_solution":"short string",'
        '"ask_user_if_they_want_this_solution":true|false}'
        "]}"
    )
    return (
        f"{monitor_note}\n\n"
        f"{extra_block}"
        f"{past_block}"
        f"{context_block}"
        f"{load_block}"
        "Window titles (may be incomplete):\n"
        f"{titles}\n\n"
        "OCR text extracted per monitor (may have errors; use with the images):\n"
        f"{ocr_section}\n\n"
        f"{_OCR_LABEL_GUIDANCE}"
        "Respond with ONLY valid JSON. No markdown code fences, no explanation before or after. "
        f"Use this exact shape: {schema_hint}\n"
        "tasks: work the user appears focused on (main content / foreground activity). "
        "distractions: only justified off-task engagement, not bookmark bars or passive UI text alone. "
        "problems: short labels for errors, blockers, confusion, or struggle. "
        "problem_solutions: for significant problems, give a concrete suggested_solution "
        "(steps, settings, or commands). Set ask_user_if_they_want_this_solution to true "
        "when the fix is non-trivial or risky and the user should opt in; use false when "
        "the advice is safe to apply without asking. Use an empty array when none apply.\n"
    )


def ocr_limit_for_requests(requests: set[str]) -> int:
    return _OCR_PER_SCREEN_FULL if "full_ocr" in requests else _OCR_PER_SCREEN_MAX
