"""Start the Nara Hermes orchestration service and its dependencies.

Hermes is launched with a project-local profile that routes Cloudflare requests
through the loopback compatibility proxy (:8643 by default).
"""

from __future__ import annotations

import argparse
import json
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
from app.hermes_runtime import (
    gateway_state_matches,
    start_hermes,
    validate_proxy_configuration,
)


BASE_DIR = Path(__file__).resolve().parent
PROXY_SERVICE_NAME = "nara-cloudflare-compat-proxy"


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


def proxy_service(proxy_port: int) -> Service:
    return Service(
        "Cloudflare Compatibility Proxy",
        proxy_port,
        BASE_DIR,
        "app.cloudflare_proxy:app",
        project_python(BASE_DIR),
    )


def configure_stdio() -> None:
    """Emit UTF-8 from the launcher itself, matching child_environment()."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def child_environment() -> dict[str, str]:
    load_project_env()
    environment = os.environ.copy()
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


def proxy_health_ready(port: int) -> bool:
    """Require our configured proxy, not merely an arbitrary healthy service."""
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/health", timeout=2
        ) as response:
            if response.status != 200:
                return False
            payload = json.load(response)
    except (urllib.error.URLError, OSError, ValueError):
        return False
    return payload.get("ok") is True and payload.get("service") == PROXY_SERVICE_NAME


def wait_until_healthy(
    service: Service,
    child: subprocess.Popen | None,
    timeout: float,
    readiness=health_ready,
) -> None:
    """Block until the service answers its health check."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if child is not None and child.poll() is not None:
            raise RuntimeError(
                f"{service.name}가 준비되기 전에 코드 {child.returncode}로 종료했습니다."
            )
        if readiness(service.port):
            print(f"[준비] {service.name}: /health 응답 확인 (:{service.port})")
            return
        time.sleep(0.5)
    raise RuntimeError(
        f"{service.name}가 {timeout:.0f}초 안에 준비되지 않았습니다 (:{service.port})."
    )


def build_parser() -> argparse.ArgumentParser:
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
        help="Hermes와 호환 프록시를 시작하지 않고 기존 Gateway를 사용",
    )
    parser.add_argument(
        "--hermes-profile",
        default=os.environ["NARA_HERMES_PROFILE"],
        help="프로젝트 전용 Hermes profile 이름",
    )
    parser.add_argument(
        "--proxy-port",
        type=int,
        default=int(os.environ["NARA_CLOUDFLARE_PROXY_PORT"]),
        help="Cloudflare 호환 프록시 포트",
    )
    return parser


def main() -> int:
    configure_stdio()
    load_project_env()
    parser = build_parser()
    argv = sys.argv[1:]
    if wants_interactive(argv):
        argv = interactive_argv(
            parser,
            ask_if={
                "upstream_timeout": "!no_upstreams",
                "hermes_profile": "!no_hermes",
                "proxy_port": "!no_hermes",
            },
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
        gateway_is_running = port_open(8642)
        if args.no_hermes:
            if not gateway_is_running:
                raise RuntimeError(
                    "--no-hermes를 사용했지만 :8642에 Hermes Gateway가 없습니다."
                )
            print("[연결] Hermes Gateway: 기존 서비스 사용 (:8642)")
        else:
            if gateway_is_running:
                raise RuntimeError(
                    ":8642에 기존 Hermes Gateway가 있습니다. 호환 프록시 profile 사용 여부를 "
                    "확인할 수 없으므로 기존 실행을 Ctrl+C로 종료한 뒤 다시 시작하세요."
                )

            environment = child_environment()
            validate_proxy_configuration(environment)
            proxy = proxy_service(args.proxy_port)
            if port_open(proxy.port):
                if not proxy_health_ready(proxy.port):
                    raise RuntimeError(
                        f":{proxy.port}가 다른 프로세스에 의해 사용 중이거나 호환 프록시가 "
                        "정상 설정되지 않았습니다."
                    )
                print(f"[연결] {proxy.name}: 기존 서비스 사용 (:{proxy.port})")
            else:
                print(f"[시작] {proxy.name}: http://127.0.0.1:{proxy.port}")
                proxy_child = start_uvicorn(proxy)
                children.append(proxy_child)
                wait_until_healthy(
                    proxy,
                    proxy_child,
                    30.0,
                    readiness=proxy_health_ready,
                )

            print(f"[시작] Hermes Gateway: profile={args.hermes_profile}")
            gateway = start_hermes(
                args.hermes_profile,
                args.proxy_port,
                child_environment(),
            )
            children.append(gateway)
            deadline = time.monotonic() + 30
            while not (
                port_open(8642)
                and gateway_state_matches(args.hermes_profile, gateway.pid)
            ):
                if gateway.poll() is not None:
                    raise RuntimeError(
                        f"Hermes Gateway가 준비되기 전에 코드 {gateway.returncode}로 종료했습니다."
                    )
                if time.monotonic() >= deadline:
                    raise RuntimeError(
                        "Hermes Gateway가 30초 안에 프로젝트 전용 profile로 준비되지 않았습니다."
                    )
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
                wait_until_healthy(service, child, args.upstream_timeout)

        print(f"\nNara Hermes Orchestrator: http://127.0.0.1:{args.port}")
        print("종료하려면 Ctrl+C를 누르세요.")

        while True:
            for child in children:
                if child.poll() is not None:
                    print(
                        f"[종료] 프로세스 {child.pid}가 코드 {child.returncode}로 종료했습니다."
                    )
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
