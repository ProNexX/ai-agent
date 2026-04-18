from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from activity_agent.config_local import load_local_config
from activity_agent.pipeline import run_capture_pipeline
from activity_agent.storage.db import connect, init_schema, insert_verified_solution

def _interval_from_config(cfg: dict) -> float:
    v = cfg.get("pipeline_interval_seconds")
    if v is None:
        return 0.0
    try:
        f = float(v)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, f)

def _db_path_from_config(cfg: dict) -> Path:
    p = cfg.get("db_path")
    return Path(p).resolve() if p else (Path.cwd() / "data" / "agent.db").resolve()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Activity agent capture pipeline")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one capture cycle then exit (overrides interval in config)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=None,
        metavar="SEC",
        help="Seconds to wait between runs (overrides pipeline_interval_seconds in config)",
    )
    parser.add_argument(
        "--verify-solution",
        action="store_true",
        help="Record a user-confirmed fix into SQLite (does not run capture)",
    )
    parser.add_argument(
        "--pipeline-result-id",
        type=int,
        default=None,
        metavar="ID",
        help="Optional pipeline_results.id tying this fix to a saved capture row",
    )
    parser.add_argument(
        "--problem",
        type=str,
        default="",
        help="Short problem description (required with --verify-solution)",
    )
    parser.add_argument(
        "--solution",
        type=str,
        default="",
        help="What worked (required with --verify-solution)",
    )
    args = parser.parse_args(argv)
    cfg = load_local_config()

    if args.verify_solution:
        prob = str(args.problem).strip()
        sol = str(args.solution).strip()
        if not prob or not sol:
            parser.error("--verify-solution requires non-empty --problem and --solution")
        db = _db_path_from_config(cfg)
        conn = connect(db)
        init_schema(conn)
        insert_verified_solution(
            conn,
            problem_summary=prob,
            solution_text=sol,
            pipeline_result_id=args.pipeline_result_id,
        )
        conn.close()
        return 0

    if args.once:
        interval = 0.0
    elif args.interval is not None:
        interval = max(0.0, float(args.interval))
    else:
        interval = _interval_from_config(cfg)

    while True:
        run_capture_pipeline()
        if interval <= 0.0:
            break
        try:
            time.sleep(interval)
        except KeyboardInterrupt:
            break
    return 0

if __name__ == "__main__":
    sys.exit(main())