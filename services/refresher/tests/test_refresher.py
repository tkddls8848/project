from __future__ import annotations

import contextlib
import re
from pathlib import Path

from app import browser as browser_module
from app.accounts import DETAIL_FIELDS, fetch_account_rows, parse_account_rows
from app.browser import BrowserSession, DialogRecorder
from app.config import DEFAULT_STORAGE_DIR, PROJECT_ROOT, Settings
from app.extender import run_extension

FIXTURE = (Path(__file__).parent / "fixtures" / "list_page_real.html").read_text(encoding="utf-8")


def test_current_list_contract():
    page = parse_account_rows(FIXTURE)
    assert len(page.rows) == 2
    assert page.page_numbers == [1, 2, 3]
    assert page.total_count == 25
    assert list(page.rows[0].detail_params) == list(DETAIL_FIELDS)
    assert page.rows[0].nav_args[3] == "PR0027"
    assert page.rows[0].status_text == "승인"


def test_pagination_is_read_from_the_krds_container_only():
    """`fn_page(...)`는 검색 버튼 등 페이지 링크 밖에도 나온다.

    컨테이너를 좁히지 않으면 그런 호출이 페이지 번호로 섞여 들어온다.
    """
    assert 'onclick="fn_page(1)"' in FIXTURE  # 페이지네이션 밖의 호출
    assert parse_account_rows(FIXTURE).page_numbers == [1, 2, 3]

    # 예전 마크업(nav.paging)은 더 이상 지원하지 않는다.
    old = FIXTURE.replace("krds-pagination", "paging").replace("page-links", "old-links")
    assert parse_account_rows(old).page_numbers == []


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


def _list_page_html(page_numbers, rows, total):
    """현재 마크업으로 목록 한 페이지를 만든다."""
    row_html = "".join(
        f"""<div class="apply-result-link">
          <a href="javascript:fn_detail('uddi:{key}','{key}','0','PR0027')">[승인] {name}</a>
        </div>"""
        for key, name in rows
    )
    links = "".join(
        f'<a class="page-link" href="javascript:fn_page({n})">{n}</a>' for n in page_numbers
    )
    return f"""<!doctype html><html><body>
      <ul class="total"><li>전체 <span class="point">{total}</span>건</li></ul>
      {row_html}
      <div class="krds-pagination"><div class="page-links">{links}</div></div>
    </body></html>"""


class FakePage:
    """fn_page(n) 호출에 따라 다른 페이지를 돌려주는 가짜 Playwright 페이지."""

    def __init__(self, pages):
        self.pages = pages
        self.current = 1
        self.visited = []

    def goto(self, _url, wait_until=None):
        self.current = 1
        self.visited.append(1)

    def content(self):
        return self.pages[self.current]

    def expect_navigation(self, wait_until=None):
        return contextlib.nullcontext()

    def evaluate(self, script):
        self.current = int(re.search(r"fn_page\((\d+)\)", script).group(1))
        self.visited.append(self.current)


class FakeBrowser:
    def __init__(self, page): self._page = page

    @contextlib.contextmanager
    def page(self): yield self._page


def test_every_page_is_collected_not_just_the_first():
    """1페이지만 읽고 끝나면 extend가 나머지를 통째로 건너뛴다."""
    numbers = [1, 2, 3]
    pages = {
        n: _list_page_html(numbers, [(f"{n}{i}", f"문서 {n}-{i}") for i in range(2)], 6)
        for n in numbers
    }
    page = FakePage(pages)

    rows = fetch_account_rows(Settings(), FakeBrowser(page))

    assert len(rows) == 6
    assert page.visited == [1, 2, 3]
    assert {row.name for row in rows} == {f"[승인] 문서 {n}-{i}" for n in numbers for i in range(2)}


def test_page_numbers_revealed_later_are_followed():
    """페이지네이션이 번호를 일부만 보여줘도 이동 후 드러난 번호를 이어서 방문한다."""
    pages = {
        1: _list_page_html([1, 2], [("a", "문서 A")], 3),
        2: _list_page_html([2, 3], [("b", "문서 B")], 3),
        3: _list_page_html([3], [("c", "문서 C")], 3),
    }
    page = FakePage(pages)

    rows = fetch_account_rows(Settings(), FakeBrowser(page))

    assert [row.name for row in rows] == ["[승인] 문서 A", "[승인] 문서 B", "[승인] 문서 C"]
    assert page.visited == [1, 2, 3]


def test_incomplete_collection_is_reported(capsys):
    """선언된 총건수와 모은 수가 다르면 조용히 넘어가지 않는다."""
    pages = {1: _list_page_html([1], [("a", "문서 A")], 63)}
    fetch_account_rows(Settings(), FakeBrowser(FakePage(pages)))
    assert "전체 63건 중 1건만" in capsys.readouterr().out


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
