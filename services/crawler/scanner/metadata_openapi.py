"""
Purpose: Scans OpenAPI metadata to check existence and collect info.
Guide: Usage: scanner = OpenAPIMetadataScanner(...); scanner.scan_range()

api_type 주의 (2026-08 리뉴얼):
    리뉴얼된 catalog JSON(schema.org Dataset)에는 REST/LINK/SOAP를 구분하는 필드가
    없다. encodingFormat은 상세페이지의 "데이터 포맷"(XML/JSON+XML)에 대응하는 값이며
    REST/LINK 구분이 아니다 - REST 3건·LINK 3건을 실측 대조해 확인했다.
    따라서 api_type은 옛 스키마(apiType)가 있을 때만 채우고, 없으면 공란으로 두며
    api_type_source='unverified'로 표시한다. 추정해서 채우지 않는다.
    실제 REST/LINK 구분은 scanner/database/metadata_api.csv의 "API 유형" 컬럼
    (main.py가 사용) 또는 상세페이지 HTML에서 얻는다.
"""

from .base_scanner import BaseMetadataScanner, extract_common_info, pick_text

class OpenAPIMetadataScanner(BaseMetadataScanner):
    """공공데이터포털 OpenAPI 메타데이터 스캐너"""

    def __init__(self, start_num, end_num, max_workers=50,
                 max_retries=3, retry_delay=1, timeout=5):
        super().__init__('openapi', start_num, end_num, max_workers,
                        max_retries, retry_delay, timeout)

    def extract_data_info(self, data, num, has_data, retry_count):
        """OpenAPI 정보 추출"""
        common = extract_common_info(data)

        # 리뉴얼 응답에는 apiType이 없다 - 있을 때만(=옛 저장분) 채운다
        api_type = pick_text(data, 'apiType')

        api_info = {
            'number': num,
            'has_data': has_data,
            'api_type': api_type,
            # base_scanner의 data_types 집계가 참조하는 키 ({scan_type}_type)
            'openapi_type': api_type,
            'api_type_source': 'metadata' if api_type else 'unverified',
            'api_url': common['url'],
            'status': 'success',
            'metadata': data,
            'retry_count': retry_count
        }
        api_info.update(common)  # title/organization/url/update_date/license 등
        return api_info
