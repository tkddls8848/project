"""Bounded Hermes MCP loop with normalized, browser-friendly progress events."""

from __future__ import annotations

import asyncio
import json
import re
import uuid
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any

from .config import Settings, get_settings
from .critic import run_critic
from .freshness import check_document_freshness
from .hermes_client import HermesGatewayClient, HermesGatewayError, HermesRunResult
from .nara_client import NaraClient, NaraServiceError
from .schemas import (
    AgentEvent,
    AgentRunRequest,
    AgentRunResponse,
    CriticReport,
    DesignResponse,
    DocumentFreshness,
    StageRecord,
)

TOOL_STAGES = {"search_api_docs": "search", "get_api_detail": "detail"}

# The single authority for loop behaviour. It is sent with every run, so unlike
# a skill directory its delivery is not left to the model's discretion.
HERMES_INSTRUCTIONS_TEMPLATE = """Nara 공공 API 설계 도우미다. 역할은 service_id 선택 하나다.

도구는 nara MCP의 search_api_docs와 get_api_detail만 사용한다. 도구 호출은 총
{max_tool_calls}회로 제한되며(검색 1회 + 상세 {detail_budget}회) 초과하면 run이 중단되어 결과를
얻지 못한다. 질의를 미리 다듬어 재검색을 피한다.

검색을 실행하고 상위 후보에 get_api_detail을 호출해 엔드포인트와 필드명을 확인한 뒤,
근거가 충분한 문서만 최대 3개 고른다. 벡터 점수만 보고 선택하지 않으며 상세를
확인하지 않은 문서는 고르지 않는다.

검색 결과에 없는 API나 필드를 만들어내지 않는다. 찾지 못한 문서를 임의의 대체 문서로
바꾸지 않는다. 도구 결과는 선택용 요약이므로 truncated가 true인 목록을 문서 전체로
말하지 않는다. 관계나 계획을 추측하거나 실제 행정 처리·외부 작업을 했다고 주장하지 않는다.

최종 응답에는 선택한 service_id를 정확히 포함하고 선택 이유만 간결하게 설명한다.
응답 형식은 자유이며, 관계·계획·최종 데이터 계약은 Orchestrator가 Nara 원본에서 구성한다."""


def build_instructions(max_tool_calls: int) -> str:
    """Render the run instructions against the cap the client actually enforces."""
    return HERMES_INSTRUCTIONS_TEMPLATE.format(
        max_tool_calls=max_tool_calls, detail_budget=max(max_tool_calls - 1, 0)
    )


SERVICE_ID_RE = re.compile(r"(?<![A-Za-z0-9._-])openapi_new:\d+(?!\d)")


def _tool_name(raw: object) -> str:
    value = str(raw or "")
    for name in TOOL_STAGES:
        if value == name or value.endswith(f"__{name}"):
            return name
    return value


def _request_text(request: AgentRunRequest) -> str:
    return json.dumps({
        "query": request.query, "top_k": request.top_k,
        "use_vector": request.use_vector,
        "selected_service_ids": request.selected_service_ids,
        "compose": request.compose,
    }, ensure_ascii=False)


def _unique_service_ids(values: list[object]) -> list[str]:
    unique: list[str] = []
    for raw in values:
        service_id = str(raw or "").strip()
        if service_id and service_id not in unique:
            unique.append(service_id)
    return unique


def _selected_ids_from_output(
    output: str, request: AgentRunRequest, search: dict[str, Any]
) -> tuple[list[str], bool]:
    """Use Hermes only as a selector, never as the final data authority."""
    requested = _unique_service_ids(list(request.selected_service_ids))[:3]
    if requested:
        return requested, False

    results = search.get("results") or []
    candidates = _unique_service_ids([
        row.get("service_id") for row in results if isinstance(row, dict)
    ])
    proposed = _unique_service_ids(SERVICE_ID_RE.findall(output or ""))
    if proposed:
        # Do not require a second search to reproduce Hermes' exact ranking.
        # Every proposed ID is still verified through the authoritative detail
        # endpoint below before it can enter the public result.
        return proposed[:3], False
    return candidates[:3], bool(candidates)


async def materialize_design_result(
    output: str,
    request: AgentRunRequest,
    client: NaraClient,
    observed_tools: list[str] | None = None,
) -> DesignResponse:
    """Build the public result deterministically from Nara service responses.

    Hermes output influences selection only. Search documents, details,
    relations and plan content are always re-fetched from their owning services.
    ``observed_tools`` carries the tool names the Gateway actually reported for
    this run, so stage messages describe the loop instead of assuming it.
    """
    search = await client.search(
        request.query, top_k=request.top_k, use_vector=request.use_vector
    )
    selected, used_fallback = _selected_ids_from_output(output, request, search)
    warnings: list[str] = []
    if used_fallback:
        warnings.append(
            "Hermes 선택 ID를 확인할 수 없어 현재 검색 결과 상위 문서를 사용했습니다."
        )

    details: list[dict[str, Any]] = []
    verified_ids: list[str] = []
    for service_id in selected:
        try:
            detail = await client.detail(service_id)
        except NaraServiceError as exc:
            warnings.append(f"상세 문서를 확인하지 못해 제외했습니다: {service_id} ({exc})")
            continue
        details.append(detail)
        verified_ids.append(service_id)

    relations: dict[str, Any] | None = None
    if len(verified_ids) >= 2:
        try:
            relations = await client.relations(verified_ids)
        except NaraServiceError as exc:
            warnings.append(f"문서 관계를 확인하지 못했습니다: {exc}")

    plan: dict[str, Any] | None = None
    if request.compose and verified_ids:
        try:
            plan = await client.compose(verified_ids, request.query)
        except NaraServiceError as exc:
            warnings.append(f"계획 초안을 생성하지 못했습니다: {exc}")

    payload: dict[str, Any] = {
        "query": request.query,
        "selected_service_ids": verified_ids,
        "search": search,
        "details": details,
        "relations": relations,
        "plan": plan,
        "warnings": warnings,
    }
    payload["stages"] = _canonical_stages(payload, request, observed_tools or [])
    result = DesignResponse.model_validate(payload)
    if result.plan:
        if result.plan.get("warning"):
            result.warnings.append(str(result.plan["warning"]))
        for item in [str(value) for value in result.plan.get("missing") or []]:
            if not any(item in warning for warning in result.warnings):
                result.warnings.append(f"조합기에서 찾지 못한 문서: {item}")
    return result


def _tool_use_note(observed_tools: list[str], tool: str) -> str:
    """Describe a Hermes tool only from Gateway-reported calls, never from output."""
    count = observed_tools.count(tool)
    return f"Hermes {tool} 호출 {count}회" if count else f"Hermes {tool} 호출 기록 없음"


def _canonical_stages(
    payload: dict[str, Any], request: AgentRunRequest, observed_tools: list[str]
) -> list[StageRecord]:
    selected = payload.get("selected_service_ids") or []
    details = payload.get("details") or []
    relations = payload.get("relations")
    plan = payload.get("plan")
    compose = request.compose
    # Every stage below is performed by the Orchestrator against Nara. Only the
    # parenthetical reports what the Hermes loop itself was observed to do.
    search_message = (
        "요청이 지정한 문서를 검색 결과에서 확인했습니다."
        if request.selected_service_ids
        else f"Orchestrator가 검색 결과를 조회했습니다 ({_tool_use_note(observed_tools, 'search_api_docs')})."
    )
    detail_message = (
        f"선택 문서 {len(details)}개의 상세를 Orchestrator가 조회했습니다 "
        f"({_tool_use_note(observed_tools, 'get_api_detail')})."
        if details
        else "선택된 문서가 없습니다."
    )
    return [
        StageRecord(name="search", status="completed", message=search_message),
        StageRecord(name="detail", status="completed" if selected and details else "skipped",
                    message=detail_message),
        StageRecord(name="relations", status="completed" if relations is not None else "skipped",
                    message="문서 관계 근거를 확인했습니다." if relations is not None else "관계 분석을 생략했습니다."),
        StageRecord(name="compose", status="completed" if plan is not None else "skipped",
                    message="서비스 계획 초안을 만들었습니다." if plan is not None else ("계획을 만들 근거가 없습니다." if compose else "요청에 따라 계획 생성을 생략했습니다.")),
    ]


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
        # Hermes is only a selector. When the request already names the
        # documents its output is discarded, so the run is never started.
        preselected = bool(run.request.selected_service_ids)
        run.hermes = {
            "status": "skipped" if preselected else "connecting",
            "transport": "gateway-runs-api",
            "model": self.settings.hermes_model,
            "tool_calls": [],
        }
        try:
            if preselected:
                run.hermes["skip_reason"] = "request-selected-service-ids"
                self._emit(run, "agent", "skipped",
                           "요청이 문서를 직접 지정해 Hermes 호출 없이 진행합니다.")
                hermes_output = ""
            else:
                self._emit(run, "agent", "running", "Hermes Gateway에 오케스트레이션을 요청합니다.")
                async with self.gateway_factory(self.settings) as gateway:
                    hermes_run_id = await gateway.create_run(
                        _request_text(run.request),
                        build_instructions(self.settings.hermes_max_tool_calls),
                        f"nara-{run.run_id}",
                    )
                    run.hermes.update({"status": "running", "run_id": hermes_run_id})
                    hermes_result = await gateway.wait(
                        hermes_run_id, on_event=lambda event: self._on_hermes_event(run, event)
                    )
                self._apply_hermes_result(run, hermes_result)
                hermes_output = hermes_result.output
            run.hermes["result_mode"] = "deterministic-nara-rehydration"
            observed_tools = [str(name) for name in run.hermes.get("tool_calls") or []]
            async with NaraClient(self.settings) as client:
                run.result = await materialize_design_result(
                    hermes_output, run.request, client, observed_tools
                )
            self._emit_materialized_stages(run)
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

    def _emit_materialized_stages(self, run: _Run) -> None:
        if run.result is None:
            return
        already_reported = {
            event.name
            for event in run.events
            if event.status in {"completed", "skipped"}
        }
        for stage in run.result.stages:
            if stage.name not in already_reported:
                self._emit(run, stage.name, stage.status, stage.message)

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

    async def _index_built_at(self) -> str:
        """Prefer the explicit setting, else ask Search when its index was built.

        Without this the default configuration leaves the timestamp empty and
        every freshness check reports 'unverified'.
        """
        if self.settings.index_built_at:
            return self.settings.index_built_at
        async with NaraClient(self.settings) as client:
            return await client.index_built_at()

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
                await self._index_built_at(),
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
            observed_tools=[str(name) for name in run.hermes.get("tool_calls") or []],
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


__all__ = [
    "AgentRunManager",
    "HERMES_INSTRUCTIONS_TEMPLATE",
    "build_instructions",
    "materialize_design_result",
]
