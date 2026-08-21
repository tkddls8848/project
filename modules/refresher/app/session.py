"""Authenticated-session handling.

data.go.kr login cannot be automated (and should not be: it involves the
operator's real credentials and may require a second factor).  The operator logs
in once in a real browser window; this module persists the resulting cookies and
replays them for every later run, headless or over plain HTTP.
"""

from __future__ import annotations

import contextlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import Settings

# Match the crawler's identity so the portal sees one consistent client.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


class NotAuthenticatedError(RuntimeError):
    """The saved session is missing or no longer valid."""


def _import_playwright():
    try:
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError as exc:  # pragma: no cover - environment guard
        raise RuntimeError(
            "Playwright가 없습니다. `python -m pip install -r requirements.txt` 뒤 "
            "`python -m playwright install chromium`을 실행하세요."
        ) from exc
    return sync_playwright


def looks_authenticated(final_url: str, html: str) -> bool:
    """Decide from the response itself, not from a selector that may change.

    A logged-out request to the account list is bounced to the login page, so the
    landing URL and the presence of a password field are the two signals that do
    not depend on the portal's markup staying the same.
    """
    lowered = final_url.lower()
    if "login" in lowered or "sso" in lowered:
        return False
    if 'type="password"' in html or "type='password'" in html:
        return False
    return True


def save_state(settings: Settings, state: dict[str, Any]) -> Path:
    settings.state_file.parent.mkdir(parents=True, exist_ok=True)
    settings.state_file.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return settings.state_file


def load_state(settings: Settings) -> dict[str, Any]:
    if not settings.state_file.is_file():
        raise NotAuthenticatedError(
            f"저장된 세션이 없습니다: {settings.state_file}\n"
            "`python main.py login`으로 먼저 로그인하세요."
        )
    return json.loads(settings.state_file.read_text(encoding="utf-8"))


def _session_ready(context: object, settings: Settings) -> bool:
    """Check the session out-of-band, without touching the visible page.

    `context.request` shares the browser's cookie jar but is a plain HTTP client,
    so polling it cannot disturb what the operator is typing.  Navigating the
    login page on a timer — the obvious implementation — wipes the form on every
    tick and makes logging in impossible.
    """
    try:
        response = context.request.get(settings.list_url)  # type: ignore[attr-defined]
        if not response.ok:
            return False
        return looks_authenticated(response.url, response.text())
    except Exception:  # noqa: BLE001 - not logged in yet, or transient
        return False


@dataclass
class OperatorDialogs:
    """Holds JS dialogs open so the person at the window answers them.

    **With no listener attached, the driver dismisses every dialog itself**
    (`browser.py` 머리말과 같은 함정이다). In a headed login window the operator
    usually clicks the same dialog first, and the driver's dismissal then fails
    with "No dialog is showing" — an unhandled rejection inside the Node driver
    that kills it outright. The Python side only finds out at its next protocol
    call, which is `storage_state()`, so a completed login was thrown away with a
    stack trace (2026-08-09에 실제로 겪었다).

    Listening without answering hands the dialog to the person in front of the
    window, which is who should be answering it anyway.
    """

    open_dialogs: list[Any] = field(default_factory=list)

    def __call__(self, dialog: Any) -> None:
        self.open_dialogs.append(dialog)

    def close_quietly(self) -> None:
        """Clear anything still open before we talk to the browser again.

        Dismissing a dialog the operator already clicked raises — but from our own
        call, which returns an ordinary error instead of crashing the driver.
        """
        for dialog in self.open_dialogs:
            with contextlib.suppress(Exception):
                dialog.dismiss()
        self.open_dialogs.clear()


def attach_dialog_handler(context: Any) -> OperatorDialogs:
    """Own the dialogs of every page in `context`, present and future."""
    dialogs = OperatorDialogs()
    context.on("page", lambda page: page.on("dialog", dialogs))
    for page in context.pages:
        page.on("dialog", dialogs)
    return dialogs


def _read_storage_state(context: Any) -> dict[str, Any]:
    """Read cookies, turning a dead driver into an actionable message."""
    try:
        return context.storage_state()
    except Exception as exc:  # noqa: BLE001 - driver death surfaces right here
        raise RuntimeError(
            "브라우저에서 세션을 읽지 못했습니다. 창이 먼저 닫혔거나 브라우저 드라이버가 "
            "종료된 경우입니다. 창을 닫지 말고 `python main.py login --manual`을 다시 "
            f"실행하세요.\n  원인: {exc}"
        ) from exc


def interactive_login(settings: Settings, poll_seconds: float = 2.0,
                      timeout_seconds: float = 600.0, manual: bool = False) -> Path:
    """Open a real browser, wait for the operator to log in, then save cookies.

    Readiness is decided by fetching the account list with the browser's cookies
    and checking whether the portal serves it — not by watching for a particular
    button — so a changed login screen does not break this.  `manual=True` skips
    detection entirely and saves when the operator says so, which is the escape
    hatch if the portal's markup fools `looks_authenticated`.
    """
    sync_playwright = _import_playwright()
    deadline = time.monotonic() + timeout_seconds
    with sync_playwright() as driver:
        browser = driver.chromium.launch(headless=False)
        try:
            context = browser.new_context(user_agent=USER_AGENT)
            # 포털이 띄우는 알림창은 창 앞의 사람이 닫는다. 드라이버가 대신 닫게
            # 두면 사람과 경합해 드라이버가 죽는다 (OperatorDialogs 참고).
            dialogs = attach_dialog_handler(context)
            page = context.new_page()
            page.goto(settings.list_url, wait_until="domcontentloaded")
            print(f"열린 창에서 로그인하세요 (대상: {settings.list_url})")
            print("이 창은 자동으로 새로고침되지 않습니다. 천천히 입력하세요.")

            if manual:
                input("\n로그인을 마쳤으면 이 터미널에서 Enter를 누르세요... ")
                dialogs.close_quietly()
                state = _read_storage_state(context)
                if not _session_ready(context, settings):
                    print("[경고] 로그인 상태로 보이지 않지만 요청대로 저장합니다. "
                          "`main.py list`가 실패하면 다시 로그인하세요.")
            else:
                print("로그인이 끝나면 자동으로 감지합니다. (Ctrl+C로 중단)\n")
                waited = 0.0
                while True:
                    if _session_ready(context, settings):
                        break
                    if time.monotonic() >= deadline:
                        raise NotAuthenticatedError(
                            "제한 시간 안에 로그인이 확인되지 않았습니다. "
                            "로그인은 됐는데 감지가 안 되면 `main.py login --manual`을 쓰세요."
                        )
                    time.sleep(poll_seconds)
                    waited += poll_seconds
                    if waited % 30 < poll_seconds:
                        print(f"  ...대기 중 ({int(waited)}초)")
                dialogs.close_quietly()
                state = _read_storage_state(context)

            path = save_state(settings, state)
            print(f"세션을 저장했습니다: {path}")
            return path
        finally:
            with contextlib.suppress(Exception):
                browser.close()


__all__ = [
    "NotAuthenticatedError", "OperatorDialogs", "USER_AGENT", "attach_dialog_handler",
    "looks_authenticated", "interactive_login", "load_state", "save_state",
]
