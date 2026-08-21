"""Bounded Hermes MCP loop with normalized, browser-friendly progress events."""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any

from .config import Settings, get_settings
from .critic import run_critic
from .freshness import check_document_freshness
from .hermes_client import HermesGatewayClient, HermesGatewayError, HermesRunResult
from .nara_client import NaraClient
from .result_materializer import (
    materialize_design_result,
    normalize_tool_name,
    tool_event_stage,
)
from .schemas import (
    AgentEvent,
    AgentRunRequest,
    AgentRunResponse,
    CriticReport,
    DesignResponse,
    DocumentFreshness,
    StageRecord,
)

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


def _request_text(request: AgentRunRequest) -> str:
    return json.dumps({
        "query": request.query, "top_k": request.top_k,
        "use_vector": request.use_vector,
        "selected_service_ids": request.selected_service_ids,
        "compose": request.compose,
    }, ensure_ascii=False)


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
MAX_RETAINED_AGENT_RUNS = 20


class AgentRunManager:
    """Own application runs backed one-to-one by Hermes Gateway runs."""

    def __init__(self, settings: Settings | None = None,
                 gateway_factory: GatewayFactory = HermesGatewayClient,
                 max_retained_runs: int = MAX_RETAINED_AGENT_RUNS):
        self.settings = settings or get_settings()
        self.gateway_factory = gateway_factory
        self._runs: dict[str, _Run] = {}
        self._max_retained_runs = max(1, int(max_retained_runs))

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
            run.changed.clear()
            for event in [item for item in run.events if item.sequence >= next_sequence]:
                next_sequence = event.sequence + 1
                yield event
            if run.done.is_set():
                return
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
            self._prune_terminal_runs()

    def _prune_terminal_runs(self) -> None:
        terminal_ids = [
            run_id
            for run_id, run in self._runs.items()
            if run.done.is_set()
            and run.status in {"completed", "failed", "cancelled"}
        ]
        for run_id in terminal_ids[: -self._max_retained_runs]:
            self._runs.pop(run_id, None)

    def _apply_hermes_result(self, run: _Run, result: HermesRunResult) -> None:
        run.hermes.update({
            "status": result.status,
            "run_id": result.run_id,
            "session_id": result.session_id,
            "usage": result.usage,
            "tool_calls": [normalize_tool_name(item) for item in result.tool_calls],
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
        stage = tool_event_stage(event)
        if stage is None:
            return
        self._emit(run, stage.name, stage.status, stage.message)

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
    "MAX_RETAINED_AGENT_RUNS",
    "HERMES_INSTRUCTIONS_TEMPLATE",
    "build_instructions",
]
