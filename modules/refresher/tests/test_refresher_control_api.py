from __future__ import annotations

import asyncio
import sys
import textwrap

import pytest
from fastapi.testclient import TestClient

from backend import main as backend_main
from backend.run_service import (
    COMMANDS,
    RefreshRequest,
    RefreshRequestError,
    RefreshRunManager,
)


# ── 요청 -> CLI argv ────────────────────────────────────────────────────

def test_login_builds_cli_arguments():
    assert RefreshRequest(command="login").to_argv() == ["login", "--timeout", "600"]
    assert RefreshRequest(command="login", manual=True).to_argv() == [
        "login", "--manual", "--timeout", "600",
    ]


def test_list_takes_no_options():
    assert RefreshRequest(command="list").to_argv() == ["list"]


def test_extend_defaults_to_dry_run():
    request = RefreshRequest(command="extend", only="버스", limit=3)
    assert request.to_argv() == ["extend", "--limit", "3", "--only", "버스"]
    assert request.writes_to_portal is False
    assert request.metadata()["dry_run"] is True


def test_commit_requires_a_second_acknowledgement():
    """dry-run 요청을 그대로 다시 보내는 것만으로 실제 제출이 되면 안 된다."""
    with pytest.raises(RefreshRequestError):
        RefreshRequest(command="extend", commit=True).to_argv()

    request = RefreshRequest(command="extend", commit=True, confirm_commit=True)
    assert request.to_argv() == ["extend", "--commit"]
    assert request.writes_to_portal is True


@pytest.mark.parametrize(
    "kwargs",
    [
        {"command": "nope"},
        {"command": "list", "commit": True},
        {"command": "list", "only": "x"},
        {"command": "extend", "manual": True},
        {"command": "extend", "limit": 0},
        {"command": "login", "timeout": 0},
    ],
)
def test_invalid_requests_are_rejected(kwargs):
    with pytest.raises(RefreshRequestError):
        RefreshRequest(**kwargs).to_argv()


def test_only_manual_login_reads_stdin():
    assert RefreshRequest(command="login", manual=True).accepts_stdin is True
    assert RefreshRequest(command="login").accepts_stdin is False
    assert RefreshRequest(command="extend").accepts_stdin is False


def test_commands_match_the_cli():
    import main as refresher_main

    parser_commands = set(
        refresher_main.build_parser()._subparsers._group_actions[0].choices
    )
    assert set(COMMANDS) == parser_commands


# ── 실행 관리 ───────────────────────────────────────────────────────────

def fake_script(tmp_path, body: str):
    path = tmp_path / "fake_main.py"
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


def test_manager_streams_output_and_completes(tmp_path):
    script = fake_script(tmp_path, """
        print("[dry-run] 2건이 대상입니다.")
        print("  [연장 예정] 버스 정보")
    """)

    async def scenario():
        manager = RefreshRunManager(python_executable=sys.executable, script=script)
        created = await manager.create_command(RefreshRequest(command="extend"))
        await manager._runs[created["run_id"]].task
        return manager.snapshot(created["run_id"])

    run = asyncio.run(scenario())
    assert run["status"] == "completed"
    assert run["metadata"]["dry_run"] is True
    assert "  [연장 예정] 버스 정보" in run["log"]


def test_manual_login_receives_stdin_from_the_browser(tmp_path):
    """터미널 Enter를 기다리는 명령을 UI 버튼으로 이어준다."""
    script = fake_script(tmp_path, """
        print("열린 창에서 로그인하세요")
        input()
        print("세션을 저장했습니다")
    """)

    async def scenario():
        manager = RefreshRunManager(python_executable=sys.executable, script=script)
        created = await manager.create_command(
            RefreshRequest(command="login", manual=True)
        )
        run_id = created["run_id"]
        assert created["accepts_stdin"] is True
        for _ in range(50):
            if any("로그인하세요" in line for line in manager.snapshot(run_id)["log"]):
                break
            await asyncio.sleep(0.1)
        await manager.send_stdin(run_id)
        await manager._runs[run_id].task
        return manager.snapshot(run_id)

    run = asyncio.run(scenario())
    assert run["status"] == "completed"
    assert "세션을 저장했습니다" in run["log"]


def test_stdin_is_refused_for_runs_that_do_not_read_it(tmp_path):
    script = fake_script(tmp_path, "import time; time.sleep(5)")

    async def scenario():
        manager = RefreshRunManager(python_executable=sys.executable, script=script)
        created = await manager.create_command(RefreshRequest(command="list"))
        try:
            with pytest.raises(RuntimeError):
                await manager.send_stdin(created["run_id"])
        finally:
            await manager.stop(created["run_id"])
            await manager._runs[created["run_id"]].task

    asyncio.run(scenario())


def test_only_one_command_runs_at_a_time(tmp_path):
    script = fake_script(tmp_path, "import time; time.sleep(5)")

    async def scenario():
        manager = RefreshRunManager(python_executable=sys.executable, script=script)
        first = await manager.create_command(RefreshRequest(command="list"))
        try:
            with pytest.raises(RuntimeError):
                await manager.create_command(RefreshRequest(command="extend"))
        finally:
            await manager.stop(first["run_id"])
            await manager._runs[first["run_id"]].task

    asyncio.run(scenario())


# ── HTTP 표면 ───────────────────────────────────────────────────────────

@pytest.fixture
def client(tmp_path, monkeypatch):
    script = fake_script(tmp_path, 'print("fake refresher")')
    monkeypatch.setattr(
        backend_main,
        "runs",
        RefreshRunManager(python_executable=sys.executable, script=script),
    )
    with TestClient(backend_main.app) as test_client:
        yield test_client


def test_preview_marks_the_writing_command(client):
    dry = client.post("/runs/preview", json={"command": "extend"}).json()
    assert dry == {
        "ok": True,
        "command": "python main.py extend",
        "writes_to_portal": False,
        "accepts_stdin": False,
    }

    live = client.post(
        "/runs/preview",
        json={"command": "extend", "commit": True, "confirm_commit": True},
    ).json()
    assert live["command"] == "python main.py extend --commit"
    assert live["writes_to_portal"] is True


def test_commit_without_confirmation_is_rejected_by_the_api(client):
    response = client.post("/runs", json={"command": "extend", "commit": True})
    assert response.status_code == 400
    assert "confirm_commit" in response.json()["detail"]


def test_dry_run_extend_starts(client):
    created = client.post("/runs", json={"command": "extend"})
    assert created.status_code == 202
    payload = created.json()
    assert payload["command"] == "python main.py extend"
    assert payload["metadata"]["dry_run"] is True


def test_health_reports_commands_and_session(client):
    payload = client.get("/health").json()
    assert payload["ok"] is True
    assert set(payload["commands"]) == set(COMMANDS)
    assert "state_file" in payload["session"]


def test_control_surface_does_not_enable_cors(client):
    """다른 출처의 페이지가 연장 제출을 일으킬 수 있으면 안 된다."""
    response = client.post(
        "/runs/preview",
        json={"command": "list"},
        headers={"Origin": "https://evil.example"},
    )
    assert "access-control-allow-origin" not in {k.lower() for k in response.headers}
