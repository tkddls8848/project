"""Execution API for Nara OpenClaw."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    __package__ = "app"

from fastapi import FastAPI, HTTPException

from .config import BASE_DIR, EXECUTOR_MODE, RUNS_DIR
from .executor import DummyGovernmentExecutor, build_dry_run, mask_inputs
from .schemas import ExecutionPlan, ExecutionRequest, RunRecord
from .store import load_run, save_run

app = FastAPI(title="Nara OpenClaw Execution Service", version="0.2.0")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@app.get("/")
async def index():
    return {
        "service": "nara-openclaw",
        "purpose": "Execute approved administrative service plans through dry-run, adapters, and audit logs.",
        "endpoints": ["/health", "/demo/plan", "/execute/dry-run", "/execute", "/runs/{run_id}"],
    }


@app.get("/health")
async def health():
    return {
        "ok": True,
        "service": "nara-openclaw",
        "mode": EXECUTOR_MODE,
        "runs_dir": str(RUNS_DIR),
    }


@app.get("/demo/plan", response_model=ExecutionPlan)
async def demo_plan():
    plan_path = BASE_DIR / "data" / "demo_execution_plan.json"
    if not plan_path.exists():
        raise HTTPException(status_code=404, detail="Demo plan not found.")
    return ExecutionPlan(**json.loads(plan_path.read_text(encoding="utf-8")))


@app.post("/execute/dry-run")
async def execute_dry_run(req: ExecutionRequest):
    return build_dry_run(req)


@app.post("/execute", response_model=RunRecord)
async def execute(req: ExecutionRequest):
    dry_run = build_dry_run(req)
    run_id = f"run_{uuid4().hex}"
    approved_at = utc_now() if req.approval.approved else None

    if not dry_run.executable:
        record = RunRecord(
            run_id=run_id,
            plan_id=req.plan.plan_id,
            goal=req.plan.goal,
            status="blocked",
            approved_by=req.approval.approver,
            approved_at=approved_at,
            created_at=utc_now(),
            dry_run=dry_run,
            executed_steps=[],
            user_inputs=mask_inputs(req.user_inputs),
        )
        save_run(record)
        raise HTTPException(status_code=400, detail=record.model_dump())

    if dry_run.approval_required and not req.approval.approved:
        record = RunRecord(
            run_id=run_id,
            plan_id=req.plan.plan_id,
            goal=req.plan.goal,
            status="blocked",
            approved_by=req.approval.approver,
            approved_at=approved_at,
            created_at=utc_now(),
            dry_run=dry_run,
            executed_steps=[],
            user_inputs=mask_inputs(req.user_inputs),
        )
        save_run(record)
        raise HTTPException(status_code=403, detail=record.model_dump())

    executor = DummyGovernmentExecutor()
    executed = [executor.execute_step(step, req.user_inputs) for step in req.plan.steps]
    status = "completed" if all(step.status == "completed" for step in executed) else "partial"

    record = RunRecord(
        run_id=run_id,
        plan_id=req.plan.plan_id,
        goal=req.plan.goal,
        status=status,
        approved_by=req.approval.approver,
        approved_at=approved_at,
        created_at=utc_now(),
        dry_run=dry_run,
        executed_steps=executed,
        user_inputs=mask_inputs(req.user_inputs),
    )
    save_run(record)
    return record


@app.get("/runs/{run_id}", response_model=RunRecord)
async def get_run(run_id: str):
    record = load_run(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    return record


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8002, reload=True)
