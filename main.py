from __future__ import annotations

import argparse
import sys
import time

from activity_agent.config_local import load_local_config
from activity_agent.pipeline import run_capture_pipeline

def _interval_from_config(cfg: dict) -> float:
    v = cfg.get("pipeline_interval_seconds")
    if v is None:
        return 0.0
    try:
        f = float(v)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, f)

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
    args = parser.parse_args(argv)
    cfg = load_local_config()

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