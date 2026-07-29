from app.config import DEFAULT_STORAGE_DIR, PROJECT_ROOT, find_project_root


def test_storage_dir_follows_project_root():
    assert DEFAULT_STORAGE_DIR == PROJECT_ROOT / "nara_storage"
    assert (PROJECT_ROOT / ".nara-root").is_file()


def test_find_project_root_finds_marker_above_nested_module(tmp_path):
    (tmp_path / ".nara-root").write_text("", encoding="utf-8")
    nested = tmp_path / "apps" / "hermes_poc"
    nested.mkdir(parents=True)
    assert find_project_root(nested) == tmp_path


def test_find_project_root_falls_back_to_parent(tmp_path):
    # 마커가 없는 트리에서는 예전 규약(모듈이 루트의 직계 자식)으로 폴백한다.
    module_dir = tmp_path / "some_module"
    module_dir.mkdir()
    assert find_project_root(module_dir) == tmp_path
