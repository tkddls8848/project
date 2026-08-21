"""Authenticated Playwright context and extension-dialog handling."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from typing import Any, Iterator

from .config import Settings
from .session import USER_AGENT, load_state

SUCCESS_MARKERS = ("연장되었습니다", "연장 되었습니다")


def _import_playwright():
    try:
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Playwright가 없습니다. requirements 설치 후 "
            "`python -m playwright install chromium`을 실행하세요."
        ) from exc
    return sync_playwright


@dataclass
class DialogRecorder:
    messages: list[str] = field(default_factory=list)

    def __call__(self, dialog: Any) -> None:
        self.messages.append(dialog.message or "")
        dialog.accept()

    @property
    def succeeded(self) -> bool:
        return any(marker in message for message in self.messages for marker in SUCCESS_MARKERS)

    @property
    def last_message(self) -> str:
        return self.messages[-1] if self.messages else ""


class BrowserSession:
    def __init__(self, settings: Settings, headless: bool | None = None):
        self.settings = settings
        self.headless = settings.headless if headless is None else headless
        self._driver = None
        self._browser = None
        self.context = None

    def __enter__(self) -> "BrowserSession":
        state = load_state(self.settings)
        # _import_playwright()는 sync_playwright 함수 자체를 돌려준다. 매니저를
        # 얻으려면 한 번 호출해야 하며, 함수에 바로 .start()를 부르면 안 된다.
        sync_playwright = _import_playwright()
        self._driver = sync_playwright().start()
        self._browser = self._driver.chromium.launch(headless=self.headless)
        self.context = self._browser.new_context(storage_state=state, user_agent=USER_AGENT)
        self.context.set_default_timeout(self.settings.timeout * 1000)
        return self

    def __exit__(self, *_exc: object) -> None:
        for closer in (self._browser, self._driver):
            if closer is not None:
                with contextlib.suppress(Exception):
                    closer.close() if closer is self._browser else closer.stop()

    @contextlib.contextmanager
    def page(self) -> Iterator[Any]:
        page = self.context.new_page()
        try:
            yield page
        finally:
            with contextlib.suppress(Exception):
                page.close()
