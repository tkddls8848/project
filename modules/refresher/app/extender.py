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
                # 연장할 수 있는 상태가 아니다. 실패가 아니라 대상이 아닌 것이다.
                return ExtendOutcome(
                    row.key, row.name, "skipped", "연장 신청하기 버튼이 없어 대상이 아닙니다."
                )
            control.click()
            with contextlib.suppress(Exception):
                page.wait_for_url(f"**{settings.list_path}*", timeout=settings.timeout * 1000)
        except Exception as exc:
            return ExtendOutcome(row.key, row.name, "failed", f"UI 경로 오류: {exc}")

        if dialogs.succeeded:
            return ExtendOutcome(row.key, row.name, "extended", portal_message=dialogs.last_message)
        # 버튼을 눌렀는데 포털이 연장 완료를 알리지 않았다. 대상이 아닌 것과 달리
        # 이건 연장에 실패한 것이다. 건너뜀으로 묶으면 종료 코드가 0이 되어
        # 아무것도 연장되지 않은 실행이 성공으로 보고된다.
        return ExtendOutcome(
            row.key, row.name, "failed", "포털이 연장을 완료하지 않았습니다.",
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
