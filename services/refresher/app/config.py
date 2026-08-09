"""Configuration for the data.go.kr account refresher."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def find_project_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / ".nara-root").is_file():
            return candidate
    return start.parent


PROJECT_ROOT = find_project_root(BASE_DIR)
DEFAULT_STORAGE_DIR = PROJECT_ROOT / "nara_storage" / "refresher"
DEFAULTS = {
    "REFRESHER_BASE_URL": "https://www.data.go.kr",
    "REFRESHER_LIST_PATH": "/iim/api/selectAcountList.do",
    "REFRESHER_LIST_STATUS": "dupReq",
    "REFRESHER_STORAGE_DIR": str(DEFAULT_STORAGE_DIR),
    "REFRESHER_TIMEOUT": "30",
    "REFRESHER_HEADLESS": "0",
}


def load_project_env() -> None:
    path = BASE_DIR / ".env"
    if path.is_file():
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    for key, value in DEFAULTS.items():
        os.environ.setdefault(key, value)


load_project_env()


@dataclass(frozen=True)
class Settings:
    base_url: str = field(default_factory=lambda: os.environ["REFRESHER_BASE_URL"].rstrip("/"))
    list_path: str = field(default_factory=lambda: os.environ["REFRESHER_LIST_PATH"])
    list_status: str = field(default_factory=lambda: os.environ["REFRESHER_LIST_STATUS"])
    storage_dir: Path = field(default_factory=lambda: Path(os.environ["REFRESHER_STORAGE_DIR"]))
    timeout: float = field(default_factory=lambda: float(os.environ["REFRESHER_TIMEOUT"]))
    headless: bool = field(default_factory=lambda: os.environ["REFRESHER_HEADLESS"].lower() not in {"0", "false", "no", ""})

    @property
    def list_url(self) -> str:
        query = f"?status={self.list_status}" if self.list_status else ""
        return f"{self.base_url}{self.list_path}{query}"

    @property
    def state_file(self) -> Path:
        return self.storage_dir / "storage_state.json"


def get_settings() -> Settings:
    load_project_env()
    return Settings()
