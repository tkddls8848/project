from __future__ import annotations

from app.flow_export import FLOW_FORMAT, FLOW_VERSION, design_to_flow
from app.schemas import DesignResponse, StageRecord

# nara_dashboard flowIO.js와 동기화된 계약 미러 (대시보드 없이 검증하기 위함)
KNOWN_NODE_TYPES = {"apiDoc", "mergeNode", "apiSearch", "categoryFilter",
                    "providerFilter", "scoreFilter", "ragChat", "summaryNode",
                    "exportNode", "saveNode", "chatOutput"}


def make_result(selected, relations=None, details=None, warnings=None) -> DesignResponse:
    return DesignResponse(
        query="청년 주거와 취업 지원 서비스를 설계해줘",
        selected_service_ids=selected,
        search={"results": [{"service_id": sid} for sid in selected]},
        details=details if details is not None else [
            {"service_id": sid, "name": f"문서 {sid}"} for sid in selected
        ],
        relations={"relations": relations} if relations is not None else None,
        plan=None,
        stages=[StageRecord(name="search", status="completed", message="-")],
        warnings=warnings or [],
    )


def assert_matches_dashboard_contract(flow):
    assert flow["format"] == FLOW_FORMAT == "nara-dashboard-flow"
    assert flow["version"] == FLOW_VERSION == 1
    assert isinstance(flow["name"], str) and flow["name"]
    assert isinstance(flow["exported_at"], str)
    node_ids = [node["id"] for node in flow["nodes"]]
    assert len(node_ids) == len(set(node_ids))
    for node in flow["nodes"]:
        assert node["type"] in KNOWN_NODE_TYPES
        assert isinstance(node["position"]["x"], int)
        assert isinstance(node["position"]["y"], int)
    for edge in flow["edges"]:
        assert edge["source"] in node_ids and edge["target"] in node_ids


def test_three_documents_with_relations_produce_nodes_and_edges():
    relations = [
        {"id": "rel:same-domain:openapi_new:1:openapi_new:2",
         "source": "openapi_new:1", "target": "openapi_new:2",
         "type": "same-domain", "evidence": ["분류체계: 복지"]},
        {"id": "rel:io-chain:openapi_new:2:openapi_new:3",
         "source": "openapi_new:2", "target": "openapi_new:3",
         "type": "io-chain", "evidence": ["응답 addr → 요청 addr"]},
    ]
    flow = design_to_flow(make_result(
        ["openapi_new:1", "openapi_new:2", "openapi_new:3"], relations=relations
    ))

    assert_matches_dashboard_contract(flow)
    assert [node["id"] for node in flow["nodes"]] == [
        "openapi_new:1", "openapi_new:2", "openapi_new:3",
    ]
    assert [node["data"]["apiId"] for node in flow["nodes"]] == ["1", "2", "3"]
    assert [edge["id"] for edge in flow["edges"]] == [
        "rel:same-domain:openapi_new:1:openapi_new:2",
        "rel:io-chain:openapi_new:2:openapi_new:3",
    ]


def test_grid_positions_follow_dashboard_layout():
    flow = design_to_flow(make_result(
        ["openapi_new:1", "openapi_new:2", "openapi_new:3"], relations=[]
    ))

    assert [node["position"] for node in flow["nodes"]] == [
        {"x": 80, "y": 120}, {"x": 360, "y": 120}, {"x": 640, "y": 120},
    ]


def test_single_document_without_relations_is_still_a_valid_flow():
    flow = design_to_flow(make_result(["openapi_new:1"]))

    assert_matches_dashboard_contract(flow)
    assert len(flow["nodes"]) == 1
    assert flow["edges"] == []


def test_relations_outside_the_selection_are_dropped():
    relations = [
        {"id": "rel:x", "source": "openapi_new:1", "target": "openapi_new:99",
         "type": "same-domain", "evidence": []},
    ]
    flow = design_to_flow(make_result(["openapi_new:1", "openapi_new:2"], relations=relations))

    assert flow["edges"] == []


def test_relation_evidence_travels_in_node_data():
    relations = [
        {"id": "rel:io", "source": "openapi_new:1", "target": "openapi_new:2",
         "type": "io-chain", "evidence": ["응답 addr → 요청 addr"]},
    ]
    flow = design_to_flow(make_result(["openapi_new:1", "openapi_new:2"], relations=relations))

    for node in flow["nodes"]:
        assert node["data"]["naraRelationNotes"] == ["io-chain: 응답 addr → 요청 addr"]
    assert node["data"]["naraTitle"] == "문서 openapi_new:2"


def test_warnings_are_summarized_into_the_selection_note():
    flow = design_to_flow(make_result(
        ["openapi_new:1"], warnings=["파생 관계를 찾지 못했습니다."]
    ))

    note = flow["nodes"][0]["data"]["naraSelectionNote"]
    assert "청년 주거와 취업 지원" in note
    assert "파생 관계를 찾지 못했습니다." in note


def test_flow_name_is_truncated_and_defaults_when_empty():
    long_query = "가" * 200
    result = make_result(["openapi_new:1"])
    result.query = long_query
    assert len(design_to_flow(result)["name"]) == 60

    result.query = ""
    assert design_to_flow(result)["name"] == "나라 에이전트 결과"
