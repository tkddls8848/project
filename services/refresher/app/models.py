"""Runtime values used by the refresher."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


@dataclass
class AccountRow:
    name: str
    detail_params: dict[str, str]
    nav_args: list[str]
    status_text: str = ""

    @property
    def key(self) -> str:
        return "&".join(f"{key}={value}" for key, value in sorted(self.detail_params.items()))


@dataclass
class ExtendOutcome:
    key: str
    name: str
    action: Literal["extended", "skipped", "failed", "would-extend"]
    message: str = ""
    portal_message: str = ""


@dataclass
class RunSummary:
    commit: bool
    outcomes: list[ExtendOutcome] = field(default_factory=list)
    started_at: str = field(default_factory=lambda: datetime.now().astimezone().isoformat())
    finished_at: str = ""

    @property
    def total(self) -> int:
        return len(self.outcomes)

    def count(self, action: str) -> int:
        return sum(item.action == action for item in self.outcomes)

    @property
    def extended(self) -> int:
        return self.count("extended")

    @property
    def skipped(self) -> int:
        return self.count("skipped")

    @property
    def failed(self) -> int:
        return self.count("failed")

    @property
    def would_extend(self) -> int:
        return self.count("would-extend")
