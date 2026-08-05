"""포털이 문서마다 붙인 AI Quick Summary를 수집하는지 검증한다.

상세 페이지에는 빈 껍데기(``#quickSummary``)만 있고 내용은
``/tcs/dss/getOrCreateQuickSummary.do``가 채운다. 여기 쓰는 응답은 2026-08-05에
15000249에서 실제로 받아 저장한 것이며, 테스트는 네트워크를 타지 않는다.
"""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from crawler.file_data_crawler import FileDataCrawler
from crawler.openapi_crawler import OpenAPICrawler
from crawler.standard_crawler import StandardCrawler
from infrastructure.quick_summary import (
    QUICK_SUMMARY_PATH,
    fetch_quick_summary,
    headings,
    parse_quick_summary,
    summary_text,
    to_plain_text,
)

FIXTURES = Path(__file__).parent / "fixtures" / "renewed"

SUMMARY_BODY = (FIXTURES / "quick_summary_15000249.json").read_text(encoding="utf-8")
# 존재하지 않는 문서에 대한 실제 응답 (HTTP 500)
ERROR_BODY = '{"code":500,"message":"INTERNAL_SERVER_ERROR"}'


def _fixture(name):
    return (FIXTURES / f"{name}.html").read_text(encoding="utf-8", errors="replace")


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
    """상세 페이지와 Quick Summary 응답만 아는 최소 세션."""

    def __init__(self, page_html="", summary=None):
        self._page = page_html
        self._summary = summary if summary is not None else FakeResponse(SUMMARY_BODY)
        self.gets = []
        self.posts = []

    def get(self, url):
        self.gets.append(url)
        return FakeResponse(self._page)

    def post(self, url, json=None, data=None):
        self.posts.append((url, json if json is not None else dict(data or {})))
        if QUICK_SUMMARY_PATH in url:
            return self._summary
        # 이 테스트가 다루지 않는 다른 POST(상세기능 조회 등)
        return FakeResponse("", 404)


def _summary_posts(session):
    return [(url, body) for url, body in session.posts if QUICK_SUMMARY_PATH in url]


# --- 응답 해석 ----------------------------------------------------------


def test_real_response_becomes_an_indexable_record():
    record = parse_quick_summary(SUMMARY_BODY)

    assert record["status"] == "ok"
    assert record["headings"] == [
        "입법절차 교육 활용",
        "법령심사 업무 매뉴얼",
        "협업 구조 개선",
        "사례 기반 실무 연수",
    ]
    assert "법제처에서 제공하는 입법절차 단계별 안내는" in record["text"]
    # 색인 대상 텍스트에는 태그가 남지 않는다.
    assert "<b>" not in record["text"]
    # 원본은 포털 페이지와 같게 다시 렌더할 수 있도록 그대로 보존한다.
    assert record["markdown"] == json.loads(SUMMARY_BODY)["result"]


def test_plain_text_keeps_paragraphs_but_drops_trailing_spaces():
    text = to_plain_text("<b>제목</b>  \n본문 첫줄  \n\n\n<b>둘째</b>  \n본문")

    assert text == "제목\n본문 첫줄\n\n둘째\n본문"


def test_headings_are_deduplicated_and_whitespace_collapsed():
    assert headings("<b>같은 제목</b>x<b>같은  제목</b>y<b>다른\n제목</b>") == [
        "같은 제목",
        "다른 제목",
    ]
    assert headings("헤딩 없는 본문") == []


@pytest.mark.parametrize("body,expected", [
    ('{"code":200,"message":"OK","result":""}', "empty"),
    ('{"code":200,"message":"OK"}', "empty"),
    ("<html>대기실</html>", "unreadable_body"),
    ("[1, 2]", "unreadable_body"),
    ("", "unreadable_body"),
])
def test_unusable_bodies_are_named_not_guessed(body, expected):
    assert parse_quick_summary(body)["status"] == expected


def test_portal_message_is_kept_when_it_explains_an_empty_result():
    record = parse_quick_summary('{"code":200,"message":"NO_DATA","result":""}')

    assert record == {"status": "empty", "message": "NO_DATA"}


def test_summary_text_accessor_tolerates_missing_records():
    assert summary_text(parse_quick_summary(SUMMARY_BODY)).startswith("입법절차 교육 활용")
    assert summary_text({"status": "timeout"}) == ""
    assert summary_text(None) == ""


# --- 요청 계약 ----------------------------------------------------------


def test_request_sends_only_the_public_data_pk_on_the_page_host():
    """페이지의 executeSearch(pk)는 dType을 넘기지 않고, 넘겨도 응답이 같다."""
    session = FakeSession()

    record = asyncio.run(
        fetch_quick_summary(session, "https://www.data.go.kr/data/15000249/fileData.do", "15000249")
    )

    assert record["status"] == "ok"
    assert session.posts == [
        ("https://www.data.go.kr/tcs/dss/getOrCreateQuickSummary.do",
         {"publicDataPk": "15000249"}),
    ]


def test_http_500_is_recorded_as_an_outcome_not_raised():
    """요약이 없는 문서에 포털이 주는 실제 응답이다."""
    session = FakeSession(summary=FakeResponse(ERROR_BODY, status=500))

    record = asyncio.run(fetch_quick_summary(session, "https://www.data.go.kr/data/1/x.do", "1"))

    assert record == {"status": "http_500", "message": "INTERNAL_SERVER_ERROR"}


@pytest.mark.parametrize("raises,expected", [
    (asyncio.TimeoutError(), "timeout"),
    (OSError("connection reset"), "request_failed"),
])
def test_transport_failures_are_recorded(raises, expected):
    session = FakeSession(summary=FakeResponse(raises=raises))

    record = asyncio.run(fetch_quick_summary(session, "https://www.data.go.kr/data/1/x.do", "1"))

    assert record["status"] == expected


# --- 타입별 크롤러 연결 -------------------------------------------------


def test_openapi_document_stores_the_summary():
    session = FakeSession(_fixture("openapi_new_15000863"))
    crawler = OpenAPICrawler(SimpleNamespace(max_workers=1, target_api_type=None))

    result = asyncio.run(crawler._crawl_static_single(
        session, "https://www.data.go.kr/data/15000863/openapi.do", {}))

    assert result.data.quick_summary["status"] == "ok"
    assert result.data.quick_summary["headings"][0] == "입법절차 교육 활용"
    assert crawler.quick_summary_fetches == {"ok": 1}
    assert _summary_posts(session) == [
        ("https://www.data.go.kr/tcs/dss/getOrCreateQuickSummary.do",
         {"publicDataPk": "15000863"}),
    ]


def test_file_data_document_stores_the_summary():
    session = FakeSession(_fixture("fileData_15000249"))
    crawler = FileDataCrawler(SimpleNamespace(max_workers=1))

    result = asyncio.run(crawler._crawl_single(
        session, "https://www.data.go.kr/data/15000249/fileData.do", {}))

    assert result.data.quick_summary["status"] == "ok"
    assert crawler.quick_summary_fetches == {"ok": 1}
    assert _summary_posts(session)[0][1] == {"publicDataPk": "15000249"}


def test_standard_document_stores_the_summary():
    session = FakeSession(_fixture("standard_15072622"))
    crawler = StandardCrawler(SimpleNamespace(max_workers=1))

    result = asyncio.run(crawler._crawl_single(
        session, "https://www.data.go.kr/data/15072622/standard.do", {}))

    assert result.data.quick_summary["status"] == "ok"
    assert crawler.quick_summary_fetches == {"ok": 1}
    assert _summary_posts(session)[0][1] == {"publicDataPk": "15072622"}


def test_a_missing_summary_does_not_fail_the_document():
    session = FakeSession(_fixture("standard_15072622"),
                          summary=FakeResponse(ERROR_BODY, status=500))
    crawler = StandardCrawler(SimpleNamespace(max_workers=1))

    result = asyncio.run(crawler._crawl_single(
        session, "https://www.data.go.kr/data/15072622/standard.do", {}))

    assert result.success
    assert result.data.info  # 메타데이터는 그대로 수집된다
    assert result.data.quick_summary["status"] == "http_500"
    assert crawler.quick_summary_fetches == {"http_500": 1}
