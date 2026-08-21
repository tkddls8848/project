"""이 서비스의 설정 기본값과 경로 배선만 본다.

``find_project_root`` 자체의 동작은 라이브러리 옆(``tests/test_paths.py``)에서
검증한다. 소비자마다 다시 확인하면 같은 함수를 네 번 테스트하게 된다.
"""

import importlib


def test_data_dir_default_points_to_shared_storage(monkeypatch):
    from app import config

    monkeypatch.delenv("NARA_DATA_DIR", raising=False)
    try:
        importlib.reload(config)
        assert config.NARA_DATA_DIR == config.PROJECT_ROOT / "api_storage" / "openapi_new"
    finally:
        importlib.reload(config)


def test_project_root_is_resolved_by_marker():
    from app import config

    # 루트는 디렉터리 깊이가 아니라 .nara-root 마커로 정해진다.
    assert (config.PROJECT_ROOT / ".nara-root").is_file()
