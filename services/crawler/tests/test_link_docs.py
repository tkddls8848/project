from link_docs import build_tasks, coverage, extract_api_rules
from link_docs.runner import LinkDocResult


def test_extracts_request_and_response_tables_from_agency_markup():
    # Deliberately not data.go.kr markup: the extractor keys off table header
    # semantics, not any one site's classes or ids.
    html = """
        <h3>요청 파라미터</h3>
        <table>
          <tr><th>항목명</th><th>설명</th><th>타입</th><th>필수여부</th></tr>
          <tr><td>serviceKey</td><td>인증키</td><td>String</td><td>필수</td></tr>
          <tr><td>numOfRows</td><td>한 페이지 결과 수</td><td>int</td><td>선택</td></tr>
        </table>
        <h3>응답 항목</h3>
        <table>
          <tr><th>항목명</th><th>설명</th><th>타입</th></tr>
          <tr><td>totalCount</td><td>전체 건수</td><td>int</td></tr>
        </table>
    """

    result = extract_api_rules(html, "https://agency.example.go.kr/api/view?id=1")

    assert result.is_productive
    assert [row["name"] for row in result.request_parameters] == ["serviceKey", "numOfRows"]
    assert [row["name"] for row in result.response_fields] == ["totalCount"]
    assert result.endpoints[0]["parameters"][0]["required"] == "필수"
    assert result.evidence["reason"] == "parameter_tables_found"


def test_layout_tables_are_not_mistaken_for_parameter_tables():
    html = """
        <table><tr><td>메뉴</td><td>홈</td></tr></table>
        <table><tr><th>공지</th></tr><tr><td>점검 안내</td></tr></table>
    """

    result = extract_api_rules(html, "https://agency.example.go.kr/notice")

    assert not result.is_productive
    assert result.parameter_tables == 0
    assert result.evidence["needs_rendered_retry"] is True


def test_javascript_rendered_page_is_flagged_rather_than_guessed():
    html = "<html><body><div id='root'></div><script>renderApiDoc();</script></body></html>"

    result = extract_api_rules(html, "https://agency.example.go.kr/spa")

    assert not result.is_productive
    assert result.endpoints == []
    assert result.evidence["reason"] == "no_parameter_table_in_static_html"


def test_unstated_method_stays_unverified():
    html = """
        <table>
          <tr><th>항목명</th><th>설명</th></tr>
          <tr><td>pageNo</td><td>페이지 번호</td></tr>
        </table>
    """

    result = extract_api_rules(html, "https://agency.example.go.kr/x")

    assert result.method == "unverified"
    assert result.endpoints[0]["method"] == "unverified"


def test_build_tasks_uses_info_url_and_drops_self_links():
    records = [
        {"api_id": "1", "info": {"URL": "https://agency.example.go.kr/api/1", "목록명": "A"}},
        {"api_id": "2", "info": {"URL": "https://www.data.go.kr/data/2/openapi.do"}},
        {"api_id": "3", "info": {"URL": ""}},
        {"api_id": "4", "info": {"URL": "ftp://agency.example.go.kr/x"}},
    ]

    tasks = build_tasks(records)

    assert [task.api_id for task in tasks] == ["1"]
    assert tasks[0].host == "agency.example.go.kr"


def test_coverage_reports_per_host_render_candidates():
    results = [
        LinkDocResult(api_id="1", url="u", host="a.go.kr", status="ok"),
        LinkDocResult(api_id="2", url="u", host="a.go.kr", status="empty"),
        LinkDocResult(api_id="3", url="u", host="b.go.kr", status="blocked"),
    ]

    report = coverage(results)

    assert report["documents"] == 3
    assert report["hosts"] == 2
    assert report["static_extracted"] == 1
    assert report["static_coverage_pct"] == 33.3
    assert report["needs_rendered_retry"] == 1
    assert report["per_host"]["a.go.kr"]["needs_render"] == 1
