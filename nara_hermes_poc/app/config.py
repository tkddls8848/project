"""Environment-based configuration for the isolated PoC."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    search_url: str = "http://127.0.0.1:8000"
    combiner_url: str = "http://127.0.0.1:8003"
    request_timeout: float = 30.0
    compose_timeout: float = 240.0


def get_settings() -> Settings:
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
