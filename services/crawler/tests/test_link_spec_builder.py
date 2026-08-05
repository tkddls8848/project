from pathlib import Path

import pytest

from crawler.link_spec_builder import (
    UNVERIFIED,
    build_link_endpoints,
    list_detail_functions,
)
from infrastructure.nara_parser import NaraParser


RENEWED_FIXTURES = Path(__file__).parent / 'fixtures' / 'renewed'


def read_renewed(name):
    """Load a 2026-08 renewal capture; tests never touch data.go.kr."""
    return (RENEWED_FIXTURES / name).read_text(encoding='utf-8', errors='replace')


@pytest.fixture
def link_detail_html():
    result = '''
      <div class="open-api-detail-result">
        <h4 class="tit">관측값을 조회하는 기능</h4>
        <div class="box-gray"><ul>
          <li><strong>HTTP Method</strong> POST</li>
          <li><strong>서비스URL</strong> https://api.example.go.kr/v1/observations?key=x</li>
        </ul></div>
        <h4>요청변수(Request Parameter)</h4>
        <table><thead><tr>
          <th>항목명(국문)</th><th>항목명(영문)</th><th>항목크기</th>
          <th>항목구분</th><th>샘플데이터</th><th>항목설명</th><th>데이터타입</th>
        </tr></thead><tbody>
          <tr><td>기준연도</td><td>year</td><td>4</td><td>필수</td><td>2025</td><td>조회 연도</td><td>string</td></tr>
          <tr><td>페이지</td><td>pageNo</td><td>3</td><td>옵션</td><td>1</td><td>페이지 번호</td><td>integer</td></tr>
        </tbody></table>
        <h4>출력결과(Response Element)</h4>
        <table><thead><tr>
          <th>항목명(국문)</th><th>항목명(영문)</th><th>항목크기</th>
          <th>항목구분</th><th>샘플데이터</th><th>항목설명</th>
        </tr></thead><tbody>
          <tr><td>결과코드</td><td>resultCode</td><td>4</td><td>필수</td><td>0000</td><td>처리 결과 코드</td></tr>
        </tbody></table>
      </div>
    '''
    return f'''
      <input type="hidden" id="publicDataDetailPk" value="uddi:fixture-operation">
      <select id="open_api_detail_select"><option selected value="1">관측값조회</option></select>
      {result}
      <!-- data.go.kr renders a duplicate mobile detail block. -->
      <select id="open_api_detail_select"><option selected value="1">관측값조회</option></select>
      {result}
    '''


def test_builds_link_endpoint_with_openapi_compatible_shape(link_detail_html):
    endpoints = build_link_endpoints(link_detail_html)

    assert len(endpoints) == 1
    endpoint = endpoints[0]
    assert set(endpoint) == {
        'method', 'path', 'description', 'parameters', 'responses', 'tags', 'section'
    }
    assert endpoint['method'] == 'POST'
    assert endpoint['path'] == '/v1/observations'
    assert endpoint['description'] == '관측값을 조회하는 기능'
    assert endpoint['tags'] == ['uddi:fixture-operation']
    assert endpoint['section'] == '관측값조회'
    assert endpoint['parameters'] == [
        {
            'name': 'year',
            'description': '기준연도: 조회 연도',
            'required': True,
            'type': 'string',
        },
        {
            'name': 'pageNo',
            'description': '페이지: 페이지 번호',
            'required': False,
            'type': 'integer',
        },
    ]
    assert endpoint['responses'] == [
        {'status_code': UNVERIFIED, 'description': 'resultCode: 처리 결과 코드'}
    ]


def test_marks_method_and_path_unverified_instead_of_guessing():
    html = '''
      <input id="publicDataDetailPk" value="uddi:no-address">
      <div class="open-api-detail-result">
        <h4>설명만 있는 기능</h4>
        <h4>요청변수(Request Parameter)</h4>
        <table><thead><tr><th>항목명(영문)</th><th>항목구분</th></tr></thead>
          <tbody><tr><td>query</td><td>필수</td></tr></tbody></table>
      </div>
    '''

    endpoint = NaraParser().extract_endpoints(html)[0]
    assert endpoint['method'] == UNVERIFIED
    assert endpoint['path'] == UNVERIFIED
    assert endpoint['parameters'][0]['type'] == UNVERIFIED


def test_builds_endpoint_from_renewed_detail_container():
    """The 2026-08 renewal moved the tables into #apiDetailFunctionDiv."""
    endpoints = build_link_endpoints(read_renewed('openapi_old_15061362.html'))

    assert len(endpoints) == 1
    endpoint = endpoints[0]
    assert endpoint['path'] == '/1613000/ConAdminInfoSvc1/GongsiReg'
    assert endpoint['method'] == UNVERIFIED
    assert endpoint['description'] == '국토교통부_건설업체등록'
    assert endpoint['tags'] == ['uddi:3c88abcf-d240-472b-b4b4-a8f2e8388bfc_202204011509']
    assert len(endpoint['parameters']) == 8
    assert len(endpoint['responses']) == 20
    assert endpoint['parameters'][0]['name'] == 'ServiceKey'
    assert endpoint['parameters'][0]['required'] is True
    assert endpoint['parameters'][0]['type'] == UNVERIFIED
    assert endpoint['responses'][0] == {
        'status_code': UNVERIFIED,
        'description': 'resultCode: 결과코드',
    }


def test_renewed_container_is_detected_by_selector_not_by_substring():
    """'open-api-detail-result' survives only inside the page's AJAX script."""
    html = read_renewed('openapi_old_15061362.html')

    assert 'open-api-detail-result' in html
    assert build_link_endpoints(html)


@pytest.mark.parametrize('fixture_name', [
    'openapi_link_15001702.html',  # no request/response tables at all
    'openapi_new_15000863.html',   # only an error-code table, not an endpoint
    'fileData_15000249.html',
    'standard_15072622.html',
])
def test_renewed_pages_without_detail_tables_yield_no_endpoints(fixture_name):
    assert build_link_endpoints(read_renewed(fixture_name)) == []


def test_nara_parser_html_branch_matches_builder_on_renewed_page():
    html = read_renewed('openapi_old_15061362.html')

    assert NaraParser().extract_endpoints(html) == build_link_endpoints(html)


def test_lists_detail_functions_that_are_not_rendered_server_side():
    """Only one of the eight detail functions is in the served HTML."""
    functions = list_detail_functions(read_renewed('openapi_old_15061362.html'))

    assert [item['oprtin_seq_no'] for item in functions] == [
        '41635', '41636', '41637', '41638', '41639', '41640', '41641', '41642'
    ]
    assert functions[0]['name'] == '국토교통부_건설업체등록'
    assert functions[0]['public_data_pk'] == '15061362'
    assert functions[0]['public_data_detail_pk'] == (
        'uddi:3c88abcf-d240-472b-b4b4-a8f2e8388bfc_202204011509'
    )
    # data.go.kr marks none of them selected, so nothing is inferred.
    assert not any(item['selected'] for item in functions)
    assert list_detail_functions(read_renewed('openapi_new_15000863.html')) == []


def test_existing_swagger_extraction_is_unchanged():
    swagger = {
        'paths': {
            '/items': {
                'get': {
                    'summary': 'List items',
                    'parameters': [{'name': 'limit', 'required': False, 'type': 'integer'}],
                    'responses': {'200': {'description': 'OK'}},
                    'tags': ['Items'],
                }
            }
        }
    }

    assert NaraParser().extract_endpoints(swagger) == [
        {
            'method': 'GET',
            'path': '/items',
            'description': 'List items',
            'parameters': [
                {'name': 'limit', 'description': '', 'required': False, 'type': 'integer'}
            ],
            'responses': [{'status_code': '200', 'description': 'OK'}],
            'tags': ['Items'],
            'section': 'Items',
        }
    ]
