"""Environment-based configuration for the isolated PoC."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

# Hermes runtime options have one source of truth: NARA_HERMES_*.
# Keep fallback values here only so a fresh clone can start before a .env exists.
HERMES_ENV_DEFAULTS = {
    "NARA_HERMES_PROFILE": "nara-openai",
    "NARA_HERMES_MODEL": "gpt-5.4-mini",
    "NARA_HERMES_TIMEOUT": "75",
    "NARA_HERMES_PROBE": "1",
}

# Plan Critic (post-run verification) options. See docs/plan_critic_agent_plan.md.
CRITIC_ENV_DEFAULTS = {
    "NARA_CRITIC_MODE": "deterministic",  # disabled | deterministic | full
    "NARA_CRITIC_TIMEOUT": "60",
    "NARA_HERMES_CRITIC_PROFILE": "nara-critic",
}


def load_project_env() -> None:
    """Load a local .env without overriding explicitly supplied process variables."""
    env_path = BASE_DIR / ".env"
    if env_path.is_file():
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                os.environ.setdefault(key, value)
    for key, value in {**HERMES_ENV_DEFAULTS, **CRITIC_ENV_DEFAULTS}.items():
        os.environ.setdefault(key, value)


def _hermes_env(key: str) -> str:
    """Read a Hermes setting from its process-wide NARA_HERMES_* variable."""
    return os.environ[key].strip()


def _hermes_timeout() -> float:
    return float(_hermes_env("NARA_HERMES_TIMEOUT"))


def _hermes_probe_enabled() -> bool:
    return _hermes_env("NARA_HERMES_PROBE").lower() not in {"0", "false", "no"}


# This guarantees Settings() itself, not just get_settings(), follows .env/process
# values. Load it before dataclass default factories can be invoked.
load_project_env()


@dataclass(frozen=True)
class Settings:
    search_url: str = "http://127.0.0.1:8000"
    combiner_url: str = "http://127.0.0.1:8003"
    request_timeout: float = 30.0
    compose_timeout: float = 240.0
    hermes_profile: str = field(
        default_factory=lambda: _hermes_env("NARA_HERMES_PROFILE")
    )
    hermes_model: str = field(default_factory=lambda: _hermes_env("NARA_HERMES_MODEL"))
    hermes_timeout: float = field(default_factory=_hermes_timeout)
    hermes_probe_enabled: bool = field(default_factory=_hermes_probe_enabled)
    critic_mode: str = field(default_factory=lambda: _hermes_env("NARA_CRITIC_MODE"))
    critic_timeout: float = field(
        default_factory=lambda: float(_hermes_env("NARA_CRITIC_TIMEOUT"))
    )
    hermes_critic_profile: str = field(
        default_factory=lambda: _hermes_env("NARA_HERMES_CRITIC_PROFILE")
    )


def get_settings() -> Settings:
    load_project_env()
    return Settings(
        search_url=os.getenv("NARA_SEARCH_URL", Settings.search_url).rstrip("/"),
        combiner_url=os.getenv(
            "NARA_COMBINER_URL", Settings.combiner_url
        ).rstrip("/"),
        request_timeout=float(
            os.getenv("NARA_REQUEST_TIMEOUT", str(Settings.request_timeout))
        ),
        compose_timeout=float(
            os.getenv("NARA_COMPOSE_TIMEOUT", str(Settings.compose_timeout))
        ),
    )
