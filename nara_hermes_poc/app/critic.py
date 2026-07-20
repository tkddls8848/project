"""Read-only post-run verification of design results (Plan Critic).

The critic never mutates the result: it re-checks the evidence contract and
returns a verdict plus findings. See docs/plan_critic_agent_plan.md.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from .config import Settings
from .nara_client import NaraServiceError
from .schemas import CriticFinding, CriticReport, DesignResponse

# Checks whose violation means the result contradicts retrieved evidence,
# not merely that evidence is missing.
CONTRADICTION_CHECKS = frozenset(
    {"selected-in-search", "relations-verified", "contract-limits"}
)
STAGE_ORDER = ("search", "detail", "relations", "compose")

CRITIC_TOOL_BUDGET = {"get_api_detail": 3, "derive_relations": 1}

ProbeFn = Callable[..., Awaitable[dict[str, Any]]]


def _finding(check: str, severity: str, target: str, message: str,
             evidence: list[str] | None = None) -> CriticFinding:
    return CriticFinding(check=check, severity=severity, target=target,
                         message=message, evidence=evidence or [])


def _relation_key(relation: dict[str, Any]) -> Any:
    # Real extractor edges carry an id; fall back to the endpoint triple so
    # id-less fixtures can still be compared deterministically.
    return relation.get("id") or (
        relation.get("source"), relation.get("target"), relation.get("type")
    )


def compute_verdict(findings: list[CriticFinding]) -> str:
    violated = {f.check for f in findings if f.severity == "violation"}
    if violated & CONTRADICTION_CHECKS:
        return "contradiction"
    if violated or any(f.severity == "unverified" for f in findings):
        return "evidence_gap"
    return "pass"


async def run_deterministic_checks(
    result: DesignResponse, requested_ids: list[str], client: Any,
    findings: list[CriticFinding],
) -> None:
    selected = result.selected_service_ids

    detail_ids = {str(doc.get("service_id", "")).strip() for doc in result.details}
    missing_details = [sid for sid in selected if sid not in detail_ids]
    for sid in missing_details:
        findings.append(_finding(
            "selected-subset-of-details", "violation", sid,
            "선택된 문서의 상세 조회 근거가 없습니다.",
        ))
    if not missing_details:
        findings.append(_finding(
            "selected-subset-of-details", "info", "-",
            f"선택 문서 {len(selected)}개 모두 상세 조회 근거가 있습니다.",
        ))

    known_ids = {
        str(item.get("service_id", "")).strip()
        for item in (result.search.get("results") or [])
    } | set(requested_ids)
    unknown = [sid for sid in selected if sid not in known_ids]
    for sid in unknown:
        findings.append(_finding(
            "selected-in-search", "violation", sid,
            "검색 결과와 사용자 요청 어디에도 없는 ID가 선택되었습니다.",
        ))
    if not unknown:
        findings.append(_finding(
            "selected-in-search", "info", "-",
            "모든 선택 ID가 검색 결과 또는 사용자 요청에 존재합니다.",
        ))

    await _check_relations(result, client, findings)

    if len(selected) >= 2 and any(
        stage.name == "relations" and stage.status == "skipped"
        for stage in result.stages
    ):
        findings.append(_finding(
            "relations-not-skipped", "violation", "relations",
            "문서가 두 개 이상인데 관계 분석이 생략되었습니다.",
        ))
    else:
        findings.append(_finding(
            "relations-not-skipped", "info", "-", "관계 분석 단계 수행 여부가 계약과 일치합니다.",
        ))

    plan_missing = [str(item) for item in ((result.plan or {}).get("missing") or [])]
    unreported = [
        item for item in plan_missing
        if not any(item in warning for warning in result.warnings)
    ]
    for item in unreported:
        findings.append(_finding(
            "plan-missing-reported", "violation", item,
            "조합기가 찾지 못한 문서가 경고로 보고되지 않았습니다.",
        ))
    if not unreported:
        findings.append(_finding(
            "plan-missing-reported", "info", "-", "조합기 누락 문서가 모두 경고로 보고되었습니다.",
        ))

    _check_contract_limits(result, findings)


async def _check_relations(
    result: DesignResponse, client: Any, findings: list[CriticFinding]
) -> None:
    claimed = (result.relations or {}).get("relations") or []
    if not claimed or len(result.selected_service_ids) < 2:
        findings.append(_finding(
            "relations-verified", "info", "-", "재검증할 관계 주장이 없습니다.",
        ))
        return
    try:
        recheck = await client.relations(result.selected_service_ids)
    except (NaraServiceError, ValueError) as exc:
        findings.append(_finding(
            "relations-verified", "unverified", "relations",
            f"관계 재조회에 실패해 주장을 검증하지 못했습니다: {exc}",
        ))
        return
    valid_keys = {_relation_key(rel) for rel in recheck.get("relations") or []}
    unsupported = [rel for rel in claimed if _relation_key(rel) not in valid_keys]
    for rel in unsupported:
        findings.append(_finding(
            "relations-verified", "violation", str(_relation_key(rel)),
            "관계 도구 재조회 결과에 없는 관계가 주장되었습니다.",
        ))
    if not unsupported:
        findings.append(_finding(
            "relations-verified", "info", "-",
            f"관계 주장 {len(claimed)}개가 모두 재조회 결과로 뒷받침됩니다.",
        ))


def _check_contract_limits(result: DesignResponse, findings: list[CriticFinding]) -> None:
    selected = result.selected_service_ids
    problems: list[str] = []
    if len(selected) > 3:
        problems.append(f"선택 문서가 {len(selected)}개로 최대 3개를 초과합니다.")
    if len(set(selected)) != len(selected):
        problems.append("선택 ID에 중복이 있습니다.")
    positions = [STAGE_ORDER.index(s.name) for s in result.stages if s.name in STAGE_ORDER]
    if any(late < early for early, late in zip(positions, positions[1:])):
        problems.append("단계 기록이 search→detail→relations→compose 순서를 벗어났습니다.")
    for problem in problems:
        findings.append(_finding("contract-limits", "violation", "-", problem))
    if not problems:
        findings.append(_finding(
            "contract-limits", "info", "-", "선택 개수·중복·단계 순서 계약을 지켰습니다.",
        ))


async def _run_probe_layer(
    result: DesignResponse, settings: Settings, probe: ProbeFn
) -> dict[str, Any]:
    calls: list[dict[str, Any]] = []
    profile = settings.hermes_critic_profile
    for sid in result.selected_service_ids[: CRITIC_TOOL_BUDGET["get_api_detail"]]:
        calls.append(await probe(
            "get_api_detail", f"service_id는 {sid!r}다.", settings, profile=profile
        ))
    if len(result.selected_service_ids) >= 2:
        calls.append(await probe(
            "derive_relations",
            f"service_ids는 {result.selected_service_ids!r}다.",
            settings, profile=profile,
        ))
    status = "called" if calls and all(c["status"] == "called" for c in calls) else "partial"
    return {"status": status, "profile": profile, "calls": calls}


async def run_critic(
    result: DesignResponse,
    requested_ids: list[str],
    settings: Settings,
    client_factory: Callable[[], Any],
    probe: ProbeFn | None = None,
) -> CriticReport:
    """Verify a completed result. Never raises except on cancellation."""
    findings: list[CriticFinding] = []
    hermes: dict[str, Any] = {}
    deterministic = False

    async def _work() -> None:
        nonlocal deterministic, hermes
        async with client_factory() as client:
            await run_deterministic_checks(result, requested_ids, client, findings)
        deterministic = True
        if settings.critic_mode == "full" and probe is not None:
            hermes = await _run_probe_layer(result, settings, probe)

    try:
        await asyncio.wait_for(_work(), timeout=settings.critic_timeout)
    except asyncio.CancelledError:
        raise
    except TimeoutError:
        findings.append(_finding(
            "critic-timeout", "unverified", "-",
            f"검증이 {settings.critic_timeout:g}초 안에 끝나지 않았습니다.",
        ))
        return CriticReport(verdict="failed", findings=findings,
                            deterministic=deterministic, hermes=hermes)
    except Exception as exc:
        findings.append(_finding(
            "critic-error", "unverified", "-", f"검증기 오류: {exc}",
        ))
        return CriticReport(verdict="failed", findings=findings,
                            deterministic=deterministic, hermes=hermes)

    return CriticReport(verdict=compute_verdict(findings), findings=findings,
                        deterministic=deterministic, hermes=hermes)


__all__ = ["run_critic", "run_deterministic_checks", "compute_verdict", "CRITIC_TOOL_BUDGET"]
