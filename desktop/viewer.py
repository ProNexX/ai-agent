"""Launch the SQLite results viewer. Run from repo root: python desktop/viewer.py"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from activity_agent.ui.viewer import main

if __name__ == "__main__":
    raise SystemExit(main())
