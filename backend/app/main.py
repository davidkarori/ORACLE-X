from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .domain import CreateRunRequest
from .store import AuditStore
from .workflow import WorkflowService


settings = get_settings()
store = AuditStore(settings.oracle_db_path)
workflow = WorkflowService(settings, store)
static_dir = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield


app = FastAPI(title="ORACLE X", version="0.1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "paper_only": True,
        "execution_enabled": settings.execution_enabled,
        "kill_switch": workflow.kill_switch,
        "integrations": {
            "featherless": settings.featherless_configured,
            "alpaca": settings.alpaca_configured,
            "mcp": bool(settings.mcp_server_url),
        },
    }


@app.get("/api/runs")
def list_runs():
    return store.list_runs()


@app.post("/api/runs", status_code=202)
async def create_run(request: CreateRunRequest):
    return workflow.start(request)


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    run = store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    return run


@app.get("/api/runs/{run_id}/replay")
def replay(run_id: str):
    run = store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    return {"run": run, "events": store.events(run_id)}


@app.post("/api/system/kill-switch")
def set_kill_switch(active: bool):
    workflow.kill_switch = active
    return {"active": workflow.kill_switch, "paper_only": True}


@app.get("/")
def index():
    return FileResponse(static_dir / "index.html")
