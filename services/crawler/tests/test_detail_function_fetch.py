"""상세기능 드롭박스의 모든 옵션을 수집하는지 검증한다.

data.go.kr은 ``select#open_api_detail_select``가 여러 기능을 제시해도 그중 하나만
서버에서 렌더한다. 나머지는 조회하기 버튼이 ``/tcs/dss/selectApiDetailFunction.do``로
가져오며, 옵션마다 요청주소·요청변수·출력결과가 다르다. 여기 쓰이는 조각 응답은
2026-08-05에 15061362에서 실제로 받아 fixture로 저장한 것이며, 테스트는 네트워크를
타지 않는다.
"""

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from bs4 import BeautifulSoup

from crawler.link_spec_builder import UNVERIFIED, build_detail_function_endpoints
from crawler.openapi_crawler import OpenAPICrawler
from infrastructure.quick_summary import QUICK_SUMMARY_PATH

FIXTURES = Path(__file__).parent / "fixtures" / "renewed"
QUICK_SUMMARY_BODY = (FIXTURES / "quick_summary_15000249.json").read_text(encoding="utf-8")

PAGE_URL = "https://www.data.go.kr/data/15061362/openapi.do"
POST_URL = "https://www.data.go.kr/tcs/dss/selectApiDetailFunction.do"
PAGE_DETAIL_PK = "uddi:3c88abcf-d240-472b-b4b4-a8f2e8388bfc_202204011509"

# 페이지가 서버에서 렌더해 둔 옵션과, 조각으로만 받을 수 있는 나머지
RENDERED_SEQ = "41635"
FETCHED_SEQ = "41636"
OPTION_SEQS = ["41635", "41636", "41637", "41638", "41639", "41640", "41641", "41642"]
OPTION_NAMES = [
    "국토교통부_건설업체등록",
    "국토교통부_등록기준사항신고",
    "국토교통부_양도신고",
    "국토교통부_법인합병신고",
    "국토교통부_상속신고",
    "국토교통부_행정처분",
    "국토교통부_행정처분 가처분",
    "국토교통부_폐업신고",
]


def _read(name):
    return (FIXTURES / name).read_text(encoding="utf-8", errors="replace")


@pytest.fixture(scope="module")
def page_html():
    return _read("openapi_old_15061362.html")


@pytest.fixture(scope="module")
def fetched_fragment():
    """41636의 실제 응답. 페이지가 렌더한 41635와 요청주소가 다르다."""
    return _read(f"detail_function_15061362_{FETCHED_SEQ}.html")


@pytest.fixture(scope="module")
def rendered_fragment(page_html):
    """41635의 응답. 포털이 페이지에 심어둔 블록과 같은 내용이다."""
    div = BeautifulSoup(page_html, "lxml").select_one("#apiDetailFunctionDiv")
    return "".join(str(child) for child in div.children)


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
    """상세 페이지 1회 + 옵션별 조각 응답을 돌려주고 요청을 전부 기록한다.

    Quick Summary 조회는 모든 문서가 하는 별개 호출이라 여기서는 관심 밖이다.
    ``posts``에는 상세기능 조회만 남기고, 요약은 고정 응답으로 흘려보낸다.
    """

    def __init__(self, page, answers):
        self._page = page
        self._answers = answers  # oprtinSeqNo -> FakeResponse
        self.posts = []
        self.gets = []

    def get(self, url):
        self.gets.append(url)
        return FakeResponse(self._page)

    def post(self, url, data=None, json=None):
        if QUICK_SUMMARY_PATH in url:
            return FakeResponse(QUICK_SUMMARY_BODY)
        self.posts.append((url, dict(data or {})))
        return self._answers.get((data or {}).get("oprtinSeqNo"), FakeResponse("", 404))


def _session(page, rendered, fetched, overrides=None):
    answers = {RENDERED_SEQ: FakeResponse(rendered)}
    for seq in OPTION_SEQS[1:]:
        answers[seq] = FakeResponse(fetched)
    answers.update(overrides or {})
    return FakeSession(page, answers)


def _crawl(session, url=PAGE_URL, csv_info=None):
    crawler = OpenAPICrawler(SimpleNamespace(max_workers=1, target_api_type=None))
    result = asyncio.run(
        crawler._crawl_static_single(session, url, csv_info if csv_info is not None else {})
    )
    return crawler, result


# --- 수집 범위 ----------------------------------------------------------


def test_every_dropdown_option_becomes_an_endpoint(page_html, rendered_fragment, fetched_fragment):
    """예전에는 기본값 하나만 남아 8개 중 7개를 잃었다."""
    session = _session(page_html, rendered_fragment, fetched_fragment)

    crawler, result = _crawl(session)

    assert result.data.api_type == "openapi_old"
    assert [endpoint["section"] for endpoint in result.data.endpoints] == OPTION_NAMES
    assert crawler.detail_function_fetches == {"ok": 8}


def test_each_option_keeps_its_own_request_address(page_html, rendered_fragment, fetched_fragment):
    """옵션마다 다른 오퍼레이션이다 - 같은 서비스라도 요청주소가 갈린다."""
    _, result = _crawl(_session(page_html, rendered_fragment, fetched_fragment))

    by_name = {endpoint["section"]: endpoint for endpoint in result.data.endpoints}
    assert by_name["국토교통부_건설업체등록"]["path"] == "/1613000/ConAdminInfoSvc1/GongsiReg"
    assert by_name["국토교통부_등록기준사항신고"]["path"] == "/1613000/ConAdminInfoSvc1/GongsiRenew"


def test_parameters_come_from_the_fetched_option_not_the_page(page_html, rendered_fragment, fetched_fragment):
    _, result = _crawl(_session(page_html, rendered_fragment, fetched_fragment))

    fetched = next(e for e in result.data.endpoints if e["section"] == "국토교통부_등록기준사항신고")
    assert len(fetched["parameters"]) == 8
    assert len(fetched["responses"]) == 20
    assert fetched["parameters"][0]["name"] == "ServiceKey"
    assert fetched["tags"] == [PAGE_DETAIL_PK]


def test_the_rendered_option_is_not_stored_twice(page_html, rendered_fragment, fetched_fragment):
    """페이지 블록은 옵션 하나의 사본이므로 병합에서 접힌다."""
    _, result = _crawl(_session(page_html, rendered_fragment, fetched_fragment))

    sections = [endpoint["section"] for endpoint in result.data.endpoints]
    assert sections.count("국토교통부_건설업체등록") == 1
    assert len(result.data.endpoints) == len(OPTION_SEQS)


# --- 요청 계약 ----------------------------------------------------------


def test_request_body_matches_the_pages_own_button(page_html, rendered_fragment, fetched_fragment):
    """publicDataPk를 빼면 포털이 404를 준다 (15000063 실측)."""
    session = _session(page_html, rendered_fragment, fetched_fragment)

    _crawl(session)

    assert session.gets == [PAGE_URL]
    assert [url for url, _ in session.posts] == [POST_URL] * len(OPTION_SEQS)
    assert session.posts[1][1] == {
        "oprtinSeqNo": FETCHED_SEQ,
        "publicDataDetailPk": PAGE_DETAIL_PK,
        "publicDataPk": "15061362",
    }


def test_documents_without_a_dropdown_make_no_extra_request():
    """LINK 문서에는 상세기능 select가 없다."""
    session = _session(_read("openapi_link_15001702.html"), "", "")

    _, result = _crawl(session, url="https://www.data.go.kr/data/15001702/openapi.do",
                       csv_info={"API 유형": "LINK"})

    assert result.data.detail_functions == []
    assert session.posts == []


def test_inline_swagger_documents_never_pay_for_the_dropdown():
    """스펙이 모든 오퍼레이션을 이미 담고 있으므로 조회는 낭비다."""
    html = """
      <input id="publicDataDetailPk" value="uddi:swagger-doc">
      <input id="publicDataPk" value="15000863">
      <select id="open_api_detail_select">
        <option value="1">첫째</option><option value="2">둘째</option>
      </select>
      <script>const swaggerJson = `{"paths": {"/x": {"get": {"summary": "s"}}}}`;</script>
    """
    session = _session(html, "", "")

    _, result = _crawl(session, csv_info={"API 유형": "REST"})

    assert result.data.api_type == "openapi_new"
    assert session.posts == []
    assert result.data.detail_functions == []


# --- 실패 처리 ----------------------------------------------------------


def test_a_failed_option_costs_only_itself(page_html, rendered_fragment, fetched_fragment):
    session = _session(page_html, rendered_fragment, fetched_fragment,
                       overrides={"41639": FakeResponse("", 500)})

    crawler, result = _crawl(session)

    assert len(result.data.endpoints) == len(OPTION_SEQS) - 1
    assert "국토교통부_상속신고" not in [e["section"] for e in result.data.endpoints]
    assert crawler.detail_function_fetches == {"ok": 7, "http_500": 1}
    failed = next(r for r in result.data.detail_functions if r["oprtin_seq_no"] == "41639")
    assert failed == {
        "oprtin_seq_no": "41639",
        "name": "국토교통부_상속신고",
        "status": "http_500",
        "endpoints": 0,
    }


def test_timeouts_and_transport_errors_are_recorded_not_raised(page_html, rendered_fragment, fetched_fragment):
    session = _session(
        page_html, rendered_fragment, fetched_fragment,
        overrides={
            "41637": FakeResponse(raises=asyncio.TimeoutError()),
            "41638": FakeResponse(raises=OSError("connection reset")),
        },
    )

    crawler, result = _crawl(session)

    assert result.success
    assert crawler.detail_function_fetches == {"ok": 6, "timeout": 1, "request_failed": 1}
    broken = next(r for r in result.data.detail_functions if r["oprtin_seq_no"] == "41638")
    assert broken["status"] == "request_failed"
    assert broken["message"] == "connection reset"


def test_a_200_without_tables_is_not_counted_as_an_operation(page_html, rendered_fragment, fetched_fragment):
    session = _session(page_html, rendered_fragment, fetched_fragment,
                       overrides={"41640": FakeResponse("<div>오류가 발생했습니다</div>")})

    crawler, result = _crawl(session)

    assert crawler.detail_function_fetches["no_endpoint"] == 1
    assert len(result.data.endpoints) == len(OPTION_SEQS) - 1


def test_page_endpoint_survives_when_every_fetch_fails(page_html):
    """조회가 전부 죽어도 페이지가 렌더한 기능은 남는다."""
    session = FakeSession(page_html, {})  # 모든 옵션이 404

    crawler, result = _crawl(session)

    assert [e["path"] for e in result.data.endpoints] == ["/1613000/ConAdminInfoSvc1/GongsiReg"]
    assert crawler.detail_function_fetches == {"http_404": 8}
    assert all(record["status"] == "http_404" for record in result.data.detail_functions)


# --- 문서에 남는 기록 ---------------------------------------------------


def test_document_records_every_option_and_its_outcome(page_html, rendered_fragment, fetched_fragment):
    _, result = _crawl(_session(page_html, rendered_fragment, fetched_fragment))

    records = result.data.detail_functions
    assert [r["oprtin_seq_no"] for r in records] == OPTION_SEQS
    assert [r["name"] for r in records] == OPTION_NAMES
    assert all(r["status"] == "ok" and r["endpoints"] == 1 for r in records)


# --- 조각 파서 ----------------------------------------------------------


def test_fragment_is_parsed_without_the_pages_container(fetched_fragment):
    """응답에는 컨테이너가 없다 - 이름은 조각에 딸려온 스크립트에만 나온다."""
    soup = BeautifulSoup(fetched_fragment, "lxml")
    assert soup.select("#apiDetailFunctionDiv, .open-api-detail-result") == []
    assert "apiDetailFunctionDiv" in fetched_fragment  # 스크립트 본문

    endpoints = build_detail_function_endpoints(
        fetched_fragment, "uddi:x", "국토교통부_등록기준사항신고"
    )

    assert len(endpoints) == 1
    endpoint = endpoints[0]
    assert endpoint["path"] == "/1613000/ConAdminInfoSvc1/GongsiRenew"
    assert endpoint["method"] == UNVERIFIED
    assert endpoint["section"] == "국토교통부_등록기준사항신고"
    # 조각의 제목은 "등록기준사항신고 리스트"지만, 문서가 키로 쓰는 이름은 옵션 쪽이다.
    assert endpoint["description"] == "국토교통부_등록기준사항신고"
    assert endpoint["tags"] == ["uddi:x"]


def test_fragment_without_tables_yields_nothing():
    assert build_detail_function_endpoints("<div>없음</div>", "uddi:x", "이름") == []
    assert build_detail_function_endpoints("", "uddi:x", "이름") == []
