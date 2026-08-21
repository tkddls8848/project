"""Build OpenAPI-like endpoint records from data.go.kr LINK detail HTML.

The builder is deliberately a pure parser. It consumes the HTML already fetched
for the data.go.kr detail page and never contacts the linked provider service.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Union
from urllib.parse import urlsplit

from bs4 import BeautifulSoup, Tag


UNVERIFIED = "unverified"
_HTTP_METHODS = ("GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS")

# Containers that hold one rendered detail-function block, most recent markup
# first. The 2026-08 data.go.kr renewal replaced the two legacy containers with
# ``#apiDetailFunctionDiv``; the legacy ones are kept as fallbacks so documents
# captured before the renewal keep parsing. Note that the literal string
# ``open-api-detail-result`` still appears inside the page's AJAX script, so
# container detection must go through ``soup.select`` and never a substring
# check on the raw HTML.
_DETAIL_ROOT_SELECTORS = (
    "#apiDetailFunctionDiv",
    ".open-api-detail-result",
    "#tab_layer_detail_function",
)

# data.go.kr renders only one detail function server-side even when
# ``select#open_api_detail_select`` offers several, and every option has its own
# 요청주소, request parameters and response elements. The rest are pulled in by
# the 조회하기 button, ``apiObj.fn_selectApiDetailFunction()``:
#
#     POST /tcs/dss/selectApiDetailFunction.do
#         oprtinSeqNo        = option value of select#open_api_detail_select
#         publicDataDetailPk = value of input#publicDataDetailPk
#         publicDataPk       = value of input#publicDataPk
#
# All three fields are required: the portal answers 404 when publicDataPk is
# left out (verified live on 15000063, 2026-08-05). The page also carries a
# stale global ``fn_selectApiDetailFunction`` that omits it — that one is dead
# code and must not be used as the contract.
#
# The response is a container-less HTML fragment which the page appends to
# ``#apiDetailFunctionDiv`` after removing ``.data-info-tit`` and
# ``.data-report-group``. This module stays a pure parser: it never issues the
# request. ``list_detail_functions`` reports the choices and ``build_fragment``
# turns a fetched answer into an endpoint.
DETAIL_FUNCTION_REQUEST_PATH = "/tcs/dss/selectApiDetailFunction.do"


class LinkSpecBuilder:
    """Convert rendered LINK detail-function tables to ``endpoints[]`` records."""

    def build(
        self,
        html: Union[str, BeautifulSoup, Tag],
        operation_ids: Optional[Sequence[str]] = None,
    ) -> List[Dict[str, Any]]:
        soup = self._make_soup(html)
        if soup is None:
            return []

        identifiers = self._operation_ids(soup, operation_ids)
        roots = self._detail_roots(soup)

        endpoints: List[Dict[str, Any]] = []
        seen = set()
        for index, root in enumerate(roots):
            operation_id = self._operation_id_for_root(root, identifiers, index)
            endpoint = self._build_endpoint(root, operation_id)
            if not endpoint:
                continue
            signature = repr(endpoint)
            if signature not in seen:
                seen.add(signature)
                endpoints.append(endpoint)
        return endpoints

    def _detail_roots(self, soup: Union[BeautifulSoup, Tag]) -> List[Tag]:
        """Return the detail-function containers rendered on the page.

        The first selector that actually matches an element wins. When the
        renewal container already holds legacy blocks — the page's AJAX handler
        appends fetched fragments into it — the inner blocks are used so each
        detail function stays a separate endpoint.
        """
        for selector in _DETAIL_ROOT_SELECTORS:
            matched = list(soup.select(selector))
            if not matched:
                continue
            roots: List[Tag] = []
            for root in matched:
                nested = list(root.select(".open-api-detail-result"))
                roots.extend(nested or [root])
            return roots
        return []

    def _make_soup(
        self, html: Union[str, BeautifulSoup, Tag]
    ) -> Optional[Union[BeautifulSoup, Tag]]:
        if isinstance(html, (BeautifulSoup, Tag)):
            return html
        if not isinstance(html, str) or not html.strip():
            return None
        return BeautifulSoup(html, "lxml")

    def _operation_ids(
        self, soup: Union[BeautifulSoup, Tag], operation_ids: Optional[Sequence[str]]
    ) -> List[str]:
        values: Iterable[Any]
        if operation_ids:
            values = operation_ids
        else:
            values = (
                node.get("value")
                for node in soup.select("input#publicDataDetailPk")
            )
        result: List[str] = []
        for value in values:
            normalized = self._clean(value)
            if normalized and normalized not in result:
                result.append(normalized)
        return result

    def _operation_id_for_root(
        self, root: Tag, operation_ids: Sequence[str], index: int
    ) -> str:
        for attribute in ("data-operation-id", "data-public-data-detail-pk"):
            value = self._clean(root.get(attribute))
            if value:
                return value
        embedded = root.select_one("input#publicDataDetailPk")
        if embedded and self._clean(embedded.get("value")):
            return self._clean(embedded.get("value"))
        if len(operation_ids) == 1:
            return operation_ids[0]
        if index < len(operation_ids):
            return operation_ids[index]
        return UNVERIFIED

    def build_fragment(
        self,
        html: Union[str, BeautifulSoup, Tag],
        operation_id: str = UNVERIFIED,
        section: str = "",
    ) -> List[Dict[str, Any]]:
        """Build the endpoint for one fetched detail-function fragment.

        The fragment has none of the page's container markup — it is only what
        the page appends into ``#apiDetailFunctionDiv`` — so the whole fragment
        is the root. ``section`` carries the dropdown label: the fragment states
        its own heading ("등록기준사항신고 리스트") but not the name the caller
        selected it by ("국토교통부_등록기준사항신고"), and the document is keyed
        on the latter.
        """
        soup = self._make_soup(html)
        if soup is None:
            return []
        endpoint = self._build_endpoint(soup, operation_id, section=section)
        return [endpoint] if endpoint else []

    def _build_endpoint(
        self, root: Tag, operation_id: str, section: str = ""
    ) -> Optional[Dict[str, Any]]:
        request_tables: List[Tag] = []
        response_tables: List[Tag] = []
        for table in root.select("table"):
            label = self._table_label(table, root).lower()
            if "요청변수" in label or "request parameter" in label:
                request_tables.append(table)
            elif any(
                marker in label
                for marker in ("출력결과", "응답변수", "response element", "response parameter")
            ):
                response_tables.append(table)

        if not request_tables and not response_tables:
            return None

        title = section or self._detail_title(root)
        description = self._description(root, title)
        parameters = [item for table in request_tables for item in self._parameters(table)]
        responses = [item for table in response_tables for item in self._responses(table)]
        tags = [operation_id] if operation_id != UNVERIFIED else []
        return {
            "method": self._explicit_method(root),
            "path": self._explicit_path(root),
            "description": description,
            "parameters": parameters,
            "responses": responses,
            "tags": tags,
            "section": title or operation_id or UNVERIFIED,
        }

    def _detail_title(self, root: Tag) -> str:
        select = root.find_previous("select", id="open_api_detail_select")
        if select:
            selected = select.select_one("option[selected]") or select.select_one("option")
            if selected:
                return self._clean(selected.get_text(" ", strip=True))
        return ""

    def _description(self, root: Tag, fallback: str) -> str:
        for heading in root.find_all(["h3", "h4", "h5"], recursive=False):
            text = self._clean(heading.get_text(" ", strip=True))
            if text and not self._is_table_heading(text) and text != "상세기능":
                return text
        return fallback

    def _table_label(self, table: Tag, root: Tag) -> str:
        caption = table.find("caption")
        if caption and self._clean(caption.get_text(" ", strip=True)):
            return self._clean(caption.get_text(" ", strip=True))
        heading = table.find_previous(["h3", "h4", "h5", "p"])
        if heading and heading in root.descendants:
            return self._clean(heading.get_text(" ", strip=True))
        return ""

    def _table_headers(self, table: Tag) -> List[str]:
        row = table.select_one("thead tr") or table.find("tr")
        if not row:
            return []
        return [self._clean(cell.get_text(" ", strip=True)) for cell in row.find_all(["th", "td"])]

    def _rows(self, table: Tag) -> Iterable[Dict[str, str]]:
        headers = self._table_headers(table)
        if not headers:
            return []
        body_rows = table.select("tbody tr")
        if not body_rows:
            body_rows = table.find_all("tr")[1:]
        records: List[Dict[str, str]] = []
        for row in body_rows:
            cells = row.find_all(["th", "td"], recursive=False)
            if not cells:
                cells = row.find_all(["th", "td"])
            values = [self._clean(cell.get_text(" ", strip=True)) for cell in cells]
            if any(values):
                records.append({header: values[i] if i < len(values) else "" for i, header in enumerate(headers)})
        return records

    def _parameters(self, table: Tag) -> List[Dict[str, Any]]:
        parameters: List[Dict[str, Any]] = []
        for row in self._rows(table):
            english_name = self._value(row, "항목명(영문)", "영문명", "변수명", "name")
            korean_name = self._value(row, "항목명(국문)", "국문명")
            name = english_name or korean_name
            if not name:
                continue
            description = self._value(row, "항목설명", "설명", "description")
            if korean_name and description and korean_name != description:
                description = f"{korean_name}: {description}"
            elif not description:
                description = korean_name
            division = self._value(row, "항목구분", "필수여부", "required")
            parameter_type = self._value(
                row, "데이터타입", "데이터 타입", "자료형", "타입", "type"
            ) or UNVERIFIED
            parameters.append(
                {
                    "name": name,
                    "description": description,
                    "required": self._required(division),
                    "type": parameter_type,
                }
            )
        return parameters

    def _responses(self, table: Tag) -> List[Dict[str, Any]]:
        responses: List[Dict[str, Any]] = []
        for row in self._rows(table):
            # A generic "응답코드" may be an application field such as
            # resultCode, not an HTTP status. Only accept explicitly HTTP-labelled
            # columns; otherwise retain the required unverified marker.
            status_code = self._value(
                row, "HTTP 상태코드", "HTTP 응답코드", "http status code"
            )
            english_name = self._value(row, "항목명(영문)", "영문명", "변수명", "name")
            korean_name = self._value(row, "항목명(국문)", "국문명")
            description = self._value(row, "항목설명", "설명", "description")
            name = english_name or korean_name
            if name and description and name != description:
                description = f"{name}: {description}"
            elif name and not description:
                description = name
            status_code = status_code or UNVERIFIED
            if status_code == UNVERIFIED and not description:
                continue
            responses.append({"status_code": status_code, "description": description})
        return responses

    def _required(self, value: str) -> bool:
        normalized = re.sub(r"\s+", "", value).lower()
        return normalized in {"필수", "required", "y", "yes", "true", "1"}

    def _explicit_method(self, root: Tag) -> str:
        for label in root.find_all(["strong", "th", "dt"]):
            label_text = self._clean(label.get_text(" ", strip=True)).lower()
            if not any(marker in label_text for marker in ("http method", "http메서드", "요청방식", "요청 방법")):
                continue
            method = self._method_token(self._text_after_label(label))
            if method:
                return method

        sample = " ".join(
            node.get_text(" ", strip=True)
            for node in root.select("pre, code, textarea, #sampleCodeArea")
        )
        methods = "|".join(_HTTP_METHODS)
        patterns = (
            rf"\b-X\s+({methods})\b",
            rf"setRequestMethod\s*\(\s*['\"]({methods})['\"]",
            rf"\bmethod\s*[:=]\s*['\"]({methods})['\"]",
        )
        for pattern in patterns:
            match = re.search(pattern, sample, re.IGNORECASE)
            if match:
                return match.group(1).upper()
        return UNVERIFIED

    def _explicit_path(self, root: Tag) -> str:
        for label in root.find_all(["strong", "th", "dt"]):
            label_text = self._clean(label.get_text(" ", strip=True)).lower()
            if not any(marker in label_text for marker in ("서비스url", "서비스 url", "요청주소", "request url", "endpoint")):
                continue
            path = self._path_from_text(self._text_after_label(label))
            if path:
                return path
        return UNVERIFIED

    def _text_after_label(self, label: Tag) -> str:
        full_text = self._clean(label.parent.get_text(" ", strip=True))
        label_text = self._clean(label.get_text(" ", strip=True))
        return self._clean(full_text[len(label_text):]) if full_text.startswith(label_text) else full_text

    def _path_from_text(self, value: str) -> str:
        url_match = re.search(r"https?://[^\s<>\"']+", value, re.IGNORECASE)
        if url_match:
            path = urlsplit(url_match.group(0).rstrip(".,;)]")).path
            return path or "/"
        relative_match = re.search(r"(?:^|\s)(/[A-Za-z0-9._~!$&'()*+,;=:@%/-]+)", value)
        return relative_match.group(1) if relative_match else ""

    def _method_token(self, value: str) -> str:
        methods = "|".join(_HTTP_METHODS)
        match = re.search(rf"\b({methods})\b", value, re.IGNORECASE)
        return match.group(1).upper() if match else ""

    def _value(self, row: Dict[str, str], *aliases: str) -> str:
        normalized = {self._header_key(key): value for key, value in row.items()}
        for alias in aliases:
            value = normalized.get(self._header_key(alias), "")
            if value:
                return value
        return ""

    def _header_key(self, value: str) -> str:
        return re.sub(r"[\s_]+", "", value).lower()

    def _is_table_heading(self, text: str) -> bool:
        lowered = text.lower()
        return any(
            marker in lowered
            for marker in (
                "요청변수", "출력결과", "응답변수", "request parameter",
                "response element", "response parameter", "샘플코드",
            )
        )

    def _clean(self, value: Any) -> str:
        return re.sub(r"\s+", " ", str(value or "")).strip()

    def detail_functions(
        self, html: Union[str, BeautifulSoup, Tag]
    ) -> List[Dict[str, Any]]:
        """List the detail functions the page offers, rendered or not.

        Only one of them is present in the served HTML; see
        ``DETAIL_FUNCTION_REQUEST_PATH`` for what fetching the others costs.
        """
        soup = self._make_soup(html)
        if soup is None:
            return []
        select = soup.select_one("select#open_api_detail_select")
        if not select:
            return []

        detail_pk = soup.select_one("input#publicDataDetailPk")
        data_pk = soup.select_one("input#publicDataPk")
        functions: List[Dict[str, str]] = []
        for option in select.find_all("option"):
            sequence = self._clean(option.get("value"))
            if not sequence:
                continue
            functions.append(
                {
                    "oprtin_seq_no": sequence,
                    "name": self._clean(option.get_text(" ", strip=True)),
                    "public_data_detail_pk": self._clean(
                        detail_pk.get("value") if detail_pk else ""
                    ) or UNVERIFIED,
                    "public_data_pk": self._clean(
                        data_pk.get("value") if data_pk else ""
                    ) or UNVERIFIED,
                    "selected": option.has_attr("selected"),
                }
            )
        return functions


def build_link_endpoints(
    html: Union[str, BeautifulSoup, Tag],
    operation_ids: Optional[Sequence[str]] = None,
) -> List[Dict[str, Any]]:
    """Functional entry point used by crawler wiring and tests."""

    return LinkSpecBuilder().build(html, operation_ids)


def list_detail_functions(
    html: Union[str, BeautifulSoup, Tag],
) -> List[Dict[str, Any]]:
    """Report every detail function offered by the page, fetched or not."""

    return LinkSpecBuilder().detail_functions(html)


def build_detail_function_endpoints(
    html: Union[str, BeautifulSoup, Tag],
    operation_id: str = UNVERIFIED,
    section: str = "",
) -> List[Dict[str, Any]]:
    """Functional entry point for a fetched detail-function fragment."""

    return LinkSpecBuilder().build_fragment(html, operation_id, section)
