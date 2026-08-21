from backend.relations.extractor import derive_relations, signature_from_detail


def _detail(service_id, provider, category, request, response):
    return {
        "service_id": service_id,
        "provider_agency_name": provider,
        "category": category,
        "request_fields": [{"name": n} for n in request],
        "response_fields": [{"name": n} for n in response],
    }


AIR = _detail(
    "openapi_new:15000001", "한국환경공단", "환경기상 - 대기",
    ["serviceKey", "sidoName", "numOfRows"],
    ["pm10Value", "pm25Value", "dataTime"],
)
STATION = _detail(
    "openapi_new:15000003", "한국환경공단", "환경기상 - 대기",
    ["serviceKey", "sidoName", "stationName"],
    ["stationName", "addr", "sidoName"],
)
BUS = _detail("openapi_new:15000002", "국토교통부", "교통물류", [], [])


def _by_type(edges):
    grouped = {}
    for edge in edges:
        grouped.setdefault(edge["type"], []).append(edge)
    return grouped


def test_signature_excludes_common_params():
    sig = signature_from_detail(AIR)
    assert sig["request_params"] == {"sidoname": "sidoName"}
    assert set(sig["response_fields"]) == {"pm10value", "pm25value", "datatime"}


def test_same_agency_and_domain_edges():
    edges = _by_type(derive_relations([signature_from_detail(AIR), signature_from_detail(STATION)]))
    assert edges["same-agency"][0]["evidence"] == ["제공기관: 한국환경공단"]
    assert edges["same-agency"][0]["confidence"] == 1.0
    assert edges["same-domain"][0]["evidence"] == ["분류체계: 환경기상 - 대기"]


def test_param_overlap_edge():
    edges = _by_type(derive_relations([signature_from_detail(AIR), signature_from_detail(STATION)]))
    overlap = edges["param-overlap"][0]
    assert overlap["evidence"] == ["공유 요청 파라미터: sidoName"]
    assert overlap["confidence"] == 0.5
    # 무방향 관계는 service_id 사전순으로 source 고정
    assert overlap["source"] == "openapi_new:15000001"


def test_io_chain_is_directional():
    edges = _by_type(derive_relations([signature_from_detail(AIR), signature_from_detail(STATION)]))
    chains = edges["io-chain"]
    # STATION 응답 sidoName → AIR 요청 sidoName 한 방향만 존재
    assert len(chains) == 1
    assert chains[0]["source"] == "openapi_new:15000003"
    assert chains[0]["target"] == "openapi_new:15000001"
    assert chains[0]["evidence"] == ["응답 sidoName → 요청 sidoName"]


def test_unrelated_docs_have_no_edges():
    assert derive_relations([signature_from_detail(AIR), signature_from_detail(BUS)]) == []


def test_min_shared_params_threshold():
    edges = _by_type(derive_relations(
        [signature_from_detail(AIR), signature_from_detail(STATION)], min_shared_params=2
    ))
    assert "param-overlap" not in edges


def test_types_filter_limits_output():
    edges = derive_relations(
        [signature_from_detail(AIR), signature_from_detail(STATION)],
        types={"io-chain"},
    )
    assert {edge["type"] for edge in edges} == {"io-chain"}


def test_all_edges_are_derived_status():
    for edge in derive_relations([signature_from_detail(AIR), signature_from_detail(STATION)]):
        assert edge["status"] == "derived"
        assert edge["generatedAt"]
