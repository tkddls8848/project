"""Start the Nara Hermes orchestration service and its dependencies.

This launcher never starts or modifies the existing Nara Workbench UI (:8010).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from app.config import PROJECT_ROOT, load_project_env

LIBS_DIR = PROJECT_ROOT / "libs"
if str(LIBS_DIR) not in sys.path:
    sys.path.insert(0, str(LIBS_DIR))

from nara_common.cli import interactive_argv, wants_interactive
from nara_common.process import (
    port_open,
    project_python,
    start_uvicorn as _start_uvicorn,
    terminate,
)


BASE_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Service:
    name: str
    port: int
    cwd: Path
    module: str
    python: Path


def service_definitions(service_port: int) -> tuple[Service, ...]:
    search_dir = PROJECT_ROOT / "services" / "search"
    combiner_dir = PROJECT_ROOT / "services" / "combiner"
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
            "Nara Hermes Orchestrator",
            service_port,
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
    return _start_uvicorn(
        service.module,
        service.cwd,
        service.port,
        service.python,
        child_environment(),
    )


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


def main() -> int:
    configure_stdio()
    load_project_env()
    parser = argparse.ArgumentParser(description="Nara Hermes 오케스트레이션 서비스 실행기")
    parser.add_argument("--port", type=int, default=8020, help="서비스 UI/API 포트")
    parser.add_argument(
        "--no-upstreams",
        action="store_true",
        help="Search·Combiner를 시작하지 않고 오케스트레이터만 실행",
    )
    parser.add_argument(
        "--upstream-timeout",
        type=float,
        default=300.0,
        help="Search·Combiner가 /health에 응답할 때까지 기다릴 최대 초",
    )
    parser.add_argument(
        "--no-hermes",
        action="store_true",
        help="Hermes Gateway를 시작하지 않고 이미 실행 중인 Gateway 사용",
    )
    parser.add_argument(
        "--hermes-profile",
        default=os.environ["NARA_HERMES_PROFILE"],
        help="함께 시작할 Hermes profile 이름",
    )
    argv = sys.argv[1:]
    if wants_interactive(argv):
        # 콘솔에서 인자 없이 부르면 물어본다. 비대화형이면 예전처럼 기본값으로 뜬다.
        # 상류를 끄면 대기 시간이, Gateway를 끄면 profile 이름이 의미를 잃는다.
        argv = interactive_argv(
            parser,
            ask_if={"upstream_timeout": "!no_upstreams", "hermes_profile": "!no_hermes"},
        )
        if argv is None:
            return 0
    args = parser.parse_args(argv)

    services = list(service_definitions(args.port))
    if args.no_upstreams:
        services = [service for service in services if service.port == args.port]

    if port_open(args.port):
        print(f"[오류] 서비스 포트 :{args.port}가 이미 사용 중입니다.")
        return 1

    children: list[subprocess.Popen] = []
    try:
        if port_open(8642):
            print("[연결] Hermes Gateway: 기존 서비스 사용 (:8642)")
        elif args.no_hermes:
            raise RuntimeError("--no-hermes를 사용했지만 :8642에 Hermes Gateway가 없습니다.")
        else:
            print(f"[시작] Hermes Gateway: profile={args.hermes_profile}")
            gateway = start_hermes(args.hermes_profile)
            children.append(gateway)
            deadline = time.monotonic() + 30
            while not port_open(8642):
                if gateway.poll() is not None:
                    raise RuntimeError(
                        f"Hermes Gateway가 준비되기 전에 코드 {gateway.returncode}로 종료되었습니다."
                    )
                if time.monotonic() >= deadline:
                    raise RuntimeError("Hermes Gateway가 30초 안에 :8642를 열지 못했습니다.")
                time.sleep(0.5)
            print("[준비] Hermes Gateway: :8642 연결 확인")

        for service in services:
            child: subprocess.Popen | None = None
            if port_open(service.port):
                print(f"[연결] {service.name}: 기존 서비스 사용 (:{service.port})")
            else:
                print(f"[시작] {service.name}: http://127.0.0.1:{service.port}")
                child = start_uvicorn(service)
                children.append(child)
            if service.port != args.port:
                # 서비스의 /health가 Search·Combiner를 호출하므로 업스트림을 먼저 준비한다.
                wait_until_healthy(service, child, args.upstream_timeout)

        print("\nNara Hermes Orchestrator: http://127.0.0.1:%d" % args.port)
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
