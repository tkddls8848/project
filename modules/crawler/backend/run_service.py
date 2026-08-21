"""크롤 요청을 CLI argv로 옮기고 공용 실행기에 넘긴다.

프로세스를 돌리고 관찰하는 부분은 `nara_common.process_runs`가 갖는다.
여기에는 크롤러 CLI에만 있는 규칙(타입·범위·심화 플래그)을 둔다.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from crawl_types import CLI_CRAWL_TYPES
from nara_common.process_runs import ProcessRunManager

BASE_DIR = Path(__file__).resolve().parent.parent
MAIN_SCRIPT = BASE_DIR / "main.py"

DATA_TYPES = CLI_CRAWL_TYPES


class CrawlRequestError(ValueError):
    """요청 조합이 CLI 규칙에 맞지 않을 때."""


@dataclass(frozen=True)
class CrawlRequest:
    """UI 입력 하나를 main.py argv 하나로 옮긴다."""

    data_type: Optional[str] = None
    start: Optional[int] = None
    end: Optional[int] = None
    workers: Optional[int] = None
    full: bool = False
    deep: bool = False
    full_download: bool = False
    harvest: bool = False
    harvest_max_hosts: int = 4
    skip_update: bool = False
    force_update: bool = False

    def validate(self) -> None:
        """main.py의 parser.error 조건을 요청 시점에 그대로 재현한다."""
        if self.data_type is not None and self.data_type not in DATA_TYPES:
            raise CrawlRequestError(f"알 수 없는 type입니다: {self.data_type}")
        if self.full and self.data_type:
            raise CrawlRequestError("--full은 type과 함께 쓸 수 없습니다.")
        if self.workers is not None and self.workers < 1:
            raise CrawlRequestError("workers는 1 이상이어야 합니다.")
        if self.full_download and not self.deep:
            raise CrawlRequestError("전량 수신은 심화 분석(deep)을 함께 켜야 합니다.")
        if self.harvest_max_hosts < 1:
            raise CrawlRequestError("harvest_max_hosts는 1 이상이어야 합니다.")

        depth_only = (self.deep or self.harvest) and not self.data_type and not self.full
        if depth_only:
            return
        if not self.full and not self.data_type:
            raise CrawlRequestError("type을 고르거나 전체 크롤(full)을 선택하세요.")
        if not self.full:
            if self.start is None or self.end is None:
                raise CrawlRequestError("시작·끝 문서번호가 필요합니다.")
            if self.start > self.end:
                raise CrawlRequestError("시작 번호가 끝 번호보다 큽니다.")

    def to_argv(self) -> list[str]:
        self.validate()
        argv: list[str] = []
        if self.full:
            argv.append("--full")
        elif self.data_type:
            argv.append(self.data_type)
            argv += ["-s", str(self.start), "-e", str(self.end)]
        if self.workers is not None:
            argv += ["-w", str(self.workers)]
        if self.skip_update:
            argv.append("--skip-update")
        if self.force_update:
            argv.append("--force-update")
        if self.deep:
            argv.append("--deep")
        if self.full_download:
            argv.append("--full-download")
        if self.harvest:
            argv.append("--harvest")
            argv += ["--harvest-max-hosts", str(self.harvest_max_hosts)]
        if not argv:
            raise CrawlRequestError("실행할 작업이 없습니다.")
        return argv

    def command_preview(self) -> str:
        return "python main.py " + " ".join(self.to_argv())

    def metadata(self) -> dict[str, object]:
        return {
            "type": self.data_type,
            "start": self.start,
            "end": self.end,
            "workers": self.workers,
            "full": self.full,
            "deep": self.deep,
            "full_download": self.full_download,
            "harvest": self.harvest,
            "harvest_max_hosts": self.harvest_max_hosts,
        }


class CrawlRunManager(ProcessRunManager):
    """크롤 요청을 받는 실행기. 실행·중단·스트리밍은 상위 클래스가 한다."""

    def __init__(self, python_executable: str | None = None, script: Path | None = None):
        super().__init__(python_executable or sys.executable, script or MAIN_SCRIPT)

    async def create_crawl(self, request: CrawlRequest) -> dict[str, object]:
        argv = request.to_argv()
        return await self.create(argv, request.command_preview(), request.metadata())


__all__ = [
    "CrawlRequest",
    "CrawlRequestError",
    "CrawlRunManager",
    "DATA_TYPES",
    "MAIN_SCRIPT",
    "BASE_DIR",
]
