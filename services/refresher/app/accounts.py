"""Read the current data.go.kr account list contract."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup, Tag

from .browser import BrowserSession
from .config import Settings
from .models import AccountRow

DETAIL_FIELDS = (
    "publicDataDetailPk", "prcuseReqstSeqNo", "cloudApi", "publicDataTyCode",
)
_DETAIL_CALL = re.compile(r"fn_detail\s*\(([^)]*)\)")
_ARGUMENT = re.compile(r"['\"]([^'\"]*)['\"]|(-?\d+)")
_PAGE_CALL = re.compile(r"fn_page\s*\(\s*(\d+)\s*\)")


@dataclass
class ListPage:
    rows: list[AccountRow] = field(default_factory=list)
    page_numbers: list[int] = field(default_factory=list)


def _text(node: Tag) -> str:
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()


def parse_account_rows(html: str) -> ListPage:
    soup = BeautifulSoup(html, "lxml")
    result = ListPage()
    seen: set[str] = set()
    for anchor in soup.select(".apply-result-link a"):
        source = f"{anchor.get('href') or ''} {anchor.get('onclick') or ''}"
        call = _DETAIL_CALL.search(source)
        if not call:
            continue
        args = [quoted or number for quoted, number in _ARGUMENT.findall(call.group(1))]
        if len(args) != len(DETAIL_FIELDS):
            continue
        params = dict(zip(DETAIL_FIELDS, args))
        key = "&".join(f"{name}={value}" for name, value in sorted(params.items()))
        if key in seen:
            continue
        seen.add(key)
        name = _text(anchor)
        status = (re.match(r"\s*\[([^]]+)]", name) or ["", ""])[1].strip()
        result.rows.append(AccountRow(name=name, detail_params=params, nav_args=args, status_text=status))

    pages = {
        int(match.group(1))
        for node in soup.select(".paging a")
        if (match := _PAGE_CALL.search(str(node.get("href") or node.get("onclick") or "")))
    }
    result.page_numbers = sorted(pages)
    return result


def fetch_account_rows(
    settings: Settings, browser: BrowserSession,
) -> list[AccountRow]:
    rows: list[AccountRow] = []
    seen: set[str] = set()
    with browser.page() as page:
        page.goto(settings.list_url, wait_until="domcontentloaded")
        first = parse_account_rows(page.content())
        for page_number in first.page_numbers or [1]:
            if page_number != 1:
                with page.expect_navigation(wait_until="domcontentloaded"):
                    page.evaluate(f"fn_page({page_number})")
            for row in parse_account_rows(page.content()).rows:
                if row.key not in seen:
                    seen.add(row.key)
                    rows.append(row)
    return rows

