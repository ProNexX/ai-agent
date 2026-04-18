import argparse
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from activity_agent.config_local import load_local_config
from activity_agent.pipeline import run_capture_pipeline
from activity_agent.storage.db import (
    connect,
    fetch_pipeline_result,
    init_schema,
    insert_verified_solution,
    list_pipeline_results,
    list_verified_solutions,
)
from activity_agent.ui.llm_format import format_llm_activity_json, llm_tree_preview, short_ts

_TEMPLATES = Path(__file__).resolve().parent / "templates"
_STATIC = Path(__file__).resolve().parent / "static"

_job_lock = threading.Lock()
_jobs: dict[str, dict[str, Any]] = {}


def _db_path() -> Path:
    cfg = load_local_config()
    p = cfg.get("db_path")
    return Path(p).resolve() if p else (Path.cwd() / "data" / "agent.db").resolve()


def _start_capture_job() -> str:
    job_id = str(uuid.uuid4())
    with _job_lock:
        _jobs[job_id] = {
            "state": "running",
            "row_id": None,
            "error": None,
            "started": time.monotonic(),
        }

    def _run() -> None:
        try:
            row = run_capture_pipeline()
            with _job_lock:
                if job_id in _jobs:
                    _jobs[job_id]["state"] = "done"
                    _jobs[job_id]["row_id"] = row.id
        except Exception as e:
            with _job_lock:
                if job_id in _jobs:
                    _jobs[job_id]["state"] = "error"
                    _jobs[job_id]["error"] = str(e)
        _prune_jobs()

    threading.Thread(target=_run, daemon=True).start()
    return job_id


def _prune_jobs() -> None:
    with _job_lock:
        if len(_jobs) <= 64:
            return
        cutoff = time.monotonic() - 3600.0
        stale = [k for k, v in _jobs.items() if v.get("started", 0) < cutoff]
        for k in stale[:32]:
            del _jobs[k]


def create_app() -> Any:
    from fastapi import FastAPI, Form, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
    from fastapi.staticfiles import StaticFiles
    from fastapi.templating import Jinja2Templates
    from starlette.requests import Request

    app = FastAPI(title="Activity Agent", docs_url=None, redoc_url=None)
    templates = Jinja2Templates(directory=str(_TEMPLATES))
    app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> Any:
        db = _db_path()
        conn = connect(db)
        try:
            init_schema(conn)
            rows = list_pipeline_results(conn, limit=200)
        finally:
            conn.close()
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "rows": rows,
                "db_path": str(db),
                "short_ts": short_ts,
                "llm_tree_preview": llm_tree_preview,
            },
        )

    @app.get("/row/{row_id}", response_class=HTMLResponse)
    def row_detail(request: Request, row_id: int) -> Any:
        db = _db_path()
        conn = connect(db)
        try:
            init_schema(conn)
            rec = fetch_pipeline_result(conn, row_id)
        finally:
            conn.close()
        if rec is None:
            raise HTTPException(status_code=404, detail="Row not found")
        llm_summary, llm_raw = format_llm_activity_json(rec.llm_text)
        return templates.TemplateResponse(
            request,
            "detail.html",
            {
                "rec": rec,
                "llm_summary": llm_summary,
                "llm_raw": llm_raw,
                "short_ts": short_ts,
            },
        )

    @app.get("/verified", response_class=HTMLResponse)
    def verified_page(request: Request) -> Any:
        db = _db_path()
        conn = connect(db)
        try:
            init_schema(conn)
            items = list_verified_solutions(conn, limit=200)
        finally:
            conn.close()
        return templates.TemplateResponse(
            request,
            "verified.html",
            {
                "items": items,
                "db_path": str(db),
                "request": request,
                "short_ts": short_ts,
            },
        )

    @app.post("/verified")
    def verified_add(
        problem: str = Form(...),
        solution: str = Form(...),
        pipeline_result_id: str = Form(""),
    ) -> Any:
        prob = problem.strip()
        sol = solution.strip()
        if not prob or not sol:
            return RedirectResponse(url="/verified?err=1", status_code=303)
        pr_id: int | None = None
        if pipeline_result_id.strip().isdigit():
            pr_id = int(pipeline_result_id.strip())
        db = _db_path()
        conn = connect(db)
        try:
            init_schema(conn)
            insert_verified_solution(
                conn,
                problem_summary=prob,
                solution_text=sol,
                pipeline_result_id=pr_id,
            )
        finally:
            conn.close()
        return RedirectResponse(url="/verified?saved=1", status_code=303)

    @app.post("/api/run")
    def api_run() -> Any:
        job_id = _start_capture_job()
        return JSONResponse({"job_id": job_id})

    @app.get("/api/job/{job_id}")
    def api_job(job_id: str) -> Any:
        with _job_lock:
            j = _jobs.get(job_id)
        if j is None:
            raise HTTPException(status_code=404, detail="Unknown job")
        body: dict[str, Any] = {"state": j["state"]}
        if j.get("row_id") is not None:
            body["row_id"] = j["row_id"]
        if j.get("error"):
            body["error"] = j["error"]
        return JSONResponse(body)

    return app


def main(argv: list[str] | None = None) -> int:
    try:
        import uvicorn
    except ModuleNotFoundError:
        print(
            "Web UI dependencies missing. Install with: pip install -e '.[web]'",
            file=sys.stderr,
        )
        return 1
    parser = argparse.ArgumentParser(description="Activity agent web UI")
    parser.add_argument(
        "--host",
        default=None,
        help="Bind address (default: web_host from local.config.json or 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        metavar="N",
        help="Port (default: web_port from local.config.json or 8765)",
    )
    args = parser.parse_args(argv)
    cfg = load_local_config()
    host = args.host or str(cfg.get("web_host") or "127.0.0.1").strip() or "127.0.0.1"
    port = args.port
    if port is None:
        try:
            port = int(cfg.get("web_port", 8765))
        except (TypeError, ValueError):
            port = 8765
    uvicorn.run(
        create_app(),
        host=host,
        port=port,
        reload=False,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
