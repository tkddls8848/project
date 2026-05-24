from typing import List
import re

class URLGenerator:
    """Utilities for generating target URLs."""

    @staticmethod
    def generate_urls_from_numbers(numbers: List[int], data_type: str) -> List[str]:
        """Generates URLs for a list of document numbers."""
        base_urls = {
            'openapi': "https://www.data.go.kr/data/{}/openapi.do",
            'fileData': "https://www.data.go.kr/data/{}/fileData.do",
            'standard': "https://www.data.go.kr/data/{}/standard.do"
        }
        base_url = base_urls.get(data_type, "https://www.data.go.kr/data/{}/openapi.do")
        return [base_url.format(num) for num in numbers]

    @staticmethod
    def generate_urls(start_num: int, end_num: int, data_type: str) -> List[str]:
        """Generates URLs for a range of document numbers."""
        numbers = list(range(start_num, end_num + 1))
        return URLGenerator.generate_urls_from_numbers(numbers, data_type)


class ApiIdExtractor:
    """Utilities for extracting API IDs from URLs."""

    @staticmethod
    def extract_api_id(url: str) -> str:
        """Extracts the API ID from a given URL."""
        # Common pattern for data.go.kr
        match = re.search(r'/data/(\d+)/', url)
        if match:
            return match.group(1)
        
        # Fallback for unexpected formats
        return f"api_{url.replace('https://', '').replace('http://', '').replace('/', '_')}"
