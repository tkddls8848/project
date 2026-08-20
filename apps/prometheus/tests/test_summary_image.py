from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from app.schemas import CriticFinding, CriticReport, DesignResponse, StageRecord
from app.summary_image import CANVAS_H, CANVAS_W, design_to_summary_svg

SVG_NS = "{http://www.w3.org/2000/svg}"


def make_result(selected, *, plan=None, relations=None, details=None,
                warnings=None, query="청년 주거와 취업 지원 서비스를 설계해줘") -> DesignResponse:
    return DesignResponse(
        query=query,
        selected_service_ids=selected,
        search={"results": [{"service_id": sid} for sid in selected]},
        details=details if details is not None else [
            {
                "service_id": sid,
                "name": f"문서 {sid}",
                "provider_agency_name": "국토교통부",
                "category": "국토관리 - 주택",
                "counts": {"endpoints": 2},
            }
            for sid in selected
        ],
        relations={"relations": relations} if relations is not None else None,
        plan=plan,
        stages=[StageRecord(name="search", status="completed", message="-")],
        warnings=warnings or [],
    )


def texts(svg: str) -> list[str]:
    root = ET.fromstring(svg)
    return [node.text or "" for node in root.iter(f"{SVG_NS}text")]


def test_summary_is_a_single_well_formed_16_9_page():
    svg = design_to_summary_svg(make_result(["openapi_new:1"]))
    root = ET.fromstring(svg)

    assert root.tag == f"{SVG_NS}svg"
    assert root.get("width") == str(CANVAS_W) and root.get("height") == str(CANVAS_H)
    assert (CANVAS_W, CANVAS_H) == (1280, 720)
    assert root.get("viewBox") == f"0 0 {CANVAS_W} {CANVAS_H}"


def test_selected_documents_and_their_metadata_are_drawn():
    svg = design_to_summary_svg(
        make_result(["openapi_new:1", "openapi_new:2", "openapi_new:3"])
    )
    rendered = texts(svg)

    for index in ("01", "02", "03"):
        assert index in rendered
    assert "문서 openapi_new:2" in rendered
    assert "openapi_new:3" in rendered
    assert any("국토교통부 · 국토관리 - 주택 · 엔드포인트 2개" == line for line in rendered)


def test_plan_text_is_rendered_as_slide_lines_without_markdown_markers():
    plan = {"suggestion": "## 서비스 개요\n- **청년 주거** 데이터를 결합한다\n\n두 번째 문단이다."}
    rendered = texts(design_to_summary_svg(make_result(["openapi_new:1"], plan=plan)))

    assert "서비스 개요" in rendered
    assert "• 청년 주거 데이터를 결합한다" in rendered
    assert "두 번째 문단이다." in rendered
    assert not any("#" in line or "**" in line for line in rendered)


def test_long_plan_text_is_wrapped_and_marked_as_truncated():
    plan = {"suggestion": "가나다라마바사아자차카타파하" * 200}
    rendered = texts(design_to_summary_svg(make_result(["openapi_new:1"], plan=plan)))

    assert any(line.endswith(" …") for line in rendered)
    assert "전체 계획 본문은 실행 결과 화면에서 확인하세요." in rendered
    # Wrapping must keep every line inside the plan panel width.
    plan_lines = [line for line in rendered if line.startswith("가나다라")]
    assert plan_lines and all(len(line) <= 48 for line in plan_lines)


def test_missing_plan_says_so_instead_of_inventing_one():
    rendered = texts(design_to_summary_svg(make_result(["openapi_new:1"])))

    assert "계획 생성을 생략했거나 계획 초안을 만들지 못했습니다." in rendered


def test_only_relations_inside_the_selection_are_summarized():
    relations = [
        {"id": "rel:io", "source": "openapi_new:1", "target": "openapi_new:2",
         "type": "io-chain", "evidence": ["응답 addr → 요청 addr"]},
        {"id": "rel:out", "source": "openapi_new:1", "target": "openapi_new:99",
         "type": "same-domain", "evidence": []},
    ]
    rendered = texts(design_to_summary_svg(
        make_result(["openapi_new:1", "openapi_new:2"], relations=relations)
    ))

    assert "1 ↔ 2 · io-chain · 응답 addr → 요청 addr" in rendered
    assert "선택 문서 2개 · 관계 근거 1건" in rendered
    assert not any("99" in line for line in rendered)


def test_critic_verdict_and_warnings_travel_onto_the_page():
    critic = CriticReport(
        verdict="evidence_gap",
        findings=[CriticFinding(check="selected-in-search", severity="unverified",
                                target="openapi_new:1", message="근거 부족")],
        deterministic=True,
    )
    svg = design_to_summary_svg(
        make_result(["openapi_new:1"], warnings=["문서 최신성(openapi_new:1): 변경 감지"]),
        critic=critic,
    )
    rendered = texts(svg)

    assert "근거 부족" in rendered
    assert any("문서 최신성(openapi_new:1): 변경 감지" in line for line in rendered)


def test_summary_without_a_critic_reports_verification_as_skipped():
    rendered = texts(design_to_summary_svg(make_result(["openapi_new:1"])))

    assert "검증 생략" in rendered


def test_page_always_carries_the_read_only_safety_note_and_timestamp():
    stamp = datetime(2026, 8, 20, 3, 4, tzinfo=timezone.utc)
    rendered = texts(design_to_summary_svg(make_result(["openapi_new:1"]),
                                           generated_at=stamp))

    assert "실제 행정 처리나 외부 시스템 변경을 수행하지 않는 검토용 요약입니다." in rendered
    assert "생성 2026-08-20 03:04 UTC" in rendered


def test_markup_in_document_text_is_escaped_not_injected():
    details = [{"service_id": "openapi_new:1", "name": "<script>alert(1)</script> & 문서"}]
    svg = design_to_summary_svg(make_result(["openapi_new:1"], details=details))

    assert "<script>" not in svg
    ET.fromstring(svg)


def test_empty_selection_still_renders_a_usable_page():
    rendered = texts(design_to_summary_svg(make_result([])))

    assert "선택된 문서가 없습니다." in rendered
    assert "문서가 한 개이거나 확인된 관계 근거가 없습니다." in rendered
