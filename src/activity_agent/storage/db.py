from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from activity_agent.core.models import PipelineResultRecord, SavedPipelineRow


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(str(db_path))

def _migrate_worked_at(conn: sqlite3.Connection) -> None:
    cur = conn.execute("PRAGMA table_info(pipeline_results)")
    cols = {row[1] for row in cur.fetchall()}
    if "worked_at" in cols:
        return
    conn.execute("ALTER TABLE pipeline_results ADD COLUMN worked_at TEXT")
    conn.execute(
        "UPDATE pipeline_results SET worked_at = captured_at "
        "WHERE worked_at IS NULL OR worked_at = ''"
    )


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
    _migrate_worked_at(conn)
    conn.commit()

def insert_pipeline_result(
    conn: sqlite3.Connection,
    capture_id: str,
    image_path: str,
    ocr_text: str,
    llm_text: str,
    captured_at: datetime,
    *,
    worked_at: datetime | None = None,
) -> int:
    processed = datetime.now(timezone.utc).isoformat()
    cap_iso = captured_at.isoformat()
    work_iso = (worked_at or captured_at).isoformat()
    cur = conn.execute(
        """
        INSERT INTO pipeline_results
        (capture_id, image_path, ocr_text, llm_text, captured_at, processed_at, worked_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            capture_id,
            image_path,
            ocr_text,
            llm_text,
            cap_iso,
            processed,
            work_iso,
        ),
    )
    conn.commit()
    return int(cur.lastrowid)

def load_row(conn: sqlite3.Connection, row_id: int) -> SavedPipelineRow | None:
    cur = conn.execute(
        """
        SELECT id, capture_id, image_path, ocr_text, llm_text,
               captured_at, processed_at, worked_at
        FROM pipeline_results WHERE id = ?
        """,
        (row_id,),
    )
    tup = cur.fetchone()
    if not tup:
        return None
    worked = tup[7] if tup[7] else tup[5]
    return SavedPipelineRow(
        id=tup[0],
        capture_id=tup[1],
        image_path=tup[2],
        ocr_text=tup[3],
        llm_text=tup[4],
        captured_at=tup[5],
        processed_at=tup[6],
        worked_at=worked,
    )


def list_pipeline_results(
    conn: sqlite3.Connection,
    *,
    limit: int = 500,
    offset: int = 0,
) -> list[PipelineResultRecord]:
    cur = conn.execute(
        """
        SELECT id, capture_id, image_path, ocr_text, llm_text,
               captured_at, processed_at, worked_at
        FROM pipeline_results
        ORDER BY id DESC
        LIMIT ? OFFSET ?
        """,
        (limit, offset),
    )
    out: list[PipelineResultRecord] = []
    for row in cur.fetchall():
        worked = row[7] if row[7] else row[5]
        out.append(
            PipelineResultRecord(
                id=row[0],
                capture_id=row[1],
                image_path=row[2],
                ocr_text=row[3],
                llm_text=row[4],
                captured_at=row[5],
                processed_at=row[6],
                worked_at=worked,
            )
        )
    return out


def fetch_pipeline_result(
    conn: sqlite3.Connection,
    row_id: int,
) -> PipelineResultRecord | None:
    cur = conn.execute(
        """
        SELECT id, capture_id, image_path, ocr_text, llm_text,
               captured_at, processed_at, worked_at
        FROM pipeline_results WHERE id = ?
        """,
        (row_id,),
    )
    row = cur.fetchone()
    if not row:
        return None
    worked = row[7] if row[7] else row[5]
    return PipelineResultRecord(
        id=row[0],
        capture_id=row[1],
        image_path=row[2],
        ocr_text=row[3],
        llm_text=row[4],
        captured_at=row[5],
        processed_at=row[6],
        worked_at=worked,
    )
