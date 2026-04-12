import sys

if sys.platform == "win32":
    from activity_agent.collectors.window.win_collector import WindowCollector
else:
    from activity_agent.collectors.window.stub_collector import WindowCollector

from activity_agent.core.models import WindowState

__all__ = ["WindowCollector", "WindowState"]
