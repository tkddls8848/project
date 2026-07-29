REQUIRED_DETAIL_FIELDS = [
    "service_id",
    "name",
    "description",
    "provider_agency_name",
    "category",
    "endpoints",
    "request_fields",
    "response_fields",
    "source",
]


def test_detail_with_canonical_id(app_client):
    response = app_client.get("/services/openapi_new:15000001")
    assert response.status_code == 200
    body = response.json()
    for field in REQUIRED_DETAIL_FIELDS:
        assert field in body, f"missing field: {field}"
    assert body["service_id"] == "openapi_new:15000001"
    assert body["name"] == "한국환경공단_에어코리아_대기오염정보"
    assert body["provider_agency_name"] == "한국환경공단"
    assert body["detail_source"] == "apidata_flat"


def test_detail_endpoints_and_fields_parsed(app_client):
    body = app_client.get("/services/openapi_new:15000001").json()

    assert body["counts"]["endpoints"] == 1
    endpoint = body["endpoints"][0]
    assert endpoint["method"] == "GET"
    assert endpoint["path"] == "/getCtprvnRltmMesureDnsty"

    request_names = {f["name"] for f in body["request_fields"]}
    assert {"serviceKey", "sidoName", "numOfRows"} <= request_names
    service_key = next(f for f in body["request_fields"] if f["name"] == "serviceKey")
    assert service_key["required"] is True
    assert service_key["role"] == "request"

    response_names = {f["name"] for f in body["response_fields"]}
    assert {"pm10Value", "pm25Value", "dataTime"} <= response_names


def test_detail_source_has_no_absolute_path(app_client):
    body = app_client.get("/services/openapi_new:15000001").json()
    raw_path = body["source"]["raw_path"]
    assert raw_path
    assert not raw_path.startswith("/")
    assert ":\\" not in raw_path
    assert body["source"]["url"].startswith("https://www.data.go.kr/")


def test_detail_with_pure_api_id_is_normalized(app_client):
    response = app_client.get("/services/15000001")
    assert response.status_code == 200
    assert response.json()["service_id"] == "openapi_new:15000001"


def test_detail_with_sparse_document(app_client):
    """endpoints/swagger가 빈 문서도 최소 계약 필드를 채워 반환한다."""
    response = app_client.get("/services/openapi_new:15000002")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "국토교통부_버스도착정보"
    assert body["endpoints"] == []
    assert body["request_fields"] == []
    assert body["response_fields"] == []


def test_detail_unsupported_prefix_is_400(app_client):
    response = app_client.get("/services/filedata:15000001")
    assert response.status_code == 400
    body = response.json()
    assert body["ok"] is False
    assert body["error_code"] == "UNSUPPORTED_SOURCE"


def test_detail_invalid_format_is_400(app_client):
    response = app_client.get("/services/not-a-valid-id")
    assert response.status_code == 400
    body = response.json()
    assert body["ok"] is False
    assert body["error_code"] == "INVALID_SERVICE_ID"


def test_detail_missing_id_is_404(app_client):
    response = app_client.get("/services/openapi_new:99999999")
    assert response.status_code == 404
    body = response.json()
    assert body["ok"] is False
    assert body["error_code"] == "NOT_FOUND"
    assert body["message"] == "service_id not found"


def test_detail_without_any_data_source_is_503(app_client, monkeypatch, tmp_path):
    from backend import main
    from backend.core import config

    monkeypatch.setattr(config, "APIDATA_DIR", tmp_path / "missing_apidata")
    main.detail_provider.reload()
    response = app_client.get("/services/openapi_new:15000001")
    assert response.status_code == 503
    body = response.json()
    assert body["ok"] is False
    assert body["error_code"] == "SERVICE_UNAVAILABLE"
