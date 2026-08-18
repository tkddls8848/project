"""Environment-based configuration for the Hermes orchestration service."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from nara_common.paths import find_project_root

BASE_DIR = Path(__file__).resolve().parent.parent

PROJECT_ROOT = find_project_root(BASE_DIR)
DEFAULT_STORAGE_DIR = PROJECT_ROOT / "nara_storage"

# Hermes runtime options have one source of truth. The application talks only to
# the authenticated Gateway Runs API; model-provider credentials stay inside the
# Hermes profile and are never sent to browser clients.
HERMES_ENV_DEFAULTS = {
    "NARA_HERMES_PROFILE": "nara-cf",
    "NARA_HERMES_MODEL": "@cf/qwen/qwen3-30b-a3b-fp8",
    "NARA_CLOUDFLARE_PROXY_PORT": "8643",
    "NARA_CLOUDFLARE_PROXY_KEY": "change-me-local-proxy",
    "HERMES_API_URL": "http://127.0.0.1:8642",
    "API_SERVER_KEY": "change-me-local-dev",
    "NARA_HERMES_RUN_TIMEOUT": "300",
    # One search plus at most three details. Each extra call re-sends every
    # earlier tool result, so the cap is what bounds token spend per run.
    "NARA_HERMES_MAX_TOOL_CALLS": "4",
}

# Local post-run verification. It never starts another LLM run.
CRITIC_ENV_DEFAULTS = {
    "NARA_CRITIC_MODE": "deterministic",  # disabled | deterministic
    "NARA_CRITIC_TIMEOUT": "60",
}

# Freshness checks are read-only. Leaving NARA_INDEX_BUILT_AT empty is the
# normal case: the orchestrator then reads the active index build time from
# Search /health, so the check runs instead of reporting 'unverified'. Set it
# only to override that value.
FRESHNESS_ENV_DEFAULTS = {
    "NARA_DOC_FRESHNESS_MODE": "deterministic",  # disabled | deterministic
    "NARA_STORAGE_DIR": str(DEFAULT_STORAGE_DIR),
    "NARA_INDEX_BUILT_AT": "",  # ISO 8601 override; empty = ask Search
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
    for key, value in {
        **HERMES_ENV_DEFAULTS,
        **CRITIC_ENV_DEFAULTS,
        **FRESHNESS_ENV_DEFAULTS,
    }.items():
        os.environ.setdefault(key, value)


def _hermes_env(key: str) -> str:
    """Read a Hermes setting from its process-wide NARA_HERMES_* variable."""
    return os.environ[key].strip()


def _freshness_env(key: str) -> str:
    """Read a freshness setting from its process-wide NARA_* variable."""
    return os.environ[key].strip()


# This guarantees Settings() itself, not just get_settings(), follows .env/process
# values. Load it before dataclass default factories can be invoked.
load_project_env()


@dataclass(frozen=True)
class Settings:
    search_url: str = "http://127.0.0.1:8000"
    combiner_url: str = "http://127.0.0.1:8003"
    request_timeout: float = 30.0
    compose_timeout: float = 240.0
    hermes_profile: str = field(default_factory=lambda: _hermes_env("NARA_HERMES_PROFILE"))
    hermes_model: str = field(default_factory=lambda: _hermes_env("NARA_HERMES_MODEL"))
    hermes_api_url: str = field(default_factory=lambda: _hermes_env("HERMES_API_URL").rstrip("/"))
    hermes_api_key: str = field(default_factory=lambda: _hermes_env("API_SERVER_KEY"))
    hermes_run_timeout: float = field(default_factory=lambda: float(_hermes_env("NARA_HERMES_RUN_TIMEOUT")))
    hermes_max_tool_calls: int = field(default_factory=lambda: int(_hermes_env("NARA_HERMES_MAX_TOOL_CALLS")))
    critic_mode: str = field(default_factory=lambda: _hermes_env("NARA_CRITIC_MODE"))
    critic_timeout: float = field(default_factory=lambda: float(_hermes_env("NARA_CRITIC_TIMEOUT")))
    freshness_mode: str = field(default_factory=lambda: _freshness_env("NARA_DOC_FRESHNESS_MODE"))
    storage_dir: Path = field(default_factory=lambda: Path(_freshness_env("NARA_STORAGE_DIR")))
    index_built_at: str = field(default_factory=lambda: _freshness_env("NARA_INDEX_BUILT_AT"))


def get_settings() -> Settings:
    load_project_env()
    return Settings(
        search_url=os.getenv("NARA_SEARCH_URL", Settings.search_url).rstrip("/"),
        combiner_url=os.getenv("NARA_COMBINER_URL", Settings.combiner_url).rstrip("/"),
        request_timeout=float(os.getenv("NARA_REQUEST_TIMEOUT", str(Settings.request_timeout))),
        compose_timeout=float(os.getenv("NARA_COMPOSE_TIMEOUT", str(Settings.compose_timeout))),
    )
