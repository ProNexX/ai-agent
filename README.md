# Activity Agent

PC activity monitor: multi-monitor screenshots, window titles, OCR, vision LLM (OpenAI-compatible or Ollama), and SQLite storage. A desktop UI is planned later.

## Repo layout

```
ai-agent/
├── main.py                 # example entrypoint
├── local.config.json       # local settings (create yourself; gitignored)
├── pyproject.toml
├── src/activity_agent/     # main package
├── config/
├── desktop/
├── data/                   # default SQLite DB location
├── assets/captures/        # screenshot PNGs (transient)
└── tests/
```

Inside `src/activity_agent/`:

- **`collectors/`** — `screenshot` (`ScreenshotCollector`, `ScreenshotCapture`), `window` (`WindowCollector`, `WindowState`; Windows + **pywin32**)
- **`inference/llm/`** — OpenAI-compatible chat + Ollama vision clients, shared prompt
- **`inference/ocr/`** — PaddleOCR wrapper (`image_to_text`)
- **`pipeline/`** — `process_capture` orchestrates OCR → LLM → DB
- **`storage/`** — SQLite helpers
- **`config_local.py`** — finds and loads `local.config.json`

## Requirements

- **64-bit Python 3.10–3.13** (`requires-python` is `<3.14`; Paddle wheels for this stack are not reliable on 3.14 yet).
- **Windows** for the window collector (uses Win32 APIs).
- **pywin32** for `WindowCollector` (install separately if imports fail: `pip install pywin32`).

## Install

From the repo root, in a venv:

```bash
pip install -e .
```

This installs `mss`, `requests`, `paddlepaddle` (CPU wheel from PyPI), and `paddleocr`.

### Paddle GPU (optional, faster OCR)

The default PyPI **`paddlepaddle`** package is CPU-only. For NVIDIA GPUs, uninstall it and install a **GPU** build from [Paddle’s install docs](https://www.paddlepaddle.org.cn/install/quick) (pick the index matching your CUDA/driver, e.g. `cu129` on Windows). After `pip install -e .`, reinstall the GPU wheel if pip pulls CPU Paddle again.

OCR device and GPU memory fraction can be set in **`local.config.json`** (see below).

## Configuration (`local.config.json`)

Create **`local.config.json`** in the **repository root**. It is **gitignored**; settings are **not** read from environment variables for app config.

Typical keys:

| Key | Purpose |
|-----|--------|
| `db_path` | SQLite file (default `data/agent.db`) |
| `llm_provider` | `"openai_compatible"` (default) or `"ollama"` |
| `openai_api_key` | Secret key for OpenAI (or compatible) API |
| `openai_base_url` | e.g. `https://api.openai.com/v1` |
| `openai_model` | e.g. `gpt-4o-mini` |
| `openai_max_tokens`, `openai_json_mode`, `llm_timeout`, `max_image_side` | Optional tuning |
| `ollama_url`, `ollama_model`, `ollama_max_tokens` | When `llm_provider` is `ollama` |
| `ocr_device` | e.g. `gpu:0` or `cpu` (optional; defaults to GPU when CUDA is available) |
| `ocr_gpu_memory_fraction` | Optional `0`–`1` Paddle GPU memory cap |

Arguments passed to **`process_capture(...)`** override JSON values when provided.

## Pipeline behavior

1. **Screenshots** — `ScreenshotCollector().capture_all_monitors()` saves one PNG per monitor (`ScreenshotCapture` rows share a `group_id`).
2. **Windows** — `WindowCollector().collect()` returns titles in `WindowState.titles`.
3. **OCR** — Each screenshot is run through PaddleOCR; text is sent to the LLM together with the images.
4. **LLM** — Asks for **JSON** with `tasks`, `distractions`, and `problems` (arrays of strings). Default provider uses the OpenAI **Chat Completions** API with vision; set `llm_provider` to `ollama` for local models (e.g. LLaVA-class).
5. **Storage** — Row written to **`pipeline_results`**; screenshot files are deleted after a successful save.

## Example

```python
from activity_agent.collectors.screenshot import ScreenshotCollector
from activity_agent.collectors.window import WindowCollector
from activity_agent.pipeline import process_capture

caps = ScreenshotCollector().capture_all_monitors()
windows = WindowCollector().collect()
row = process_capture(caps, windows.titles)
```

Database: **`data/agent.db`**, table **`pipeline_results`** (`capture_id`, `image_path`, `ocr_text`, `llm_text`, timestamps). `image_path` may list multiple files separated by `|` when several monitors were captured.

## Paddle install notes

If `pip` cannot resolve **`paddlepaddle`**, use the official Paddle CPU/GPU index from [Paddle install](https://www.paddlepaddle.org.cn/install/quick). Do not install the wrong PyPI name **`paddle`**.

## License

[MIT](LICENSE). Copyright (c) 2026 activity-agent contributors.
