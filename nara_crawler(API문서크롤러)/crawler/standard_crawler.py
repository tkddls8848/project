import asyncio
import aiohttp
import json
import os
from bs4 import BeautifulSoup
from typing import List, Dict, Optional, Any

from crawler.base_crawler import BaseCrawler
from domain.schemas import CrawlResult, CrawlData
from utils.text_utils import clean_text
from utils.url_utils import ApiIdExtractor

class StandardCrawler(BaseCrawler):
    """Crawler for standard data type services."""

    def __init__(self, config):
        super().__init__(config)
        self.semaphore = asyncio.Semaphore(config.max_workers)

    async def create_session(self) -> aiohttp.ClientSession:
        """Creates an optimized HTTP session."""
        return self.create_http_session()

    async def crawl(self, urls: List[str], csv_metadata: Optional[Dict[int, Dict]] = None) -> List[CrawlResult]:
        """Executes the crawling process for standard data."""
        # Standard crawler usually takes (url, csv_row) pairs.
        # If csv_metadata is provided as Dict[int, Dict], we need to map urls to it.
        # The main_standard.py logic passed a list of tuples.
        # BaseCrawler signature asks for list of urls and optional metadata dict.
        # We need to adapt.
        
        print(f"\nStarting Standard Crawling for {len(urls)} URLs...")
        
        url_csv_data_pairs = self.pair_urls_with_metadata(urls, csv_metadata)

        results = []
        async with await self.create_session() as session:
            results = await self.collect_in_batches(
                url_csv_data_pairs,
                lambda pair: self._crawl_single(session, pair[0], pair[1]),
                desc="Crawling standard",
                unit="url"
            )

        for result in results:
            if result.success:
                self.stats['success'] += 1
                if result.data and result.data.standard_grid_table:
                    self.stats['table_crawl_success'] = self.stats.get('table_crawl_success', 0) + 1
            else:
                self.stats['failed'] += 1

        return results

    async def _crawl_single(self, session: aiohttp.ClientSession, url: str, csv_row_data: Dict) -> CrawlResult:
        """Crawls a single standard URL."""
        async with self.semaphore:
            errors = []
            api_id = ApiIdExtractor.extract_api_id(url)
            if not api_id:
                return CrawlResult(url=url, success=False, errors=["Could not extract API ID"])

            try:
                async with session.get(url) as response:
                    if response.status != 200:
                         return CrawlResult(url=url, success=False, errors=[f"HTTP {response.status}"])

                    html = await response.text()
                    # No SoupStrainer here: the grid table is matched via
                    # ancestor div/id selectors, so the surrounding structure
                    # must be kept. lxml alone is already a big speedup.
                    soup = self.make_soup(html)

                standard_grid_table = self._extract_standard_grid_table(soup)
                html_info = self._extract_table_bs(soup)
                merged_info = csv_row_data.copy()
                merged_info.update(html_info)

                crawl_data = CrawlData(
                    api_id=api_id,
                    api_type='standard',
                    crawled_url=url,
                    info=merged_info,
                    standard_grid_table=standard_grid_table
                )

                success = bool(merged_info or standard_grid_table)
                if not success:
                    errors.append("Both metadata and Grid Table are missing")

                return CrawlResult(
                    url=url,
                    success=success,
                    data=crawl_data,
                    errors=errors
                )

            except Exception as e:
                return CrawlResult(url=url, success=False, errors=[str(e)])

    def _extract_standard_grid_table(self, soup: BeautifulSoup) -> List[Dict]:
        """Extracts standard grid table from soup."""
        table_data = []
        target_table = None
        selectors = [
            '#tab_layer_grid > div.table-responsive.standard-data-table.boxed-table > table',
            '#tab_layer_grid table',
            'div.standard-data-table table',
            'table.standard-data-table',
        ]
        for selector in selectors:
            target_table = soup.select_one(selector)
            if target_table:
                break

        if not target_table:
            return table_data

        headers = []
        header_row = target_table.find('thead')
        if header_row:
            th_elements = header_row.find_all('th')
            headers = [clean_text(th.get_text()).strip() for th in th_elements]

        if not headers:
            first_row = target_table.find('tr')
            if first_row:
                th_elements = first_row.find_all('th')
                if th_elements:
                    headers = [clean_text(th.get_text()).strip() for th in th_elements]

        tbody = target_table.find('tbody')
        if tbody:
            rows = tbody.find_all('tr')
        else:
            rows = [row for row in target_table.find_all('tr') if row.find('td')]

        for row in rows:
            td_elements = row.find_all('td')
            if not td_elements: continue

            row_data = {}
            for i, td in enumerate(td_elements):
                key = headers[i] if i < len(headers) else f'column_{i}'
                value = clean_text(td.get_text()).strip()
                
                links = td.find_all('a')
                for link in links:
                    href = link.get('href', '').strip()
                    if href:
                        link_key = f'{key}_link' if key else f'link_{i}'
                        row_data[link_key] = href
                
                row_data[key] = value
            
            if row_data:
                table_data.append(row_data)

        return table_data

    def _extract_table_bs(self, soup: BeautifulSoup) -> Dict:
        """Extracts standard detail metadata tables from page HTML."""
        info = {}
        for table in soup.select('table.stdDataDetail, table.dataset-table'):
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

    def refine_results(self, results: List[CrawlResult]) -> Dict[str, Any]:
        return {"total_refined": 0, "failed_refines": 0, "refined_files": []}
