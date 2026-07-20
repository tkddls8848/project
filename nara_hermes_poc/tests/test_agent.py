from __future__ import annotations

import asyncio

from app.agent import AgentRunManager
from app.config import Settings
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


async def run_manager(monkeypatch, settings, client_factory=None):
    factory = client_factory or (lambda _: FakeNaraClient())
    monkeypatch.setattr("app.agent.NaraClient", factory)
    manager = AgentRunManager(settings)
    created = await manager.create(AgentRunRequest(query="미세먼지 알림 서비스"))
    await manager._runs[created.run_id].task
    return manager.snapshot(created.run_id)


def test_agent_run_emits_live_stages_and_normalizes_result(monkeypatch):
    async def scenario():
        completed = await run_manager(monkeypatch, Settings(hermes_probe_enabled=False))
        assert completed.status == "completed"
        assert completed.hermes["status"] == "partial"
        assert [call["tool"] for call in completed.hermes["calls"]] == [
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
            monkeypatch, Settings(hermes_probe_enabled=False, critic_mode="deterministic")
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
            monkeypatch, Settings(hermes_probe_enabled=False, critic_mode="disabled")
        )
        assert completed.status == "completed"
        assert completed.critic is None
        assert not any(event.name == "critic" for event in completed.events)
        assert not any(stage.name == "critic" for stage in completed.result.stages)

    asyncio.run(scenario())


def test_critic_failure_keeps_the_run_completed(monkeypatch):
    clients = []

    def factory(_):
        if clients:  # 첫 번째는 실행 루프, 두 번째(critic)부터 실패
            raise RuntimeError("critic client unavailable")
        clients.append(True)
        return FakeNaraClient()

    async def scenario():
        completed = await run_manager(
            monkeypatch,
            Settings(hermes_probe_enabled=False, critic_mode="deterministic"),
            client_factory=factory,
        )
        assert completed.status == "completed"
        assert completed.critic is not None
        assert completed.critic.verdict == "failed"
        assert any("계획 검증을 완료하지 못했습니다" in warning for warning in completed.result.warnings)

    asyncio.run(scenario())
