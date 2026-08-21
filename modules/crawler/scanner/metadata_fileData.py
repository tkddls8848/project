"""
Purpose: Scans fileData metadata to check existence and collect info.
Guide: Usage: scanner = fileDataMetadataScanner(...); scanner.scan_range()

file_type 주의 (2026-08 리뉴얼):
    리뉴얼된 catalog JSON의 encodingFormat이 옛 fileType/format을 대체한다.
    상세페이지의 "확장자"와 값이 일치함을 실측 확인했다 (15000249 → 'PDF').
    fileSize에 해당하는 필드는 리뉴얼 응답에 없어 공란으로 남는다.
"""

from .base_scanner import BaseMetadataScanner, extract_common_info, pick_text

class fileDataMetadataScanner(BaseMetadataScanner):
    """공공데이터포털 fileData 메타데이터 스캐너"""

    def __init__(self, start_num, end_num, max_workers=50,
                 max_retries=3, retry_delay=1, timeout=5):
        super().__init__('fileData', start_num, end_num, max_workers,
                        max_retries, retry_delay, timeout)

    def extract_data_info(self, data, num, has_data, retry_count):
        """fileData 정보 추출"""
        common = extract_common_info(data)

        # encodingFormat(신규) → fileType/format(옛 스키마) 순
        file_type = common['data_format'] or pick_text(data, 'fileType')

        file_info = {
            'number': num,
            'has_data': has_data,
            'file_type': file_type,
            # base_scanner의 data_types 집계가 참조하는 키 ({scan_type}_type)
            'fileData_type': file_type,
            'file_size': pick_text(data, 'fileSize'),
            'alternate_name': pick_text(data, 'alternateName'),
            'spatial_coverage': pick_text(data, 'spatialCoverage'),
            'temporal_coverage': pick_text(data, 'temporalCoverage'),
            'download_url': common['url'],
            'status': 'success',
            'metadata': data,
            'retry_count': retry_count
        }
        file_info.update(common)  # title/organization/url/update_date/license 등
        return file_info
