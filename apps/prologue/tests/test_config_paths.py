"""이 앱의 경로와 시작 설정 검증을 본다.

``find_project_root`` 자체의 동작은 라이브러리 옆(``tests/test_paths.py``)에서
검증한다. 소비자마다 다시 확인하면 같은 함수를 네 번 테스트하게 된다.
"""

import pytest

from app.config import DEFAULT_STORAGE_DIR, PROJECT_ROOT, Settings


def test_storage_dir_follows_project_root():
    assert DEFAULT_STORAGE_DIR == PROJECT_ROOT / "api_storage"
    assert (PROJECT_ROOT / ".nara-root").is_file()


@pytest.mark.parametrize("value", [0, 7])
def test_settings_reject_tool_call_limits_outside_nara_contract(value):
    with pytest.raises(ValueError, match="1에서 6 사이"):
        Settings(hermes_max_tool_calls=value)


@pytest.mark.parametrize("value", [4, 6])
def test_settings_accept_tool_call_limits_within_nara_contract(value):
    assert Settings(hermes_max_tool_calls=value).hermes_max_tool_calls == value


def test_settings_reports_non_integer_tool_call_environment(monkeypatch):
    monkeypatch.setenv("NARA_HERMES_MAX_TOOL_CALLS", "many")

    with pytest.raises(ValueError, match="NARA_HERMES_MAX_TOOL_CALLS.*정수"):
        Settings()
