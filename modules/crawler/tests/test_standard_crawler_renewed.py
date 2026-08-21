"""standard(표준데이터) crawling against the 2026-08 renewed portal markup.

Two things broke at once on this page type. The metadata tables the crawler
scanned are gone, and so is the item grid: the renewed page serves no
``<table>`` element at all. The first is recoverable through the shared
key/value parser; the second is not recoverable from the page, so these tests
pin the empty grid as an observed fact and check that it is reported instead of
passing as a clean crawl.

Everything runs off saved HTML — nothing here touches the network.
"""

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from crawler.standard_crawler import StandardCrawler

FIXTURE = Path(__file__).parent / "fixtures" / "renewed" / "standard_15072622.html"
DATA_URL = "https://www.data.go.kr/data/15072622/standard.do"


def _config():
    return SimpleNamespace(max_workers=1, target_api_type=None)


@pytest.fixture(scope="module")
def renewed_html():
    return FIXTURE.read_text(encoding="utf-8")


@pytest.fixture
def crawler():
    return StandardCrawler(_config())


# --------------------------------------------------------------------- stubs


class _StubResponse:
    def __init__(self, body, status=200):
        self._body = body
        self.status = status

    async def text(self):
        return self._body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _StubSession:
    """Serves one canned page for every request and records the URLs asked for."""

    def __init__(self, body, status=200):
        self.body = body
        self.status = status
        self.requested = []

    def get(self, url, **kwargs):
        self.requested.append(url)
        return _StubResponse(self.body, self.status)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


# ------------------------------------------------------------ legacy markup


# Pre-renewal shape: metadata in ``table.stdDataDetail``, the item grid in
# ``#tab_layer_grid``. Stored documents were crawled from pages like this, so
# it has to keep parsing after the switch to the shared parser.
LEGACY_HTML = """
<html><body>
  <table class="stdDataDetail">
    <tr><th>제공기관</th><td>구형기관</td></tr>
    <tr><th>소관기관</th><td>구형소관</td></tr>
  </table>
  <div id="tab_layer_grid">
    <div class="table-responsive standard-data-table boxed-table">
      <table>
        <thead><tr><th>항목명</th><th>설명</th></tr></thead>
        <tbody>
          <tr><td><a href="/data/1/standard.do">화장실명</a></td><td>공중화장실 이름</td></tr>
          <tr><td>소재지도로명주소</td><td>도로명 주소</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</body></html>
"""

# What a renewed page would look like if the portal put the grid back: the
# ``krds-table-wrap``/``tbl col bg`` shape that /tcs/dss/stdFileList.do still
# returns today, inside one of the renewed ``tab-layer-`` containers.
RENEWED_WITH_GRID_HTML = """
<html><body>
  <div id="tab-layer-std-05">
    <div class="krds-table-wrap m-table">
      <table class="tbl col bg">
        <thead><tr><th scope="col">데이터명</th><th scope="col">등록일</th></tr></thead>
        <tbody>
          <tr><td><a href="/data/15075531/fileData.do">행정안전부_공중화장실정보</a></td><td>2026-06-05</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</body></html>
"""


# ------------------------------------------------------------------ metadata


def test_renewed_page_metadata_comes_back_through_the_shared_parser(crawler, renewed_html):
    info = crawler._extract_table_bs(crawler.make_soup(renewed_html), renewed_html)

    assert len(info) == 25
    assert info["소관기관"] == "행정안전부"
    assert info["표준데이터셋제공시스템"] == "재난관리업무포털(NDMS)"
    assert info["관련법령"] == "재해구호법"
    assert info["제공범위(대상)"] == (
        "「재해구호법」에 따른 임시주거시설 중 지진겸용 임시주거시설에 대한 정보"
    )
    assert info["표준데이터 기본정보"].startswith("행정안전부에서 운영하는 재난안전데이터 공유플랫폼")


def test_renewed_page_recovers_the_phone_number_from_the_inline_script(crawler, renewed_html):
    # The value element renders empty; only the script source carries the number.
    assert "044-205-4467" not in crawler.make_soup(renewed_html).get_text()

    info = crawler._extract_table_bs(crawler.make_soup(renewed_html), renewed_html)
    assert info["관리부서 전화번호"] == "044-205-4467"


def test_old_table_metadata_still_parses(crawler):
    info = crawler._extract_table_bs(crawler.make_soup(LEGACY_HTML), LEGACY_HTML)

    assert info["제공기관"] == "구형기관"
    assert info["소관기관"] == "구형소관"
    # The grid rows sit in a table too. They carry no <th>/<td> pair per row,
    # so the legacy fallback must not fold them into the metadata.
    assert "화장실명" not in info
    assert "항목명" not in info


# ---------------------------------------------------------------- grid table


def test_renewed_page_serves_no_grid_at_all(crawler, renewed_html):
    soup = crawler.make_soup(renewed_html)

    # Not "the selector missed it" — the page has no table element whatsoever.
    assert soup.select("table") == []
    assert crawler._extract_standard_grid_table(soup) == []


def test_old_grid_container_still_parses(crawler):
    rows = crawler._extract_standard_grid_table(crawler.make_soup(LEGACY_HTML))

    assert rows == [
        {"항목명": "화장실명", "항목명_link": "/data/1/standard.do", "설명": "공중화장실 이름"},
        {"항목명": "소재지도로명주소", "설명": "도로명 주소"},
    ]


def test_grid_inside_a_renewed_tab_layer_container_is_found(crawler):
    # The old selectors are all #tab_layer_grid based and would return nothing here.
    rows = crawler._extract_standard_grid_table(crawler.make_soup(RENEWED_WITH_GRID_HTML))

    assert rows == [
        {
            "데이터명": "행정안전부_공중화장실정보",
            "데이터명_link": "/data/15075531/fileData.do",
            "등록일": "2026-06-05",
        }
    ]


def test_describe_sections_names_the_containers_the_server_rendered(crawler, renewed_html):
    sections = crawler._describe_sections(crawler.make_soup(renewed_html))

    # The in-page navigation links to #tab-layer-std-01..06, but only std-01 is
    # emitted under that name; the rest are rendered as api-/file- containers.
    assert sections == "tab-layer-std-01, tab-layer-api-01, tab-layer-api-02, tab-layer-api-04, tab-layer-file-06"


# ------------------------------------------------------------------ crawling


def test_empty_grid_is_reported_instead_of_passing_silently(crawler, renewed_html):
    session = _StubSession(renewed_html)

    result = asyncio.run(crawler._crawl_single(session, DATA_URL, {}))

    # Metadata alone is still worth storing, so the document is not failed.
    assert result.success is True
    assert result.data.api_id == "15072622"
    assert result.data.api_type == "standard"
    assert len(result.data.info) == 25
    assert result.data.standard_grid_table == []

    # ...but the missing grid has to be visible on the result.
    assert len(result.errors) == 1
    assert "Standard grid table is empty" in result.errors[0]
    assert "tab-layer-api-01" in result.errors[0]


def test_csv_metadata_is_kept_and_html_wins_on_conflict(crawler, renewed_html):
    session = _StubSession(renewed_html)
    csv_row = {"소관기관": "CSV값", "CSV전용키": "유지됨"}

    result = asyncio.run(crawler._crawl_single(session, DATA_URL, csv_row))

    assert result.data.info["CSV전용키"] == "유지됨"
    assert result.data.info["소관기관"] == "행정안전부"


def test_crawl_counts_the_documents_whose_grid_came_back_empty(crawler, renewed_html, monkeypatch):
    session = _StubSession(renewed_html)

    async def _session():
        return session

    monkeypatch.setattr(crawler, "create_session", _session)

    results = asyncio.run(crawler.crawl([DATA_URL]))

    assert len(results) == 1
    assert crawler.stats["success"] == 1
    assert crawler.stats["table_crawl_success"] == 0
    assert crawler.stats["table_crawl_failed"] == 1
