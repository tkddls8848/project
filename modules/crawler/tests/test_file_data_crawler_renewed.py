"""fileData crawling against the 2026-08 renewed portal markup.

The renewal removed the ``<table>`` metadata layout, and on this particular
dataset it also removed the JSON-LD block the download fast path relied on.
These tests pin both the new parsing route and the fallback that has to carry
datasets with no JSON-LD, using a saved page — nothing here touches the network.
"""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from crawler.file_data_crawler import FileDataCrawler

FIXTURE = Path(__file__).parent / "fixtures" / "renewed" / "fileData_15000249.html"
DETAIL_PK = "uddi:d4688e5d-983f-42bb-9268-feb029292456"
DATA_URL = "https://www.data.go.kr/data/15000249/fileData.do"


def _config():
    return SimpleNamespace(max_workers=1, target_api_type=None)


@pytest.fixture(scope="module")
def renewed_html():
    return FIXTURE.read_text(encoding="utf-8")


@pytest.fixture
def crawler():
    return FileDataCrawler(_config())


# --------------------------------------------------------------------- stubs


class _StubResponse:
    def __init__(self, body, status=200):
        self._body = body
        self.status = status
        self.headers = {"Content-Type": "application/json"}

    async def text(self):
        return self._body

    async def json(self):
        return json.loads(self._body)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _StubSession:
    """Serves canned bodies by URL and records what was requested."""

    def __init__(self, routes):
        self.routes = routes
        self.requested = []

    def get(self, url, **kwargs):
        self.requested.append(url)
        for fragment, body in self.routes.items():
            if fragment in url:
                if body is None:
                    return _StubResponse("", status=404)
                return _StubResponse(body)
        return _StubResponse("", status=404)


def _download_payload():
    """Shape of a real selectFileDataDownload.do response (verified 2026-08-03)."""
    return json.dumps(
        {
            "dataSetFileDetailInfo": {"atachFileYn": "Y", "publicDataPk": "15000249"},
            "fileDataRegistVO": {
                "dataNm": "법제처_법제업무편람_20250115",
                "atchFileId": "FILE_000000003665965",
                "fileDetailSn": "1",
            },
            "atchFileId": "FILE_000000003665965",
            "fileDetailSn": "1",
            "status": True,
        },
        ensure_ascii=False,
    )


def _crawl(crawler, session):
    return asyncio.run(crawler._crawl_single(session, DATA_URL, {}))


# ------------------------------------------------------------------ metadata


def test_renewed_page_yields_full_metadata_through_shared_parser(crawler, renewed_html):
    from infrastructure.detail_page_parser import extract_detail_info

    info = extract_detail_info(renewed_html, renewed_html)

    assert len(info) == 26
    assert info["파일데이터명"] == "법제처_법제업무편람_20250115"
    assert info["제공기관"] == "법제처"
    assert info["관리부서명"] == "국가법령정보센터"


def test_crawl_extracts_metadata_from_renewed_markup(crawler, renewed_html):
    session = _StubSession({"/data/15000249/fileData.do": renewed_html})

    result = _crawl(crawler, session)

    assert result.success is True
    assert result.data.info["파일데이터명"] == "법제처_법제업무편람_20250115"
    assert result.data.info["제공기관"] == "법제처"
    assert result.data.info["관리부서명"] == "국가법령정보센터"
    assert len(result.data.info) == 26


def test_soup_is_not_strained_past_the_renewed_key_blocks(crawler, renewed_html):
    """The old ['table', 'input'] strainer dropped every <li> metadata block."""
    soup = crawler.make_soup(renewed_html)

    assert len(soup.select("strong.key")) == 26
    assert soup.select("table") == []


def test_csv_metadata_is_preserved_and_overlaid_by_the_page(crawler, renewed_html):
    session = _StubSession({"/data/15000249/fileData.do": renewed_html})

    result = asyncio.run(
        crawler._crawl_single(session, DATA_URL, {"분류체계": "from-csv", "목록명": "csv-only"})
    )

    # The page wins where both supply a key; CSV-only keys survive.
    assert result.data.info["분류체계"] == "일반공공행정 - 법제"
    assert result.data.info["목록명"] == "csv-only"


# ------------------------------------------------------------- operation ids


def test_operation_ids_come_from_the_page_input(crawler, renewed_html):
    session = _StubSession({"/data/15000249/fileData.do": renewed_html})

    result = _crawl(crawler, session)

    assert result.data.operation_ids == [DETAIL_PK]


def test_infuser_is_not_queried_when_the_page_supplies_the_uddi(crawler, renewed_html):
    session = _StubSession({"/data/15000249/fileData.do": renewed_html})

    _crawl(crawler, session)

    assert not any("infuser" in url for url in session.requested)


# ------------------------------------------------------------ jsonld absence


def test_renewed_filedata_page_has_no_jsonld(crawler, renewed_html):
    """This dataset is agency-hosted, so it carries no JSON-LD at all."""
    assert crawler._extract_jsonld_datasets(renewed_html) == []
    assert crawler._extract_jsonld_download_urls(renewed_html, "any", None) == {}


def test_atch_file_id_string_in_page_is_not_treated_as_a_file_id(crawler, renewed_html):
    """The only 'atchFileId' on the page is the captcha handler's parameter name."""
    assert "atchFileId" in renewed_html
    assert crawler._extract_jsonld_download_urls(renewed_html, "any", None) == {}


def test_crawl_completes_without_jsonld_fastpath(crawler, renewed_html):
    session = _StubSession({"/data/15000249/fileData.do": renewed_html})

    result = _crawl(crawler, session)

    assert result.success is True
    assert crawler.stats.get("jsonld_fastpath", 0) == 0
    assert result.errors == []


# ------------------------------------------------------------ fallback chain


def test_fallback_builds_download_url_from_selectfiledatadownload(crawler, renewed_html):
    session = _StubSession(
        {
            "/data/15000249/fileData.do": renewed_html,
            "selectFileDataDownload.do": _download_payload(),
        }
    )

    result = _crawl(crawler, session)

    assert result.data.download_urls == {
        "법제처_법제업무편람_20250115": (
            "https://www.data.go.kr/cmm/cmm/fileDownload.do"
            "?atchFileId=FILE_000000003665965&fileDetailSn=1"
        )
    }


def test_fallback_requests_the_uddi_from_the_page(crawler, renewed_html):
    session = _StubSession(
        {
            "/data/15000249/fileData.do": renewed_html,
            "selectFileDataDownload.do": _download_payload(),
        }
    )

    _crawl(crawler, session)

    assert any(
        f"publicDataPk=15000249&publicDataDetailPk={DETAIL_PK}" in url
        for url in session.requested
    )


def test_dataset_without_attached_file_still_succeeds(crawler, renewed_html):
    """atachFileYn 'N' datasets yield metadata and no download URL, not an error."""
    empty = json.dumps({"dataSetFileDetailInfo": {"atachFileYn": "N"}, "status": False})
    session = _StubSession(
        {
            "/data/15000249/fileData.do": renewed_html,
            "selectFileDataDownload.do": empty,
        }
    )

    result = _crawl(crawler, session)

    assert result.success is True
    assert result.data.download_urls == {}
    assert result.data.info["파일데이터명"] == "법제처_법제업무편람_20250115"


def test_download_endpoint_failure_does_not_sink_the_crawl(crawler, renewed_html):
    session = _StubSession({"/data/15000249/fileData.do": renewed_html})

    result = _crawl(crawler, session)

    assert result.success is True
    assert result.data.download_urls == {}
    assert result.data.info["제공기관"] == "법제처"


# ------------------------------------------------------- legacy compatibility


LEGACY_HTML = """
<html><body>
  <table class="fileDataDetail">
    <tr><th>파일데이터명</th><td>구형_데이터_20200101</td></tr>
    <tr><th>제공기관</th><td>구형기관</td></tr>
  </table>
  <input type="hidden" id="publicDataDetailPk" value="uddi:legacy-0001" />
  <script type="application/ld+json">
  {"@type": "Dataset", "name": "legacy",
   "distribution": [{"@type": "DataDownload", "encodingFormat": "CSV",
   "contentUrl": "https://www.data.go.kr/cmm/cmm/fileDownload.do?atchFileId=FILE_LEGACY&amp;fileDetailSn=1"}]}
  </script>
</body></html>
"""


def test_pre_renewal_markup_still_parses(crawler):
    session = _StubSession({"/data/15000249/fileData.do": LEGACY_HTML})

    result = _crawl(crawler, session)

    assert result.data.info["파일데이터명"] == "구형_데이터_20200101"
    assert result.data.info["제공기관"] == "구형기관"
    assert result.data.operation_ids == ["uddi:legacy-0001"]


def test_jsonld_fastpath_still_wins_when_the_page_has_one(crawler):
    session = _StubSession({"/data/15000249/fileData.do": LEGACY_HTML})

    result = _crawl(crawler, session)

    assert crawler.stats["jsonld_fastpath"] == 1
    assert result.data.download_urls == {
        "구형_데이터_20200101": (
            "https://www.data.go.kr/cmm/cmm/fileDownload.do"
            "?atchFileId=FILE_LEGACY&fileDetailSn=1"
        )
    }
    assert not any("selectFileDataDownload" in url for url in session.requested)


def test_extract_table_bs_alias_delegates_to_the_shared_parser(crawler, renewed_html):
    """metadata_updater borrows this helper; it must keep working on both vintages."""
    assert crawler._extract_table_bs(crawler.make_soup(LEGACY_HTML))["제공기관"] == "구형기관"
    assert crawler._extract_table_bs(crawler.make_soup(renewed_html))["제공기관"] == "법제처"
