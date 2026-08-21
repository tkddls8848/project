from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field


def _load_common_paths():
    current_file = Path(__file__).resolve()
    marker_parent = next((candidate for candidate in current_file.parents if (candidate / ".nara-root").is_file()), None)
    if marker_parent is None:
        raise RuntimeError("repository marker .nara-root was not found")
    libraries = marker_parent / "libs"
    if str(libraries) not in sys.path:
        sys.path.insert(0, str(libraries))
    from nara_common.paths import find_project_root

    return find_project_root(current_file)


PROJECT_ROOT = _load_common_paths()
# 저장소 안 위치가 바뀌어도 따라오도록 이 파일 기준으로 잡는다.
SERVICE_ROOT = Path(__file__).resolve().parent.parent

from adapters.registry import AdapterRegistry
from api.auth import LocalSessionAuth, Principal, authenticated_principal
from domain.operations import OperationValidationError
from domain.plans import ExecutionPlan
from infra.database import ApprovalBindingChanged, Conflict, Database, Forbidden, NotFound


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=1, max_length=1024)


class ValidatePlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan: ExecutionPlan
    user_inputs: dict[str, Any]


class CreateRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_id: str = Field(min_length=1, max_length=128)
    plan_version: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    user_inputs: dict[str, Any]


class ApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    challenge: str = Field(min_length=16, max_length=256)
    reauth_password: str = Field(min_length=1, max_length=1024)


def _http_error(error: Exception) -> HTTPException:
    if isinstance(error, NotFound):
        return HTTPException(status_code=404, detail=str(error))
    if isinstance(error, Forbidden):
        return HTTPException(status_code=403, detail=str(error))
    if isinstance(error, Conflict):
        return HTTPException(status_code=409, detail=str(error))
    return HTTPException(status_code=400, detail="request could not be processed")


def create_app(
    *,
    database_path: Path | None = None,
    catalog_path: Path | None = None,
    local_users: dict[str, str] | None = None,
    approval_ttl_seconds: int = 300,
    session_ttl_seconds: int = 3600,
) -> FastAPI:
    database_path = database_path or PROJECT_ROOT / "api_storage" / "epilogue" / "epilogue.sqlite3"
    catalog_path = catalog_path or SERVICE_ROOT / "config" / "operations.json"
    if local_users is None:
        configured_password = os.environ.get("NARA_EPILOGUE_PASSWORD")
        local_users = {"local": configured_password} if configured_password else {}

    database = Database(database_path, approval_ttl_seconds=approval_ttl_seconds)
    operation_registry = AdapterRegistry.from_json(catalog_path)
    local_auth = LocalSessionAuth(database, local_users, session_ttl_seconds)
    application = FastAPI(
        title="Nara Administrative Service Executor",
        version="0.1.0",
        description="Local execution-control service. Dummy Adapter only; no real administrative submission.",
    )
    # Intentionally no CORS middleware: this service can initiate controlled execution.
    application.state.database = database
    application.state.operation_registry = operation_registry
    application.state.local_auth = local_auth

    @application.exception_handler(RequestValidationError)
    async def validation_error_without_input_echo(_request: Request, _error: RequestValidationError) -> JSONResponse:
        # FastAPI's default validation body embeds rejected values. This execution
        # surface returns only a stable error code so secrets cannot be reflected.
        return JSONResponse(status_code=422, content={"detail": "request validation failed"})

    @application.get("/")
    def index() -> dict[str, Any]:
        return {
            "service": "nara-epilogue",
            "adapter_mode": "dummy-only",
            "notice": "No real government or external HTTP request is performed.",
        }

    @application.get("/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "service": "nara-epilogue", "adapter_mode": "dummy-only"}

    @application.post("/auth/sessions", status_code=status.HTTP_201_CREATED)
    def create_session(request: LoginRequest) -> dict[str, str]:
        token = local_auth.issue_session(request.username, request.password)
        return {"access_token": token, "token_type": "bearer"}

    @application.post("/execution-plans/validate")
    def validate_plan(
        request: ValidatePlanRequest,
        principal: Principal = Depends(authenticated_principal),
    ) -> dict[str, Any]:
        del principal
        try:
            impacts = operation_registry.validate_plan(request.plan, request.user_inputs)
            database.save_validated_plan(request.plan)
        except OperationValidationError as error:
            raise HTTPException(status_code=400, detail="plan validation failed") from error
        except (Conflict, NotFound, Forbidden) as error:
            raise _http_error(error) from error
        return {
            "plan_id": request.plan.plan_id,
            "plan_version": request.plan.plan_version,
            "content_hash": request.plan.content_hash,
            "executable": True,
            "approval_required": True,
            "impacts": impacts,
        }

    @application.post("/execution-runs")
    def create_execution_run(
        request: CreateRunRequest,
        response: Response,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        principal: Principal = Depends(authenticated_principal),
    ) -> dict[str, Any]:
        if idempotency_key is None:
            raise HTTPException(status_code=400, detail="Idempotency-Key header is required")
        try:
            plan = database.get_plan(request.plan_id, request.plan_version, request.content_hash)
            operation_registry.validate_plan(plan, request.user_inputs)
            run, created = database.create_run(principal.principal_id, plan, request.user_inputs, idempotency_key)
        except OperationValidationError as error:
            raise HTTPException(status_code=400, detail="run input validation failed") from error
        except (Conflict, NotFound, Forbidden) as error:
            raise _http_error(error) from error
        response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return run

    @application.get("/execution-runs/{run_id}")
    def get_execution_run(run_id: str, principal: Principal = Depends(authenticated_principal)) -> dict[str, Any]:
        try:
            return database.get_run(run_id, principal.principal_id)
        except (Conflict, NotFound, Forbidden) as error:
            raise _http_error(error) from error

    @application.get("/execution-runs/{run_id}/events")
    def get_execution_events(run_id: str, principal: Principal = Depends(authenticated_principal)) -> list[dict[str, Any]]:
        try:
            return database.list_events(run_id, principal.principal_id)
        except (Conflict, NotFound, Forbidden) as error:
            raise _http_error(error) from error

    @application.post("/execution-runs/{run_id}/approvals", status_code=status.HTTP_201_CREATED)
    def approve_execution_run(
        run_id: str,
        request: ApprovalRequest,
        principal: Principal = Depends(authenticated_principal),
    ) -> dict[str, Any]:
        if not local_auth.authenticate(principal.principal_id, request.reauth_password):
            raise HTTPException(status_code=401, detail="reauthentication failed")
        try:
            return database.approve(run_id, principal.principal_id, request.challenge)
        except (Conflict, NotFound, Forbidden) as error:
            raise _http_error(error) from error

    @application.post("/execution-runs/{run_id}/approval-challenges", status_code=status.HTTP_201_CREATED)
    def renew_approval_challenge(
        run_id: str,
        principal: Principal = Depends(authenticated_principal),
    ) -> dict[str, Any]:
        try:
            return database.renew_approval_challenge(run_id, principal.principal_id)
        except (Conflict, NotFound, Forbidden) as error:
            raise _http_error(error) from error

    @application.post("/execution-runs/{run_id}/start", status_code=status.HTTP_202_ACCEPTED)
    def start_execution_run(run_id: str, principal: Principal = Depends(authenticated_principal)) -> dict[str, Any]:
        try:
            return database.queue_run(run_id, principal.principal_id)
        except ApprovalBindingChanged as error:
            raise HTTPException(
                status_code=409,
                detail={"message": "approval is no longer valid", "approval_challenge": error.challenge},
            ) from error
        except (Conflict, NotFound, Forbidden) as error:
            raise _http_error(error) from error

    @application.post("/execution-runs/{run_id}/cancel")
    def cancel_execution_run(run_id: str, principal: Principal = Depends(authenticated_principal)) -> dict[str, Any]:
        try:
            return database.cancel(run_id, principal.principal_id)
        except (Conflict, NotFound, Forbidden) as error:
            raise _http_error(error) from error

    @application.post("/execution-runs/{run_id}/reconcile")
    def reconcile_execution_run(run_id: str, principal: Principal = Depends(authenticated_principal)) -> dict[str, Any]:
        # Dummy receipts are local data; this endpoint never makes an external request.
        try:
            return database.reconcile_from_receipt(run_id, principal.principal_id)
        except (Conflict, NotFound, Forbidden) as error:
            raise _http_error(error) from error

    return application


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api.main:app", host="127.0.0.1", port=8002, reload=False)
