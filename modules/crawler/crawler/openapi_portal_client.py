"""data.go.kr OpenAPI 상세 페이지의 보조 portal 요청 client."""

from __future__ import annotations

import asyncio
import collections
import json
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode, urlsplit, urlunsplit

import aiohttp

from crawler.link_spec_builder import (
    DETAIL_FUNCTION_REQUEST_PATH,
    UNVERIFIED,
    build_detail_function_endpoints,
)

LINK_URL_PATH = "/tcs/dss/selectApiLinkUrl.do"


class OpenAPIPortalClient:
    """보조 요청을 best-effort로 수행하고 status별 횟수를 집계한다."""

    def __init__(self) -> None:
        self.link_url_lookups: collections.Counter = collections.Counter()
        self.detail_function_fetches: collections.Counter = collections.Counter()

    async def resolve_link_url(
        self,
        session: aiohttp.ClientSession,
        page_url: str,
        api_id: str,
        operation_ids: Optional[List[str]] = None,
        declared_url: str = "",
    ) -> Dict[str, Any]:
        if declared_url:
            lookup: Dict[str, Any] = {
                "status": "page_provided_url",
                "url": declared_url,
            }
        else:
            lookup = await self._fetch_link_url(
                session, page_url, api_id, operation_ids
            )
        self.link_url_lookups[lookup["status"]] += 1
        return lookup

    async def _fetch_link_url(
        self,
        session: aiohttp.ClientSession,
        page_url: str,
        api_id: str,
        operation_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """LINK 제공처 URL을 조회하되 실패를 status로 반환한다."""
        lookup: Dict[str, Any] = {"status": "unavailable", "url": None}
        parsed_page = urlsplit(page_url)
        request_url = urlunsplit(
            (
                parsed_page.scheme or "https",
                parsed_page.netloc or "www.data.go.kr",
                LINK_URL_PATH,
                urlencode({"publicDataPk": api_id}),
                "",
            )
        )
        lookup["request_url"] = request_url

        try:
            async with session.get(request_url) as response:
                if response.status != 200:
                    lookup["status"] = f"http_{response.status}"
                    return lookup
                body = await response.text()
        except asyncio.TimeoutError:
            lookup["status"] = "timeout"
            return lookup
        except Exception as exc:
            lookup["status"] = "request_failed"
            lookup["message"] = str(exc)
            return lookup

        try:
            payload = json.loads(body)
        except (ValueError, TypeError):
            lookup["status"] = "unreadable_body"
            return lookup
        if not isinstance(payload, dict):
            lookup["status"] = "unreadable_body"
            return lookup

        detail_pk = str(payload.get("publicDataDetailPk") or "").strip()
        if detail_pk:
            matches = bool(operation_ids) and detail_pk in operation_ids
            lookup["detail_pk_matches_page"] = matches
            if not matches:
                lookup["public_data_detail_pk"] = detail_pk

        if payload.get("status") is not True:
            lookup["status"] = "declined"
            message = str(payload.get("errorDc") or "").strip()
            if message:
                lookup["message"] = message
            return lookup

        link_url = str(payload.get("linkUrl") or "").strip()
        if not link_url:
            lookup["status"] = "empty"
            return lookup

        lookup["status"] = "ok"
        lookup["url"] = link_url
        return lookup

    async def fetch_detail_functions(
        self,
        session: aiohttp.ClientSession,
        page_url: str,
        api_id: str,
        functions: List[Dict[str, Any]],
        operation_ids: Optional[List[str]] = None,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """드롭다운의 모든 기능을 조회하고 옵션별 실패를 격리한다."""
        parsed_page = urlsplit(page_url)
        request_url = urlunsplit(
            (
                parsed_page.scheme or "https",
                parsed_page.netloc or "www.data.go.kr",
                DETAIL_FUNCTION_REQUEST_PATH,
                "",
                "",
            )
        )
        page_detail_pk = operation_ids[0] if operation_ids else ""

        endpoints: List[Dict[str, Any]] = []
        records: List[Dict[str, Any]] = []
        for function in functions:
            record, built = await self._fetch_one_detail_function(
                session, request_url, function, api_id, page_detail_pk
            )
            self.detail_function_fetches[record["status"]] += 1
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
        """기능 하나를 조회해 endpoint로 바꾸고 실패는 status로 반환한다."""
        sequence = str(function.get("oprtin_seq_no") or "").strip()
        name = str(function.get("name") or "").strip()
        record: Dict[str, Any] = {
            "oprtin_seq_no": sequence,
            "name": name,
            "status": "unavailable",
            "endpoints": 0,
        }
        if not sequence:
            record["status"] = "no_sequence"
            return record, []

        detail_pk = self._known(function.get("public_data_detail_pk")) or page_detail_pk
        payload = {
            "oprtinSeqNo": sequence,
            "publicDataDetailPk": detail_pk,
            "publicDataPk": self._known(function.get("public_data_pk")) or api_id,
        }

        try:
            async with session.post(request_url, data=payload) as response:
                if response.status != 200:
                    record["status"] = f"http_{response.status}"
                    return record, []
                body = await response.text()
        except asyncio.TimeoutError:
            record["status"] = "timeout"
            return record, []
        except Exception as exc:
            record["status"] = "request_failed"
            record["message"] = str(exc)
            return record, []

        built = build_detail_function_endpoints(body, detail_pk or UNVERIFIED, name)
        if not built:
            record["status"] = "no_endpoint"
            return record, []

        record["status"] = "ok"
        record["endpoints"] = len(built)
        return record, built

    @staticmethod
    def _known(value: Any) -> str:
        text = str(value or "").strip()
        return "" if text == UNVERIFIED else text


__all__ = ["OpenAPIPortalClient"]
