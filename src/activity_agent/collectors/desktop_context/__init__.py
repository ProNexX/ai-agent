import sys

if sys.platform == "win32":
    from activity_agent.collectors.desktop_context.win_collector import DesktopContextCollector
else:
    from activity_agent.collectors.desktop_context.stub_collector import DesktopContextCollector

from activity_agent.core.models import (
    DesktopContext,
    FocusChange,
    ForegroundFocus,
)

__all__ = [
    "DesktopContext",
    "DesktopContextCollector",
    "FocusChange",
    "ForegroundFocus",
]
