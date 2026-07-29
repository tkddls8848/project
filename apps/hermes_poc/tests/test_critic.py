from __future__ import annotations

import asyncio

from app.config import Settings
from app.critic import compute_verdict, run_critic
from app.nara_client import NaraServiceError
from app.schemas import DesignResponse, StageRecord


def make_result(**overrides) -> DesignResponse:
    base = {
        "query": "청년 주거와 취업 지원",
        "selected_service_ids": ["openapi_new:1", "openapi_new:2"],
        "search": {"results": [
            {"service_id": "openapi_new:1", "name": "주거 지원"},
            {"service_id": "openapi_new:2", "name": "취업 지원"},
        ]},
        "details": [
            {"service_id": "openapi_new:1", "name": "주거 지원"},
            {"service_id": "openapi_new:2", "name": "취업 지원"},
        ],
        "relations": {"relations": [
            {"id": "rel:same-domain:openapi_new:1:openapi_new:2",
             "source": "openapi_new:1", "target": "openapi_new:2",
             "type": "same-domain", "evidence": ["분류체계: 복지"]},
        ]},
        "plan": {"suggestion": "실행이 아닌 계획 초안", "missing": []},
        "stages": [
            StageRecord(name="search", status="completed", message="-"),
            StageRecord(name="detail", status="completed", message="-"),
            StageRecord(name="relations", status="completed", message="-"),
            StageRecord(name="compose", status="completed", message="-"),
        ],
        "warnings": [],
    }
    base.update(overrides)
    return DesignResponse(**base)


class FakeClient:
    def __init__(self, relations=None, error=None, delay=0.0):
        self._relations = relations
        self._error = error
        self._delay = delay

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    async def relations(self, service_ids):
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._error:
            raise self._error
        if self._relations is not None:
            return {"relations": self._relations}
        return {"relations": [
            {"id": "rel:same-domain:openapi_new:1:openapi_new:2",
             "source": "openapi_new:1", "target": "openapi_new:2",
             "type": "same-domain"},
        ]}


def settings(**overrides) -> Settings:
    return Settings(hermes_probe_enabled=False, **overrides)


def critic(result, requested_ids=(), client=None, config=None):
    return asyncio.run(run_critic(
        result, list(requested_ids), config or settings(),
        client_factory=lambda: client or FakeClient(),
    ))


def test_clean_result_passes_with_info_findings_only():
    report = critic(make_result())

    assert report.verdict == "pass"
    assert report.deterministic
    assert all(finding.severity == "info" for finding in report.findings)


def test_selected_id_without_detail_is_an_evidence_gap():
    report = critic(make_result(details=[{"service_id": "openapi_new:1"}]))

    assert report.verdict == "evidence_gap"
    assert any(
        finding.check == "selected-subset-of-details" and finding.target == "openapi_new:2"
        for finding in report.findings
    )


def test_selected_id_absent_from_search_and_request_is_a_contradiction():
    report = critic(make_result(search={"results": [{"service_id": "openapi_new:1"}]}))

    assert report.verdict == "contradiction"
    assert any(finding.check == "selected-in-search" for finding in report.findings)


def test_requested_ids_legitimize_selection_outside_search_results():
    report = critic(
        make_result(search={"results": [{"service_id": "openapi_new:1"}]}),
        requested_ids=["openapi_new:2"],
    )

    assert not any(
        finding.check == "selected-in-search" and finding.severity == "violation"
        for finding in report.findings
    )


def test_relation_claim_missing_from_recheck_is_a_contradiction():
    report = critic(make_result(), client=FakeClient(relations=[]))

    assert report.verdict == "contradiction"
    assert any(finding.check == "relations-verified" for finding in report.findings)


def test_failed_relation_recheck_is_unverified_not_a_violation():
    error = NaraServiceError("nara-search", "nara-search 연결 실패")
    report = critic(make_result(), client=FakeClient(error=error))

    assert report.verdict == "evidence_gap"
    assert any(
        finding.check == "relations-verified" and finding.severity == "unverified"
        for finding in report.findings
    )


def test_skipped_relations_with_two_documents_is_an_evidence_gap():
    stages = [
        StageRecord(name="search", status="completed", message="-"),
        StageRecord(name="detail", status="completed", message="-"),
        StageRecord(name="relations", status="skipped", message="-"),
        StageRecord(name="compose", status="completed", message="-"),
    ]
    report = critic(make_result(relations=None, stages=stages))

    assert report.verdict == "evidence_gap"
    assert any(finding.check == "relations-not-skipped" for finding in report.findings)


def test_unreported_combiner_missing_ids_are_an_evidence_gap():
    report = critic(make_result(plan={"suggestion": "-", "missing": ["openapi_new:9"]}))

    assert report.verdict == "evidence_gap"
    assert any(
        finding.check == "plan-missing-reported" and finding.target == "openapi_new:9"
        for finding in report.findings
    )


def test_duplicate_selection_violates_contract_limits():
    result = make_result()
    result.selected_service_ids.append("openapi_new:1")
    report = critic(result)

    assert report.verdict == "contradiction"
    assert any(finding.check == "contract-limits" for finding in report.findings)


def test_critic_exception_yields_failed_report_without_raising():
    class BrokenFactory:
        def __call__(self):
            raise RuntimeError("client factory broke")

    report = asyncio.run(run_critic(
        make_result(), [], settings(), client_factory=BrokenFactory()
    ))

    assert report.verdict == "failed"
    assert not report.deterministic
    assert any(finding.check == "critic-error" for finding in report.findings)


def test_critic_timeout_yields_failed_report():
    report = critic(
        make_result(),
        client=FakeClient(delay=0.2),
        config=settings(critic_timeout=0.01),
    )

    assert report.verdict == "failed"
    assert any(finding.check == "critic-timeout" for finding in report.findings)


def test_compute_verdict_prefers_contradiction_over_evidence_gap():
    from app.schemas import CriticFinding

    findings = [
        CriticFinding(check="selected-subset-of-details", severity="violation",
                      target="-", message="-"),
        CriticFinding(check="relations-verified", severity="violation",
                      target="-", message="-"),
    ]
    assert compute_verdict(findings) == "contradiction"
