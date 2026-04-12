from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class WindowState:
    id: str
    captured_at: datetime
    titles: tuple[str, ...]
