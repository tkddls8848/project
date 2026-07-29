"""
Purpose: Scans OpenAPI metadata to check existence and collect info.
Guide: Usage: scanner = OpenAPIMetadataScanner(...); scanner.scan_range()
"""

from .base_scanner import BaseMetadataScanner

class OpenAPIMetadataScanner(BaseMetadataScanner):
    """공공데이터포털 OpenAPI 메타데이터 스캐너"""
    
    def __init__(self, start_num, end_num, max_workers=50, 
                 max_retries=3, retry_delay=1, timeout=5):
        super().__init__('openapi', start_num, end_num, max_workers, 
                        max_retries, retry_delay, timeout)
    
    def extract_data_info(self, data, num, has_data, retry_count):
        """OpenAPI 정보 추출"""
        api_info = {
            'number': num,
            'has_data': has_data,
            'title': data.get('title', ''),
            'organization': data.get('organization', ''),
            'description': data.get('description', ''),
            'api_type': data.get('apiType', ''),
            'url': data.get('url', ''),  # base_scanner 호환성을 위한 키
            'api_url': data.get('url', ''),
            'update_date': data.get('updateDate', data.get('modified', '')),
            'license': data.get('license', ''),
            'status': 'success',
            'metadata': data,
            'retry_count': retry_count
        }
        return api_info