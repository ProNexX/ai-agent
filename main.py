from activity_agent.collectors.screenshot import ScreenshotCollector
from activity_agent.collectors.window import WindowCollector
from activity_agent.pipeline import process_capture

caps = ScreenshotCollector().capture_all_monitors()
windows = WindowCollector().collect()
row = process_capture(caps, windows.titles)