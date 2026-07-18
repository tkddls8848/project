"""Start the unified gateway and its existing sibling services."""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
GATEWAY_MODULES = ("fastapi", "httpx", "uvicorn")


@dataclass(frozen=True)
class Service:
    key: str
    name: str
    port: int
    cwd: Path
    module: str
    required_modules: tuple[str, ...]
    preferred_modules: tuple[str, ...] = ()


SERVICES = (
    Service(
        "search",
        "문서 검색",
        8000,
        PROJECT_DIR / "nara_search(API문서검색)",
        "backend.main:app",
        ("fastapi", "pydantic", "uvicorn"),
        ("faiss", "sentence_transformers"),
    ),
    Service(
        "combiner",
        "문서 조합",
        8003,
        PROJECT_DIR / "nara_combiner(API문서조합기)",
        "app.main:app",
        ("dotenv", "fastapi", "httpx", "jinja2", "pydantic", "uvicorn"),
    ),
)


def port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.3):
            return True
    except OSError:
        return False


def _unique_paths(paths: Iterable[Path]) -> list[Path]:
    result: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        normalized = str(path.resolve()).lower()
        if normalized not in seen:
            seen.add(normalized)
            result.append(path)
    return result


def _project_python(project_dir: Path) -> Path:
    if os.name == "nt":
        return project_dir / "venv" / "Scripts" / "python.exe"
    return project_dir / "venv" / "bin" / "python"


def supports_modules(python: Path, modules: Iterable[str]) -> bool:
    if not python.is_file():
        return False
    module_names = tuple(modules)
    if not module_names:
        return True
    check = (
        "import importlib.util,sys;"
        f"mods={module_names!r};"
        "sys.exit(0 if all(importlib.util.find_spec(m) is not None for m in mods) else 1)"
    )
    try:
        completed = subprocess.run(
            [str(python), "-c", check],
            cwd=str(BASE_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0


def _base_python() -> Path:
    executable = getattr(sys, "_base_executable", None)
    if executable:
        return Path(executable)
    name = "python.exe" if os.name == "nt" else "python"
    return Path(sys.base_prefix) / name


def resolve_service_python(service: Service) -> Path:
    override = os.getenv(f"NARA_{service.key.upper()}_PYTHON", "").strip()
    current = Path(sys.executable)
    candidates = _unique_paths(
        [
            *([Path(override)] if override else []),
            _project_python(service.cwd),
            current,
            _base_python(),
        ]
    )

    valid = [
        python
        for python in candidates
        if supports_modules(python, service.required_modules)
    ]
    if override and (not valid or valid[0].resolve() != Path(override).resolve()):
        raise RuntimeError(
            f"NARA_{service.key.upper()}_PYTHON이 필요한 패키지를 제공하지 않습니다: {override}"
        )
    if not valid:
        modules = ", ".join(service.required_modules)
        raise RuntimeError(
            f"{service.name}을 실행할 Python 환경을 찾지 못했습니다. 필요한 모듈: {modules}"
        )

    for python in valid:
        if supports_modules(python, service.preferred_modules):
            return python
    return valid[0]


def start_uvicorn(
    module: str,
    cwd: Path,
    port: int,
    python: Path,
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
    kwargs: dict = {"cwd": str(cwd), "env": os.environ.copy()}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    return subprocess.Popen(command, **kwargs)


def terminate(children: list[subprocess.Popen]) -> None:
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Nara API Workbench 통합 실행기")
    parser.add_argument(
        "--no-services",
        action="store_true",
        help="기존 8000/8003 서비스를 시작하지 않고 통합 UI만 실행",
    )
    parser.add_argument("--port", type=int, default=8010, help="통합 앱 포트 (기본 8010)")
    args = parser.parse_args()

    current_python = Path(sys.executable)
    if not supports_modules(current_python, GATEWAY_MODULES):
        requirements = BASE_DIR / "requirements.txt"
        print("[오류] 현재 Python 환경에 통합 앱 실행 패키지가 없습니다.")
        print("다음 명령을 먼저 실행하세요:")
        print(f'  "{current_python}" -m pip install -r "{requirements}"')
        return 1

    if port_open(args.port):
        print(f"[오류] 포트 {args.port}가 이미 사용 중입니다.")
        return 1

    pending: list[tuple[Service, Path]] = []
    if not args.no_services:
        try:
            for service in SERVICES:
                if not service.cwd.exists() or port_open(service.port):
                    continue
                pending.append((service, resolve_service_python(service)))
        except RuntimeError as exc:
            print(f"[오류] {exc}")
            return 1

    children: list[subprocess.Popen] = []
    try:
        if not args.no_services:
            for service in SERVICES:
                if not service.cwd.exists():
                    print(f"[건너뜀] {service.name}: 프로젝트 폴더가 없습니다.")
                    continue
                if port_open(service.port):
                    print(f"[연결] {service.name}: 기존 서비스 사용 (:{service.port})")
                    continue
                python = next(
                    interpreter
                    for candidate, interpreter in pending
                    if candidate.key == service.key
                )
                environment = (
                    "현재 venv"
                    if python.resolve() == current_python.resolve()
                    else str(python)
                )
                print(
                    f"[시작] {service.name}: http://127.0.0.1:{service.port}"
                    f" ({environment})"
                )
                children.append(
                    start_uvicorn(service.module, service.cwd, service.port, python)
                )

        gateway = start_uvicorn("main:app", BASE_DIR, args.port, current_python)
        children.append(gateway)
        print("")
        print(f"Nara API Workbench: http://127.0.0.1:{args.port}")
        print("종료하려면 Ctrl+C를 누르세요.")

        while True:
            for child in children:
                code = child.poll()
                if code is not None:
                    print(f"[종료] 프로세스 {child.pid}가 코드 {code}로 종료되었습니다.")
                    return code or 1
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n통합 앱을 종료합니다.")
        return 0
    finally:
        terminate(children)


if __name__ == "__main__":
    raise SystemExit(main())
