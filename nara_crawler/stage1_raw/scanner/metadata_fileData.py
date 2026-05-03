"""
Purpose: Scans fileData metadata to check existence and collect info.
Guide: Usage: scanner = fileDataMetadataScanner(...); scanner.scan_range()
"""

from .base_scanner import BaseMetadataScanner

class fileDataMetadataScanner(BaseMetadataScanner):
    """공공데이터포털 fileData 메타데이터 스캐너"""
    
    def __init__(self, start_num, end_num, max_workers=50, 
                 max_retries=3, retry_delay=1, timeout=5):
        super().__init__('fileData', start_num, end_num, max_workers, 
                        max_retries, retry_delay, timeout)
    
    def extract_data_info(self, data, num, has_data, retry_count):
        """fileData 정보 추출"""
        file_info = {
            'number': num,
            'has_data': has_data,
            'title': data.get('title', ''),
            'organization': data.get('organization', ''),
            'description': data.get('description', ''),
            'file_type': data.get('fileType', data.get('format', '')),
            'file_size': data.get('fileSize', ''),
            'url': data.get('url', ''),  # base_scanner 호환성을 위한 키
            'download_url': data.get('url', ''),
            'update_date': data.get('updateDate', data.get('modified', '')),
            'license': data.get('license', ''),
            'status': 'success',
            'metadata': data,
            'retry_count': retry_count
        }
        return file_info