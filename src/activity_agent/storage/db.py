from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

@dataclass(frozen=True)
class SavedPipelineRow:
    id: int
    capture_id: str
    image_path: str
    ocr_text: str
    llm_text: str

def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(str(db_path))

def init_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS pipeline_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            capture_id TEXT NOT NULL,
            image_path TEXT NOT NULL,
            ocr_text TEXT NOT NULL,
            llm_text TEXT NOT NULL,
            captured_at TEXT NOT NULL,
            processed_at TEXT NOT NULL
        )
        """
    )
    conn.commit()

def insert_pipeline_result(
    conn: sqlite3.Connection,
    capture_id: str,
    image_path: str,
    ocr_text: str,
    llm_text: str,
    captured_at: datetime,
) -> int:
    processed = datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        """
        INSERT INTO pipeline_results
        (capture_id, image_path, ocr_text, llm_text, captured_at, processed_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            capture_id,
            image_path,
            ocr_text,
            llm_text,
            captured_at.isoformat(),
            processed,
        ),
    )
    conn.commit()
    return int(cur.lastrowid)

def load_row(conn: sqlite3.Connection, row_id: int) -> SavedPipelineRow | None:
    cur = conn.execute(
        "SELECT id, capture_id, image_path, ocr_text, llm_text "
        "FROM pipeline_results WHERE id = ?",
        (row_id,),
    )
    tup = cur.fetchone()
    if not tup:
        return None
    return SavedPipelineRow(
        id=tup[0],
        capture_id=tup[1],
        image_path=tup[2],
        ocr_text=tup[3],
        llm_text=tup[4],
    )
