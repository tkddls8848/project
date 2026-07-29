"""Deterministic orchestration that Hermes can later drive through tools."""

from __future__ import annotations

import asyncio
from typing import Any

from .nara_client import NaraClient, NaraServiceError
from .schemas import DesignRequest, DesignResponse, StageRecord


class NaraOrchestrator:
    def __init__(self, client: NaraClient):
        self.client = client

    async def design(self, request: DesignRequest) -> DesignResponse:
        stages: list[StageRecord] = []
        warnings: list[str] = []

        search = await self.client.search(
            request.query, top_k=request.top_k, use_vector=request.use_vector
        )
        results = search.get("results") or []
        stages.append(
            StageRecord(
                name="search",
                status="completed",
                message=f"검색 결과 {len(results)}개를 확인했습니다.",
            )
        )

        selected_ids = self._select_ids(request.selected_service_ids, results)
        if not selected_ids:
            stages.extend(
                [
                    StageRecord(
                        name="detail",
                        status="skipped",
                        message="선택된 API 문서가 없습니다.",
                    ),
                    StageRecord(
                        name="relations",
                        status="skipped",
                        message="관계를 분석할 API 문서가 없습니다.",
                    ),
                    StageRecord(
                        name="compose",
                        status="skipped",
                        message="조합할 API 문서가 없습니다.",
                    ),
                ]
            )
            warnings.append("검색 결과가 없어 서비스 계획을 생성하지 않았습니다.")
            return DesignResponse(
                query=request.query,
                selected_service_ids=[],
                search=search,
                details=[],
                stages=stages,
                warnings=warnings,
            )

        details = await asyncio.gather(
            *(self.client.detail(service_id) for service_id in selected_ids)
        )
        stages.append(
            StageRecord(
                name="detail",
                status="completed",
                message=f"선택 문서 {len(details)}개의 상세 정보를 확인했습니다.",
            )
        )

        relations: dict[str, Any] | None = None
        if len(selected_ids) >= 2:
            relations = await self.client.relations(selected_ids)
            relation_count = len(relations.get("relations") or [])
            stages.append(
                StageRecord(
                    name="relations",
                    status="completed",
                    message=f"문서 관계 {relation_count}개를 확인했습니다.",
                )
            )
            if relation_count == 0:
                warnings.append("선택 문서 사이에서 파생 관계를 찾지 못했습니다.")
        else:
            stages.append(
                StageRecord(
                    name="relations",
                    status="skipped",
                    message="문서가 한 개이므로 관계 조회를 생략했습니다.",
                )
            )

        plan: dict[str, Any] | None = None
        if request.compose:
            try:
                plan = await self.client.compose(selected_ids, request.query)
            except NaraServiceError as exc:
                stages.append(
                    StageRecord(
                        name="compose",
                        status="failed",
                        message="계획 생성에 실패했지만 문서 분석 결과는 유지합니다.",
                    )
                )
                warnings.append(str(exc))
            else:
                stages.append(
                    StageRecord(
                        name="compose",
                        status="completed",
                        message="행정 서비스 계획 초안을 생성했습니다.",
                    )
                )
                if plan.get("warning"):
                    warnings.append(str(plan["warning"]))
                if plan.get("missing"):
                    warnings.append(
                        "조합기에서 찾지 못한 문서: " + ", ".join(plan["missing"])
                    )
        else:
            stages.append(
                StageRecord(
                    name="compose",
                    status="skipped",
                    message="요청에 따라 계획 생성을 생략했습니다.",
                )
            )

        return DesignResponse(
            query=request.query,
            selected_service_ids=selected_ids,
            search=search,
            details=details,
            relations=relations,
            plan=plan,
            stages=stages,
            warnings=warnings,
        )

    @staticmethod
    def _select_ids(
        requested_ids: list[str], search_results: list[dict[str, Any]]
    ) -> list[str]:
        candidates = requested_ids or [
            str(item.get("service_id", "")).strip() for item in search_results[:3]
        ]
        selected: list[str] = []
        for service_id in candidates:
            if service_id and service_id not in selected:
                selected.append(service_id)
        return selected[:3]


async def run_design(request: DesignRequest) -> DesignResponse:
    async with NaraClient() as client:
        return await NaraOrchestrator(client).design(request)


__all__ = ["NaraOrchestrator", "NaraServiceError", "run_design"]
