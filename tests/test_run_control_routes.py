from __future__ import annotations

import builtins
import importlib
from collections.abc import AsyncIterator

from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

import nara_common.run_control_routes as run_control_routes
from nara_common.run_control_routes import create_run_control_app


class RunRequest(BaseModel):
    command: str


class FakeRunManager:
    def __init__(self):
        self.shutdown_called = False

    def active_run_id(self):
        return "active"

    def recent(self):
        return [{"run_id": "active", "status": "running"}]

    def snapshot(self, run_id: str):
        if run_id == "missing":
            raise KeyError(run_id)
        return {"run_id": run_id, "status": "running"}

    async def stop(self, run_id: str):
        if run_id == "missing":
            raise KeyError(run_id)
        return {"run_id": run_id, "status": "stopping"}

    async def stream(
        self, run_id: str, after: int = 0
    ) -> AsyncIterator[dict[str, object]]:
        if run_id == "missing":
            raise KeyError(run_id)
        yield {
            "sequence": after + 1,
            "kind": "log",
            "status": "running",
            "message": "진행 중",
        }

    async def shutdown(self):
        self.shutdown_called = True


def test_factory_module_import_does_not_require_fastapi(monkeypatch):
    original_import = builtins.__import__

    def reject_fastapi(name, *args, **kwargs):
        if name == "fastapi" or name.startswith("fastapi."):
            raise AssertionError("FastAPI를 module import 시점에 가져오면 안 됩니다.")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", reject_fastapi)
    importlib.reload(run_control_routes)


def make_app(tmp_path, manager: FakeRunManager):
    static_dir = tmp_path / "frontend"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("control ui", encoding="utf-8")
    (static_dir / "app.js").write_text("", encoding="utf-8")

    async def health():
        return {"ok": True, "active_run_id": manager.active_run_id()}

    async def preview(request: RunRequest):
        return {"ok": True, "command": request.command}

    async def create(request: RunRequest):
        if request.command == "invalid":
            raise HTTPException(status_code=422, detail="service validation")
        return {"run_id": "created", "command": request.command}

    return create_run_control_app(
        title="Test Control",
        version="1.0",
        description="test",
        static_dir=static_dir,
        manager_provider=lambda: manager,
        health_endpoint=health,
        preview_endpoint=preview,
        create_endpoint=create,
        run_not_found_message="실행 없음",
    )


def test_factory_registers_the_shared_control_surface(tmp_path):
    manager = FakeRunManager()
    app = make_app(tmp_path, manager)

    with TestClient(app) as client:
        assert client.get("/").text == "control ui"
        assert client.get("/favicon.ico").status_code == 204
        assert client.get("/static/app.js").status_code == 200
        assert client.get("/health").json() == {
            "ok": True,
            "active_run_id": "active",
        }
        assert client.post("/runs/preview", json={"command": "list"}).json() == {
            "ok": True,
            "command": "list",
        }
        created = client.post("/runs", json={"command": "list"})
        assert created.status_code == 202
        assert created.json() == {"run_id": "created", "command": "list"}
        assert client.get("/runs").json() == {
            "active_run_id": "active",
            "runs": [{"run_id": "active", "status": "running"}],
        }
        assert client.get("/runs/active").json()["run_id"] == "active"
        assert client.post("/runs/active/stop").json()["status"] == "stopping"

    assert manager.shutdown_called is True


def test_factory_preserves_service_errors_and_not_found_messages(tmp_path):
    manager = FakeRunManager()
    with TestClient(make_app(tmp_path, manager)) as client:
        service_error = client.post("/runs", json={"command": "invalid"})
        assert service_error.status_code == 422
        assert service_error.json() == {"detail": "service validation"}

        missing = client.get("/runs/missing")
        assert missing.status_code == 404
        assert missing.json() == {"detail": "실행 없음"}
        assert client.post("/runs/missing/stop").status_code == 404


def test_factory_serializes_progress_and_missing_run_sse(tmp_path):
    manager = FakeRunManager()
    with TestClient(make_app(tmp_path, manager)) as client:
        response = client.get("/runs/active/events?after=7")
        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.text == (
            'id: 8\nevent: progress\ndata: {"sequence": 8, "kind": "log", '
            '"status": "running", "message": "진행 중"}\n\n'
        )

        missing = client.get("/runs/missing/events")
        assert missing.text == (
            'event: error\ndata: {"message": "실행 없음"}\n\n'
        )
