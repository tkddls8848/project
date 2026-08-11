from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, call

import pytest

from nara_common import process


def test_port_open_connects_to_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    create_connection = Mock(return_value=MagicMock())
    monkeypatch.setattr(process.socket, "create_connection", create_connection)

    assert process.port_open(8010) is True
    create_connection.assert_called_once_with(("127.0.0.1", 8010), timeout=0.3)


def test_port_open_returns_false_for_socket_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        process.socket,
        "create_connection",
        Mock(side_effect=OSError("unavailable")),
    )

    assert process.port_open(8010) is False


@pytest.mark.parametrize(
    ("os_name", "parts"),
    [
        ("nt", ("venv", "Scripts", "python.exe")),
        ("posix", ("venv", "bin", "python")),
    ],
)
def test_project_python_uses_platform_venv_layout(
    monkeypatch: pytest.MonkeyPatch,
    os_name: str,
    parts: tuple[str, ...],
) -> None:
    directory = Path("project")
    monkeypatch.setattr(process, "os", SimpleNamespace(name=os_name))

    assert process.project_python(directory) == directory.joinpath(*parts)


@pytest.mark.parametrize("os_name", ["nt", "posix"])
def test_start_uvicorn_builds_platform_command(
    monkeypatch: pytest.MonkeyPatch,
    os_name: str,
) -> None:
    child = Mock()
    popen = Mock(return_value=child)
    environment = {"SETTING": "value"}
    cwd = Path("service")
    python = Path("python")
    monkeypatch.setattr(process, "os", SimpleNamespace(name=os_name))
    monkeypatch.setattr(process.subprocess, "Popen", popen)
    monkeypatch.setattr(
        process.subprocess, "CREATE_NEW_PROCESS_GROUP", 512, raising=False
    )

    result = process.start_uvicorn(
        "app.main:app", cwd, 8123, python, environment
    )

    expected_kwargs: dict[str, object] = {
        "cwd": str(cwd),
        "env": environment,
    }
    if os_name == "nt":
        expected_kwargs["creationflags"] = 512
    popen.assert_called_once_with(
        [
            str(python),
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8123",
        ],
        **expected_kwargs,
    )
    assert popen.call_args.kwargs["env"] is environment
    assert result is child


def test_terminate_uses_reverse_order_and_one_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = Mock()
    second = Mock()
    first.poll.side_effect = [None, None]
    second.poll.side_effect = [None, None]
    first.wait.side_effect = subprocess.TimeoutExpired("first", 0.1)

    events = Mock()
    events.attach_mock(first.terminate, "first_terminate")
    events.attach_mock(first.wait, "first_wait")
    events.attach_mock(first.kill, "first_kill")
    events.attach_mock(second.terminate, "second_terminate")
    events.attach_mock(second.wait, "second_wait")
    events.attach_mock(second.kill, "second_kill")

    monotonic = Mock(side_effect=[10.0, 12.0, 20.0])
    monkeypatch.setattr(process.time, "monotonic", monotonic)

    process.terminate([first, second])

    assert events.mock_calls == [
        call.second_terminate(),
        call.first_terminate(),
        call.second_wait(timeout=3.0),
        call.first_wait(timeout=0.1),
        call.first_kill(),
    ]
    assert monotonic.call_count == 3
