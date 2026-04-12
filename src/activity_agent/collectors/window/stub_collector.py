from __future__ import annotations

import uuid
from datetime import datetime, timezone

from activity_agent.collectors.window.types import WindowState

class WindowCollector:
    def collect(self) -> WindowState:
        return WindowState(
            id=str(uuid.uuid4()),
            captured_at=datetime.now(timezone.utc),
            titles=(),
        )
