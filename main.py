from activity_agent.collectors.screenshot import ScreenshotCollector
from activity_agent.pipeline import process_capture

cap = ScreenshotCollector().capture()
row = process_capture(
    cap,
    ollama_model="deepseek-coder:33b",
    on_saved=lambda r: print(r.id, r.llm_text[:200]),
)