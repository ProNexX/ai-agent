from activity_agent.collectors.screenshot import ScreenshotCollector
from activity_agent.collectors.window import get_foreground_windows
from activity_agent.pipeline import process_capture


cap = ScreenshotCollector().capture()
active_windows = get_foreground_windows()
row = process_capture(
    cap,
    active_windows,
    ollama_model="llama3.2",
    on_saved=lambda r: print(r.id, r.llm_text[:200]),
)