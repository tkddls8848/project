"""
Purpose: Scans standard metadata to check existence and collect info.
Guide: Usage: scanner = standardMetadataScanner(...); scanner.scan_range()

standard_type 주의 (2026-08 리뉴얼):
    리뉴얼된 catalog JSON에는 옛 standardType/type에 대응하는 필드가 없다.
    "@type"은 schema.org 표식(항상 'Dataset')이라 표준 구분자로 쓸 수 없고,
    additionalType은 분류체계(예: '공공질서및안전 - 안전관리')다. 추정하지 않고
    공란으로 두며(standard_type_source='unverified'), 분류체계는 classification에,
    관련법령은 legislation에 따로 담는다. 15072619~15072627 구간 실측 확인.
    리뉴얼 응답에는 license도 없어 공란으로 남는다.
"""

from .base_scanner import BaseMetadataScanner, extract_common_info, pick_text

class standardMetadataScanner(BaseMetadataScanner):
    """공공데이터포털 standard 메타데이터 스캐너"""

    def __init__(self, start_num, end_num, max_workers=50,
                 max_retries=3, retry_delay=1, timeout=5):
        super().__init__('standard', start_num, end_num, max_workers,
                        max_retries, retry_delay, timeout)

    def extract_data_info(self, data, num, has_data, retry_count):
        """standard 정보 추출"""
        common = extract_common_info(data)

        # 옛 스키마에만 존재하는 키다 ('@type'은 schema.org 표식이므로 쓰지 않는다)
        standard_type = pick_text(data, 'standardType', 'type')

        standard_info = {
            'number': num,
            'has_data': has_data,
            # base_scanner의 data_types 집계가 참조하는 키 ({scan_type}_type)
            'standard_type': standard_type,
            'standard_type_source': 'metadata' if standard_type else 'unverified',
            'standard_code': pick_text(data, 'standardCode'),
            'legislation': pick_text(data, 'legislation'),
            'standard_url': common['url'],
            'status': 'success',
            'metadata': data,
            'retry_count': retry_count
        }
        standard_info.update(common)  # title/organization/url/update_date 등
        return standard_info
