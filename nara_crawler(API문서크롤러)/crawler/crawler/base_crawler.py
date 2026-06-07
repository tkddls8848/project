from abc import ABC, abstractmethod
import asyncio
import aiohttp
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional, Any
from bs4 import BeautifulSoup, SoupStrainer
from tqdm import tqdm

from crawler.domain.schemas import CrawlerConfig, CrawlResult
from crawler.managers.file_storage import DataExporter

from crawler.managers.summary_service import SummaryService

class BaseCrawler(ABC):
    """Abstract base class for all crawlers."""

    def __init__(self, config: CrawlerConfig):
        self.config = config
        self.stats = {
            'success': 0,
            'failed': 0,
            'total_time': 0,
            'api_call_success': 0,
            'api_call_failed': 0,
            'csv_processed': 0,
            'table_crawl_success': 0,
            'table_crawl_failed': 0
        }

    @abstractmethod
    async def crawl(self, urls: List[str], csv_metadata: Optional[Dict[int, Dict]] = None) -> List[CrawlResult]:
        """Execute the crawling logic."""
        pass

    @staticmethod
    def make_soup(html: str, only_tags: Optional[List[str]] = None) -> BeautifulSoup:
        """Builds a BeautifulSoup tree using the fast C-based lxml parser.

        When ``only_tags`` is given, a SoupStrainer restricts parsing to those
        tags (and their descendants), skipping the page's large <script> blocks
        and cutting parse time/memory on these script-heavy data.go.kr pages.
        """
        if only_tags:
            return BeautifulSoup(html, 'lxml', parse_only=SoupStrainer(only_tags))
        return BeautifulSoup(html, 'lxml')

    def create_http_session(self) -> aiohttp.ClientSession:
        """Creates a shared default HTTP session for crawlers."""
        connector_limit = max(100, self.config.max_workers * 2)
        per_host_limit = max(30, self.config.max_workers)
        connector = aiohttp.TCPConnector(
            limit=connector_limit,
            limit_per_host=per_host_limit,
            ttl_dns_cache=300,
            enable_cleanup_closed=True
        )
        timeout = aiohttp.ClientTimeout(total=15, connect=5, sock_read=10)
        return aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        )

    def pair_urls_with_metadata(self, urls: List[str], csv_metadata: Optional[Dict[int, Dict]] = None) -> List[tuple[str, Dict]]:
        """Pairs generated URLs with their CSV metadata rows."""
        if not csv_metadata:
            return [(url, {}) for url in urls]

        pairs = []
        for url in urls:
            match = re.search(r'/data/(\d+)/', url)
            if not match:
                pairs.append((url, {}))
                continue
            doc_num = int(match.group(1))
            pairs.append((url, csv_metadata.get(doc_num, {})))
        return pairs

    async def collect_in_batches(self, items: List[Any], task_factory, desc: str, unit: str = "url", batch_size: Optional[int] = None) -> List[CrawlResult]:
        """Runs async work in bounded batches to avoid creating all tasks at once."""
        if not items:
            return []

        effective_batch_size = batch_size or max(1, self.config.max_workers * 4)
        results = []

        with tqdm(total=len(items), desc=desc, unit=unit) as progress:
            for start in range(0, len(items), effective_batch_size):
                batch = items[start:start + effective_batch_size]
                tasks = [task_factory(item) for item in batch]

                for coro in asyncio.as_completed(tasks):
                    try:
                        results.append(await coro)
                    except Exception as exc:
                        results.append(CrawlResult(url="unknown", success=False, errors=[str(exc)]))
                    finally:
                        progress.update(1)

        return results

    def save_results(self, results: List[CrawlResult]) -> Dict[str, Any]:
        """Saves the crawled results using DataExporter."""
        saved_info = {
            'total_saved': 0,
            'failed_saves': 0,
            'saved_files': []
        }

        print(f"\nSaving results to {self.config.output_dir}...")
        save_targets = [
            result
            for result in results
            if result.success and result.data
        ]

        if not save_targets:
            return saved_info

        def save_one(result: CrawlResult):
            data_dict = result.data.model_dump(exclude_none=True)
            saved_files, save_errors = DataExporter.save_crawling_result(
                data=data_dict,
                output_dir=self.config.output_dir,
                api_id=result.data.api_id,
                formats=self.config.formats
            )
            return saved_files, save_errors

        save_workers = min(32, max(1, self.config.max_workers))
        with ThreadPoolExecutor(max_workers=save_workers) as executor:
            futures = [executor.submit(save_one, result) for result in save_targets]
            for future in tqdm(as_completed(futures), total=len(futures), desc="Saving results", unit="file"):
                try:
                    saved_files, save_errors = future.result()
                except Exception as exc:
                    saved_files, save_errors = [], [str(exc)]

                if saved_files:
                    saved_info['total_saved'] += 1
                    saved_info['saved_files'].extend(saved_files)
                else:
                    saved_info['failed_saves'] += 1

                if save_errors:
                    saved_info.setdefault('save_errors', []).extend(save_errors)

        return saved_info

    def save_results_sequential(self, results: List[CrawlResult]) -> Dict[str, Any]:
        """Saves results one by one. Kept for debugging output or filesystem issues."""
        saved_info = {
            'total_saved': 0,
            'failed_saves': 0,
            'saved_files': []
        }

        print(f"\nSaving results to {self.config.output_dir}...")
        for result in tqdm(results, desc="Saving results", unit="file"):
            if result.success and result.data:
                # Convert Pydantic model to dict for saving
                data_dict = result.data.model_dump(exclude_none=True)
                
                saved_files, save_errors = DataExporter.save_crawling_result(
                    data=data_dict,
                    output_dir=self.config.output_dir,
                    api_id=result.data.api_id,
                    formats=self.config.formats
                )

                if saved_files:
                    saved_info['total_saved'] += 1
                    saved_info['saved_files'].extend(saved_files)
                else:
                    saved_info['failed_saves'] += 1
            elif not result.success:
                 saved_info['failed_saves'] += 0

        return saved_info

    @abstractmethod
    def refine_results(self, results: List[CrawlResult]) -> Dict[str, Any]:
        """Refines the raw crawled data."""
        pass

    def generate_summary(self, results: List[CrawlResult], saved_info: Dict, extra_stats: Dict = None, start_doc: int = None, end_doc: int = None) -> Dict[str, Any]:
        """Generates a summary report."""
        return SummaryService.generate_crawling_summary(results, self.stats, saved_info, extra_stats, start_doc, end_doc)
