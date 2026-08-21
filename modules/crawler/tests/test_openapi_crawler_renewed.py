"""OpenAPI 상세 페이지 파싱 — 2026-08 리뉴얼 마크업과 옛 마크업 양쪽 회귀 테스트.

픽스처는 리뉴얼 후 실제로 내려받은 페이지다(`tests/fixtures/renewed/`).
네트워크는 쓰지 않는다.
"""

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from bs4 import BeautifulSoup

from crawler.openapi_crawler import DETAIL_TAGS, OpenAPICrawler
from infrastructure.detail_page_parser import extract_detail_info

FIXTURES = Path(__file__).parent / "fixtures" / "renewed"


def _config():
    return SimpleNamespace(max_workers=1, target_api_type=None)


def _crawler():
    return OpenAPICrawler(_config())


def _fixture(name):
    return (FIXTURES / name).read_text(encoding="utf-8", errors="replace")


@pytest.fixture(scope="module")
def pages():
    return {name: _fixture(f"{name}.html") for name in (
        "openapi_new_15000863",
        "openapi_old_15061362",
        "openapi_link_15001702",
    )}


class FakeResponse:
    def __init__(self, html, status=200):
        self._html = html
        self.status = status

    async def text(self):
        return self._html

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False


class FakeSession:
    """Serves one stored page; asserts nothing leaves for data.go.kr."""

    def __init__(self, html):
        self._html = html
        self.requested = []

    def get(self, url):
        self.requested.append(url)
        return FakeResponse(self._html)


# --- inline swaggerJson -------------------------------------------------


@pytest.mark.parametrize("keyword", ["var", "const", "let"])
def test_swagger_literal_is_read_whatever_binding_declares_it(keyword):
    crawler = _crawler()
    html = f'<script>{keyword} swaggerJson = `{{"swagger":"2.0","paths":{{}}}}`;</script>'

    assert crawler._extract_swagger_json_from_html(html) == {"swagger": "2.0", "paths": {}}


@pytest.mark.parametrize("literal", ["``", "`  `", "`\n`"])
def test_empty_literal_reads_as_no_inline_spec(literal):
    """`const swaggerJson = ``;` is how a page says it carries no spec."""
    crawler = _crawler()
    html = f"<script>const swaggerJson = {literal};</script>"

    assert crawler._find_swagger_literal(html) is None
    assert crawler._extract_swagger_json_from_html(html) is None


def test_renewed_openapi_new_page_yields_a_parseable_spec(pages):
    crawler = _crawler()

    swagger = crawler._extract_swagger_json_from_html(pages["openapi_new_15000863"])

    assert swagger is not None
    assert swagger["host"] == "apis.data.go.kr/6300000/openapi2022/restrnt"
    assert list(swagger["paths"]) == ["/getrestrnt"]


@pytest.mark.parametrize("name", ["openapi_old_15061362", "openapi_link_15001702"])
def test_renewed_pages_without_a_spec_report_none(pages, name):
    assert _crawler()._extract_swagger_json_from_html(pages[name]) is None


def test_unparseable_literal_is_not_mistaken_for_a_spec():
    crawler = _crawler()
    html = "const swaggerJson = `{not valid json}`;"

    assert crawler._find_swagger_literal(html) == "{not valid json}"
    assert crawler._extract_swagger_json_from_html(html) is None


# --- 메타데이터 (공유 파서 경유) ----------------------------------------


@pytest.mark.parametrize(
    "name,tel",
    [
        ("openapi_new_15000863", "042-270-3444"),
        ("openapi_old_15061362", "02-3496-3842"),
        ("openapi_link_15001702", "051-400-5641"),
    ],
)
def test_renewed_metadata_and_script_injected_phone_number(pages, name, tel):
    html = pages[name]
    soup = _crawler().make_soup(html, DETAIL_TAGS)

    info = extract_detail_info(soup, html)

    assert len(info) >= 18
    assert info["제공기관"]
    assert info["관리부서 전화번호"] == tel


@pytest.mark.parametrize(
    "name", ["openapi_new_15000863", "openapi_old_15061362", "openapi_link_15001702"]
)
def test_strainer_tag_list_keeps_the_whole_metadata_block(pages, name):
    """The strainer trims parse cost on these ~200KB pages; it must not trim data."""
    html = pages[name]

    strained = extract_detail_info(_crawler().make_soup(html, DETAIL_TAGS), html)
    whole = extract_detail_info(BeautifulSoup(html, "lxml"), html)

    assert strained == whole


def test_pre_renewal_table_markup_still_parses():
    html = (
        '<table><tr><th>제공기관</th><td>국토교통부</td></tr>'
        '<tr><th>API 유형</th><td>REST</td></tr></table>'
        '<script>var telNo = "0234963842";</script>'
    )
    soup = _crawler().make_soup(html, DETAIL_TAGS)

    info = extract_detail_info(soup, html)

    assert info["제공기관"] == "국토교통부"
    assert info["API 유형"] == "REST"
    assert info["관리부서 전화번호"] == "02-3496-3842"


# --- api_type 판별 ------------------------------------------------------


def test_renewed_new_page_is_detected_as_openapi_new(pages):
    crawler = _crawler()
    html = pages["openapi_new_15000863"]
    soup = crawler.make_soup(html, DETAIL_TAGS)
    info = extract_detail_info(soup, html)
    swagger = crawler._extract_swagger_json_from_html(html)

    assert crawler._detect_api_type(info, soup, swagger) == "openapi_new"
    assert crawler._build_api_type_evidence(info, soup, swagger, html) == {
        "reason": "inline_swagger_json_parsed",
        "csv_api_type": "REST",
        "csv_declares_link": False,
        "swagger_json_parsed": True,
        "swagger_marker_present": True,
        "public_data_detail_pk_present": True,
    }


def test_renewed_old_page_is_detected_as_openapi_old(pages):
    crawler = _crawler()
    html = pages["openapi_old_15061362"]
    soup = crawler.make_soup(html, DETAIL_TAGS)
    info = extract_detail_info(soup, html)

    assert crawler._extract_swagger_json_from_html(html) is None
    assert crawler._detect_api_type(info, soup, None) == "openapi_old"
    # An empty literal is no inline spec at all, so the evidence must not claim
    # a spec was found and failed to parse.
    evidence = crawler._build_api_type_evidence(info, soup, None, html)
    assert evidence["swagger_marker_present"] is False
    assert evidence["reason"] == "legacy_html_without_inline_swagger"


def test_link_page_is_detected_from_the_csv_declaration(pages):
    crawler = _crawler()
    html = pages["openapi_link_15001702"]
    soup = crawler.make_soup(html, DETAIL_TAGS)
    info = dict({"API 유형": "LINK"})
    info.update(extract_detail_info(soup, html))

    assert crawler._detect_api_type(info, soup, None) == "openapi_link"
    assert crawler._build_api_type_evidence(info, soup, None, html)["reason"] == (
        "csv_api_type_declares_link"
    )


def test_renewed_link_page_declares_its_type_in_html_too(pages):
    """The renewed page renders API 유형 itself, so LINK survives a missing CSV row."""
    crawler = _crawler()
    html = pages["openapi_link_15001702"]
    soup = crawler.make_soup(html, DETAIL_TAGS)

    info = extract_detail_info(soup, html)

    assert info["API 유형"] == "LINK"
    assert crawler._detect_api_type(info, soup, None) == "openapi_link"


# --- 외부 엔드포인트 URL ------------------------------------------------


def test_external_endpoint_url_survives_a_versioned_path_segment(pages):
    """openapi_new 픽스처의 oprtinUrl 은 /openapi2022/ 처럼 번호가 붙는다."""
    urls = _crawler()._extract_external_endpoint_urls(pages["openapi_new_15000863"])

    assert urls == ["http://bigdata.daejeon.go.kr/openapi2022/restrnt.do"]


@pytest.mark.parametrize("name", ["openapi_old_15061362", "openapi_link_15001702"])
def test_pages_without_an_external_endpoint_report_none(pages, name):
    """These two carry no external endpoint in the served HTML.

    openapi_old routes through the portal gateway (apis.data.go.kr), which is
    excluded on purpose; the LINK page fetches its 제공처 URL over AJAX
    (``/tcs/dss/selectApiLinkUrl.do``), so it is not in the page at all.
    """
    assert _crawler()._extract_external_endpoint_urls(pages[name]) == []


# --- 상세 페이지 크롤 전체 경로 ------------------------------------------


@pytest.mark.parametrize(
    "name,api_id,csv_info,expected_type,expected_pk,extra_requests",
    [
        (
            "openapi_new_15000863",
            "15000863",
            {"API 유형": "REST"},
            "openapi_new",
            "uddi:3e2e1bec-9f11-4d55-969d-952ece9d8f79_202301161728",
            [],
        ),
        (
            "openapi_link_15001702",
            "15001702",
            {"API 유형": "LINK"},
            "openapi_link",
            "uddi:bdcc718f-b253-4f8d-9f18-f3bbfc60fc24_202509011426",
            # A LINK document also asks the portal for its 제공처 URL; see
            # test_link_url_resolution.py.
            ["https://www.data.go.kr/tcs/dss/selectApiLinkUrl.do?publicDataPk=15001702"],
        ),
    ],
)
def test_crawling_a_renewed_page_end_to_end(
    pages, name, api_id, csv_info, expected_type, expected_pk, extra_requests
):
    crawler = _crawler()
    session = FakeSession(pages[name])
    url = f"https://www.data.go.kr/data/{api_id}/openapi.do"

    result = asyncio.run(crawler._crawl_static_single(session, url, csv_info))

    assert result.success, result.errors
    assert result.data.api_id == api_id
    assert result.data.api_type == expected_type
    assert result.data.operation_ids == [expected_pk]
    # csv_info is the base; the page's own metadata is merged over it.
    assert len(result.data.info) >= 18
    assert result.data.info["제공기관"]
    assert session.requested == [url] + extra_requests


def test_swagger_backed_page_keeps_its_spec_and_endpoints(pages):
    crawler = _crawler()
    session = FakeSession(pages["openapi_new_15000863"])

    result = asyncio.run(
        crawler._crawl_static_single(session, "https://www.data.go.kr/data/15000863/openapi.do", {})
    )

    assert result.data.swagger_json["info"]["title"] == "대전광역시 문화관광(모범음식점)"
    assert [endpoint["path"] for endpoint in result.data.endpoints] == ["/getrestrnt"]
