import importlib


def test_data_dir_default_points_to_shared_storage(monkeypatch):
    from app import config

    monkeypatch.delenv("NARA_DATA_DIR", raising=False)
    try:
        importlib.reload(config)
        assert config.NARA_DATA_DIR == config.BASE_DIR.parent / "nara_storage" / "openapi_new"
    finally:
        importlib.reload(config)
