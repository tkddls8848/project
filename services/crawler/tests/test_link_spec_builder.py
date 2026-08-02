import pytest

from crawler.link_spec_builder import UNVERIFIED, build_link_endpoints
from infrastructure.nara_parser import NaraParser


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
