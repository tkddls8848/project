from __future__ import annotations

import asyncio
import json

from app.agent import AgentRunManager, materialize_design_result
from app.config import Settings
from app.hermes_client import HermesRunResult
from app.nara_client import NaraServiceError
from app.schemas import AgentRunRequest


class FakeNaraClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    async def search(self, query, top_k=5, use_vector=True):
        return {
            "query": query,
            "results": [
                {"service_id": "openapi_new:1", "name": "문서 1"},
                {"service_id": "openapi_new:2", "name": "문서 2"},
            ],
            "diagnostics": {"fusion": "rrf"},
        }

    async def detail(self, service_id):
        return {"service_id": service_id, "name": service_id}

    async def relations(self, service_ids):
        return {"relations": [{"source": service_ids[0], "target": service_ids[1]}]}

    async def compose(self, service_ids, question):
        return {"service_ids": service_ids, "suggestion": "검토용 계획 초안"}


def gateway_output(plan=None):
    return json.dumps({
        "query": "미세먼지 알림 서비스",
        "selected_service_ids": ["openapi_new:1", "openapi_new:2"],
        "search": {
            "query": "미세먼지 알림 서비스",
            "results": [
                {"service_id": "openapi_new:1", "name": "문서 1"},
                {"service_id": "openapi_new:2", "name": "문서 2"},
            ],
        },
        "details": [
            {"service_id": "openapi_new:1", "name": "문서 1"},
            {"service_id": "openapi_new:2", "name": "문서 2"},
        ],
        "relations": {"relations": [{"source": "openapi_new:1", "target": "openapi_new:2"}]},
        "plan": plan or {"service_ids": ["openapi_new:1", "openapi_new:2"], "suggestion": "검토용 계획 초안"},
        "warnings": [],
    }, ensure_ascii=False)


class FakeGateway:
    output = gateway_output()
    stopped: list[str] = []

    def __init__(self, _settings):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    async def create_run(self, _input, _instructions, _session_id):
        return "run_gateway_1"

    async def wait(self, run_id, on_event=None):
        tools = ["search_api_docs", "get_api_detail", "get_api_detail"]
        for tool in tools:
            if on_event:
                await on_event({"event": "tool.started", "tool": f"mcp__nara__{tool}"})
                await on_event({"event": "tool.completed", "tool": f"mcp__nara__{tool}", "error": False})
        return HermesRunResult(
            run_id=run_id, status="completed", output=self.output,
            session_id="session-1", usage={"total_tokens": 321}, tool_calls=tools,
        )

    async def stop(self, run_id):
        self.stopped.append(run_id)


async def run_manager(
    monkeypatch, settings, client_factory=None, output=None, request=None, gateway=None
):
    factory = client_factory or (lambda _: FakeNaraClient())
    monkeypatch.setattr("app.agent.NaraClient", factory)
    FakeGateway.output = output or gateway_output()
    manager = AgentRunManager(settings, gateway_factory=gateway or FakeGateway)
    created = await manager.create(
        request or AgentRunRequest(query="미세먼지 알림 서비스")
    )
    await manager._runs[created.run_id].task
    return manager.snapshot(created.run_id)


def test_agent_run_emits_live_stages_and_normalizes_result(monkeypatch):
    async def scenario():
        completed = await run_manager(monkeypatch, Settings(critic_mode="disabled"))
        assert completed.status == "completed"
        assert completed.hermes["status"] == "completed"
        assert completed.hermes["transport"] == "gateway-runs-api"
        assert completed.hermes["tool_calls"] == [
            "search_api_docs",
            "get_api_detail",
            "get_api_detail",
        ]
        assert completed.result is not None
        assert completed.result.selected_service_ids == ["openapi_new:1", "openapi_new:2"]
        assert any(event.name == "relations" and event.status == "completed" for event in completed.events)
        assert completed.events[-1].name == "completed"

    asyncio.run(scenario())


def test_deterministic_critic_verifies_the_result_after_the_loop(monkeypatch):
    async def scenario():
        completed = await run_manager(
            monkeypatch, Settings(critic_mode="deterministic")
        )
        assert completed.status == "completed"
        assert completed.critic is not None
        assert completed.critic.verdict == "pass"
        assert completed.critic.deterministic
        assert completed.result.stages[-1].name == "critic"
        assert any(event.name == "critic" and event.status == "completed" for event in completed.events)

    asyncio.run(scenario())


def test_disabled_critic_leaves_no_report_and_no_events(monkeypatch):
    async def scenario():
        completed = await run_manager(
            monkeypatch, Settings(critic_mode="disabled")
        )
        assert completed.status == "completed"
        assert completed.critic is None
        assert not any(event.name == "critic" for event in completed.events)
        assert not any(stage.name == "critic" for stage in completed.result.stages)

    asyncio.run(scenario())


def test_critic_failure_keeps_the_run_completed(monkeypatch):
    calls = 0

    def factory(_):
        nonlocal calls
        calls += 1
        if calls == 1:
            return FakeNaraClient()
        raise RuntimeError("critic client unavailable")

    async def scenario():
        completed = await run_manager(
            monkeypatch,
            Settings(critic_mode="deterministic"),
            client_factory=factory,
        )
        assert completed.status == "completed"
        assert completed.critic is not None
        assert completed.critic.verdict == "failed"
        assert any("계획 검증을 완료하지 못했습니다" in warning for warning in completed.result.warnings)

    asyncio.run(scenario())


def test_combiner_missing_documents_are_reported_and_pass_the_critic(monkeypatch):
    class MissingPlanClient(FakeNaraClient):
        async def compose(self, service_ids, question):
            return {
                "service_ids": service_ids,
                "suggestion": "검토용 계획 초안",
                "warning": "일부 문서를 찾지 못해 나머지로 진행했습니다.",
                "missing": ["openapi_new:9"],
            }

    async def scenario():
        completed = await run_manager(
            monkeypatch,
            Settings(critic_mode="deterministic"),
            client_factory=lambda _: MissingPlanClient(),
        )
        warnings = completed.result.warnings
        assert any("일부 문서를 찾지 못해" in warning for warning in warnings)
        assert any("openapi_new:9" in warning for warning in warnings)
        # 경고를 빠뜨리면 critic이 plan-missing-reported 위반으로 자기 결과를 깎는다.
        assert completed.critic.verdict == "pass"

    asyncio.run(scenario())


def test_markdown_gateway_output_is_rehydrated_from_nara_services():
    async def scenario():
        output = """### 검토 결과
선택 문서는 `openapi_new:2`입니다. 전체 결과는 Orchestrator가 확인하세요.
"""
        result = await materialize_design_result(
            output,
            AgentRunRequest(query="미세먼지 알림 서비스"),
            FakeNaraClient(),
        )
        assert result.selected_service_ids == ["openapi_new:2"]
        assert result.details == [{"service_id": "openapi_new:2", "name": "openapi_new:2"}]
        assert result.plan["suggestion"] == "검토용 계획 초안"

    asyncio.run(scenario())


def test_agent_run_does_not_require_json_gateway_output(monkeypatch):
    async def scenario():
        completed = await run_manager(
            monkeypatch,
            Settings(critic_mode="disabled"),
            output="문서 검토 결과 `openapi_new:2`를 선택했습니다.",
        )
        assert completed.status == "completed"
        assert completed.result.selected_service_ids == ["openapi_new:2"]
        assert completed.hermes["result_mode"] == "deterministic-nara-rehydration"

    asyncio.run(scenario())


def test_unavailable_gateway_selection_is_removed_by_detail_verification():
    class MissingDetailClient(FakeNaraClient):
        async def detail(self, service_id):
            if service_id == "openapi_new:999":
                raise NaraServiceError("nara-search", "service_id not found", 404)
            return await super().detail(service_id)

    async def scenario():
        result = await materialize_design_result(
            "존재하지 않는 openapi_new:999를 선택했습니다.",
            AgentRunRequest(query="미세먼지 알림 서비스"),
            MissingDetailClient(),
        )
        assert result.selected_service_ids == []
        assert any("상세 문서를 확인하지 못해 제외" in warning for warning in result.warnings)

    asyncio.run(scenario())


def test_preselected_documents_skip_the_hermes_run(monkeypatch):
    class UnusableGateway(FakeGateway):
        async def create_run(self, _input, _instructions, _session_id):
            raise AssertionError("선택 ID가 있으면 Hermes run을 만들면 안 됩니다.")

    async def scenario():
        completed = await run_manager(
            monkeypatch,
            Settings(critic_mode="disabled"),
            request=AgentRunRequest(
                query="미세먼지 알림 서비스",
                selected_service_ids=["openapi_new:1", "openapi_new:2"],
            ),
            gateway=UnusableGateway,
        )
        assert completed.status == "completed"
        assert completed.hermes["status"] == "skipped"
        assert completed.hermes["skip_reason"] == "request-selected-service-ids"
        assert "run_id" not in completed.hermes
        assert completed.hermes["tool_calls"] == []
        assert completed.result.selected_service_ids == ["openapi_new:1", "openapi_new:2"]
        assert any(event.name == "agent" and event.status == "skipped" for event in completed.events)
        # Hermes를 부르지 않았으므로 검토했다고 주장하지 않는다.
        search_stage = next(stage for stage in completed.result.stages if stage.name == "search")
        assert "Hermes" not in search_stage.message

    asyncio.run(scenario())


def test_freshness_metadata_gap_is_reported_without_failing_run(monkeypatch):
    async def scenario():
        completed = await run_manager(
            monkeypatch,
            Settings(
                critic_mode="disabled",
                freshness_mode="deterministic",
                index_built_at="",
            ),
        )
        assert completed.status == "completed"
        assert [item.status for item in completed.freshness] == ["unverified", "unverified"]
        assert any(event.name == "freshness" and event.status == "completed" for event in completed.events)
        assert any("문서 최신성" in warning for warning in completed.result.warnings)

    asyncio.run(scenario())
