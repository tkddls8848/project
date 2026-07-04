"""Execution API for Nara OpenClaw.

모든 실행은 DummyGovernmentExecutor 기반이며 실제 기관 제출을 수행하지
않는다. 승인 게이트: dry-run 통과 + approved=true + 승인자 존재를 모두
요구하며, 실행과 차단 모두 감사 기록(run 파일)을 남긴다.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    __package__ = "app"

from fastapi import FastAPI, HTTPException

from . import config
from .executor import DummyGovernmentExecutor, build_dry_run, mask_inputs
from .schemas import ExecutionPlan, ExecutionRequest, RunRecord
from .store import load_run, save_run

app = FastAPI(
    title="Nara OpenClaw Execution Service",
    version="0.3.0",
    description=(
        "행정서비스 실행 계획의 dry-run·승인·더미 실행 API. "
        "executor_mode='dummy'는 실제 기관 제출이 아니라 모사 실행이다."
    ),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@app.get("/")
async def index():
    return {
        "service": "nara-openclaw",
        "purpose": "Execute approved administrative service plans through dry-run, adapters, and audit logs.",
        "executor_mode": config.EXECUTOR_MODE,
        "notice": "Dummy executor only. No real government submission is performed.",
        "endpoints": ["/health", "/demo/plan", "/execute/dry-run", "/execute", "/runs/{run_id}"],
    }


@app.get("/health")
async def health():
    return {
        "ok": True,
        "service": "nara-openclaw",
        "mode": config.EXECUTOR_MODE,
        "runs_dir": str(config.RUNS_DIR),
    }


@app.get("/demo/plan", response_model=ExecutionPlan)
async def demo_plan():
    plan_path = config.BASE_DIR / "data" / "demo_execution_plan.json"
    if not plan_path.exists():
        raise HTTPException(status_code=404, detail="Demo plan not found.")
    return ExecutionPlan(**json.loads(plan_path.read_text(encoding="utf-8")))


@app.post("/execute/dry-run")
async def execute_dry_run(req: ExecutionRequest):
    """외부 실행 없이 입력·승인 요건만 점검한다."""
    return build_dry_run(req)


def _blocked_record(req: ExecutionRequest, dry_run, status_reason: str) -> RunRecord:
    return RunRecord(
        run_id=f"run_{uuid4().hex}",
        plan_id=req.plan.plan_id,
        goal=req.plan.goal,
        status="blocked",
        status_reason=status_reason,
        executor_mode=config.EXECUTOR_MODE,
        approved_by=req.approval.approver,
        approved_at=utc_now() if req.approval.approved else None,
        created_at=utc_now(),
        dry_run=dry_run,
        executed_steps=[],
        user_inputs=mask_inputs(req.user_inputs),
    )


@app.post("/execute", response_model=RunRecord)
async def execute(req: ExecutionRequest):
    """승인된 계획을 더미 어댑터로 실행한다. 실제 기관 제출 없음.

    차단 조건(모두 감사 기록 저장):
    - dry-run 실패 → 400 (status_reason=dry_run_blocked)
    - 승인 필요 계획에 approved=false → 403 (approval_missing)
    - 승인 필요 계획에 승인자 미지정 → 403 (approver_missing)
    """
    dry_run = build_dry_run(req)

    if not dry_run.executable:
        record = _blocked_record(req, dry_run, "dry_run_blocked")
        save_run(record)
        raise HTTPException(status_code=400, detail=record.model_dump())

    if dry_run.approval_required:
        if not req.approval.approved:
            record = _blocked_record(req, dry_run, "approval_missing")
            save_run(record)
            raise HTTPException(status_code=403, detail=record.model_dump())
        if not (req.approval.approver or "").strip():
            record = _blocked_record(req, dry_run, "approver_missing")
            save_run(record)
            raise HTTPException(status_code=403, detail=record.model_dump())

    executor = DummyGovernmentExecutor()
    executed = [executor.execute_step(step, req.user_inputs) for step in req.plan.steps]
    status = "completed" if all(step.status == "completed" for step in executed) else "partial"

    record = RunRecord(
        run_id=f"run_{uuid4().hex}",
        plan_id=req.plan.plan_id,
        goal=req.plan.goal,
        status=status,
        status_reason=None,
        executor_mode=config.EXECUTOR_MODE,
        approved_by=req.approval.approver,
        approved_at=utc_now() if req.approval.approved else None,
        created_at=utc_now(),
        dry_run=dry_run,
        executed_steps=executed,
        user_inputs=mask_inputs(req.user_inputs),
    )
    save_run(record)
    return record


@app.get("/runs/{run_id}", response_model=RunRecord)
async def get_run(run_id: str):
    """저장된 run 기록(마스킹된 입력 포함)을 조회한다."""
    record = load_run(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    return record


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8002, reload=True)
