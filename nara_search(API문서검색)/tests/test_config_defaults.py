import importlib


def test_apidata_default_points_to_shared_storage(monkeypatch):
    from backend.core import config

    monkeypatch.delenv("NARA_SEARCH_APIDATA_DIR", raising=False)
    try:
        importlib.reload(config)
        assert config.APIDATA_DIR == config.BASE_DIR.parent / "nara_storage" / "openapi_new"
    finally:
        # 다른 테스트가 모듈 상태에 의존하지 않도록 원복 reload
        importlib.reload(config)
