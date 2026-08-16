from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from nara_common import process_runs
from nara_common.process_runs import MAX_EVENTS, ProcessRunManager


def _manager_with_run() -> tuple[ProcessRunManager, process_runs._Run]:
    manager = ProcessRunManager(sys.executable, Path("main.py"))
    run = process_runs._Run(run_id="r1", argv=["extend"], command="python main.py extend", metadata={})
    manager._runs[run.run_id] = run
    return manager, run


def test_event_sequence_keeps_growing_past_the_buffer_limit():
    """이벤트 배열은 잘리지만 번호는 이어져야 한다.

    번호를 배열 길이로 매기면 한계에 닿은 뒤 모든 이벤트가 같은 번호를 받는다.
    전체 크롤은 수십만 줄을 뿜으므로 장시간 실행에서 반드시 걸린다.
    """
    manager, run = _manager_with_run()

    for index in range(MAX_EVENTS + 5):
        manager._emit(run, "log", f"line {index}")

    sequences = [event["sequence"] for event in run.events]
    assert len(run.events) == MAX_EVENTS
    assert len(set(sequences)) == len(sequences)
    assert sequences[-1] == MAX_EVENTS + 5


def test_stream_delivers_events_emitted_after_the_buffer_limit():
    """한계를 넘긴 뒤의 이벤트도 스트림으로 나가야 한다.

    번호가 겹치면 `stream`이 이미 본 것으로 판단해 버려서, 작업은 계속 도는데
    웹 UI의 진행률과 로그만 멈춘다.
    """

    async def scenario():
        manager, run = _manager_with_run()
        for index in range(MAX_EVENTS + 3):
            manager._emit(run, "log", f"line {index}")
        run.done.set()
        return [event async for event in manager.stream(run.run_id, after=MAX_EVENTS)]

    delivered = asyncio.run(scenario())

    assert [event["message"] for event in delivered] == [
        f"line {MAX_EVENTS}",
        f"line {MAX_EVENTS + 1}",
        f"line {MAX_EVENTS + 2}",
    ]


def test_stream_resumes_from_the_requested_sequence():
    """SSE `id:`로 나간 번호를 그대로 다시 받으면 그 다음부터 이어져야 한다."""

    async def scenario():
        manager, run = _manager_with_run()
        for index in range(5):
            manager._emit(run, "log", f"line {index}")
        run.done.set()
        return [event async for event in manager.stream(run.run_id, after=3)]

    delivered = asyncio.run(scenario())

    assert [event["sequence"] for event in delivered] == [4, 5]
