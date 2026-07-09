"""
Purpose: Scans standard metadata to check existence and collect info.
Guide: Usage: scanner = standardMetadataScanner(...); scanner.scan_range()
"""

from .base_scanner import BaseMetadataScanner

class standardMetadataScanner(BaseMetadataScanner):
    """공공데이터포털 standard 메타데이터 스캐너"""
    
    def __init__(self, start_num, end_num, max_workers=50, 
                 max_retries=3, retry_delay=1, timeout=5):
        super().__init__('standard', start_num, end_num, max_workers, 
                        max_retries, retry_delay, timeout)
    
    def extract_data_info(self, data, num, has_data, retry_count):
        """standard 정보 추출"""
        standard_info = {
            'number': num,
            'has_data': has_data,
            'title': data.get('title', ''),
            'organization': data.get('organization', ''),
            'description': data.get('description', ''),
            'standard_type': data.get('standardType', data.get('type', '')),
            'standard_code': data.get('standardCode', ''),
            'url': data.get('url', ''),  # base_scanner 호환성을 위한 키
            'standard_url': data.get('url', ''),
            'update_date': data.get('updateDate', data.get('modified', '')),
            'license': data.get('license', ''),
            'status': 'success',
            'metadata': data,
            'retry_count': retry_count
        }
        return standard_info