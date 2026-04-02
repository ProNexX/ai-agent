# Activity Agent

PC activity monitor: capture context, infer tasks, show overview in a desktop app later.

## Repo layout

```
ai-agent/
├── main.py
├── pyproject.toml
├── models/              # legacy DTOs
├── services/            # legacy experiments
├── src/activity_agent/  # main package
├── config/
├── desktop/
├── data/
├── assets/captures/
└── tests/
```

`src/activity_agent/`: `collectors/` (window, screenshot), `core/`, `inference/` (ocr, llm), `pipeline/`, `storage/`, `api/`.

Use a **64-bit Python 3.10–3.13** venv (`pyproject.toml` is `<3.14`). **3.14** has no usable Paddle wheels for this stack yet.

**Install (editable, from repo root):** `pip install -e .` — pulls `mss`, `requests`, `paddlepaddle`, and `paddleocr` (OCR is required for `process_capture`, not optional).

If `pip` cannot resolve `paddlepaddle` on your OS, use the CPU index from [Paddle install](https://www.paddlepaddle.org.cn/install/quick). Do not `pip install paddle` (wrong PyPI name).

Screenshot only saves a PNG and returns `ScreenshotCapture`. To run the full chain (OCR → Ollama → SQLite → optional callback for the desktop app):

```python
from activity_agent.collectors.screenshot import ScreenshotCollector
from activity_agent.pipeline import process_capture

cap = ScreenshotCollector().capture()
row = process_capture(cap, ollama_model="llama3.2", on_saved=lambda r: ...)
```

DB file: `data/agent.db` table `pipeline_results`.
