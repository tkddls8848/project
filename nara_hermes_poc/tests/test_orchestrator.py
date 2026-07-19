from __future__ import annotations

import asyncio

from app.nara_client import NaraServiceError
from app.orchestrator import NaraOrchestrator
from app.schemas import DesignRequest


class FakeNaraClient:
    def __init__(self, results=None):
        self.results = results if results is not None else [
            {"service_id": "openapi_new:1", "name": "주거 지원"},
            {"service_id": "openapi_new:2", "name": "취업 지원"},
            {"service_id": "openapi_new:3", "name": "교육 지원"},
            {"service_id": "openapi_new:4", "name": "기타"},
        ]
        self.calls: list[tuple] = []

    async def search(self, query, top_k=5, use_vector=True):
        self.calls.append(("search", query, top_k, use_vector))
        return {
            "query": query,
            "results": self.results,
            "diagnostics": {"fusion": "rrf"},
        }

    async def detail(self, service_id):
        self.calls.append(("detail", service_id))
        return {"service_id": service_id, "description": "검증된 문서"}

    async def relations(self, service_ids):
        self.calls.append(("relations", tuple(service_ids)))
        return {"ids": service_ids, "missing": [], "relations": []}

    async def compose(self, service_ids, question):
        self.calls.append(("compose", tuple(service_ids), question))
        return {
            "service_ids": service_ids,
            "suggestion": "실행이 아닌 계획 초안",
            "missing": [],
        }


def test_design_runs_all_read_and_plan_stages():
    async def scenario():
        client = FakeNaraClient()
        result = await NaraOrchestrator(client).design(
            DesignRequest(query="청년 주거와 취업 지원", top_k=5)
        )
        assert result.selected_service_ids == [
            "openapi_new:1",
            "openapi_new:2",
            "openapi_new:3",
        ]
        assert [stage.status for stage in result.stages] == [
            "completed",
            "completed",
            "completed",
            "completed",
        ]
        assert any(
            "파생 관계를 찾지 못했습니다." in warning
            for warning in result.warnings
        )
        assert result.plan["suggestion"] == "실행이 아닌 계획 초안"
        assert not any(call[0] in {"write", "execute"} for call in client.calls)

    asyncio.run(scenario())


def test_explicit_selection_is_preserved_and_compose_can_be_skipped():
    async def scenario():
        client = FakeNaraClient()
        result = await NaraOrchestrator(client).design(
            DesignRequest(
                query="선택 문서 검토",
                selected_service_ids=["openapi_new:9"],
                compose=False,
            )
        )
        assert result.selected_service_ids == ["openapi_new:9"]
        assert result.relations is None
        assert result.plan is None
        assert [stage.status for stage in result.stages] == [
            "completed",
            "completed",
            "skipped",
            "skipped",
        ]
        assert not any(call[0] == "compose" for call in client.calls)

    asyncio.run(scenario())


def test_no_results_stops_without_detail_or_compose():
    async def scenario():
        client = FakeNaraClient(results=[])
        result = await NaraOrchestrator(client).design(
            DesignRequest(query="존재하지 않는 서비스")
        )
        assert result.selected_service_ids == []
        assert result.details == []
        assert [stage.status for stage in result.stages] == [
            "completed",
            "skipped",
            "skipped",
            "skipped",
        ]
        assert [call[0] for call in client.calls] == ["search"]

    asyncio.run(scenario())


def test_compose_failure_preserves_document_analysis():
    class FailingCombinerClient(FakeNaraClient):
        async def compose(self, service_ids, question):
            raise NaraServiceError(
                "nara-combiner", "nara-combiner 응답 시간 초과"
            )

    async def scenario():
        result = await NaraOrchestrator(FailingCombinerClient()).design(
            DesignRequest(query="청년 주거와 취업 지원")
        )

        assert result.search["results"]
        assert len(result.details) == 3
        assert result.relations is not None
        assert result.plan is None
        assert result.stages[-1].status == "failed"
        assert "응답 시간 초과" in result.warnings[-1]

    asyncio.run(scenario())
