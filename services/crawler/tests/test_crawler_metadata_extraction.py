from types import SimpleNamespace

from bs4 import BeautifulSoup

from crawler.file_data_crawler import FileDataCrawler
from crawler.openapi_crawler import OpenAPICrawler
from domain.schemas import CrawlData


def _config():
    return SimpleNamespace(max_workers=1, target_api_type=None)


def test_openapi_type_distinguishes_the_three_subtypes():
    crawler = OpenAPICrawler(_config())
    soup = BeautifulSoup('', 'lxml')
    swagger = {'openapi': '3.0.0', 'paths': {}}

    assert crawler._detect_api_type({'API 유형': 'LINK'}, soup, None) == 'openapi_link'
    assert crawler._detect_api_type({}, soup, swagger) == 'openapi_new'
    assert crawler._detect_api_type({}, soup, None) == 'openapi_old'


def test_api_type_evidence_records_legacy_representation_details():
    crawler = OpenAPICrawler(_config())
    old_soup = BeautifulSoup(
        '<input type="hidden" id="publicDataDetailPk" value="123">'
        '<select id="open_api_detail_select"><option value="1">기능</option></select>',
        'lxml',
    )

    old_evidence = crawler._build_api_type_evidence({}, old_soup, None)
    assert old_evidence['reason'] == 'legacy_html_without_inline_swagger'

    soup = BeautifulSoup('<input type="hidden" id="publicDataDetailPk" value="123">', 'lxml')
    assert crawler._build_api_type_evidence({}, soup, None) == {
        'reason': 'legacy_html_without_inline_swagger',
        'csv_api_type': None,
        'csv_declares_link': False,
        'swagger_json_parsed': False,
        'swagger_marker_present': False,
        'public_data_detail_pk_present': True,
    }

    invalid = crawler._build_api_type_evidence(
        {}, soup, None, 'var swaggerJson = `{not valid json}`;'
    )
    assert invalid['reason'] == 'legacy_inline_swagger_unparseable'


def test_extracts_external_endpoint_urls_without_data_go_kr_links():
    crawler = OpenAPICrawler(_config())
    html = r'''
        <a href="https://www.data.go.kr/data/15000017/openapi.do">detail</a>
        <code>http:\/\/openapi.tour.go.kr\/openapi\/service\/TourismAccdtService\/getList?numOfRows=10</code>
        <script>const other = "https://api.example.go.kr/v1/items";</script>
        <script src="https://cdn.example.org/assets/app.js"></script>
    '''

    assert crawler._extract_external_endpoint_urls(html) == [
        'http://openapi.tour.go.kr/openapi/service/TourismAccdtService/getList?numOfRows=10',
        'https://api.example.go.kr/v1/items',
    ]


def test_tolerant_jsonld_parser_preserves_complete_dataset_and_downloads():
    crawler = FileDataCrawler(_config())
    html = '''
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Dataset",
          "name": "Fixture dataset",
          "description": "A description with an unescaped "quoted phrase", plus text inside",
          "publisher": {"@type": "Organization", "name": "Fixture Agency"},
          "license": "https://example.org/license",
          "temporalCoverage": "2025-01-01/2025-12-31",
          "dateModified": "2026-07-31",
          "distribution": [{
            "@type": "DataDownload",
            "encodingFormat": "CSV",
            "contentSize": "42 MB",
            "contentUrl": "https://www.data.go.kr/cmm/cmm/fileDownload.do?atchFileId=FILE_1&amp;fileDetailSn=1"
          }]
        }
        </script>
    '''

    datasets = crawler._extract_jsonld_datasets(html)
    assert len(datasets) == 1
    dataset = datasets[0]
    assert dataset['description'] == 'A description with an unescaped "quoted phrase", plus text inside'
    assert dataset['publisher']['name'] == 'Fixture Agency'
    assert dataset['license'] == 'https://example.org/license'
    assert dataset['temporalCoverage'] == '2025-01-01/2025-12-31'
    assert dataset['dateModified'] == '2026-07-31'
    assert dataset['distribution'][0]['contentSize'] == '42 MB'

    assert crawler._extract_jsonld_download_urls(html, 'Fixture', datasets) == {
        'Fixture': 'https://www.data.go.kr/cmm/cmm/fileDownload.do?atchFileId=FILE_1&fileDetailSn=1'
    }


def test_crawl_data_exposes_new_metadata_fields():
    data = CrawlData(
        api_id='15000017',
        api_type='openapi_link',
        crawled_url='https://www.data.go.kr/data/15000017/openapi.do',
        external_endpoint_urls=['http://openapi.tour.go.kr/openapi/service/example'],
        api_type_evidence={'reason': 'csv_api_type_declares_link'},
        jsonld_datasets=[{'@type': 'Dataset', 'license': 'https://example.org/license'}],
    )

    dumped = data.model_dump()
    assert dumped['external_endpoint_urls'][0].startswith('http://openapi.tour.go.kr/')
    assert dumped['api_type_evidence']['reason'] == 'csv_api_type_declares_link'
    assert dumped['jsonld_datasets'][0]['license'] == 'https://example.org/license'
