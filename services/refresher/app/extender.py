"""Submit extensions through the verified data.go.kr browser flow."""

from __future__ import annotations

import contextlib
import json
from datetime import datetime

from .browser import BrowserSession, DialogRecorder
from .config import Settings
from .models import AccountRow, ExtendOutcome, RunSummary

_EXTEND_SELECTOR = "button:has-text('연장 신청하기')"


def extend_via_ui(
    settings: Settings, browser: BrowserSession, row: AccountRow,
) -> ExtendOutcome:
    with browser.page() as page:
        dialogs = DialogRecorder()
        page.on("dialog", dialogs)
        try:
            page.goto(settings.list_url, wait_until="domcontentloaded")
            args = ", ".join(json.dumps(value, ensure_ascii=False) for value in row.nav_args)
            with page.expect_navigation(wait_until="domcontentloaded"):
                page.evaluate(f"fn_detail({args})")
            control = page.locator(_EXTEND_SELECTOR).last
            if control.count() == 0:
                return ExtendOutcome(row.key, row.name, "skipped", "연장 신청하기 버튼이 없습니다.")
            control.click()
            with contextlib.suppress(Exception):
                page.wait_for_url(f"**{settings.list_path}*", timeout=settings.timeout * 1000)
        except Exception as exc:
            return ExtendOutcome(row.key, row.name, "failed", f"UI 경로 오류: {exc}")

        if dialogs.succeeded:
            return ExtendOutcome(row.key, row.name, "extended", portal_message=dialogs.last_message)
        return ExtendOutcome(
            row.key, row.name, "skipped", "포털이 연장을 완료하지 않았습니다.",
            dialogs.last_message,
        )


def run_extension(
    settings: Settings,
    rows: list[AccountRow],
    commit: bool = False,
    limit: int | None = None,
) -> RunSummary:
    selected = rows[:limit] if limit is not None else rows
    summary = RunSummary(commit=commit)
    if not commit:
        summary.outcomes = [
            ExtendOutcome(row.key, row.name, "would-extend", "--commit을 붙이면 연장합니다.")
            for row in selected
        ]
    else:
        with BrowserSession(settings, headless=True) as browser:
            summary.outcomes = [extend_via_ui(settings, browser, row) for row in selected]
    summary.finished_at = datetime.now().astimezone().isoformat()
    return summary
