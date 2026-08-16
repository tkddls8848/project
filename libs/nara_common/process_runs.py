"""브라우저에서 CLI 배치 도구를 실행·관찰·중단하기 위한 공용 실행기.

crawler와 refresher는 둘 다 argparse CLI이고, 웹 UI는 그 CLI를 그대로 실행해
출력을 스트리밍한다. 백엔드가 도구 내부 함수를 직접 부르지 않으므로 브라우저에서
누른 실행과 터미널에서 친 명령이 갈라지지 않는다.

요청을 argv로 옮기는 규칙은 도구마다 다르므로 각 서비스가 갖는다. 여기에는
프로세스를 돌리고 관찰하는 부분만 둔다.
"""

from __future__ import annotations

import asyncio
import os
import re
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

KST = timezone(timedelta(hours=9))

# 전체 크롤은 수십만 줄을 뿜는다. 메모리에 들고 있을 양을 제한한다.
MAX_LOG_LINES = 400
MAX_EVENTS = 2000

TERMINAL_STATUSES = frozenset({"completed", "failed", "cancelled"})

# tqdm 진행 표시줄: "Crawling:  45%|####5     | 45/100 [00:10<00:12,  4.5it/s]"
TQDM_RE = re.compile(
    r"^(?P<desc>.*?)\s*:?\s*(?P<pct>\d{1,3})%\|[^|]*\|\s*(?P<done>\d+)/(?P<total>\d+)"
)


def parse_progress(line: str) -> dict[str, Any] | None:
    """tqdm 한 줄에서 진행률을 뽑는다. 진행 표시줄이 아니면 None."""
    match = TQDM_RE.match(line.strip())
    if not match:
        return None
    done = int(match.group("done"))
    total = int(match.group("total"))
    if total <= 0:
        return None
    return {
        "label": match.group("desc").strip() or "진행 중",
        "done": done,
        "total": total,
        "percent": round(done * 100 / total, 1),
    }


def split_stream(buffer: str) -> tuple[list[str], str]:
    """줄바꿈과 캐리지리턴 모두에서 줄을 끊는다.

    tqdm은 같은 줄을 ``\\r``로 덮어쓰며 갱신하므로 ``\\n``만 기준으로 자르면
    작업이 끝날 때까지 진행률이 한 줄도 나오지 않는다.
    """
    parts = re.split(r"\r\n|\n|\r", buffer)
    return parts[:-1], parts[-1]


@dataclass
class _Run:
    run_id: str
    argv: list[str]
    command: str
    metadata: dict[str, Any]
    status: str = "running"
    events: list[dict[str, Any]] = field(default_factory=list)
    # 이벤트 배열은 MAX_EVENTS에서 잘리므로 길이로 번호를 매기면 그 뒤로
    # 같은 번호가 반복된다. 잘림과 무관하게 계속 늘어나는 카운터를 따로 둔다.
    last_sequence: int = 0
    log: list[str] = field(default_factory=list)
    progress: dict[str, Any] | None = None
    started_at: str = ""
    ended_at: str = ""
    exit_code: int | None = None
    error: str | None = None
    accepts_stdin: bool = False
    process: asyncio.subprocess.Process | None = None
    task: asyncio.Task[None] | None = None
    done: asyncio.Event = field(default_factory=asyncio.Event)
    changed: asyncio.Event = field(default_factory=asyncio.Event)

    def snapshot(self, *, include_log: bool = True) -> dict[str, Any]:
        payload = {
            "run_id": self.run_id,
            "status": self.status,
            "command": self.command,
            "metadata": self.metadata,
            "progress": self.progress,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "exit_code": self.exit_code,
            "error": self.error,
            "accepts_stdin": self.accepts_stdin,
        }
        if include_log:
            payload["log"] = list(self.log)
        return payload


class ProcessRunManager:
    """한 번에 하나의 실행만 허용한다.

    두 도구 모두 외부 사이트를 상대하고 공유 저장소에 쓴다. 동시에 여러 개를
    돌리면 상대 사이트에 부담을 주고 산출물이 서로를 덮어쓴다.
    """

    def __init__(self, python_executable: str, script: Path, cwd: Path | None = None):
        self._python = python_executable
        self._script = Path(script)
        self._cwd = Path(cwd) if cwd else self._script.parent
        self._runs: dict[str, _Run] = {}
        self._active_id: str | None = None

    # ── 조회 ────────────────────────────────────────────────────────────
    def active_run_id(self) -> str | None:
        run = self._runs.get(self._active_id or "")
        if run is None or run.done.is_set():
            return None
        return run.run_id

    def snapshot(self, run_id: str) -> dict[str, Any]:
        run = self._runs.get(run_id)
        if run is None:
            raise KeyError(run_id)
        return run.snapshot()

    def recent(self, limit: int = 20) -> list[dict[str, Any]]:
        runs = sorted(self._runs.values(), key=lambda item: item.started_at, reverse=True)
        return [run.snapshot(include_log=False) for run in runs[:limit]]

    # ── 실행 ────────────────────────────────────────────────────────────
    async def create(
        self,
        argv: list[str],
        command: str,
        metadata: dict[str, Any] | None = None,
        *,
        accepts_stdin: bool = False,
        environment: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        if not argv:
            # 인자가 없으면 두 CLI 모두 콘솔에서 대화형으로 빠진다.
            # 서버에서는 절대 그 경로로 보내지 않는다.
            raise ValueError("실행할 인자가 없습니다.")
        if self.active_run_id() is not None:
            raise RuntimeError("이미 실행 중인 작업이 있습니다. 끝나거나 중단된 뒤에 시작하세요.")

        run = _Run(
            run_id=uuid.uuid4().hex,
            argv=list(argv),
            command=command,
            metadata=metadata or {},
            started_at=_now_iso(),
            accepts_stdin=accepts_stdin,
        )
        self._runs[run.run_id] = run
        self._active_id = run.run_id
        self._emit(run, "started", command)
        run.task = asyncio.create_task(
            self._execute(run, environment), name=f"run-{run.run_id}"
        )
        return run.snapshot()

    async def stop(self, run_id: str) -> dict[str, Any]:
        run = self._runs.get(run_id)
        if run is None:
            raise KeyError(run_id)
        if run.done.is_set():
            return run.snapshot()
        run.status = "stopping"
        self._emit(run, "stopping", "중단을 요청했습니다.")
        process = run.process
        if process is not None and process.returncode is None:
            try:
                process.terminate()
            except ProcessLookupError:
                pass
        return run.snapshot()

    async def send_stdin(self, run_id: str, text: str = "\n") -> dict[str, Any]:
        """실행 중인 프로세스의 stdin으로 한 줄 보낸다.

        `refresher login --manual`처럼 터미널에서 Enter를 기다리는 명령을
        브라우저 버튼으로 이어주기 위한 것이다.
        """
        run = self._runs.get(run_id)
        if run is None:
            raise KeyError(run_id)
        if not run.accepts_stdin:
            raise RuntimeError("이 실행은 입력을 받지 않습니다.")
        process = run.process
        if run.done.is_set() or process is None or process.stdin is None:
            raise RuntimeError("실행이 이미 끝나 입력을 보낼 수 없습니다.")
        if not text.endswith("\n"):
            text += "\n"
        process.stdin.write(text.encode("utf-8"))
        await process.stdin.drain()
        self._emit(run, "stdin", "브라우저에서 입력을 보냈습니다.")
        return run.snapshot()

    async def stream(self, run_id: str, after: int = 0) -> AsyncIterator[dict[str, Any]]:
        run = self._runs.get(run_id)
        if run is None:
            raise KeyError(run_id)
        next_sequence = after + 1
        while True:
            for event in [item for item in run.events if item["sequence"] >= next_sequence]:
                next_sequence = event["sequence"] + 1
                yield event
            if run.done.is_set():
                return
            run.changed.clear()
            await run.changed.wait()

    async def _execute(self, run: _Run, environment: dict[str, str] | None) -> None:
        child_env = os.environ.copy()
        # 자식이 한글을 UTF-8로 내보내게 고정한다. 콘솔 코드페이지(cp949)에
        # 맡기면 파이프로 받을 때 한글이 물음표로 바뀐다.
        child_env.update(
            {"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}
        )
        child_env.update(environment or {})
        try:
            run.process = await asyncio.create_subprocess_exec(
                self._python, "-u", str(self._script), *run.argv,
                cwd=str(self._cwd),
                env=child_env,
                stdin=asyncio.subprocess.PIPE if run.accepts_stdin else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            await self._pump(run)
            run.exit_code = await run.process.wait()
            if run.status == "stopping":
                run.status = "cancelled"
                self._emit(run, "cancelled", "사용자가 실행을 중단했습니다.")
            elif run.exit_code == 0:
                run.status = "completed"
                self._emit(run, "completed", "실행을 완료했습니다.")
            else:
                run.status = "failed"
                run.error = f"명령이 코드 {run.exit_code}로 종료했습니다."
                self._emit(run, "failed", run.error)
        except asyncio.CancelledError:
            run.status = "cancelled"
            self._emit(run, "cancelled", "실행이 취소되었습니다.")
            raise
        except OSError as exc:
            run.status = "failed"
            run.error = f"명령을 시작하지 못했습니다: {exc}"
            self._emit(run, "failed", run.error)
        finally:
            # 중단으로 끝난 프로세스는 stdout 파이프 transport가 남아 Windows
            # proactor 루프에서 "unclosed transport" 경고를 낸다. 명시적으로 닫는다.
            transport = getattr(run.process, "_transport", None)
            if transport is not None:
                transport.close()
            run.ended_at = _now_iso()
            run.done.set()
            run.changed.set()
            if self._active_id == run.run_id:
                self._active_id = None

    async def _pump(self, run: _Run) -> None:
        assert run.process is not None and run.process.stdout is not None
        buffer = ""
        while True:
            chunk = await run.process.stdout.read(4096)
            if not chunk:
                break
            buffer += chunk.decode("utf-8", errors="replace")
            lines, buffer = split_stream(buffer)
            for line in lines:
                self._consume_line(run, line)
        if buffer.strip():
            self._consume_line(run, buffer)

    def _consume_line(self, run: _Run, line: str) -> None:
        text = line.rstrip()
        if not text.strip():
            return
        progress = parse_progress(text)
        if progress is not None:
            run.progress = progress
            self._emit(run, "progress", text, progress=progress)
            return
        run.log.append(text)
        if len(run.log) > MAX_LOG_LINES:
            del run.log[: len(run.log) - MAX_LOG_LINES]
        self._emit(run, "log", text)

    def _emit(self, run: _Run, kind: str, message: str, **extra: Any) -> None:
        run.last_sequence += 1
        run.events.append(
            {
                "sequence": run.last_sequence,
                "kind": kind,
                "status": run.status,
                "message": message,
                **extra,
            }
        )
        if len(run.events) > MAX_EVENTS:
            del run.events[: len(run.events) - MAX_EVENTS]
        run.changed.set()


def _now_iso() -> str:
    return datetime.now(KST).isoformat()


__all__ = [
    "MAX_EVENTS",
    "MAX_LOG_LINES",
    "ProcessRunManager",
    "TERMINAL_STATUSES",
    "parse_progress",
    "split_stream",
]
