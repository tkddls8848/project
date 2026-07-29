def test_catalog_lists_fixture_docs(app_client):
    res = app_client.get("/catalog")
    assert res.status_code == 200
    payload = res.json()
    assert payload["total"] == 3
    by_id = {doc["api_id"]: doc for doc in payload["docs"]}
    air = by_id["15000001"]
    assert air["service_id"] == "openapi_new:15000001"
    assert air["provider"] == "한국환경공단"
    assert {"key": "pm10Value", "desc": "미세먼지(PM10) 농도"} in air["fields"]
    assert air["endpoints"][0]["method"] == "GET"
    # swagger가 빈 문서도 목록에는 나온다
    assert by_id["15000002"]["fields"] == []


def test_catalog_empty_when_apidata_missing(app_client, monkeypatch, tmp_path):
    from backend.core import config
    from backend import main

    monkeypatch.setattr(config, "APIDATA_DIR", tmp_path / "none")
    main.catalog_listing.reload()
    res = app_client.get("/catalog")
    assert res.status_code == 200
    assert res.json() == {"total": 0, "docs": []}


def test_catalog_skips_non_object_json(app_client, monkeypatch, tmp_path, fixture_apidata_dir):
    import shutil
    from backend.core import config
    from backend import main

    apidata = tmp_path / "apidata"
    apidata.mkdir()
    shutil.copy(fixture_apidata_dir / "15000001_20260101120000.json", apidata / "15000001_20260101120000.json")
    (apidata / "15999998_20260101120000.json").write_text("[1, 2, 3]", encoding="utf-8")

    monkeypatch.setattr(config, "APIDATA_DIR", apidata)
    main.catalog_listing.reload()
    res = app_client.get("/catalog")
    assert res.status_code == 200
    payload = res.json()
    assert payload["total"] == 1
    assert payload["docs"][0]["api_id"] == "15000001"
