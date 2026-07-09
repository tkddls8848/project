import os
import asyncio
import aiohttp
import json
import re
from typing import List, Dict, Optional, Any
from bs4 import BeautifulSoup

from crawler.base_crawler import BaseCrawler
from domain.schemas import CrawlResult, CrawlData
from utils.text_utils import clean_text
from utils.url_utils import ApiIdExtractor

class FileDataCrawler(BaseCrawler):
    """Crawler for fileData type services."""

    def __init__(self, config):
        super().__init__(config)
        self.semaphore = asyncio.Semaphore(config.max_workers)
        self.file_info_semaphore = asyncio.Semaphore(max(1, config.max_workers))

    async def create_session(self) -> aiohttp.ClientSession:
        """Creates an optimized HTTP session."""
        return self.create_http_session()

    async def crawl(self, urls: List[str], csv_metadata: Optional[Dict[int, Dict]] = None) -> List[CrawlResult]:
        """Executes the crawling process for fileData."""
        print(f"\nStarting FileData Crawling for {len(urls)} URLs...")
        
        url_csv_data_pairs = self.pair_urls_with_metadata(urls, csv_metadata)

        results = []
        async with await self.create_session() as session:
            results = await self.collect_in_batches(
                url_csv_data_pairs,
                lambda pair: self._crawl_single(session, pair[0], pair[1]),
                desc="Crawling fileData",
                unit="url"
            )

        for result in results:
            if result.success:
                self.stats['success'] += 1
                if result.data and result.data.info:
                    self.stats['api_call_success'] += 1
            else:
                self.stats['failed'] += 1

        return results

    async def _crawl_single(self, session: aiohttp.ClientSession, url: str, csv_row_data: Dict) -> CrawlResult:
        """Crawls a single fileData URL."""
        async with self.semaphore:
            errors = []
            api_id = ApiIdExtractor.extract_api_id(url)
            if not api_id:
                return CrawlResult(url=url, success=False, errors=["Could not extract API ID"])

            try:
                html_info = {}
                html_operation_ids = []
                jsonld_download_urls = {}
                merged_info = csv_row_data.copy()
                try:
                    async with session.get(url) as response:
                        if response.status == 200:
                            html = await response.text()
                            soup = self.make_soup(html, ['table', 'input'])
                            html_info = self._extract_table_bs(soup)
                            html_operation_ids = self._extract_public_data_detail_pks(soup)
                            merged_info.update(html_info)
                            file_name = merged_info.get('파일데이터명') or merged_info.get('목록명') or api_id
                            jsonld_download_urls = self._extract_jsonld_download_urls(html, file_name)
                except Exception as exc:
                    errors.append(f"HTML metadata fetch failed: {exc}")

                # Fast path: data.go.kr embeds the full download URL (atchFileId)
                # in the page's JSON-LD, so for most file datasets we can build
                # the download links from the single page fetch — no extra
                # infuser/selectFileDataDownload requests needed.
                if jsonld_download_urls:
                    download_urls_dict = jsonld_download_urls
                    operation_ids = html_operation_ids
                    self.stats['jsonld_fastpath'] = self.stats.get('jsonld_fastpath', 0) + 1
                else:
                    # Fallback: resolve operation IDs, then fetch atchFileId per file.
                    operation_ids = await self._extract_operation_ids(session, api_id)
                    if not operation_ids:
                        operation_ids = html_operation_ids

                    download_urls_dict = {}
                    if operation_ids:
                        operation_id_urls = [
                            f"https://www.data.go.kr/tcs/dss/selectFileDataDownload.do?publicDataPk={api_id}&publicDataDetailPk={op_id}"
                            for op_id in operation_ids
                        ]

                        file_info_results = await asyncio.gather(
                            *(self._extract_file_info_limited(session, op_url) for op_url in operation_id_urls),
                            return_exceptions=True
                        )
                        for file_info in file_info_results:
                            if isinstance(file_info, Exception) or not file_info:
                                continue
                            for data_nm, atch_id in file_info.items():
                                download_urls_dict[data_nm] = self._generate_download_url(atch_id)

                # Prepare Data
                crawl_data = CrawlData(
                    api_id=api_id,
                    api_type='fileData',
                    crawled_url=url,
                    info=merged_info,
                    operation_ids=operation_ids,
                    download_urls=download_urls_dict
                )

                success = bool(merged_info or operation_ids or download_urls_dict)
                if not success:
                    errors.append("No CSV or HTML metadata found")

                return CrawlResult(
                    url=url,
                    success=success,
                    data=crawl_data,
                    errors=errors
                )

            except Exception as e:
                return CrawlResult(url=url, success=False, errors=[str(e)])

    def _extract_table_bs(self, soup: BeautifulSoup) -> Dict:
        """Extracts fileData detail tables from page HTML."""
        info = {}
        for table in soup.select('table.fileDataDetail, table.dataset-table'):
            for row in table.find_all('tr'):
                th = row.find('th')
                td = row.find('td')
                if not th or not td:
                    continue
                key = clean_text(th.get_text())
                if not key:
                    continue
                for script in td.find_all('script'):
                    script.decompose()
                value = clean_text(td.get_text())
                if value:
                    info[key] = value
        return info

    def _extract_public_data_detail_pks(self, soup: BeautifulSoup) -> List[str]:
        ids = []
        for input_tag in soup.select('input#publicDataDetailPk'):
            value = input_tag.get('value', '').strip()
            if value and value not in ids:
                ids.append(value)
        return ids

    async def _extract_operation_ids(self, session: aiohttp.ClientSession, doc_number: str) -> List[str]:
        """Extracts operation IDs from infuser API."""
        api_url = f"https://infuser.odcloud.kr/oas/docs?namespace={doc_number}/v1"
        try:
            async with session.get(api_url) as response:
                if response.status != 200: return []
                
                # Simple check for JSON
                if 'application/json' not in response.headers.get('Content-Type', ''): return []
                
                data = await response.json()
                paths = data.get('paths', {})
                ids = []
                
                if isinstance(paths, dict):
                    for path_value in paths.values():
                        if isinstance(path_value, dict):
                            for method_details in path_value.values():
                                if isinstance(method_details, dict) and 'operationId' in method_details:
                                    op_id = method_details['operationId']
                                    # Remove 'get' case-insensitive
                                    op_id_cleaned = re.sub(r'get', '', op_id, flags=re.IGNORECASE)
                                    ids.append(op_id_cleaned)
                return ids
        except:
            return []

    async def _extract_file_info(self, session: aiohttp.ClientSession, url: str) -> Dict[str, str]:
        """Extracts file info (dataNm, atchFileId) from URL."""
        file_info = {}
        try:
            async with session.get(url) as response:
                if response.status != 200: return {}
                text = await response.text()
                
                data = None
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    match = re.search(r'<body[^>]*>(.*?)</body>', text, re.DOTALL | re.IGNORECASE)
                    if match:
                        try:
                            data = json.loads(match.group(1).strip())
                        except:
                            pass
                
                if data:
                    self._find_file_info_recursive(data, file_info)
        except:
            pass
        return file_info

    async def _extract_file_info_limited(self, session: aiohttp.ClientSession, url: str) -> Dict[str, str]:
        async with self.file_info_semaphore:
            return await self._extract_file_info(session, url)

    def _find_file_info_recursive(self, obj: Any, info_dict: Dict[str, str]):
        if isinstance(obj, dict):
            if 'dataNm' in obj and 'atchFileId' in obj:
                nm = str(obj['dataNm']).strip()
                fid = str(obj['atchFileId']).strip()
                if nm and fid:
                    info_dict[nm] = fid
            else:
                for v in obj.values():
                    self._find_file_info_recursive(v, info_dict)
        elif isinstance(obj, list):
            for item in obj:
                self._find_file_info_recursive(item, info_dict)

    def _generate_download_url(self, atch_file_id: str) -> str:
        return f"https://www.data.go.kr/cmm/cmm/fileDownload.do?atchFileId={atch_file_id}&fileDetailSn=1"

    def _extract_jsonld_download_urls(self, html: str, file_name: str) -> Dict[str, str]:
        """Extracts download URLs from the page's JSON-LD distribution block.

        data.go.kr embeds the full download URL (including atchFileId) in the
        <script type="application/ld+json"> Dataset metadata, available from the
        single page fetch. A targeted regex is used instead of json.loads
        because the JSON-LD description field frequently contains unescaped
        quotes that break strict JSON parsing.
        """
        if not html:
            return {}

        pattern = re.compile(
            r'"encodingFormat"\s*:\s*"([^"]*)"\s*,\s*"contentUrl"\s*:\s*"([^"]*atchFileId=[^"]*)"',
            re.IGNORECASE,
        )
        matches = pattern.findall(html)
        if not matches:
            urls_only = re.findall(r'"contentUrl"\s*:\s*"([^"]*atchFileId=[^"]*)"', html, re.IGNORECASE)
            matches = [('', content_url) for content_url in urls_only]

        download_urls: Dict[str, str] = {}
        base = file_name or 'file'
        for idx, (fmt, content_url) in enumerate(matches):
            content_url = content_url.replace('&amp;', '&')
            if len(matches) == 1:
                key = base
            elif fmt:
                key = f"{base} ({fmt})"
            else:
                key = f"{base}_{idx + 1}"
            download_urls[key] = content_url
        return download_urls

    def refine_results(self, results: List[CrawlResult]) -> Dict[str, Any]:
        return {"total_refined": 0, "failed_refines": 0, "refined_files": []}
