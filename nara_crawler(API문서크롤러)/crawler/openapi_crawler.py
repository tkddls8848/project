import asyncio
import aiohttp
import re
import json
from typing import List, Dict, Optional, Any
from bs4 import BeautifulSoup

from crawler.base_crawler import BaseCrawler
from domain.schemas import CrawlResult, CrawlData
from utils.text_utils import clean_text
from utils.url_utils import ApiIdExtractor
from infrastructure.nara_parser import NaraParser

class OpenAPICrawler(BaseCrawler):
    """
    Crawler for OpenAPI services.
    Handles Link and Swagger APIs using static HTTP requests.
    """

    def __init__(self, config):
        super().__init__(config)
        self.semaphore = asyncio.Semaphore(config.max_workers)
        self.target_api_type = config.target_api_type
        self.skipped_by_api_type = 0

    async def create_session(self) -> aiohttp.ClientSession:
        return self.create_http_session()

    async def crawl(self, urls: List[str], csv_metadata: Optional[Dict[int, Dict]] = None) -> List[CrawlResult]:
        print(f"\nStarting OpenAPI Crawling for {len(urls)} URLs...")

        url_csv_data_pairs = self.pair_urls_with_metadata(urls, csv_metadata)
        async with await self.create_session() as session:
            return await self.collect_in_batches(
                url_csv_data_pairs,
                lambda pair: self._crawl_static_single(session, pair[0], pair[1]),
                desc="Crawling OpenAPI",
                unit="url"
            )

    async def _crawl_static_single(self, session: aiohttp.ClientSession, url: str, csv_info: Dict) -> CrawlResult:
        """Crawls one OpenAPI page without browser rendering."""
        async with self.semaphore:
            try:
                api_id = ApiIdExtractor.extract_api_id(url)
                if not api_id:
                    return CrawlResult(url=url, success=False, errors=["Could not extract API ID"])

                async with session.get(url) as response:
                    if response.status != 200:
                        return CrawlResult(url=url, success=False, errors=[f"HTTP {response.status}"])
                    html = await response.text()

                soup = self.make_soup(html, ['table', 'input'])
                table_info = self._extract_table_bs(soup, html)
                merged_info = csv_info.copy()
                merged_info.update(table_info)

                operation_ids = self._extract_public_data_detail_pk(soup)
                swagger_json = self._extract_swagger_json_from_html(html)
                api_type = self._detect_api_type(merged_info, soup, swagger_json)
                if self.target_api_type and api_type != self.target_api_type:
                    self.skipped_by_api_type += 1
                    return CrawlResult(url=url, success=True, data=None)

                data_payload: Dict[str, Any] = {}
                if api_type == 'openapi_new':
                    parser = NaraParser()
                    data_payload['swagger_json'] = swagger_json
                    data_payload['endpoints'] = parser.extract_endpoints(swagger_json or {})

                crawl_data = CrawlData(
                    api_id=api_id,
                    api_type=api_type,
                    crawled_url=url,
                    info=merged_info,
                    swagger_json=data_payload.get('swagger_json'),
                    endpoints=data_payload.get('endpoints'),
                    operation_ids=operation_ids
                )

                return CrawlResult(url=url, success=True, data=crawl_data)
            except Exception as e:
                return CrawlResult(url=url, success=False, errors=[str(e)])

    def _detect_api_type(self, info: Dict, soup: BeautifulSoup, swagger_json: Optional[Dict]) -> str:
        """Determines data.go.kr OpenAPI subtype from CSV/HTML evidence."""
        api_type_val = str(info.get('API 유형', '') or info.get('API 타입', '')).upper()
        if 'LINK' in api_type_val:
            return 'openapi_link'
        if swagger_json:
            return 'openapi_new'
        return 'openapi_link'

    def _extract_table_bs(self, soup: BeautifulSoup, html: str = "") -> Dict:
        """Extracts table data using BeautifulSoup."""
        info = {}
        tables = soup.select('table')
        for table in tables:
            for row in table.find_all('tr'):
                th = row.find('th')
                td = row.find('td')
                if th and td:
                    key = clean_text(th.get_text())
                    # Remove script tags before extracting text
                    for script in td.find_all('script'):
                        script.decompose()
                    val = td.get_text()
                    # Remove JavaScript code patterns - remove everything from backtick or 'var' onwards
                    val = re.sub(r'`\s*var\s+.*$', '', val, flags=re.DOTALL).strip()
                    # Also remove standalone backtick at the end
                    val = re.sub(r'`$', '', val).strip()
                    val = clean_text(val)
                    if key: info[key] = val
        tel_no = self._extract_tel_no(html)
        if tel_no:
            info['관리부서 전화번호'] = tel_no
        return info

    def _extract_tel_no(self, html: str) -> Optional[str]:
        """Extracts and formats telNo injected by page JavaScript."""
        if not html:
            return None
        match = re.search(r'var\s+telNo\s*=\s*"([^"]+)"', html)
        if not match:
            return None
        digits = re.sub(r'\D', '', match.group(1))
        if not digits:
            return None
        if digits.startswith('02') and len(digits) >= 9:
            return f"{digits[:2]}-{digits[2:-4]}-{digits[-4:]}"
        if len(digits) >= 10:
            return f"{digits[:3]}-{digits[3:-4]}-{digits[-4:]}"
        return digits

    def _extract_public_data_detail_pk(self, soup: BeautifulSoup) -> Optional[List[str]]:
        """Extracts publicDataDetailPk from hidden input tag."""
        try:
            input_tag = soup.find('input', {'type': 'hidden', 'id': 'publicDataDetailPk'})
            if input_tag and input_tag.get('value'):
                value = input_tag.get('value').strip()
                if value:
                    return [value]
        except:
            pass
        return None

    def _extract_swagger_json_from_html(self, html: str) -> Optional[Dict[str, Any]]:
        """Extracts inline swaggerJson from data.go.kr HTML."""
        match = re.search(r'var\s+swaggerJson\s*=\s*`(\{[\s\S]*?\})`\s*;', html)
        if not match:
            match = re.search(r'var\s+swaggerJson\s*=\s*`(\{[\s\S]*?\})`', html)
        if not match:
            return None

        json_str = match.group(1)
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            try:
                return json.loads(re.sub(r'\s+', ' ', json_str))
            except json.JSONDecodeError:
                return None

    def refine_results(self, results: List[CrawlResult]) -> Dict[str, Any]:
        return {"total_refined": 0, "failed_refines": 0, "refined_files": []}
