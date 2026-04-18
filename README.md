<div align="center">
<img src="docs/github-banner.svg" alt="activity-agent — desktop activity monitoring" width="100%" />
</div>

# Activity Agent

PC activity monitor: multi-monitor screenshots, window titles, OCR, vision LLM (OpenAI-compatible or Ollama), and SQLite storage. Browse results and trigger captures from the optional **web UI** (`activity-agent-web`).

## Repo layout

```
ai-agent/
├── main.py                 # CLI entrypoint
├── local.config.json       # local settings (create yourself; gitignored)
├── pyproject.toml
├── src/activity_agent/     # main package
├── data/                   # default SQLite DB location
├── assets/captures/        # screenshot PNGs (transient)
└── tests/
```

Inside `src/activity_agent/`:

- **`collectors/`** — `screenshot`, `window`, `desktop_context` (Windows focus/idle), `system_load` (`SystemLoadCollector`, `SystemLoadState`: CPU/RAM/swap via **psutil**, cross-platform)
- **`inference/llm/`** — OpenAI-compatible chat + Ollama vision clients, shared prompt
- **`inference/ocr/`** — PaddleOCR wrapper (`image_to_text`)
- **`pipeline/`** — `process_capture` orchestrates OCR → LLM → DB
- **`storage/`** — SQLite helpers
- **`ui/`** — optional FastAPI web app (`web_app.py`), Jinja templates, static CSS; **`llm_format.py`** shared JSON→summary formatting
- **`tools/`** — small diagnostics (e.g. `python -m activity_agent.tools.paddle_gpu_check`)
- **`config_local.py`** — finds and loads `local.config.json`

## Requirements

- **64-bit Python 3.10–3.13** (`requires-python` is `<3.14`; Paddle wheels for this stack are not reliable on 3.14 yet).
- **Windows** for window and desktop-context collectors (Win32 APIs via **pywin32**, declared in `pyproject.toml`).

## Install

From the repo root, in a venv:

```bash
pip install -e .
```

This installs `mss`, `requests`, `pywin32`, `psutil`, `paddlepaddle` (CPU wheel from PyPI), and `paddleocr`.

### Web UI (optional)

Local browser UI to list capture results, open a row (OCR + LLM), run one capture, and record verified fixes:

```bash
pip install -e ".[web]"
activity-agent-web
```

Open **http://127.0.0.1:8765** (default). Bind address and port: **`web_host`**, **`web_port`** in `local.config.json`, or `activity-agent-web --host 127.0.0.1 --port 8765`.

### Paddle GPU (optional, faster OCR)

The default PyPI **`paddlepaddle`** package is CPU-only. For NVIDIA GPUs, uninstall it and install a **GPU** build from [Paddle’s install docs](https://www.paddlepaddle.org.cn/install/quick) (pick the index matching your CUDA/driver, e.g. `cu129` on Windows). After `pip install -e .`, reinstall the GPU wheel if pip pulls CPU Paddle again.

OCR device and GPU memory fraction can be set in **`local.config.json`** (see below).

If the UI or logs say GPU is unavailable for OCR, check what **this same venv** sees:

```bash
python -m activity_agent.tools.paddle_gpu_check
```

You need **`compiled_with_cuda: True`** and **`cuda.device_count()` ≥ 1**. If `compiled_with_cuda` is **False**, you still have the **CPU-only** `paddlepaddle` wheel from PyPI (install **`paddlepaddle-gpu`** from Paddle’s CUDA index). If CUDA is compiled but **device count is 0**, fix drivers / `nvidia-smi` / `CUDA_VISIBLE_DEVICES` for the process that runs `activity-agent-web` or `main.py`.

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
| `llm_context_loop_enabled` | `true` / `false`: planner + final LLM passes (default **false**). See AGENTS.md. |
| `openai_planner_model`, `ollama_planner_model` | Optional; override planner model only when the context loop is on. |
| `llm_planner_max_tokens`, `verified_solutions_prompt_limit` | Optional tuning for planner output and verified-fixes snippet size. |
| `ocr_device` | e.g. `gpu:0` or `cpu` (optional; defaults to GPU when CUDA is available) |
| `ocr_gpu_memory_fraction` | Optional `0`–`1` Paddle GPU memory cap |
| `pipeline_interval_seconds` | `0`, missing, or invalid: run **once** and exit. Positive number: **`main.py`** repeats `run_capture_pipeline` every that many seconds until Ctrl+C. |
| `system_load_cpu_sample_seconds` | How long to sample CPU for `SystemLoadCollector` (default **0.1**). Use **0** for a non-blocking read (less representative on first sample). |
| `web_host`, `web_port` | Optional bind address / port for **`activity-agent-web`** (defaults `127.0.0.1`, `8765`). |

Arguments passed to **`process_capture(...)`** override JSON values when provided. Optional **`desktop_context=`** / **`system_load=`** let you pass pre-built snapshots; otherwise fresh collectors run each pipeline pass.

## Pipeline behavior

1. **Screenshots** — `ScreenshotCollector().capture_all_monitors()` saves one PNG per monitor (`ScreenshotCapture` rows share a `group_id`).
2. **Windows** — `WindowCollector().collect()` returns titles in `WindowState.titles`.
3. **Desktop context** — `DesktopContextCollector().collect()` (unless `desktop_context=`) records foreground window (title, PID, executable), input idle, and in-process focus history (Windows).
4. **System load** — `SystemLoadCollector().collect()` (unless `system_load=`) records CPU % (short sample), RAM use, and swap/page-file use (**psutil**).
5. **OCR** — Each screenshot is run through PaddleOCR; text is sent to the LLM with images plus desktop-context and system-load blocks.
6. **LLM** — Asks for **JSON** with `tasks`, `distractions`, and `problems` (plus optional `problem_solutions` when the context loop is enabled). Prompts distinguish real distractions from passive browser chrome (bookmarks bar, tabs, etc.). Default provider uses the OpenAI **Chat Completions** API with vision; set `llm_provider` to `ollama` for local models (e.g. LLaVA-class). Optional **`llm_context_loop_enabled`**: planner pass then final pass (see README config table / AGENTS.md).
7. **Storage** — Row written to **`pipeline_results`**; screenshot files are deleted after a successful save.

## Running `main.py`

- **`python main.py`** — Uses **`pipeline_interval_seconds`** from `local.config.json` (default behavior when the key is missing is **one run**).
- **`python main.py --once`** — Single run even if an interval is set in config.
- **`python main.py --interval 120`** — Run every **120** seconds (overrides config). **`--interval 0`** means one run.

Between repeats, **Ctrl+C** stops the loop (after the current cycle finishes, or while sleeping).

## Example

```python
from activity_agent.pipeline import run_capture_pipeline

row = run_capture_pipeline()
```

To wire collectors yourself (custom paths, tests, or partial runs):

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
