"""Bounded Hermes MCP loop with normalized, browser-friendly progress events."""

from __future__ import annotations

import asyncio
import os
import re
import shutil
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import Settings, get_settings
from .critic import run_critic
from .nara_client import NaraClient, NaraServiceError
from .schemas import (
    AgentEvent,
    AgentRunRequest,
    AgentRunResponse,
    CriticReport,
    DesignResponse,
    StageRecord,
)

NARA_TOOLS = {"search_api_docs", "get_api_detail", "derive_relations", "compose_service_plan"}


def _hermes_executable() -> str | None:
    configured = os.getenv("HERMES_EXE", "").strip()
    if configured and Path(configured).is_file():
        return configured
    candidate = Path(os.getenv("LOCALAPPDATA", "")) / "hermes" / "hermes-agent" / "venv" / "Scripts" / "hermes.exe"
    return str(candidate) if candidate.is_file() else shutil.which("hermes")


async def run_hermes_tool_probe(
    tool_name: str, instruction: str, settings: Settings, profile: str | None = None
) -> dict[str, Any]:
    """Ask Hermes to invoke one specific Nara MCP tool exactly once."""
    if tool_name not in NARA_TOOLS:
        raise ValueError(f"Unsupported Nara tool: {tool_name}")
    executable = _hermes_executable()
    if not settings.hermes_probe_enabled:
        return {"tool": tool_name, "status": "disabled", "tools": []}
    if not executable:
        return {"tool": tool_name, "status": "unavailable", "tools": [], "message": "Hermes executable was not found."}

    prompt = (
        f"반드시 nara MCP의 {tool_name} 도구만 정확히 한 번 호출하라. {instruction} "
        "다른 도구, 스킬, 파일 접근을 사용하지 마라. 도구 응답 뒤에는 짧게 완료만 답하라."
    )
    environment = os.environ.copy()
    environment["PYTHONUTF8"] = "1"
    environment["PYTHONIOENCODING"] = "utf-8"
    process: asyncio.subprocess.Process | None = None
    try:
        process = await asyncio.create_subprocess_exec(
            executable, "-p", profile or settings.hermes_profile, "-m", settings.hermes_model, "chat", "-q", prompt,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, env=environment,
        )
        output, _ = await asyncio.wait_for(process.communicate(), timeout=settings.hermes_timeout)
    except TimeoutError:
        if process and process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.communicate(), timeout=5)
            except TimeoutError:
                process.kill()
                await process.communicate()
        return {"tool": tool_name, "status": "timeout", "tools": [], "message": f"Hermes {tool_name} timed out."}
    except OSError as exc:
        return {"tool": tool_name, "status": "failed", "tools": [], "message": str(exc)}

    text = output.decode("utf-8", errors="replace")
    tools = re.findall(r"mcp__nara__(search_api_docs|get_api_detail|derive_relations|compose_service_plan)", text)
    exact_tool_call = tools.count(tool_name) == 1 and all(tool == tool_name for tool in tools)
    # Hermes' OpenAI provider renders an MCP invocation as `mcp__nara <args>`
    # (without the concrete tool suffix), while the local provider includes it.
    # The bounded prompt allows exactly one Nara tool, so this is sufficient to
    # treat the abbreviated trace as a confirmed invocation.
    abbreviated_nara_call = not tools and "mcp__nara" in text and "Unknown tool" not in text
    called_once = exact_tool_call or abbreviated_nara_call
    return {
        "tool": tool_name,
        "status": "called" if called_once else "failed",
        "tools": tools,
        "verification": "exact-tool-name" if exact_tool_call else "bounded-nara-trace" if abbreviated_nara_call else "none",
        "exit_code": process.returncode,
        "message": None if called_once else f"Hermes did not call only {tool_name} once.",
    }


@dataclass
class _Run:
    run_id: str
    request: AgentRunRequest
    status: str = "queued"
    events: list[AgentEvent] = field(default_factory=list)
    result: DesignResponse | None = None
    hermes: dict[str, Any] = field(default_factory=dict)
    critic: CriticReport | None = None
    error: str | None = None
    done: asyncio.Event = field(default_factory=asyncio.Event)
    changed: asyncio.Event = field(default_factory=asyncio.Event)
    task: asyncio.Task[None] | None = None


class AgentRunManager:
    """Read-only execution policy: one search, <=3 details, one relation, one plan."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._runs: dict[str, _Run] = {}

    async def create(self, request: AgentRunRequest) -> AgentRunResponse:
        run = _Run(run_id=uuid.uuid4().hex, request=request)
        self._runs[run.run_id] = run
        self._emit(run, "queued", "queued", "에이전트 실행을 준비하고 있습니다.")
        run.task = asyncio.create_task(self._execute(run), name=f"nara-agent-{run.run_id}")
        return self.snapshot(run.run_id)

    def snapshot(self, run_id: str) -> AgentRunResponse:
        run = self._runs.get(run_id)
        if not run:
            raise KeyError(run_id)
        return AgentRunResponse(run_id=run.run_id, status=run.status, query=run.request.query, events=run.events,
                                result=run.result, hermes=run.hermes, critic=run.critic, error=run.error)

    async def stop(self, run_id: str) -> AgentRunResponse:
        run = self._runs.get(run_id)
        if not run:
            raise KeyError(run_id)
        if run.task and not run.task.done():
            run.task.cancel()
        return self.snapshot(run_id)

    async def stream(self, run_id: str, after: int = 0) -> AsyncIterator[AgentEvent]:
        run = self._runs.get(run_id)
        if not run:
            raise KeyError(run_id)
        next_sequence = after + 1
        while True:
            for event in [item for item in run.events if item.sequence >= next_sequence]:
                next_sequence = event.sequence + 1
                yield event
            if run.done.is_set():
                return
            run.changed.clear()
            await run.changed.wait()

    async def _execute(self, run: _Run) -> None:
        run.status = "running"
        run.hermes = {"status": "running", "calls": []}
        self._emit(run, "agent", "running", "Hermes 도구 루프를 시작합니다.")
        try:
            run.result = await self._run_loop(run)
            calls = run.hermes["calls"]
            run.hermes["status"] = "called" if calls and all(call["status"] == "called" for call in calls) else "partial"
            failed = [call["tool"] for call in calls if call["status"] != "called"]
            if failed:
                run.result.warnings.append("Hermes 호출을 확인하지 못한 도구: " + ", ".join(failed))
            await self._run_critic(run)
            run.status = "completed"
            self._emit(run, "completed", "completed", "구조화된 서비스 계획 결과를 준비했습니다.")
        except asyncio.CancelledError:
            run.status = "cancelled"
            self._emit(run, "cancelled", "cancelled", "사용자가 실행을 중단했습니다.")
            raise
        except Exception as exc:
            run.status = "failed"
            run.error = str(exc)
            self._emit(run, "failed", "failed", str(exc))
        finally:
            run.done.set()
            run.changed.set()

    async def _run_loop(self, run: _Run) -> DesignResponse:
        request = run.request
        stages: list[StageRecord] = []
        warnings: list[str] = []
        async with NaraClient(self.settings) as client:
            self._stage(run, stages, "search", "running", "Hermes가 API 검색 도구를 호출하고 있습니다.")
            await self._call_hermes(run, "search", "search_api_docs", f"query는 {request.query!r}다.")
            search = await client.search(request.query, top_k=request.top_k, use_vector=request.use_vector)
            results = search.get("results") or []
            self._stage(run, stages, "search", "completed", f"검색 결과 {len(results)}개를 확인했습니다.")

            selected = self._select_ids(request.selected_service_ids, results)
            if not selected:
                for name, message in [("detail", "선택할 API 문서가 없습니다."), ("relations", "분석할 API 문서가 없습니다."), ("compose", "계획을 만들 API 문서가 없습니다.")]:
                    self._stage(run, stages, name, "skipped", message)
                warnings.append("검색 결과가 없어 서비스 계획을 만들지 않았습니다.")
                return DesignResponse(query=request.query, selected_service_ids=[], search=search, details=[], stages=stages, warnings=warnings)

            self._stage(run, stages, "detail", "running", "선택한 API 문서의 상세를 확인하고 있습니다.")
            for service_id in selected:
                await self._call_hermes(run, "detail", "get_api_detail", f"service_id는 {service_id!r}다.")
            details = await asyncio.gather(*(client.detail(service_id) for service_id in selected))
            self._stage(run, stages, "detail", "completed", f"선택 문서 {len(details)}개의 상세를 확인했습니다.")

            relations: dict[str, Any] | None = None
            if len(selected) >= 2:
                self._stage(run, stages, "relations", "running", "API 간 관계 근거를 분석하고 있습니다.")
                await self._call_hermes(run, "relations", "derive_relations", f"service_ids는 {selected!r}다.")
                relations = await client.relations(selected)
                self._stage(run, stages, "relations", "completed", f"문서 관계 {len(relations.get('relations') or [])}개를 확인했습니다.")
            else:
                self._stage(run, stages, "relations", "skipped", "문서가 한 개여서 관계 분석을 생략했습니다.")

            plan: dict[str, Any] | None = None
            if request.compose:
                self._stage(run, stages, "compose", "running", "읽기 전용 서비스 계획 초안을 만들고 있습니다.")
                await self._call_hermes(run, "compose", "compose_service_plan", f"service_ids는 {selected!r}, question은 {request.query!r}다.")
                try:
                    plan = await client.compose(selected, request.query)
                    self._stage(run, stages, "compose", "completed", "서비스 계획 초안을 만들었습니다.")
                except NaraServiceError as exc:
                    self._stage(run, stages, "compose", "failed", "계획 생성에 실패했지만 문서 분석 결과는 유지합니다.")
                    warnings.append(str(exc))
            else:
                self._stage(run, stages, "compose", "skipped", "요청에 따라 계획 생성을 생략했습니다.")
            return DesignResponse(query=request.query, selected_service_ids=selected, search=search, details=details,
                                  relations=relations, plan=plan, stages=stages, warnings=warnings)

    async def _run_critic(self, run: _Run) -> None:
        """Verify the finished result read-only; never fail the run (fail-soft)."""
        if self.settings.critic_mode == "disabled" or run.result is None:
            return
        self._emit(run, "critic", "running", "결과의 근거 계약을 재검증하고 있습니다.")
        run.critic = await run_critic(
            run.result, run.request.selected_service_ids, self.settings,
            client_factory=lambda: NaraClient(self.settings),
            probe=run_hermes_tool_probe,
        )
        issues = sum(1 for f in run.critic.findings if f.severity != "info")
        messages = {
            "pass": "근거 검증을 통과했습니다.",
            "evidence_gap": f"근거 부족 {issues}건을 확인했습니다.",
            "contradiction": f"근거 모순 {issues}건을 확인했습니다.",
            "failed": "검증을 완료하지 못했습니다 (결과는 유효합니다).",
        }
        status = "failed" if run.critic.verdict == "failed" else "completed"
        message = messages.get(run.critic.verdict, run.critic.verdict)
        if run.critic.verdict == "failed":
            run.result.warnings.append("계획 검증을 완료하지 못했습니다 (결과는 유효합니다).")
        run.result.stages.append(StageRecord(name="critic", status=status, message=message))
        self._emit(run, "critic", status, message)

    async def _call_hermes(self, run: _Run, stage: str, tool_name: str, instruction: str) -> None:
        call = await run_hermes_tool_probe(tool_name, instruction, self.settings)
        run.hermes["calls"].append(call)
        status = "completed" if call["status"] == "called" else "failed"
        message = f"Hermes {tool_name} 호출을 확인했습니다." if status == "completed" else call.get("message", "Hermes 호출을 확인하지 못했습니다.")
        self._emit(run, stage, status, message)

    def _stage(self, run: _Run, stages: list[StageRecord], name: str, status: str, message: str) -> None:
        stages.append(StageRecord(name=name, status=status, message=message))
        self._emit(run, name, status, message)

    @staticmethod
    def _select_ids(requested: list[str], results: list[dict[str, Any]]) -> list[str]:
        candidates = requested or [str(item.get("service_id", "")).strip() for item in results[:3]]
        selected: list[str] = []
        for service_id in candidates:
            if service_id and service_id not in selected:
                selected.append(service_id)
        return selected[:3]

    @staticmethod
    def _emit(run: _Run, name: str, status: str, message: str) -> None:
        run.events.append(AgentEvent(sequence=len(run.events) + 1, name=name, status=status, message=message))
        run.changed.set()


__all__ = ["AgentRunManager", "run_hermes_tool_probe"]
