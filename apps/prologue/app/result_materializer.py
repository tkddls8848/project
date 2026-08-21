"""Hermes 선택 결과를 Nara 원본으로 재구성하고 진행 단계를 만든다."""

from __future__ import annotations

import re
from typing import Any

from .nara_client import NaraClient, NaraServiceError
from .schemas import AgentRunRequest, DesignResponse, StageRecord


TOOL_STAGES = {"search_api_docs": "search", "get_api_detail": "detail"}
SERVICE_ID_RE = re.compile(r"(?<![A-Za-z0-9._-])openapi_new:\d+(?!\d)")


def normalize_tool_name(raw: object) -> str:
    value = str(raw or "")
    for name in TOOL_STAGES:
        if value == name or value.endswith(f"__{name}"):
            return name
    return value


def tool_event_stage(event: dict[str, Any]) -> StageRecord | None:
    """Gateway가 보고한 도구 이벤트만으로 진행 단계 문구를 만든다."""
    event_name = event.get("event")
    if event_name not in {"tool.started", "tool.completed"}:
        return None
    tool = normalize_tool_name(event.get("tool"))
    if tool not in TOOL_STAGES:
        return None
    status = (
        "running"
        if event_name == "tool.started"
        else ("failed" if event.get("error") else "completed")
    )
    actions = {
        "running": "호출하고 있습니다",
        "completed": "완료했습니다",
        "failed": "실패했습니다",
    }
    return StageRecord(
        name=TOOL_STAGES[tool],
        status=status,
        message=f"Hermes가 {tool} 도구를 {actions[status]}.",
    )


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
    """Hermes는 최종 데이터가 아니라 service_id 선택에만 사용한다."""
    requested = _unique_service_ids(list(request.selected_service_ids))[:3]
    if requested:
        return requested, False

    results = search.get("results") or []
    candidates = _unique_service_ids([
        row.get("service_id") for row in results if isinstance(row, dict)
    ])
    proposed = _unique_service_ids(SERVICE_ID_RE.findall(output or ""))
    if proposed:
        # Hermes 순위를 재현하려고 검색을 한 번 더 하지 않는다. 공개 결과에 넣기
        # 전 아래의 정식 상세 endpoint에서 모든 ID를 다시 검증한다.
        return proposed[:3], False
    return candidates[:3], bool(candidates)


async def materialize_design_result(
    output: str,
    request: AgentRunRequest,
    client: NaraClient,
    observed_tools: list[str] | None = None,
) -> DesignResponse:
    """Nara 서비스 응답만으로 공개 결과를 결정형으로 재구성한다."""
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
    """모델 출력이 아니라 Gateway가 보고한 호출만 서술한다."""
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
    # 단계는 Orchestrator가 Nara에 수행한 작업이다. 괄호 안의 Hermes 동작만
    # Gateway가 실제로 보고한 도구 호출 기록에서 가져온다.
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
        StageRecord(
            name="detail",
            status="completed" if selected and details else "skipped",
            message=detail_message,
        ),
        StageRecord(
            name="relations",
            status="completed" if relations is not None else "skipped",
            message=(
                "문서 관계 근거를 확인했습니다."
                if relations is not None
                else "관계 분석을 생략했습니다."
            ),
        ),
        StageRecord(
            name="compose",
            status="completed" if plan is not None else "skipped",
            message=(
                "서비스 계획 초안을 만들었습니다."
                if plan is not None
                else (
                    "계획을 만들 근거가 없습니다."
                    if compose
                    else "요청에 따라 계획 생성을 생략했습니다."
                )
            ),
        ),
    ]


__all__ = [
    "materialize_design_result",
    "normalize_tool_name",
    "tool_event_stage",
]
