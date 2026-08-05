import os
import asyncio
import aiohttp
import json
import re
import html as html_module
from typing import List, Dict, Optional, Any
from bs4 import BeautifulSoup

from crawler.base_crawler import BaseCrawler
from domain.schemas import CrawlResult, CrawlData
from infrastructure.detail_page_parser import extract_detail_info
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
                jsonld_datasets = []
                merged_info = csv_row_data.copy()
                try:
                    async with session.get(url) as response:
                        if response.status == 200:
                            html = await response.text()
                            # Parsed whole rather than through a SoupStrainer: the
                            # renewal moved metadata into <li><strong class="key">
                            # blocks, and any tag list narrow enough to be worth its
                            # ~9% parse saving silently drops whichever tags the
                            # shared parser selects — which is how this broke before.
                            soup = self.make_soup(html)
                            html_info = extract_detail_info(soup, html)
                            html_operation_ids = self._extract_public_data_detail_pks(soup)
                            merged_info.update(html_info)
                            file_name = merged_info.get('파일데이터명') or merged_info.get('목록명') or api_id
                            jsonld_datasets = self._extract_jsonld_datasets(html)
                            jsonld_download_urls = self._extract_jsonld_download_urls(
                                html, file_name, jsonld_datasets
                            )
                except Exception as exc:
                    errors.append(f"HTML metadata fetch failed: {exc}")

                # Fast path: pages whose file is hosted on the portal embed the
                # full download URL (atchFileId) in their JSON-LD, so the links
                # come out of the single page fetch with no extra
                # infuser/selectFileDataDownload requests.
                #
                # Datasets served from the agency's own site instead
                # (제공형태 "기관자체에서 다운로드") carry no JSON-LD and no
                # atchFileId at all, so they always take the fallback below.
                if jsonld_download_urls:
                    download_urls_dict = jsonld_download_urls
                    operation_ids = html_operation_ids
                    self.stats['jsonld_fastpath'] = self.stats.get('jsonld_fastpath', 0) + 1
                else:
                    # Fallback: resolve operation IDs, then fetch atchFileId per file.
                    # The page's own publicDataDetailPk is preferred: it is the uddi
                    # selectFileDataDownload expects, whereas infuser returns a
                    # different id shape and answered 404 for every namespace tried
                    # on 2026-08-03. infuser is still queried when the page has no
                    # id, so a namespace that does resolve is not lost.
                    operation_ids = html_operation_ids
                    if not operation_ids:
                        operation_ids = await self._extract_operation_ids(session, api_id)

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

                quick_summary = await self.collect_quick_summary(session, url, api_id)

                # Prepare Data
                crawl_data = CrawlData(
                    api_id=api_id,
                    api_type='fileData',
                    crawled_url=url,
                    info=merged_info,
                    operation_ids=operation_ids,
                    download_urls=download_urls_dict,
                    jsonld_datasets=jsonld_datasets,
                    quick_summary=quick_summary,
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
        """Deprecated alias for the shared detail-page parser.

        The table scan this used to carry is gone; ``utils.metadata_updater``
        borrows this crawler purely for the helper, so the name is kept as a
        delegation rather than broken from the outside. New code should call
        ``extract_detail_info`` directly.

        Note that ``metadata_updater`` passes a soup built with a
        ``['table', 'input']`` strainer, which drops the renewed key blocks
        before this is ever reached — that call site needs widening too.
        """
        return extract_detail_info(soup)

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

    def _extract_jsonld_download_urls(
        self,
        html: str,
        file_name: str,
        datasets: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, str]:
        """Extracts download URLs from parsed Dataset JSON-LD distributions."""
        if not html:
            return {}

        matches: List[tuple[str, str]] = []
        for dataset in datasets if datasets is not None else self._extract_jsonld_datasets(html):
            distributions = dataset.get('distribution', [])
            if isinstance(distributions, dict):
                distributions = [distributions]
            if not isinstance(distributions, list):
                continue
            for distribution in distributions:
                if not isinstance(distribution, dict):
                    continue
                content_url = distribution.get('contentUrl')
                if isinstance(content_url, str) and 'atchFileId=' in content_url:
                    encoding_format = distribution.get('encodingFormat', '')
                    matches.append((str(encoding_format or ''), content_url))

        # Preserve the old download fast path even when a malformed block is too
        # damaged for the tolerant full-document parser.
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

    def _extract_jsonld_datasets(self, html: str) -> List[Dict[str, Any]]:
        """Parses and preserves complete schema.org Dataset JSON-LD objects.

        Some data.go.kr pages contain bare quotes inside ``description``. The
        tolerant loader repairs only quotes that cannot close a JSON key/value,
        then retries with permissive control-character handling.
        """
        if not html:
            return []

        soup = BeautifulSoup(html, 'lxml')
        datasets: List[Dict[str, Any]] = []
        for script in soup.find_all('script', attrs={'type': re.compile(r'application/ld\+json', re.I)}):
            raw = script.string if script.string is not None else script.get_text()
            parsed = self._loads_jsonld_tolerant(raw or '')
            if parsed is None:
                continue
            self._collect_jsonld_datasets(parsed, datasets)
        return datasets

    def _loads_jsonld_tolerant(self, raw: str) -> Optional[Any]:
        text = html_module.unescape(raw).strip()
        if text.startswith('<![CDATA[') and text.endswith(']]>'):
            text = text[9:-3].strip()
        if not text:
            return None
        try:
            return json.loads(text, strict=False)
        except json.JSONDecodeError:
            repaired = self._repair_json_string_field(text, 'description')
            repaired = self._repair_bare_json_quotes(repaired)
            repaired = re.sub(r',\s*([}\]])', r'\1', repaired)
            try:
                return json.loads(repaired, strict=False)
            except json.JSONDecodeError:
                return None

    def _repair_json_string_field(self, text: str, field_name: str) -> str:
        """Escapes bare quotes up to the next JSON property after a string field."""
        field_pattern = re.compile(rf'("{re.escape(field_name)}"\s*:\s*")', re.I)
        cursor = 0
        pieces: List[str] = []
        while True:
            match = field_pattern.search(text, cursor)
            if not match:
                pieces.append(text[cursor:])
                break
            pieces.append(text[cursor:match.end()])
            value_start = match.end()
            closing = re.search(
                r'(?<!\\)"\s*(?=,\s*"[^"\\]+"\s*:|})',
                text[value_start:],
                re.DOTALL,
            )
            if not closing:
                pieces.append(text[value_start:])
                break
            value_end = value_start + closing.start()
            value = text[value_start:value_end]
            value = re.sub(r'(?<!\\)"', r'\\"', value)
            pieces.extend((value, text[value_end:value_end + 1]))
            cursor = value_end + 1
        return ''.join(pieces)

    def _repair_bare_json_quotes(self, text: str) -> str:
        output: List[str] = []
        in_string = False
        escaped = False
        for index, char in enumerate(text):
            if escaped:
                output.append(char)
                escaped = False
                continue
            if char == '\\' and in_string:
                output.append(char)
                escaped = True
                continue
            if char != '"':
                output.append(char)
                continue
            if not in_string:
                in_string = True
                output.append(char)
                continue

            next_non_space = ''
            for following in text[index + 1:]:
                if not following.isspace():
                    next_non_space = following
                    break
            if next_non_space in ':,}]' or not next_non_space:
                in_string = False
                output.append(char)
            else:
                output.append(r'\"')
        return ''.join(output)

    def _collect_jsonld_datasets(self, value: Any, datasets: List[Dict[str, Any]]) -> None:
        if isinstance(value, dict):
            jsonld_type = value.get('@type')
            types = jsonld_type if isinstance(jsonld_type, list) else [jsonld_type]
            if any(
                str(item).lower() == 'dataset' or str(item).lower().rstrip('/').endswith('/dataset')
                for item in types
                if item is not None
            ):
                datasets.append(value)
            for child in value.values():
                self._collect_jsonld_datasets(child, datasets)
        elif isinstance(value, list):
            for child in value:
                self._collect_jsonld_datasets(child, datasets)

    def refine_results(self, results: List[CrawlResult]) -> Dict[str, Any]:
        return {"total_refined": 0, "failed_refines": 0, "refined_files": []}
