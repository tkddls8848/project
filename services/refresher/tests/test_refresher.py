from __future__ import annotations

from pathlib import Path

from app import browser as browser_module
from app.accounts import DETAIL_FIELDS, parse_account_rows
from app.browser import BrowserSession, DialogRecorder
from app.config import DEFAULT_STORAGE_DIR, PROJECT_ROOT, Settings
from app.extender import run_extension

FIXTURE = (Path(__file__).parent / "fixtures" / "list_page_real.html").read_text(encoding="utf-8")


def test_current_list_contract():
    page = parse_account_rows(FIXTURE)
    assert len(page.rows) == 2
    assert page.page_numbers == [1, 2, 3]
    assert list(page.rows[0].detail_params) == list(DETAIL_FIELDS)
    assert page.rows[0].nav_args[3] == "PR0027"
    assert page.rows[0].status_text == "승인"


def test_unknown_layout_returns_no_rows():
    assert parse_account_rows("<a href='/future-layout'>row</a>").rows == []


def test_dry_run_does_not_open_a_browser(tmp_path):
    row = parse_account_rows(FIXTURE).rows[0]
    summary = run_extension(Settings(storage_dir=tmp_path), [row], commit=False)
    assert summary.would_extend == 1
    assert summary.extended == 0


def test_success_dialog_is_the_completion_signal():
    class Dialog:
        message = "연장되었습니다."

        def accept(self):
            pass

    recorder = DialogRecorder()
    recorder(Dialog())
    assert recorder.succeeded
    assert recorder.last_message == "연장되었습니다."


def test_storage_path_is_repository_relative():
    assert DEFAULT_STORAGE_DIR == PROJECT_ROOT / "nara_storage" / "refresher"


def test_browser_session_starts_the_playwright_manager(tmp_path, monkeypatch):
    """`_import_playwright()`는 sync_playwright 함수를 돌려준다.

    거기에 바로 `.start()`를 부르면 `'function' object has no attribute 'start'`로
    죽는다. list·extend가 이 경로로만 브라우저를 연다.
    """
    started: list[str] = []

    class FakeContext:
        def set_default_timeout(self, _ms): pass

    class FakeBrowser:
        def new_context(self, **_kwargs): return FakeContext()
        def close(self): started.append("browser-closed")

    class FakeChromium:
        def launch(self, headless): started.append(f"launch headless={headless}"); return FakeBrowser()

    class FakeDriver:
        chromium = FakeChromium()
        def stop(self): started.append("driver-stopped")

    class FakeManager:
        def start(self): started.append("started"); return FakeDriver()

    monkeypatch.setattr(browser_module, "_import_playwright", lambda: (lambda: FakeManager()))
    monkeypatch.setattr(browser_module, "load_state", lambda _settings: {"cookies": []})

    with BrowserSession(Settings(storage_dir=tmp_path), headless=True) as session:
        assert session.context is not None

    assert started[0] == "started"
    assert "launch headless=True" in started
    assert "driver-stopped" in started
