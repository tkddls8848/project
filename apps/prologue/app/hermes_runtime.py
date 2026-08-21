"""프로젝트 전용 Hermes profile과 Gateway 프로세스를 준비한다."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

from nara_common.process import project_python

BASE_DIR = Path(__file__).resolve().parent.parent
HERMES_RUNTIME_ROOT = BASE_DIR / ".runtime" / "hermes"
HERMES_PROFILE_TEMPLATE = BASE_DIR / "config" / "hermes.example.yaml"
PROFILE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


def validate_proxy_configuration(environment: dict[str, str]) -> None:
    required = (
        "CLOUDFLARE_ACCOUNT_ID",
        "CLOUDFLARE_API_TOKEN",
        "NARA_CLOUDFLARE_PROXY_KEY",
    )
    missing = [key for key in required if not environment.get(key, "").strip()]
    if missing:
        raise RuntimeError(
            "Cloudflare 프록시 설정이 비었습니다: "
            + ", ".join(missing)
            + ". apps/prologue/.env에 값을 입력하세요."
        )


def _yaml_value(value: object) -> str:
    """경로 인용 문제를 피하도록 YAML에서도 유효한 JSON 값으로 만든다."""
    return json.dumps(value, ensure_ascii=False)


def render_hermes_profile(
    proxy_port: int, environment: dict[str, str]
) -> str:
    replacements: dict[str, object] = {
        "__NARA_CLOUDFLARE_PROXY_URL__": f"http://127.0.0.1:{proxy_port}/v1",
        "__NARA_HERMES_MODEL__": environment["NARA_HERMES_MODEL"],
        "__NARA_PROLOGUE_PYTHON__": str(project_python(BASE_DIR)),
        "__NARA_PROLOGUE_DIR__": str(BASE_DIR),
        "__NARA_SEARCH_URL__": environment.get(
            "NARA_SEARCH_URL", "http://127.0.0.1:8000"
        ),
    }
    rendered = HERMES_PROFILE_TEMPLATE.read_text(encoding="utf-8")
    for placeholder, value in replacements.items():
        rendered = rendered.replace(placeholder, _yaml_value(value))
    unresolved = sorted(set(re.findall(r"__[A-Z0-9_]+__", rendered)))
    if unresolved:
        raise RuntimeError(
            "Hermes profile 템플릿에 치환되지 않은 값이 있습니다: "
            + ", ".join(unresolved)
        )
    return rendered


def ensure_hermes_runtime_profile(
    profile: str, proxy_port: int, environment: dict[str, str]
) -> Path:
    if (
        not PROFILE_NAME_PATTERN.fullmatch(profile)
        or profile in {".", ".."}
        or ".." in profile
    ):
        raise RuntimeError(f"안전하지 않은 Hermes profile 이름입니다: {profile!r}")
    profile_dir = HERMES_RUNTIME_ROOT / "profiles" / profile
    profile_dir.mkdir(parents=True, exist_ok=True)
    config_path = profile_dir / "config.yaml"
    rendered = render_hermes_profile(proxy_port, environment)
    if not config_path.is_file() or config_path.read_text(encoding="utf-8") != rendered:
        config_path.write_text(rendered, encoding="utf-8")
    return config_path


def gateway_state_matches(profile: str, expected_pid: int) -> bool:
    """리스닝 Gateway가 프로젝트 전용 profile 프로세스인지 확인한다."""
    state_path = HERMES_RUNTIME_ROOT / "profiles" / profile / "gateway_state.json"
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return False
    return (
        payload.get("kind") == "hermes-gateway"
        and payload.get("gateway_state") == "running"
        and payload.get("pid") == expected_pid
    )


def hermes_executable() -> Path:
    override = os.getenv("HERMES_EXE", "").strip()
    if override:
        return Path(override)
    local_app_data = os.getenv("LOCALAPPDATA", "")
    return (
        Path(local_app_data)
        / "hermes"
        / "hermes-agent"
        / "venv"
        / "Scripts"
        / "hermes.exe"
    )


def hermes_python_executable(
    executable: Path, environment: dict[str, str]
) -> Path | None:
    """Hermes venv를 유지하면서 직접 추적할 Python 프로세스를 찾는다."""
    venv_python = executable.with_name("python.exe" if os.name == "nt" else "python")
    if not venv_python.is_file():
        return None
    if os.name != "nt":
        return venv_python

    pyvenv_config = executable.parent.parent / "pyvenv.cfg"
    try:
        lines = pyvenv_config.read_text(encoding="utf-8").splitlines()
    except OSError:
        return venv_python
    home = next(
        (
            line.split("=", 1)[1].strip()
            for line in lines
            if line.partition("=")[0].strip().lower() == "home"
        ),
        "",
    )
    base_python = Path(home) / "python.exe"
    if not home or not base_python.is_file():
        return venv_python
    environment["__PYVENV_LAUNCHER__"] = str(venv_python)
    return base_python


def start_hermes(
    profile: str, proxy_port: int, environment: dict[str, str]
) -> subprocess.Popen:
    executable = hermes_executable()
    if not executable.is_file():
        raise RuntimeError(
            "Hermes 실행 파일을 찾지 못했습니다. HERMES_EXE를 지정하거나 Hermes를 설치하세요: "
            f"{executable}"
        )
    # Hermes는 별도 venv와 Python 버전을 사용한다. 현재 프로젝트의 경로가
    # 유입되면 다른 ABI의 확장 모듈을 먼저 읽을 수 있으므로 제거한다.
    for name in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
        environment.pop(name, None)
    validate_proxy_configuration(environment)
    config_path = ensure_hermes_runtime_profile(profile, proxy_port, environment)
    # profile 디렉터리를 직접 가리켜 사용자 전역 active_profile을 따르지 않는다.
    environment["HERMES_HOME"] = str(config_path.parent)
    environment["HERMES_PROFILE"] = profile
    environment["HERMES_INFERENCE_PROVIDER"] = "custom:cloudflare_proxy"
    kwargs: dict[str, object] = {"cwd": str(BASE_DIR), "env": environment}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    print(f"[설정] 프로젝트 전용 Hermes profile: {config_path}")

    python_executable = hermes_python_executable(executable, environment)
    if python_executable is not None:
        command = [
            str(python_executable),
            "-m",
            "hermes_cli.main",
            "-m",
            environment["NARA_HERMES_MODEL"],
            "gateway",
        ]
    else:
        command = [
            str(executable),
            "-m",
            environment["NARA_HERMES_MODEL"],
            "gateway",
        ]
    return subprocess.Popen(command, **kwargs)


__all__ = [
    "ensure_hermes_runtime_profile",
    "gateway_state_matches",
    "hermes_executable",
    "hermes_python_executable",
    "render_hermes_profile",
    "start_hermes",
    "validate_proxy_configuration",
]
