"""연장 CLI 요청을 argv로 옮기고 공용 실행기에 넘긴다.

실행·스트리밍·중단은 `nara_common.process_runs`가 한다. 여기에는 refresher
CLI에만 있는 규칙을 둔다. 그중 중요한 것은 `extend --commit`이다. 이것만이
포털에 실제로 제출하는 경로이므로, 요청에서 한 번 더 명시하지 않으면 만들 수 없다.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from nara_common.process_runs import ProcessRunManager

BASE_DIR = Path(__file__).resolve().parent.parent
MAIN_SCRIPT = BASE_DIR / "main.py"

COMMANDS = ("login", "list", "extend")

# 이 값들만 포털을 변경한다. 나머지는 전부 읽기 전용이다.
WRITING_COMMANDS = frozenset({"extend"})


class RefreshRequestError(ValueError):
    """요청 조합이 CLI 규칙이나 안전 규칙에 맞지 않을 때."""


@dataclass(frozen=True)
class RefreshRequest:
    command: str
    manual: bool = False
    timeout: float = 600.0
    commit: bool = False
    limit: Optional[int] = None
    only: str = ""
    # 실제 제출은 요청에서 따로 한 번 더 인정해야 한다. dry-run 요청을 그대로
    # 다시 보내는 것만으로 실제 제출이 되어서는 안 된다.
    confirm_commit: bool = False

    def validate(self) -> None:
        if self.command not in COMMANDS:
            raise RefreshRequestError(f"알 수 없는 명령입니다: {self.command}")

        if self.command != "login" and self.manual:
            raise RefreshRequestError("--manual은 login에서만 씁니다.")
        if self.command == "login" and self.timeout <= 0:
            raise RefreshRequestError("로그인 대기 시간은 0보다 커야 합니다.")

        if self.command != "extend":
            if self.commit or self.limit is not None or self.only:
                raise RefreshRequestError("--commit·--limit·--only는 extend에서만 씁니다.")
            return

        if self.limit is not None and self.limit < 1:
            raise RefreshRequestError("limit은 1 이상이어야 합니다.")
        if self.commit and not self.confirm_commit:
            raise RefreshRequestError(
                "실제 연장 제출은 confirm_commit을 함께 보내야 합니다."
            )

    def to_argv(self) -> list[str]:
        self.validate()
        argv = [self.command]
        if self.command == "login":
            if self.manual:
                argv.append("--manual")
            argv += ["--timeout", _number(self.timeout)]
        elif self.command == "extend":
            if self.commit:
                argv.append("--commit")
            if self.limit is not None:
                argv += ["--limit", str(self.limit)]
            if self.only:
                argv += ["--only", self.only]
        return argv

    def command_preview(self) -> str:
        return "python main.py " + " ".join(self.to_argv())

    @property
    def writes_to_portal(self) -> bool:
        return self.command in WRITING_COMMANDS and self.commit

    @property
    def accepts_stdin(self) -> bool:
        """`login --manual`은 터미널에서 Enter를 기다린다.

        브라우저에는 그 터미널이 없으므로 stdin을 열어두고 UI 버튼으로 잇는다.
        """
        return self.command == "login" and self.manual

    def metadata(self) -> dict[str, object]:
        return {
            "command": self.command,
            "manual": self.manual,
            "commit": self.commit,
            "limit": self.limit,
            "only": self.only,
            "writes_to_portal": self.writes_to_portal,
            "dry_run": self.command == "extend" and not self.commit,
        }


def _number(value: float) -> str:
    """600.0이 아니라 600으로 넘겨 명령이 사람이 친 것과 같게 보이도록 한다."""
    return str(int(value)) if float(value).is_integer() else str(value)


class RefreshRunManager(ProcessRunManager):
    def __init__(self, python_executable: str | None = None, script: Path | None = None):
        super().__init__(python_executable or sys.executable, script or MAIN_SCRIPT)

    async def create_command(self, request: RefreshRequest) -> dict[str, object]:
        argv = request.to_argv()
        return await self.create(
            argv,
            request.command_preview(),
            request.metadata(),
            accepts_stdin=request.accepts_stdin,
        )


__all__ = [
    "BASE_DIR",
    "COMMANDS",
    "MAIN_SCRIPT",
    "RefreshRequest",
    "RefreshRequestError",
    "RefreshRunManager",
    "WRITING_COMMANDS",
]
