def _types(payload):
    return {edge["type"] for edge in payload["relations"]}


def test_relations_between_air_and_station(app_client):
    res = app_client.get("/relations", params={"ids": "15000001,15000003"})
    assert res.status_code == 200
    payload = res.json()
    assert payload["ids"] == ["openapi_new:15000001", "openapi_new:15000003"]
    assert payload["missing"] == []
    assert _types(payload) == {"same-agency", "same-domain", "param-overlap", "io-chain"}
    chain = [e for e in payload["relations"] if e["type"] == "io-chain"][0]
    assert chain["source"] == "openapi_new:15000003"
    assert chain["evidence"] == ["응답 sidoName → 요청 sidoName"]
    assert all(e["status"] == "derived" for e in payload["relations"])


def test_relations_reports_missing_ids(app_client):
    res = app_client.get("/relations", params={"ids": "15000001,15999999"})
    assert res.status_code == 200
    payload = res.json()
    assert payload["missing"] == ["openapi_new:15999999"]
    assert payload["relations"] == []


def test_relations_requires_at_least_two_ids(app_client):
    res = app_client.get("/relations", params={"ids": "15000001"})
    assert res.status_code == 400
    assert res.json()["error_code"] == "INVALID_IDS"


def test_relations_rejects_malformed_id(app_client):
    res = app_client.get("/relations", params={"ids": "15000001,bogus prefix:x"})
    assert res.status_code == 400
