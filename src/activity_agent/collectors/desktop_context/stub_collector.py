from __future__ import annotations

import uuid
from datetime import datetime, timezone

from activity_agent.collectors.desktop_context.types import DesktopContext

class DesktopContextCollector:
    def collect(self) -> DesktopContext:
        return DesktopContext(
            id=str(uuid.uuid4()),
            captured_at=datetime.now(timezone.utc),
            foreground=None,
            idle_seconds=0.0,
            recent_focus_changes=(),
        )
