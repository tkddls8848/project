"""세션 상태와 보유 API 목록을 읽는다 (읽기 전용).

목록은 CLI를 거치지 않고 `fetch_account_rows`를 직접 부른다. 화면에 표로 그리려면
구조화된 값이 필요한데, CLI는 사람이 읽는 문장을 찍기 때문이다. 실행 계열
명령(login/extend)은 계속 CLI 서브프로세스로 돈다.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from app.accounts import fetch_account_rows
from app.browser import BrowserSession
from app.config import get_settings
from app.session import NotAuthenticatedError


def session_state() -> dict[str, Any]:
    settings = get_settings()
    state_file = settings.state_file
    exists = state_file.is_file()
    return {
        "authenticated_hint": exists,
        "state_file": str(state_file),
        "saved_at": (
            datetime.fromtimestamp(state_file.stat().st_mtime, timezone.utc).isoformat()
            if exists
            else None
        ),
        "list_url": settings.list_url,
        "storage_dir": str(settings.storage_dir),
        "headless": settings.headless,
    }


def _rows_blocking() -> list[dict[str, Any]]:
    settings = get_settings()
    with BrowserSession(settings, headless=True) as browser:
        rows = fetch_account_rows(settings, browser)
    return [
        {
            "name": row.name,
            "status_text": row.status_text,
            "key": row.key,
            "detail_params": row.detail_params,
        }
        for row in rows
    ]


async def list_accounts() -> dict[str, Any]:
    """저장된 세션으로 목록을 읽는다.

    Playwright 동기 API는 실행 중인 이벤트 루프가 있는 스레드에서 못 쓰므로
    워커 스레드에서 돌린다.
    """
    try:
        rows = await asyncio.to_thread(_rows_blocking)
    except NotAuthenticatedError as exc:
        return {"ok": False, "reason": "not-authenticated", "message": str(exc), "rows": []}
    except RuntimeError as exc:
        return {"ok": False, "reason": "error", "message": str(exc), "rows": []}
    return {"ok": True, "total": len(rows), "rows": rows}


__all__ = ["list_accounts", "session_state"]
