from __future__ import annotations

import asyncio
import json

import pytest

from app.agent import AgentRunManager, parse_design_result
from app.config import Settings
from app.hermes_client import HermesRunResult
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
        tools = ["search_api_docs", "get_api_detail", "get_api_detail", "derive_relations", "compose_service_plan"]
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


async def run_manager(monkeypatch, settings, client_factory=None, output=None):
    factory = client_factory or (lambda _: FakeNaraClient())
    monkeypatch.setattr("app.agent.NaraClient", factory)
    FakeGateway.output = output or gateway_output()
    manager = AgentRunManager(settings, gateway_factory=FakeGateway)
    created = await manager.create(AgentRunRequest(query="미세먼지 알림 서비스"))
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
            "derive_relations",
            "compose_service_plan",
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
    def factory(_):
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
    async def scenario():
        plan = {
            "service_ids": ["openapi_new:1", "openapi_new:2"],
            "suggestion": "검토용 계획 초안",
            "warning": "일부 문서를 찾지 못해 나머지로 진행했습니다.",
            "missing": ["openapi_new:9"],
        }
        completed = await run_manager(
            monkeypatch,
            Settings(critic_mode="deterministic"),
            output=gateway_output(plan),
        )
        warnings = completed.result.warnings
        assert any("일부 문서를 찾지 못해" in warning for warning in warnings)
        assert any("openapi_new:9" in warning for warning in warnings)
        # 경고를 빠뜨리면 critic이 plan-missing-reported 위반으로 자기 결과를 깎는다.
        assert completed.critic.verdict == "pass"

    asyncio.run(scenario())


def test_gateway_result_must_be_plain_json():
    request = AgentRunRequest(query="미세먼지 알림 서비스")
    with pytest.raises(ValueError, match="JSON 객체"):
        parse_design_result(f"```json\n{gateway_output()}\n```", request)


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
