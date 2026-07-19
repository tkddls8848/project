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


def test_agent_run_emits_live_stages_and_normalizes_result(monkeypatch):
    async def scenario():
        monkeypatch.setattr("app.agent.NaraClient", lambda _: FakeNaraClient())
        manager = AgentRunManager(Settings(hermes_probe_enabled=False))
        created = await manager.create(AgentRunRequest(query="미세먼지 알림 서비스"))
        run = manager._runs[created.run_id]
        await run.task

        completed = manager.snapshot(created.run_id)
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
