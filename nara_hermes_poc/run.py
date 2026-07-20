"""Start the isolated Nara Hermes PoC and its Nara dependencies.

This launcher never starts or modifies the existing Nara Workbench UI (:8010).
"""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from app.config import load_project_env


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent


@dataclass(frozen=True)
class Service:
    name: str
    port: int
    cwd: Path
    module: str
    python: Path


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


def service_definitions(poc_port: int) -> tuple[Service, ...]:
    search_dir = PROJECT_DIR / "nara_search(API문서검색)"
    combiner_dir = PROJECT_DIR / "nara_combiner(API문서조합기)"
    return (
        Service(
            "Nara Search",
            8000,
            search_dir,
            "backend.main:app",
            project_python(search_dir),
        ),
        Service(
            "Nara Combiner",
            8003,
            combiner_dir,
            "app.main:app",
            project_python(combiner_dir),
        ),
        Service(
            "Nara Hermes PoC",
            poc_port,
            BASE_DIR,
            "app.main:app",
            project_python(BASE_DIR),
        ),
    )


def configure_stdio() -> None:
    """Emit UTF-8 from the launcher itself, matching child_environment().

    A Windows console already handles Korean through the console API, but a
    redirected stream falls back to the locale encoding (cp949). Children are
    forced to UTF-8, so without this a piped log mixes both encodings.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def child_environment() -> dict[str, str]:
    load_project_env()
    environment = os.environ.copy()
    # Keep Korean MCP tool results and subprocess output consistently UTF-8.
    environment["PYTHONUTF8"] = "1"
    environment["PYTHONIOENCODING"] = "utf-8"
    return environment


def start_uvicorn(service: Service) -> subprocess.Popen:
    if not service.cwd.is_dir():
        raise RuntimeError(f"{service.name} 프로젝트 폴더가 없습니다: {service.cwd}")
    if not service.python.is_file():
        raise RuntimeError(f"{service.name} Python 환경이 없습니다: {service.python}")
    command = [
        str(service.python),
        "-m",
        "uvicorn",
        service.module,
        "--host",
        "127.0.0.1",
        "--port",
        str(service.port),
    ]
    kwargs: dict[str, object] = {
        "cwd": str(service.cwd),
        "env": child_environment(),
    }
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    return subprocess.Popen(command, **kwargs)


def health_ready(port: int) -> bool:
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/health", timeout=2
        ) as response:
            return response.status == 200
    except (urllib.error.URLError, OSError):
        return False


def wait_until_healthy(
    service: Service, child: subprocess.Popen | None, timeout: float
) -> None:
    """Block until the service answers /health.

    Nara Search binds its port long before the embedding model finishes
    loading, so a port check alone would report readiness too early.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if child is not None and child.poll() is not None:
            raise RuntimeError(
                f"{service.name}가 준비되기 전에 코드 {child.returncode}로 종료되었습니다."
            )
        if health_ready(service.port):
            print(f"[준비] {service.name}: /health 응답 확인 (:{service.port})")
            return
        time.sleep(0.5)
    raise RuntimeError(
        f"{service.name}가 {timeout:.0f}초 안에 준비되지 않았습니다 (:{service.port})."
    )


def hermes_executable() -> Path:
    override = os.getenv("HERMES_EXE", "").strip()
    if override:
        return Path(override)
    local_app_data = os.getenv("LOCALAPPDATA", "")
    return Path(local_app_data) / "hermes" / "hermes-agent" / "venv" / "Scripts" / "hermes.exe"


def start_hermes(profile: str) -> subprocess.Popen:
    executable = hermes_executable()
    if not executable.is_file():
        raise RuntimeError(
            "Hermes 실행 파일을 찾지 못했습니다. HERMES_EXE를 지정하거나 Hermes를 설치하세요: "
            f"{executable}"
        )
    kwargs: dict[str, object] = {"cwd": str(BASE_DIR), "env": child_environment()}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    return subprocess.Popen(
        [
            str(executable),
            "-p",
            profile,
            "-m",
            os.environ["NARA_HERMES_MODEL"],
            "gateway",
        ],
        **kwargs,
    )


def terminate(children: list[subprocess.Popen]) -> None:
    for child in reversed(children):
        if child.poll() is None:
            child.terminate()
    deadline = time.monotonic() + 5
    for child in reversed(children):
        if child.poll() is None:
            try:
                child.wait(timeout=max(0.1, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                child.kill()


def main() -> int:
    configure_stdio()
    load_project_env()
    parser = argparse.ArgumentParser(description="Nara Hermes PoC 통합 실행기")
    parser.add_argument("--poc-port", type=int, default=8020, help="PoC UI 포트")
    parser.add_argument(
        "--no-upstreams",
        action="store_true",
        help="Search·Combiner를 시작하지 않고 PoC만 실행",
    )
    parser.add_argument(
        "--upstream-timeout",
        type=float,
        default=300.0,
        help="Search·Combiner가 /health에 응답할 때까지 기다릴 최대 초",
    )
    parser.add_argument(
        "--with-hermes",
        action="store_true",
        help="nara-poc Hermes Gateway도 함께 실행",
    )
    parser.add_argument(
        "--hermes-profile",
        default=os.environ["NARA_HERMES_PROFILE"],
        help="함께 시작할 Hermes profile 이름",
    )
    args = parser.parse_args()

    services = list(service_definitions(args.poc_port))
    if args.no_upstreams:
        services = [service for service in services if service.port == args.poc_port]

    if port_open(args.poc_port):
        print(f"[오류] PoC 포트 :{args.poc_port}가 이미 사용 중입니다.")
        return 1

    children: list[subprocess.Popen] = []
    try:
        for service in services:
            child: subprocess.Popen | None = None
            if port_open(service.port):
                print(f"[연결] {service.name}: 기존 서비스 사용 (:{service.port})")
            else:
                print(f"[시작] {service.name}: http://127.0.0.1:{service.port}")
                child = start_uvicorn(service)
                children.append(child)
            if service.port != args.poc_port:
                # PoC의 /health가 Search·Combiner를 그대로 호출하므로
                # 업스트림이 준비된 뒤에 PoC를 띄운다.
                wait_until_healthy(service, child, args.upstream_timeout)

        if args.with_hermes:
            print(f"[시작] Hermes Gateway: profile={args.hermes_profile}")
            children.append(
                start_hermes(args.hermes_profile)
            )

        print("\nNara Hermes PoC: http://127.0.0.1:%d" % args.poc_port)
        print("종료하려면 Ctrl+C를 누르세요.")

        while True:
            for child in children:
                if child.poll() is not None:
                    print(f"[종료] 프로세스 {child.pid}가 코드 {child.returncode}로 종료되었습니다.")
                    return child.returncode or 1
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n통합 실행을 종료합니다.")
        return 0
    except RuntimeError as exc:
        print(f"[오류] {exc}")
        return 1
    finally:
        terminate(children)


if __name__ == "__main__":
    raise SystemExit(main())
