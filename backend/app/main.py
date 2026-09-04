from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi import Depends
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from .auth import Principal, require_role
from .config import get_settings
from .domain import CreateRunRequest
from .quant import StrategyEngine
from .store import build_store
from .workflow import WorkflowService


settings = get_settings()
store = build_store(settings.database_url, settings.oracle_db_path)
workflow = WorkflowService(settings, store)
static_dir = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield


app = FastAPI(title="ORACLE X", version="0.1.0", lifespan=lifespan)
if settings.cors_origin_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/api/health")
def health(_: Principal = Depends(require_role("read"))):
    state = workflow.system_state
    return {
        "status": "ok",
        "paper_only": True,
        "execution_enabled": settings.execution_enabled,
        "system_state": state.status,
        "kill_switch": state.kill_switch_active,
        "persistence": store.backend_name,
        "mcp_read_only": True,
        "integrations": {
            "featherless": settings.featherless_configured,
            "alpaca": settings.alpaca_configured,
            "mcp": bool(settings.mcp_server_url),
        },
    }


@app.get("/api/runs")
def list_runs(_: Principal = Depends(require_role("read"))):
    return store.list_runs()


@app.post("/api/runs", status_code=202)
async def create_run(request: CreateRunRequest, principal: Principal = Depends(require_role("operator"))):
    return await workflow.run_to_completion(request)


@app.get("/api/runs/{run_id}")
def get_run(run_id: str, _: Principal = Depends(require_role("read"))):
    run = store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    return run


@app.get("/api/runs/{run_id}/replay")
def replay(run_id: str, _: Principal = Depends(require_role("read"))):
    run = store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    return {"run": run, "events": store.events(run_id)}


@app.get("/api/runs/{run_id}/mcp-calls")
def mcp_calls(run_id: str, _: Principal = Depends(require_role("read"))):
    run = store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    return run.mcp_calls


@app.get("/api/memories/{symbol}")
def memories(symbol: str, _: Principal = Depends(require_role("read"))):
    return store.list_memories(symbol.strip().upper())


@app.get("/api/strategies")
def strategies(_: Principal = Depends(require_role("read"))):
    return {"supported": sorted(family.value for family in StrategyEngine.SUPPORTED), "naked_short_options": False}


@app.post("/api/system/kill-switch")
def set_kill_switch(active: bool, reason: str = "Operator request", principal: Principal = Depends(require_role("operator"))):
    return {"active": workflow.set_kill_switch(active, reason, principal.subject), "paper_only": True}


@app.get("/")
def index():
    return FileResponse(static_dir / "index.html")
