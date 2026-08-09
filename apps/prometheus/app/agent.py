"""Bounded Hermes MCP loop with normalized, browser-friendly progress events."""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from .config import Settings, get_settings
from .critic import run_critic
from .freshness import check_document_freshness
from .hermes_client import HermesGatewayClient, HermesGatewayError, HermesRunResult
from .nara_client import NaraClient
from .schemas import (
    AgentEvent,
    AgentRunRequest,
    AgentRunResponse,
    CriticReport,
    DesignResponse,
    DocumentFreshness,
    StageRecord,
)

NARA_TOOLS = {
    "search_api_docs", "get_api_detail", "derive_relations",
    "compose_service_plan", "check_doc_freshness",
}
TOOL_STAGES = {
    "search_api_docs": "search", "get_api_detail": "detail",
    "derive_relations": "relations", "compose_service_plan": "compose",
    "check_doc_freshness": "freshness",
}

HERMES_INSTRUCTIONS = """Nara 공공 API 설계 도우미다.
nara MCP의 읽기 전용 도구만 사용한다. 검색 결과의 상세를 확인해 최대 3개를 고르고,
2개 이상이면 관계를 확인한다. compose=true일 때만 계획을 만든다. 외부 작업을 했다고
주장하지 않는다. 최종 출력은 Markdown 없이 다음 키를 모두 가진 JSON 객체 하나다:
query, selected_service_ids, search, details, relations, plan, warnings."""


def _tool_name(raw: object) -> str:
    value = str(raw or "")
    for name in NARA_TOOLS:
        if value == name or value.endswith(f"__{name}"):
            return name
    return value


def _extract_json_object(text: str) -> dict[str, Any]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("Hermes 최종 응답이 JSON 객체가 아닙니다.") from exc
    if not isinstance(payload, dict):
        raise ValueError("Hermes 최종 응답이 JSON 객체가 아닙니다.")
    return payload


def _request_text(request: AgentRunRequest) -> str:
    return json.dumps({
        "query": request.query, "top_k": request.top_k,
        "use_vector": request.use_vector,
        "selected_service_ids": request.selected_service_ids,
        "compose": request.compose,
    }, ensure_ascii=False)


def _canonical_stages(payload: dict[str, Any], compose: bool) -> list[StageRecord]:
    selected = payload.get("selected_service_ids") or []
    details = payload.get("details") or []
    relations = payload.get("relations")
    plan = payload.get("plan")
    return [
        StageRecord(name="search", status="completed", message="Hermes가 검색 결과를 검토했습니다."),
        StageRecord(name="detail", status="completed" if selected and details else "skipped",
                    message=f"선택 문서 {len(details)}개의 상세를 검토했습니다." if details else "선택된 문서가 없습니다."),
        StageRecord(name="relations", status="completed" if relations is not None else "skipped",
                    message="문서 관계 근거를 확인했습니다." if relations is not None else "관계 분석을 생략했습니다."),
        StageRecord(name="compose", status="completed" if plan is not None else "skipped",
                    message="서비스 계획 초안을 만들었습니다." if plan is not None else ("계획을 만들 근거가 없습니다." if compose else "요청에 따라 계획 생성을 생략했습니다.")),
    ]


def parse_design_result(output: str, request: AgentRunRequest) -> DesignResponse:
    payload = _extract_json_object(output)
    payload["query"] = request.query
    payload["stages"] = _canonical_stages(payload, request.compose)
    selected = payload.get("selected_service_ids")
    if (
        not isinstance(selected, list)
        or not all(isinstance(value, str) and value.strip() for value in selected)
        or len(selected) > 3
        or len(set(selected)) != len(selected)
    ):
        raise ValueError("Hermes 결과의 selected_service_ids는 중복 없는 최대 3개 배열이어야 합니다.")
    if not request.compose and payload.get("plan") is not None:
        raise ValueError("compose=false 요청에서 Hermes가 계획을 생성했습니다.")
    try:
        result = DesignResponse.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"Hermes 결과가 DesignResponse 계약과 맞지 않습니다: {exc}") from exc
    if result.plan:
        if result.plan.get("warning"):
            result.warnings.append(str(result.plan["warning"]))
        for item in [str(value) for value in result.plan.get("missing") or []]:
            if not any(item in warning for warning in result.warnings):
                result.warnings.append(f"조합기에서 찾지 못한 문서: {item}")
    return result


@dataclass
class _Run:
    run_id: str
    request: AgentRunRequest
    status: str = "queued"
    events: list[AgentEvent] = field(default_factory=list)
    result: DesignResponse | None = None
    hermes: dict[str, Any] = field(default_factory=dict)
    critic: CriticReport | None = None
    freshness: list[DocumentFreshness] = field(default_factory=list)
    error: str | None = None
    done: asyncio.Event = field(default_factory=asyncio.Event)
    changed: asyncio.Event = field(default_factory=asyncio.Event)
    task: asyncio.Task[None] | None = None


GatewayFactory = Callable[[Settings], HermesGatewayClient]


class AgentRunManager:
    """Own application runs backed one-to-one by Hermes Gateway runs."""

    def __init__(self, settings: Settings | None = None,
                 gateway_factory: GatewayFactory = HermesGatewayClient):
        self.settings = settings or get_settings()
        self.gateway_factory = gateway_factory
        self._runs: dict[str, _Run] = {}

    async def create(self, request: AgentRunRequest) -> AgentRunResponse:
        run = _Run(run_id=uuid.uuid4().hex, request=request)
        self._runs[run.run_id] = run
        self._emit(run, "queued", "queued", "Hermes Gateway run을 준비하고 있습니다.")
        run.task = asyncio.create_task(self._execute(run), name=f"nara-agent-{run.run_id}")
        return self.snapshot(run.run_id)

    def snapshot(self, run_id: str) -> AgentRunResponse:
        run = self._runs.get(run_id)
        if not run:
            raise KeyError(run_id)
        return AgentRunResponse(run_id=run.run_id, status=run.status, query=run.request.query, events=run.events,
                                result=run.result, hermes=run.hermes, critic=run.critic, freshness=run.freshness, error=run.error)

    async def stop(self, run_id: str) -> AgentRunResponse:
        run = self._runs.get(run_id)
        if not run:
            raise KeyError(run_id)
        hermes_run_id = run.hermes.get("run_id")
        if hermes_run_id and run.status in {"queued", "running"}:
            async with self.gateway_factory(self.settings) as gateway:
                await gateway.stop(str(hermes_run_id))
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
        run.hermes = {
            "status": "connecting",
            "transport": "gateway-runs-api",
            "model": self.settings.hermes_model,
            "tool_calls": [],
        }
        self._emit(run, "agent", "running", "Hermes Gateway에 오케스트레이션을 요청합니다.")
        try:
            async with self.gateway_factory(self.settings) as gateway:
                hermes_run_id = await gateway.create_run(
                    _request_text(run.request), HERMES_INSTRUCTIONS, f"nara-{run.run_id}"
                )
                run.hermes.update({"status": "running", "run_id": hermes_run_id})
                hermes_result = await gateway.wait(
                    hermes_run_id, on_event=lambda event: self._on_hermes_event(run, event)
                )
            self._apply_hermes_result(run, hermes_result)
            run.result = parse_design_result(hermes_result.output, run.request)
            await self._run_freshness(run)
            await self._run_critic(run)
            run.status = "completed"
            self._emit(run, "completed", "completed", "근거가 검증된 서비스 계획 결과를 준비했습니다.")
        except asyncio.CancelledError:
            run.status = "cancelled"
            run.hermes["status"] = "cancelled"
            self._emit(run, "cancelled", "cancelled", "사용자가 실행을 중단했습니다.")
        except (HermesGatewayError, ValueError) as exc:
            run.status = "failed"
            run.hermes["status"] = "failed"
            run.error = str(exc)
            self._emit(run, "failed", "failed", str(exc))
        except Exception as exc:
            run.status = "failed"
            run.error = str(exc)
            self._emit(run, "failed", "failed", str(exc))
        finally:
            run.done.set()
            run.changed.set()

    def _apply_hermes_result(self, run: _Run, result: HermesRunResult) -> None:
        run.hermes.update({
            "status": result.status,
            "run_id": result.run_id,
            "session_id": result.session_id,
            "usage": result.usage,
            "tool_calls": [_tool_name(item) for item in result.tool_calls],
        })

    async def _on_hermes_event(self, run: _Run, event: dict[str, Any]) -> None:
        event_name = event.get("event")
        if event_name not in {"tool.started", "tool.completed"}:
            return
        tool = _tool_name(event.get("tool"))
        if tool not in TOOL_STAGES:
            return
        stage = TOOL_STAGES[tool]
        status = "running" if event_name == "tool.started" else ("failed" if event.get("error") else "completed")
        action = "호출하고 있습니다" if status == "running" else "완료했습니다"
        self._emit(run, stage, status, f"Hermes가 {tool} 도구를 {action}.")

    async def _run_freshness(self, run: _Run) -> None:
        """Compare selected documents with crawler manifests without refreshing data."""
        if self.settings.freshness_mode == "disabled" or run.result is None:
            return
        self._emit(run, "freshness", "running", "문서 최신성 근거를 확인하고 있습니다.")
        try:
            run.freshness = await asyncio.to_thread(
                check_document_freshness,
                run.result.selected_service_ids,
                self.settings.storage_dir,
                self.settings.index_built_at,
            )
            issues = [item for item in run.freshness if item.status != "fresh"]
            for item in issues:
                run.result.warnings.append(f"문서 최신성({item.service_id}): {item.message}")
            message = "선택 문서의 최신성 근거를 확인했습니다." if not issues else f"문서 최신성 확인 불가 또는 변경 감지 {len(issues)}건이 있습니다."
            self._emit(run, "freshness", "completed", message)
        except Exception as exc:
            run.result.warnings.append(f"문서 최신성 검증을 완료하지 못했습니다: {exc}")
            self._emit(run, "freshness", "failed", "문서 최신성 검증에 실패했지만 결과는 유지합니다.")

    async def _run_critic(self, run: _Run) -> None:
        """Verify the finished result read-only; never fail the run (fail-soft)."""
        if self.settings.critic_mode == "disabled" or run.result is None:
            return
        self._emit(run, "critic", "running", "결과의 근거 계약을 재검증하고 있습니다.")
        run.critic = await run_critic(
            run.result, run.request.selected_service_ids, self.settings,
            client_factory=lambda: NaraClient(self.settings),
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

    @staticmethod
    def _emit(run: _Run, name: str, status: str, message: str) -> None:
        run.events.append(AgentEvent(sequence=len(run.events) + 1, name=name, status=status, message=message))
        run.changed.set()


__all__ = ["AgentRunManager", "HERMES_INSTRUCTIONS", "parse_design_result"]
