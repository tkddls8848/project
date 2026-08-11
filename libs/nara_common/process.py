"""Process helpers shared by the repository's Python launchers."""

from __future__ import annotations

import os
import socket
import subprocess
import time
from collections.abc import Sequence
from pathlib import Path


def port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.3):
            return True
    except OSError:
        return False


def project_python(directory: Path) -> Path:
    if os.name == "nt":
        return directory / "venv" / "Scripts" / "python.exe"
    return directory / "venv" / "bin" / "python"


def start_uvicorn(
    module: str,
    cwd: Path,
    port: int,
    python: Path,
    environment: dict[str, str],
) -> subprocess.Popen:
    command = [
        str(python),
        "-m",
        "uvicorn",
        module,
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]
    kwargs: dict[str, object] = {"cwd": str(cwd), "env": environment}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    return subprocess.Popen(command, **kwargs)


def terminate(children: Sequence[subprocess.Popen]) -> None:
    for child in reversed(children):
        if child.poll() is None:
            child.terminate()
    deadline = time.monotonic() + 5
    for child in reversed(children):
        if child.poll() is not None:
            continue
        try:
            child.wait(timeout=max(0.1, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            child.kill()
