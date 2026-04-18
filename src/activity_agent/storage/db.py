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


def _ensure_verified_solutions(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS verified_solutions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            problem_summary TEXT NOT NULL,
            solution_text TEXT NOT NULL,
            pipeline_result_id INTEGER,
            verified_at TEXT NOT NULL
        )
        """
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
    _ensure_verified_solutions(conn)
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


def insert_verified_solution(
    conn: sqlite3.Connection,
    *,
    problem_summary: str,
    solution_text: str,
    pipeline_result_id: int | None = None,
) -> int:
    _ensure_verified_solutions(conn)
    verified = datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        """
        INSERT INTO verified_solutions
        (problem_summary, solution_text, pipeline_result_id, verified_at)
        VALUES (?, ?, ?, ?)
        """,
        (problem_summary.strip(), solution_text.strip(), pipeline_result_id, verified),
    )
    conn.commit()
    return int(cur.lastrowid)


def list_verified_solutions(
    conn: sqlite3.Connection,
    *,
    limit: int = 100,
) -> list[dict[str, int | str | None]]:
    """Recent verified fixes for UI (newest first)."""
    _ensure_verified_solutions(conn)
    lim = max(1, min(int(limit), 500))
    cur = conn.execute(
        """
        SELECT id, problem_summary, solution_text, pipeline_result_id, verified_at
        FROM verified_solutions
        ORDER BY id DESC
        LIMIT ?
        """,
        (lim,),
    )
    out: list[dict[str, int | str | None]] = []
    for row in cur.fetchall():
        out.append(
            {
                "id": int(row[0]),
                "problem_summary": str(row[1]),
                "solution_text": str(row[2]),
                "pipeline_result_id": int(row[3]) if row[3] is not None else None,
                "verified_at": str(row[4]),
            }
        )
    return out


def verified_solutions_prompt_section(
    conn: sqlite3.Connection,
    *,
    limit: int = 8,
) -> str:
    """Human-readable block for LLM prompts; empty if none."""
    _ensure_verified_solutions(conn)
    lim = max(1, min(int(limit), 50))
    cur = conn.execute(
        """
        SELECT problem_summary, solution_text
        FROM verified_solutions
        ORDER BY id DESC
        LIMIT ?
        """,
        (lim,),
    )
    rows = cur.fetchall()
    if not rows:
        return ""
    lines = [
        "Previously verified fixes (user confirmed these worked; use as hints, not facts):"
    ]
    for prob, sol in rows:
        lines.append(f"- Problem: {prob}")
        lines.append(f"  Fix that worked: {sol}")
    return "\n".join(lines)
