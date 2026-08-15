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

# 페이지네이션은 KRDS 컴포넌트다. `fn_page(1)`은 페이지 링크 밖(검색 버튼 등)에도
# 나오므로 컨테이너를 좁혀 잡지 않으면 엉뚱한 번호를 페이지로 읽는다.
_PAGE_LINKS = ".krds-pagination a.page-link"
_TOTAL_COUNT = "ul.total .point"


@dataclass
class ListPage:
    rows: list[AccountRow] = field(default_factory=list)
    page_numbers: list[int] = field(default_factory=list)
    total_count: int | None = None


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
        for node in soup.select(_PAGE_LINKS)
        if (match := _PAGE_CALL.search(str(node.get("href") or node.get("onclick") or "")))
    }
    result.page_numbers = sorted(pages)

    total = soup.select_one(_TOTAL_COUNT)
    if total is not None:
        digits = re.sub(r"\D", "", total.get_text())
        result.total_count = int(digits) if digits else None
    return result


def fetch_account_rows(
    settings: Settings, browser: BrowserSession,
) -> list[AccountRow]:
    """목록의 모든 페이지를 돌며 행을 모은다.

    페이지 번호는 방문할 때마다 다시 읽는다. 목록이 길어 페이지네이션이 번호를
    일부만 보여주는 경우에도, 이동한 뒤 새로 드러난 번호를 이어서 방문한다.
    """
    rows: list[AccountRow] = []
    seen: set[str] = set()
    visited: set[int] = set()
    known: set[int] = {1}
    declared_total: int | None = None

    with browser.page() as page:
        page.goto(settings.list_url, wait_until="domcontentloaded")
        while remaining := sorted(known - visited):
            page_number = remaining[0]
            if page_number != 1:  # 1페이지는 goto로 이미 열려 있다
                with page.expect_navigation(wait_until="domcontentloaded"):
                    page.evaluate(f"fn_page({page_number})")
            visited.add(page_number)

            parsed = parse_account_rows(page.content())
            known.update(parsed.page_numbers)
            if parsed.total_count is not None:
                declared_total = parsed.total_count
            for row in parsed.rows:
                if row.key not in seen:
                    seen.add(row.key)
                    rows.append(row)

    # 일부 페이지만 읽고 조용히 끝나면 extend가 남은 항목을 통째로 건너뛴다.
    if declared_total is not None and len(rows) != declared_total:
        print(f"[경고] 전체 {declared_total}건 중 {len(rows)}건만 확인했습니다 "
              f"(방문한 페이지: {sorted(visited)}).")
    return rows

