import importlib


def test_apidata_default_points_to_shared_storage(monkeypatch):
    from backend.core import config

    monkeypatch.delenv("NARA_SEARCH_APIDATA_DIR", raising=False)
    try:
        importlib.reload(config)
        assert config.APIDATA_DIR == config.PROJECT_ROOT / "nara_storage" / "openapi_new"
    finally:
        # 다른 테스트가 모듈 상태에 의존하지 않도록 원복 reload
        importlib.reload(config)


def test_project_root_is_resolved_by_marker():
    from backend.core import config

    # 루트는 디렉터리 깊이가 아니라 .nara-root 마커로 정해진다.
    assert (config.PROJECT_ROOT / ".nara-root").is_file()


def test_find_project_root_falls_back_to_parent(tmp_path):
    from backend.core.config import find_project_root

    # 마커가 없는 트리에서는 예전 규약(모듈이 루트의 직계 자식)으로 폴백한다.
    module_dir = tmp_path / "some_module"
    module_dir.mkdir()
    assert find_project_root(module_dir) == tmp_path


def test_find_project_root_finds_marker_above_nested_module(tmp_path):
    from backend.core.config import find_project_root

    (tmp_path / ".nara-root").write_text("", encoding="utf-8")
    nested = tmp_path / "services" / "search"
    nested.mkdir(parents=True)
    assert find_project_root(nested) == tmp_path
