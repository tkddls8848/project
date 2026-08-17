"""이 앱의 경로 배선만 본다.

``find_project_root`` 자체의 동작은 라이브러리 옆(``tests/test_paths.py``)에서
검증한다. 소비자마다 다시 확인하면 같은 함수를 네 번 테스트하게 된다.
"""

from app.config import DEFAULT_STORAGE_DIR, PROJECT_ROOT


def test_storage_dir_follows_project_root():
    assert DEFAULT_STORAGE_DIR == PROJECT_ROOT / "nara_storage"
    assert (PROJECT_ROOT / ".nara-root").is_file()
