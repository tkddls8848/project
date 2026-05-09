import asyncio
import aiohttp
import re
import os
import json
from typing import List, Dict, Optional, Any
from html import unescape
from bs4 import BeautifulSoup

from stage1_raw.crawler.base_crawler import BaseCrawler
from stage1_raw.domain.schemas import CrawlResult, CrawlData
from stage1_raw.utils.text_utils import clean_text
from stage1_raw.utils.url_utils import ApiIdExtractor
from stage1_raw.infrastructure.nara_parser import NaraParser

class OpenAPICrawler(BaseCrawler):
    """
    Crawler for OpenAPI services.
    Handles Link, Swagger, and old-style APIs using static HTTP requests.
    """

    OLD_DETAIL_URL = "https://www.data.go.kr/tcs/dss/selectApiDetailFunction.do"

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

                soup = BeautifulSoup(html, 'html.parser')
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
                elif api_type == 'openapi_old':
                    old_info = await self._extract_openapi_old_info(session, url, api_id, soup)
                    data_payload.update(old_info)

                crawl_data = CrawlData(
                    api_id=api_id,
                    api_type=api_type,
                    crawled_url=url,
                    info=merged_info,
                    swagger_json=data_payload.get('swagger_json'),
                    endpoints=data_payload.get('endpoints'),
                    operation_ids=operation_ids
                )

                if api_type == 'openapi_old':
                    crawl_data.info['api_details'] = data_payload.get('api_details', [])
                    crawl_data.info['basic_info'] = data_payload.get('basic_info', {})

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
        if soup.find('select', {'id': 'open_api_detail_select'}):
            return 'openapi_old'
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

    def _extract_public_data_pk(self, soup: BeautifulSoup, fallback: str) -> str:
        input_tag = soup.find('input', {'id': 'publicDataPk'})
        if input_tag and input_tag.get('value'):
            return input_tag.get('value').strip()
        return fallback

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

    async def _extract_openapi_old_info(
        self,
        session: aiohttp.ClientSession,
        url: str,
        api_id: str,
        soup: BeautifulSoup
    ) -> Dict[str, Any]:
        detail_pk = self._extract_public_data_detail_value(soup)
        public_data_pk = self._extract_public_data_pk(soup, api_id)
        options = self._extract_old_select_options(soup)

        api_details = []
        for option in options:
            detail = await self._fetch_old_detail(
                session=session,
                page_url=url,
                oprtin_seq_no=option['oprtinSeqNo'],
                public_data_detail_pk=detail_pk,
                public_data_pk=public_data_pk
            )
            if detail:
                if option.get('name'):
                    detail.setdefault('descriptions', {})['상세기능명'] = option['name']
                api_details.append(detail)

        basic_info = {}
        org = soup.select_one('.api-provider')
        if org:
            basic_info['provider'] = clean_text(org.get_text())
        version = soup.select_one('.api-version')
        if version:
            basic_info['version'] = clean_text(version.get_text())

        return {'api_details': api_details, 'basic_info': basic_info}

    def _extract_public_data_detail_value(self, soup: BeautifulSoup) -> str:
        input_tag = soup.find('input', {'id': 'publicDataDetailPk'})
        if input_tag and input_tag.get('value'):
            return input_tag.get('value').strip()
        return ""

    def _extract_old_select_options(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        select = soup.find('select', {'id': 'open_api_detail_select'})
        if not select:
            return []
        options = []
        for opt in select.find_all('option'):
            value = opt.get('value', '').strip()
            if value:
                options.append({
                    'oprtinSeqNo': value,
                    'name': clean_text(opt.get_text())
                })
        return options

    async def _fetch_old_detail(
        self,
        session: aiohttp.ClientSession,
        page_url: str,
        oprtin_seq_no: str,
        public_data_detail_pk: str,
        public_data_pk: str
    ) -> Optional[Dict[str, Any]]:
        if not oprtin_seq_no or not public_data_detail_pk:
            return None

        headers = {
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': page_url,
            'Origin': 'https://www.data.go.kr',
            'Accept': 'text/html, */*; q=0.01',
        }
        data = {
            'oprtinSeqNo': oprtin_seq_no,
            'publicDataDetailPk': public_data_detail_pk,
            'publicDataPk': public_data_pk,
        }

        try:
            async with session.post(self.OLD_DETAIL_URL, data=data, headers=headers) as response:
                if response.status != 200:
                    return None
                html = await response.text()
        except Exception:
            return None

        return self._parse_old_detail_html(html)

    def _parse_old_detail_html(self, html: str) -> Optional[Dict[str, Any]]:
        soup = BeautifulSoup(html, 'html.parser')
        container = soup.select_one('#open-api-detail-result')
        if not container:
            return None

        service_url = self._extract_service_url(container)
        tables = container.select('table')
        parsed = {
            'endpoint': {'Request': None, 'Response': None},
            'service_url': service_url,
            'descriptions': {}
        }

        title = container.find(['h3', 'h4', 'strong'])
        if title:
            parsed['descriptions']['설명'] = clean_text(title.get_text())

        table_payloads = [self._parse_detail_table(table) for table in tables]
        table_payloads = [payload for payload in table_payloads if payload]
        if table_payloads:
            parsed['endpoint']['Request'] = table_payloads[0]
        if len(table_payloads) > 1:
            parsed['endpoint']['Response'] = table_payloads[1]
        if service_url:
            parsed['descriptions']['서비스URL'] = service_url

        return parsed

    def _extract_service_url(self, container: BeautifulSoup) -> Optional[str]:
        label_value = self._extract_service_url_from_labeled_fields(container)
        if label_value:
            return label_value

        link = container.find('a', href=re.compile(r'^https?://'))
        if link and link.get('href'):
            return self._clean_service_url(link.get('href'))

        attr_url = self._extract_service_url_from_attributes(container)
        if attr_url:
            return attr_url

        text = container.get_text(" ", strip=True)
        label_match = re.search(r'(?:서비스\s*URL|서비스URL|요청\s*주소|요청주소)\s*[:：]?\s*(\S+)', text, re.IGNORECASE)
        if label_match:
            return self._clean_service_value(label_match.group(1))

        return self._extract_first_url(text)

    def _extract_service_url_from_labeled_fields(self, container: BeautifulSoup) -> Optional[str]:
        """Finds service URL/operation value near labels such as 서비스URL or 요청주소."""
        label_pattern = re.compile(r'(서비스\s*URL|서비스URL|요청\s*주소|요청주소)', re.IGNORECASE)

        for row in container.find_all('tr'):
            cells = row.find_all(['th', 'td'])
            if len(cells) < 2:
                continue
            for idx, cell in enumerate(cells[:-1]):
                if label_pattern.search(clean_text(cell.get_text())):
                    value = self._extract_service_value_from_node(cells[idx + 1])
                    if value:
                        return value

        for node in container.find_all(string=label_pattern):
            parent = node.parent
            candidates = []
            if parent:
                candidates.extend([
                    parent,
                    parent.find_next_sibling(),
                    parent.find_next(),
                    parent.parent.find_next_sibling() if parent.parent else None,
                ])
            for candidate in candidates:
                if candidate:
                    value = self._extract_service_value_from_node(candidate, label_pattern)
                    if value:
                        return value

        return None

    def _extract_service_url_from_attributes(self, container: BeautifulSoup) -> Optional[str]:
        for tag in container.find_all(True):
            for attr in ('href', 'value', 'data-url', 'data-href', 'action'):
                value = tag.get(attr)
                if not value:
                    continue
                url = self._extract_first_url(str(value))
                if url:
                    return url
        return None

    def _extract_service_value_from_node(self, node, label_pattern: Optional[re.Pattern] = None) -> Optional[str]:
        if not node:
            return None
        link = node.find('a', href=re.compile(r'^https?://')) if hasattr(node, 'find') else None
        if link and link.get('href'):
            return self._clean_service_url(link.get('href'))
        text = node.get_text(" ", strip=True) if hasattr(node, 'get_text') else str(node)
        url = self._extract_first_url(text)
        if url:
            return url
        if label_pattern:
            text = label_pattern.sub('', text, count=1)
        return self._clean_service_value(text)

    def _extract_first_url(self, text: str) -> Optional[str]:
        if not text:
            return None
        text = unescape(text)
        match = re.search(r'https?://[^\s<>"\'\]\)]+', text)
        return self._clean_service_url(match.group(0)) if match else None

    def _clean_service_url(self, url: Optional[str]) -> Optional[str]:
        if not url:
            return None
        cleaned = unescape(str(url)).strip()
        cleaned = cleaned.rstrip('.,;:）)]}"\'')
        return cleaned or None

    def _clean_service_value(self, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        cleaned = unescape(str(value)).strip()
        cleaned = re.sub(r'^(서비스\s*URL|서비스URL|요청\s*주소|요청주소)\s*[:：]?\s*', '', cleaned, flags=re.IGNORECASE)
        cleaned = cleaned.strip().strip(':-：').strip()
        cleaned = cleaned.rstrip('.,;:）)]}"\'')
        if not cleaned or cleaned in {'-', '없음'}:
            return None
        return cleaned

    def _parse_detail_table(self, table) -> List[Dict[str, str]]:
        rows = table.find_all('tr')
        if not rows:
            return []

        headers = [clean_text(th.get_text()) for th in rows[0].find_all('th')]
        parsed_rows = []
        for row in rows[1:]:
            cells = row.find_all('td')
            if not cells:
                continue
            row_data = {}
            for idx, cell in enumerate(cells):
                key = headers[idx] if idx < len(headers) and headers[idx] else f'col_{idx}'
                row_data[key] = clean_text(cell.get_text())
            if row_data:
                parsed_rows.append(row_data)
        return parsed_rows

    def refine_results(self, results: List[CrawlResult]) -> Dict[str, Any]:
        return {"total_refined": 0, "failed_refines": 0, "refined_files": []}
