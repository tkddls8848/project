"""LINK 문서의 제공처 URL 복구 — info['URL'] 동등성 회귀 테스트.

리뉴얼된 상세 페이지는 제공처 URL 을 더 이상 렌더하지 않고, 바로가기 버튼이
``/tcs/dss/selectApiLinkUrl.do`` 를 AJAX 로 조회한다. 여기 박아둔 응답 본문은
조정자가 실제 호출로 확인한 값이다. 세션은 가짜이고 네트워크는 쓰지 않는다.
"""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from crawler.openapi_crawler import OpenAPICrawler
from infrastructure.quick_summary import QUICK_SUMMARY_PATH

FIXTURES = Path(__file__).parent / "fixtures" / "renewed"
QUICK_SUMMARY_BODY = (FIXTURES / "quick_summary_15000249.json").read_text(encoding="utf-8")

LINK_PAGE_URL = "https://www.data.go.kr/data/15001702/openapi.do"
LOOKUP_URL = "https://www.data.go.kr/tcs/dss/selectApiLinkUrl.do?publicDataPk=15001702"
PAGE_DETAIL_PK = "uddi:bdcc718f-b253-4f8d-9f18-f3bbfc60fc24_202509011426"

# 실측 응답(Content-Type 은 text/html 이지만 본문은 JSON 이다).
LOOKUP_OK = json.dumps(
    {
        "publicDataDetailPk": PAGE_DETAIL_PK,
        "linkUrl": "https://www.nfqs.go.kr/hpmg/api/actionApiDetail.do?apiCd=008",
        "status": True,
    }
)
LOOKUP_OK_FRAGMENT = json.dumps(
    {
        "publicDataDetailPk": PAGE_DETAIL_PK,
        "linkUrl": "http://www.jejuits.go.kr/open_api/open_apiView.do#its",
        "status": True,
    }
)


def _crawler():
    return OpenAPICrawler(SimpleNamespace(max_workers=1, target_api_type=None))


def _fixture(name):
    return (FIXTURES / f"{name}.html").read_text(encoding="utf-8", errors="replace")


@pytest.fixture(scope="module")
def link_page():
    return _fixture("openapi_link_15001702")


@pytest.fixture(scope="module")
def swagger_page():
    return _fixture("openapi_new_15000863")


class FakeResponse:
    def __init__(self, body="", status=200, raises=None):
        self._body = body
        self.status = status
        self._raises = raises

    async def text(self):
        return self._body

    async def __aenter__(self):
        if self._raises is not None:
            raise self._raises
        return self

    async def __aexit__(self, *exc_info):
        return False


class FakeSession:
    """Serves the detail page, plus one scripted answer for the lookup call.

    Every GET is recorded so a test can prove that a non-LINK document makes no
    lookup call at all. The lookup is a GET; the POSTs a document also makes
    (Quick Summary, detail functions) are answered but kept out of ``requested``
    so those assertions stay about the lookup.
    """

    def __init__(self, page_html, lookup_body=None, lookup_status=200, lookup_raises=None):
        self._page_html = page_html
        self._lookup = FakeResponse(lookup_body or "", lookup_status, lookup_raises)
        self.requested = []
        self.posted = []

    def get(self, url):
        self.requested.append(url)
        if "selectApiLinkUrl" in url:
            return self._lookup
        return FakeResponse(self._page_html)

    def post(self, url, data=None, json=None):
        self.posted.append((url, json if json is not None else dict(data or {})))
        if QUICK_SUMMARY_PATH in url:
            return FakeResponse(QUICK_SUMMARY_BODY)
        return FakeResponse("", 404)


def _crawl(session, url=LINK_PAGE_URL, csv_info=None):
    crawler = _crawler()
    result = asyncio.run(
        crawler._crawl_static_single(session, url, csv_info if csv_info is not None else {"API 유형": "LINK"})
    )
    return crawler, result


def _lookup_evidence(result):
    return result.data.api_type_evidence["link_url_lookup"]


# --- 정상 경로 ----------------------------------------------------------


def test_link_document_recovers_the_provider_url_into_info(link_page):
    crawler, result = _crawl(FakeSession(link_page, LOOKUP_OK))

    assert result.success, result.errors
    assert result.data.info["URL"] == "https://www.nfqs.go.kr/hpmg/api/actionApiDetail.do?apiCd=008"
    # The rest of the document is untouched by the extra call.
    assert len(result.data.info) >= 18
    assert result.data.api_type == "openapi_link"
    assert crawler.link_url_lookups == {"ok": 1}


def test_lookup_uses_the_documented_endpoint_on_the_page_host(link_page):
    session = FakeSession(link_page, LOOKUP_OK)

    _crawl(session)

    assert session.requested == [LINK_PAGE_URL, LOOKUP_URL]


def test_recovered_url_is_recorded_as_evidence(link_page):
    _, result = _crawl(FakeSession(link_page, LOOKUP_OK))

    evidence = _lookup_evidence(result)
    assert evidence["status"] == "ok"
    assert evidence["url"].startswith("https://www.nfqs.go.kr/")
    assert evidence["request_url"] == LOOKUP_URL


def test_response_detail_pk_is_only_flagged_when_it_matches_the_page(link_page):
    """The page's hidden input already carries it, so the value is not stored twice."""
    _, result = _crawl(FakeSession(link_page, LOOKUP_OK))

    evidence = _lookup_evidence(result)
    assert result.data.operation_ids == [PAGE_DETAIL_PK]
    assert evidence["detail_pk_matches_page"] is True
    assert "public_data_detail_pk" not in evidence


def test_a_disagreeing_detail_pk_is_kept(link_page):
    body = json.dumps(
        {"publicDataDetailPk": "uddi:other_202601010000", "linkUrl": "https://a.go.kr/api/x", "status": True}
    )

    _, result = _crawl(FakeSession(link_page, body))

    evidence = _lookup_evidence(result)
    assert evidence["detail_pk_matches_page"] is False
    assert evidence["public_data_detail_pk"] == "uddi:other_202601010000"


# --- external_endpoint_urls 반영 ----------------------------------------


def test_provider_url_joins_the_phase_b_endpoint_list(link_page):
    _, result = _crawl(FakeSession(link_page, LOOKUP_OK))

    assert result.data.external_endpoint_urls == [
        "https://www.nfqs.go.kr/hpmg/api/actionApiDetail.do?apiCd=008"
    ]


def test_declared_url_skips_the_scrape_heuristic_but_drops_the_fragment(link_page):
    """/open_api/ fails the scraped-URL path heuristic; a declared URL is exempt."""
    _, result = _crawl(FakeSession(link_page, LOOKUP_OK_FRAGMENT))

    assert result.data.info["URL"] == "http://www.jejuits.go.kr/open_api/open_apiView.do#its"
    assert result.data.external_endpoint_urls == [
        "http://www.jejuits.go.kr/open_api/open_apiView.do"
    ]


def test_self_referential_provider_url_stays_out_of_the_endpoint_list(link_page):
    body = json.dumps(
        {"linkUrl": "https://www.data.go.kr/data/15001702/openapi.do", "status": True}
    )

    _, result = _crawl(FakeSession(link_page, body))

    assert result.data.info["URL"] == "https://www.data.go.kr/data/15001702/openapi.do"
    assert result.data.external_endpoint_urls == []


# --- 실패를 삼키지 않는다 ------------------------------------------------


@pytest.mark.parametrize(
    "session_kwargs,expected_status",
    [
        ({"lookup_body": json.dumps({"status": False, "errorDc": "권한이 없습니다."})}, "declined"),
        ({"lookup_body": json.dumps({"linkUrl": "", "status": True})}, "empty"),
        ({"lookup_body": "<html>error page</html>"}, "unreadable_body"),
        ({"lookup_body": json.dumps(["not", "a", "dict"])}, "unreadable_body"),
        ({"lookup_body": "{}", "lookup_status": 500}, "http_500"),
        ({"lookup_raises": asyncio.TimeoutError()}, "timeout"),
        ({"lookup_raises": ConnectionResetError("peer reset")}, "request_failed"),
    ],
)
def test_a_failed_lookup_leaves_no_url_but_says_why(link_page, session_kwargs, expected_status):
    crawler, result = _crawl(FakeSession(link_page, **session_kwargs))

    # The document is still crawled: only the URL is missing.
    assert result.success, result.errors
    assert result.data.api_type == "openapi_link"
    assert len(result.data.info) >= 18
    assert "URL" not in result.data.info
    assert result.data.external_endpoint_urls == []

    evidence = _lookup_evidence(result)
    assert evidence["status"] == expected_status
    assert evidence["url"] is None
    assert crawler.link_url_lookups == {expected_status: 1}


def test_declined_lookup_keeps_the_portal_message(link_page):
    body = json.dumps({"status": False, "errorDc": "권한이 없습니다."})

    _, result = _crawl(FakeSession(link_page, body))

    assert _lookup_evidence(result)["message"] == "권한이 없습니다."


def test_a_broken_lookup_does_not_stop_the_other_documents(link_page):
    """One failure must not propagate out of the per-document coroutine."""
    crawler = _crawler()
    sessions = [
        FakeSession(link_page, lookup_raises=ConnectionResetError("boom")),
        FakeSession(link_page, LOOKUP_OK),
    ]

    async def run_all():
        return await asyncio.gather(
            *(crawler._crawl_static_single(s, LINK_PAGE_URL, {"API 유형": "LINK"}) for s in sessions)
        )

    results = asyncio.run(run_all())

    assert [r.success for r in results] == [True, True]
    assert [r.data.info.get("URL") for r in results] == [
        None,
        "https://www.nfqs.go.kr/hpmg/api/actionApiDetail.do?apiCd=008",
    ]
    assert crawler.link_url_lookups == {"request_failed": 1, "ok": 1}


# --- 호출하지 않아야 하는 경우 -------------------------------------------


def test_a_non_link_document_never_asks_for_a_provider_url(swagger_page):
    session = FakeSession(swagger_page, LOOKUP_OK)
    page_url = "https://www.data.go.kr/data/15000863/openapi.do"

    crawler, result = _crawl(session, page_url, {"API 유형": "REST"})

    assert result.data.api_type == "openapi_new"
    assert session.requested == [page_url]
    assert "link_url_lookup" not in result.data.api_type_evidence
    assert "URL" not in result.data.info
    assert crawler.link_url_lookups == {}


def test_a_page_that_still_renders_the_url_is_not_asked_again():
    """Pre-renewal markup carried the 제공처 URL in the metadata table."""
    html = (
        '<input type="hidden" id="publicDataDetailPk" value="uddi:legacy_202001010000">'
        "<table>"
        "<tr><th>API 유형</th><td>LINK</td></tr>"
        "<tr><th>제공기관</th><td>국립수산물품질관리원</td></tr>"
        "<tr><th>URL</th><td>https://legacy.example.go.kr/api/list.do</td></tr>"
        "</table>"
    )
    session = FakeSession(html, LOOKUP_OK)

    crawler, result = _crawl(session, LINK_PAGE_URL, {})

    assert result.data.api_type == "openapi_link"
    assert session.requested == [LINK_PAGE_URL]
    assert result.data.info["URL"] == "https://legacy.example.go.kr/api/list.do"
    assert _lookup_evidence(result)["status"] == "page_provided_url"
    assert result.data.external_endpoint_urls == ["https://legacy.example.go.kr/api/list.do"]
    assert crawler.link_url_lookups == {"page_provided_url": 1}


def test_a_filtered_out_document_costs_no_lookup(link_page):
    crawler = OpenAPICrawler(SimpleNamespace(max_workers=1, target_api_type="openapi_new"))
    session = FakeSession(link_page, LOOKUP_OK)

    result = asyncio.run(crawler._crawl_static_single(session, LINK_PAGE_URL, {"API 유형": "LINK"}))

    assert result.success and result.data is None
    assert session.requested == [LINK_PAGE_URL]
    assert crawler.link_url_lookups == {}
