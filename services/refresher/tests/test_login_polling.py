"""로그인 창을 사람이 쓰는 동안 지켜야 할 두 가지.

1. 폴링이 입력하던 화면을 건드리지 않는다. 최초 구현은 2초마다
   `page.goto(list_url)`로 세션을 확인해 로그인 폼을 주기적으로 리셋했고, 그래서
   **로그인 자체가 불가능**했다. 폴링은 페이지가 아니라 컨텍스트의 HTTP 클라이언트로 한다.
2. 알림창은 사람이 닫는다. 핸들러를 안 붙이면 드라이버가 스스로 닫으려다 이미 닫힌
   대화상자를 만나 죽고, 로그인을 마친 세션이 통째로 날아간다 (2026-08-09).
"""

from __future__ import annotations

import pytest

from app.config import Settings
from app.session import _session_ready, attach_dialog_handler

playwright_api = pytest.importorskip("playwright.sync_api")

FORM = """
<html><body>
  <form><input id="userId" type="text"><input id="pw" type="password"></form>
</body></html>
"""


@pytest.fixture
def browser_context():
    with playwright_api.sync_playwright() as driver:
        try:
            browser = driver.chromium.launch(headless=True)
        except Exception as exc:  # noqa: BLE001
            pytest.skip(f"Chromium 미설치: {exc}")
        context = browser.new_context()
        try:
            yield context
        finally:
            browser.close()


def test_polling_leaves_the_login_form_untouched(browser_context):
    page = browser_context.new_page()
    page.set_content(FORM)
    page.fill("#userId", "my-account")
    page.fill("#pw", "secret")
    url_before = page.url

    # 도달 불가 호스트: 폴링은 실패하지만 페이지를 건드려서는 안 된다.
    settings = Settings(base_url="https://unreachable.invalid")
    for _ in range(3):
        assert _session_ready(browser_context, settings) is False

    assert page.input_value("#userId") == "my-account", "입력이 폴링에 지워졌다"
    assert page.input_value("#pw") == "secret"
    assert page.url == url_before, "폴링이 페이지를 네비게이션했다"


def test_unreachable_portal_is_not_reported_as_logged_in(browser_context):
    settings = Settings(base_url="https://unreachable.invalid")

    assert _session_ready(browser_context, settings) is False


def test_dialog_is_left_for_the_operator_and_does_not_kill_the_driver(browser_context):
    dialogs = attach_dialog_handler(browser_context)
    page = browser_context.new_page()
    page.set_content("<html><body>login</body></html>")

    # evaluate는 즉시 돌아오고, alert는 그 뒤에 뜬다 — 안 그러면 호출이 대화상자에 막힌다.
    page.evaluate("setTimeout(() => { window.answered = false; alert('세션 만료'); "
                  "window.answered = true; }, 10)")
    page.wait_for_timeout(300)

    assert dialogs.open_dialogs, "대화상자가 드라이버에 의해 이미 닫혔다"

    dialogs.close_quietly()
    page.wait_for_timeout(200)
    assert page.evaluate("window.answered") is True, "대화상자가 닫히지 않아 페이지가 막혀 있다"

    # 원래 버그는 여기서 'Connection closed while reading from the driver'였다.
    assert browser_context.storage_state() is not None


def test_closing_a_dialog_the_operator_already_clicked_is_harmless(browser_context):
    dialogs = attach_dialog_handler(browser_context)
    page = browser_context.new_page()
    page.set_content("<html><body>login</body></html>")
    page.evaluate("setTimeout(() => alert('중복 확인'), 10)")
    page.wait_for_timeout(300)

    # 사람이 창에서 먼저 눌렀다고 치고, 그 뒤 우리가 정리에 들어간다.
    dialogs.open_dialogs[0].dismiss()
    dialogs.close_quietly()

    assert browser_context.storage_state() is not None
