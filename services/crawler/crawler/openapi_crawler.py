import asyncio
import aiohttp
import collections
import re
import json
import html as html_module
from typing import List, Dict, Optional, Any, Tuple
from urllib.parse import urlencode, urlsplit, urlunsplit
from bs4 import BeautifulSoup

from crawler.base_crawler import BaseCrawler
from crawler.link_spec_builder import (
    DETAIL_FUNCTION_REQUEST_PATH,
    UNVERIFIED,
    build_detail_function_endpoints,
    list_detail_functions,
)
from domain.schemas import CrawlResult, CrawlData
from utils.url_utils import ApiIdExtractor
from infrastructure.detail_page_parser import extract_detail_info
from infrastructure.nara_parser import NaraParser

# The metadata block lives in <li> since the 2026-08 renewal and in <table>
# before it; <input> carries publicDataDetailPk and <select> the detail-function
# dropdown. Parsing is restricted to those tags because a detail page is ~200KB,
# most of it inline <script> the parser never reads.
DETAIL_TAGS = ['table', 'input', 'li', 'select']

# swaggerJson was declared with `var` before the renewal and `const` after it,
# so accept any binding form. The value is a template literal; the escape-aware
# body pattern keeps an escaped backtick inside the JSON from ending the match
# early.
SWAGGER_LITERAL_RE = re.compile(
    r'(?:var|const|let)\s+swaggerJson\s*=\s*`((?:[^`\\]|\\.)*)`'
)

# Hosts that are the portal itself or boilerplate, never a provider endpoint.
EXCLUDED_HOSTS = {
    'data.go.kr',
    'www.data.go.kr',
    'schema.org',
    'www.w3.org',
    'jquery.com',
}

# The renewed detail page no longer renders a LINK document's 제공처 URL: the
# 바로가기 button asks this endpoint for it (see fn_goUrlLink in the page). One
# deterministic request per LINK document restores info['URL'], which the whole
# stored LINK corpus is keyed on (link_docs/runner.py build_tasks).
LINK_URL_PATH = '/tcs/dss/selectApiLinkUrl.do'

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
        # Per-outcome tally of the LINK provider-URL lookups, so a run can be
        # judged without re-reading every stored document.
        self.link_url_lookups: collections.Counter = collections.Counter()
        # Same, for the per-option detail-function fetches.
        self.detail_function_fetches: collections.Counter = collections.Counter()

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

                soup = self.make_soup(html, DETAIL_TAGS)
                html_info = extract_detail_info(soup, html)
                if not html_info:
                    # A layout the strainer's tag list has not caught up with
                    # would otherwise drop every field without a trace, so read
                    # the full tree once before accepting an empty result.
                    html_info = extract_detail_info(html)
                merged_info = csv_info.copy()
                merged_info.update(html_info)

                operation_ids = self._extract_public_data_detail_pk(soup)
                swagger_json = self._extract_swagger_json_from_html(html)
                api_type = self._detect_api_type(merged_info, soup, swagger_json)
                api_type_evidence = self._build_api_type_evidence(merged_info, soup, swagger_json, html)
                external_endpoint_urls = self._extract_external_endpoint_urls(html)
                if self.target_api_type and api_type != self.target_api_type:
                    self.skipped_by_api_type += 1
                    return CrawlResult(url=url, success=True, data=None)

                # Only LINK documents have a 제공처 URL to recover, and only they
                # pay for the extra request.
                if api_type == 'openapi_link':
                    declared_url = str(merged_info.get('URL') or '').strip()
                    if declared_url:
                        # Pre-renewal pages rendered the URL themselves; when a
                        # page still does, the lookup buys nothing.
                        lookup = {'status': 'page_provided_url', 'url': declared_url}
                    else:
                        lookup = await self._fetch_link_url(session, url, api_id, operation_ids)
                        if lookup['url']:
                            merged_info['URL'] = lookup['url']
                    api_type_evidence['link_url_lookup'] = lookup
                    self.link_url_lookups[lookup['status']] += 1
                    if lookup['url']:
                        external_endpoint_urls = self._with_declared_endpoint(
                            external_endpoint_urls, lookup['url']
                        )

                data_payload: Dict[str, Any] = {}
                detail_function_records: List[Dict[str, Any]] = []
                if api_type == 'openapi_new':
                    # The inline spec already enumerates every operation, so a
                    # dropdown on such a page buys nothing and costs requests.
                    parser = NaraParser()
                    data_payload['swagger_json'] = swagger_json
                    data_payload['endpoints'] = parser.extract_endpoints(swagger_json or {})
                else:
                    # No inline swaggerJson — but data.go.kr still renders the
                    # request/response tables on the detail page, so the parser can
                    # synthesise the same endpoints[] shape from that HTML. This
                    # applies to legacy (openapi_old) documents just as much as to
                    # openapi_link. Without this, a REST-declared document whose
                    # inline spec cannot be parsed would stay unsearchable.
                    parser = NaraParser()
                    page_endpoints = parser.extract_endpoints(html, operation_ids)
                    functions = list_detail_functions(soup)
                    if functions:
                        fetched, detail_function_records = await self._fetch_detail_functions(
                            session, url, api_id, functions, operation_ids
                        )
                        # The page's own block is a duplicate of one option, so
                        # it only fills gaps — including the case where every
                        # fetch failed and it is all the document has.
                        data_payload['endpoints'] = self._merge_endpoints(
                            fetched, page_endpoints
                        )
                    else:
                        data_payload['endpoints'] = page_endpoints

                quick_summary = await self.collect_quick_summary(session, url, api_id)

                crawl_data = CrawlData(
                    api_id=api_id,
                    api_type=api_type,
                    crawled_url=url,
                    info=merged_info,
                    swagger_json=data_payload.get('swagger_json'),
                    endpoints=data_payload.get('endpoints'),
                    operation_ids=operation_ids,
                    external_endpoint_urls=external_endpoint_urls,
                    api_type_evidence=api_type_evidence,
                    detail_functions=detail_function_records,
                    quick_summary=quick_summary,
                )

                return CrawlResult(url=url, success=True, data=crawl_data)
            except Exception as e:
                return CrawlResult(url=url, success=False, errors=[str(e)])

    def _detect_api_type(
        self,
        info: Dict,
        _soup: BeautifulSoup,
        swagger_json: Optional[Dict],
    ) -> str:
        """Determines subtype from the declared delivery mode and parsed spec."""
        api_type_val = str(info.get('API 유형', '') or info.get('API 타입', '')).upper()
        if 'LINK' in api_type_val:
            return 'openapi_link'
        if swagger_json:
            return 'openapi_new'
        # A non-LINK OpenAPI page without a parseable inline Swagger document is
        # the legacy representation. Its contract is rendered in HTML tables.
        return 'openapi_old'

    def _build_api_type_evidence(
        self,
        info: Dict,
        soup: BeautifulSoup,
        swagger_json: Optional[Dict],
        html: str = '',
    ) -> Dict[str, Any]:
        """Returns the observable evidence used by ``_detect_api_type``."""
        api_type_val = str(info.get('API 유형', '') or info.get('API 타입', '')).strip()
        csv_declares_link = 'LINK' in api_type_val.upper()
        swagger_present = bool(swagger_json)
        swagger_marker_present = self._find_swagger_literal(html) is not None
        if csv_declares_link:
            reason = 'csv_api_type_declares_link'
        elif swagger_present:
            reason = 'inline_swagger_json_parsed'
        elif swagger_marker_present:
            reason = 'legacy_inline_swagger_unparseable'
        else:
            reason = 'legacy_html_without_inline_swagger'
        return {
            'reason': reason,
            'csv_api_type': api_type_val or None,
            'csv_declares_link': csv_declares_link,
            'swagger_json_parsed': swagger_present,
            'swagger_marker_present': swagger_marker_present,
            'public_data_detail_pk_present': bool(
                soup.find('input', {'type': 'hidden', 'id': 'publicDataDetailPk'})
            ),
        }

    async def _fetch_link_url(
        self,
        session: aiohttp.ClientSession,
        page_url: str,
        api_id: str,
        operation_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Asks the portal where a LINK document's provider page lives.

        Runs on the caller's session and inside its semaphore slot, so it adds
        no concurrency of its own. Every failure is reported as a status in the
        returned record rather than raised: one unreachable lookup must not cost
        a document its metadata, let alone stop the crawl.
        """
        lookup: Dict[str, Any] = {'status': 'unavailable', 'url': None}
        parsed_page = urlsplit(page_url)
        request_url = urlunsplit((
            parsed_page.scheme or 'https',
            parsed_page.netloc or 'www.data.go.kr',
            LINK_URL_PATH,
            urlencode({'publicDataPk': api_id}),
            '',
        ))
        lookup['request_url'] = request_url

        try:
            async with session.get(request_url) as response:
                if response.status != 200:
                    lookup['status'] = f'http_{response.status}'
                    return lookup
                body = await response.text()
        except asyncio.TimeoutError:
            lookup['status'] = 'timeout'
            return lookup
        except Exception as exc:
            lookup['status'] = 'request_failed'
            lookup['message'] = str(exc)
            return lookup

        # The endpoint answers JSON under a text/html content type, so the body
        # is parsed directly; aiohttp's resp.json() would reject it outright.
        try:
            payload = json.loads(body)
        except (ValueError, TypeError):
            lookup['status'] = 'unreadable_body'
            return lookup
        if not isinstance(payload, dict):
            lookup['status'] = 'unreadable_body'
            return lookup

        detail_pk = str(payload.get('publicDataDetailPk') or '').strip()
        if detail_pk:
            # The page's own hidden input carries this value, so only the
            # agreement is recorded — and the response's value when it disagrees.
            matches = bool(operation_ids) and detail_pk in operation_ids
            lookup['detail_pk_matches_page'] = matches
            if not matches:
                lookup['public_data_detail_pk'] = detail_pk

        # The page's own button treats anything but a literal true as a refusal.
        if payload.get('status') is not True:
            lookup['status'] = 'declined'
            message = str(payload.get('errorDc') or '').strip()
            if message:
                lookup['message'] = message
            return lookup

        link_url = str(payload.get('linkUrl') or '').strip()
        if not link_url:
            lookup['status'] = 'empty'
            return lookup

        lookup['status'] = 'ok'
        lookup['url'] = link_url
        return lookup

    def _with_declared_endpoint(self, urls: List[str], declared_url: str) -> List[str]:
        """Adds the portal-declared provider URL to the scraped endpoint list.

        ``_extract_external_endpoint_urls`` puts scraped URLs through a path
        heuristic because a detail page is full of unrelated links. This one is
        not scraped — data.go.kr names it as the document's provider — so only
        the host rules apply. Agency paths such as ``/open_api/`` would not
        survive the heuristic even though they are exactly what Phase B wants.
        """
        try:
            parsed = urlsplit(declared_url)
        except ValueError:
            return urls
        host = (parsed.hostname or '').lower()
        if parsed.scheme.lower() not in ('http', 'https'):
            return urls
        if not host or host in EXCLUDED_HOSTS or host.endswith('.data.go.kr'):
            return urls
        normalized = urlunsplit(
            (parsed.scheme.lower(), parsed.netloc, parsed.path, parsed.query, '')
        )
        if normalized in urls:
            return urls
        return urls + [normalized]

    async def _fetch_detail_functions(
        self,
        session: aiohttp.ClientSession,
        page_url: str,
        api_id: str,
        functions: List[Dict[str, Any]],
        operation_ids: Optional[List[str]] = None,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Collects every operation the detail-function dropdown offers.

        data.go.kr renders one option into the page and leaves the rest behind
        the 조회하기 button, so a document with eight operations otherwise stores
        one. Each option has its own 요청주소, request parameters and response
        elements — verified live on 15061362, whose options resolve to different
        paths (``/GongsiReg`` vs ``/GongsiRenew``).

        Every option is fetched, including the one already on the page: which
        option the server rendered is not stated in the markup, so re-fetching
        it is what makes each endpoint's name trustworthy. The duplicate costs
        one request and is dropped by the caller's merge.

        Runs on the caller's session inside its semaphore slot, so it adds no
        concurrency of its own. Failures are recorded per option and never
        raised — one dead option must not cost a document the other seven.
        """
        parsed_page = urlsplit(page_url)
        request_url = urlunsplit((
            parsed_page.scheme or 'https',
            parsed_page.netloc or 'www.data.go.kr',
            DETAIL_FUNCTION_REQUEST_PATH,
            '',
            '',
        ))
        page_detail_pk = operation_ids[0] if operation_ids else ''

        endpoints: List[Dict[str, Any]] = []
        records: List[Dict[str, Any]] = []
        for function in functions:
            record, built = await self._fetch_one_detail_function(
                session, request_url, function, api_id, page_detail_pk
            )
            self.detail_function_fetches[record['status']] += 1
            records.append(record)
            endpoints.extend(built)
        return endpoints, records

    async def _fetch_one_detail_function(
        self,
        session: aiohttp.ClientSession,
        request_url: str,
        function: Dict[str, Any],
        api_id: str,
        page_detail_pk: str,
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Fetches one option and turns the returned fragment into an endpoint."""
        sequence = str(function.get('oprtin_seq_no') or '').strip()
        name = str(function.get('name') or '').strip()
        record: Dict[str, Any] = {
            'oprtin_seq_no': sequence,
            'name': name,
            'status': 'unavailable',
            'endpoints': 0,
        }
        if not sequence:
            record['status'] = 'no_sequence'
            return record, []

        detail_pk = self._known(function.get('public_data_detail_pk')) or page_detail_pk
        payload = {
            'oprtinSeqNo': sequence,
            'publicDataDetailPk': detail_pk,
            'publicDataPk': self._known(function.get('public_data_pk')) or api_id,
        }

        try:
            async with session.post(request_url, data=payload) as response:
                if response.status != 200:
                    record['status'] = f'http_{response.status}'
                    return record, []
                body = await response.text()
        except asyncio.TimeoutError:
            record['status'] = 'timeout'
            return record, []
        except Exception as exc:
            record['status'] = 'request_failed'
            record['message'] = str(exc)
            return record, []

        built = build_detail_function_endpoints(
            body, detail_pk or UNVERIFIED, name
        )
        if not built:
            # A 200 with no request/response table is the portal answering with
            # an error page, so it is not counted as a collected operation.
            record['status'] = 'no_endpoint'
            return record, []

        record['status'] = 'ok'
        record['endpoints'] = len(built)
        return record, built

    @staticmethod
    def _known(value: Any) -> str:
        """Returns the value unless it is the parser's 'not stated' marker."""
        text = str(value or '').strip()
        return '' if text == UNVERIFIED else text

    def _merge_endpoints(
        self, fetched: List[Dict[str, Any]], from_page: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Keeps every fetched endpoint and adds page ones it does not cover.

        Identity is (method, path, section): options of one document routinely
        share a method and even a path, so the operation name is part of what
        makes an endpoint distinct.
        """
        merged = list(fetched)
        seen = {self._endpoint_key(endpoint) for endpoint in merged}
        for endpoint in from_page:
            key = self._endpoint_key(endpoint)
            if key not in seen:
                seen.add(key)
                merged.append(endpoint)
        return merged

    @staticmethod
    def _endpoint_key(endpoint: Dict[str, Any]) -> tuple:
        return (endpoint.get('method'), endpoint.get('path'), endpoint.get('section'))

    def _extract_external_endpoint_urls(self, html: str) -> List[str]:
        """Extracts external HTTP(S) endpoint candidates embedded in the detail page.

        The page may render endpoint examples as text or JavaScript rather than links,
        so extraction intentionally scans the original HTML. Known metadata/asset
        hosts are excluded, while paths that look like API/service endpoints are kept.
        """
        if not html:
            return []

        decoded = html_module.unescape(html).replace(r'\/', '/')
        candidates = re.findall(r'https?://[^\s<>"\'`]+', decoded, flags=re.IGNORECASE)
        # Agencies version the segment itself ("/openapi2022/restrnt.do"), so a
        # trailing number is accepted. Only digits are allowed after the keyword:
        # letters would make "rest" swallow paths such as "/restaurants/".
        endpoint_hint = re.compile(
            r'/(?:openapi|api|service|services|rest|open-api|v\d+)\d*(?:/|$)',
            re.IGNORECASE,
        )
        urls: List[str] = []
        for candidate in candidates:
            candidate = candidate.rstrip('.,;:)]}\\')
            try:
                parsed = urlsplit(candidate)
            except ValueError:
                continue
            host = (parsed.hostname or '').lower()
            if not host or host in EXCLUDED_HOSTS or host.endswith('.data.go.kr'):
                continue
            if not endpoint_hint.search(parsed.path):
                continue
            normalized = urlunsplit((parsed.scheme.lower(), parsed.netloc, parsed.path, parsed.query, ''))
            if normalized not in urls:
                urls.append(normalized)
        return urls

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

    def _find_swagger_literal(self, html: str) -> Optional[str]:
        """Returns the inline swaggerJson template literal, or None if absent.

        Every OpenAPI detail page declares the variable, but pages without an
        inline spec render it empty (``const swaggerJson = ``;``). An empty
        literal is therefore reported as *no* inline spec rather than as an
        unparseable one — api_type detection turns on that distinction.
        """
        if not html:
            return None
        match = SWAGGER_LITERAL_RE.search(html)
        if not match:
            return None
        return match.group(1).strip() or None

    def _extract_swagger_json_from_html(self, html: str) -> Optional[Dict[str, Any]]:
        """Extracts inline swaggerJson from data.go.kr HTML."""
        json_str = self._find_swagger_literal(html)
        if not json_str:
            return None

        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            try:
                return json.loads(re.sub(r'\s+', ' ', json_str))
            except json.JSONDecodeError:
                return None

    def refine_results(self, results: List[CrawlResult]) -> Dict[str, Any]:
        return {"total_refined": 0, "failed_refines": 0, "refined_files": []}
