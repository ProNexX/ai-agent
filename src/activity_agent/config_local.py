from __future__ import annotations

import json
from pathlib import Path

CONFIG_FILENAME = "local.config.json"

def find_local_config_path() -> Path | None:
    here = Path(__file__).resolve()
    roots = [Path.cwd().resolve(), *here.parents]
    seen: set[Path] = set()
    for root in roots:
        try:
            key = root.resolve()
        except OSError:
            continue
        if key in seen:
            continue
        seen.add(key)
        candidate = root / CONFIG_FILENAME
        if candidate.is_file():
            return candidate
    return None

def load_local_config() -> dict:
    path = find_local_config_path()
    if path is None:
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))
