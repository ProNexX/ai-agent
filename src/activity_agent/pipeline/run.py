from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from activity_agent.collectors.screenshot.collector import ScreenshotCapture
from activity_agent.inference.llm_ollama import ollama_evaluate
from activity_agent.inference.ocr_text import image_to_text
from activity_agent.storage.db import (
    SavedPipelineRow,
    connect,
    init_schema,
    insert_pipeline_result,
    load_row,
)

NotifyFn = Callable[[SavedPipelineRow], None]


def process_capture(
    capture: ScreenshotCapture,
    *,
    db_path: Path = Path("data") / "agent.db",
    ollama_url: str = "http://localhost:11434/api/generate",
    ollama_model: str = "llama3.2",
    on_saved: NotifyFn | None = None,
) -> SavedPipelineRow:
    ocr_plain = image_to_text(capture.path)
    llm_out = ollama_evaluate(ocr_plain, url=ollama_url, model=ollama_model)

    conn = connect(db_path)
    init_schema(conn)
    row_id = insert_pipeline_result(
        conn,
        capture_id=capture.id,
        image_path=str(capture.path),
        ocr_text=ocr_plain,
        llm_text=llm_out,
        captured_at=capture.captured_at,
    )
    row = load_row(conn, row_id)
    conn.close()
    if row is None:
        raise RuntimeError("failed to read saved row")
    if on_saved is not None:
        on_saved(row)
    return row
