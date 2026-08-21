"""Generic extraction of API rules from arbitrary agency documentation pages.

LINK-type documents point at each agency's own portal, and every agency renders
its API reference differently. Writing one adapter per host does not scale --
the LINK corpus already spans dozens of hosts and grows into the hundreds at
full crawl size.

What *is* common is the shape of the content: a table (or definition list)
whose header row names things like 항목명 / 설명 / 타입 / 필수여부, split into a
request section and a response section. This module keys off that shape instead
of off any single site's markup.

Nothing here guesses. A field that the page does not state is reported as
``unverified`` rather than filled in with a plausible value, matching the rest
of the repository's evidence rules.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup, Tag

UNVERIFIED = "unverified"

# Header cells that mark a table as a parameter/field listing.
_NAME_HEADERS = ("항목명", "항목", "파라미터", "변수명", "요소명", "필드", "name", "이름", "키")
_DESC_HEADERS = ("설명", "항목설명", "내용", "description", "비고", "의미")
_TYPE_HEADERS = ("타입", "자료형", "형식", "type", "데이터타입", "크기")
_REQUIRED_HEADERS = ("필수", "필수여부", "required", "옵션")
_SAMPLE_HEADERS = ("샘플", "예시", "예제", "sample", "example", "예")

# Words that mark the surrounding section as request- or response-side.
_REQUEST_MARKERS = ("요청", "입력", "request", "parameter", "파라미터", "질의")
_RESPONSE_MARKERS = ("응답", "출력", "response", "결과", "리턴")

_SERVICE_URL_LABELS = ("서비스url", "요청url", "호출url", "endpoint", "요청주소", "api url", "url")
_METHOD_PATTERN = re.compile(r"\b(GET|POST|PUT|DELETE|PATCH)\b")


@dataclass
class ExtractedTable:
    """One parameter table found on the page, with its detected role."""

    section: str  # "request" | "response" | "unknown"
    caption: str
    rows: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class ExtractionResult:
    """Everything the static pass could establish about one agency page."""

    url: str
    endpoints: List[Dict[str, Any]] = field(default_factory=list)
    request_parameters: List[Dict[str, str]] = field(default_factory=list)
    response_fields: List[Dict[str, str]] = field(default_factory=list)
    service_urls: List[str] = field(default_factory=list)
    method: str = UNVERIFIED
    tables_seen: int = 0
    parameter_tables: int = 0
    evidence: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_productive(self) -> bool:
        """True when the static pass actually recovered API rules.

        This is the signal that decides whether a page needs a rendered-browser
        retry, so it deliberately requires real parameters rather than merely a
        200 response or a non-empty page.
        """
        return bool(self.request_parameters or self.response_fields)


def _norm(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _match_header(cell: str, candidates: tuple) -> bool:
    lowered = cell.replace(" ", "").lower()
    return any(candidate.replace(" ", "").lower() in lowered for candidate in candidates)


def _classify_section(text: str) -> str:
    lowered = text.lower()
    request_hit = any(marker in lowered for marker in _REQUEST_MARKERS)
    response_hit = any(marker in lowered for marker in _RESPONSE_MARKERS)
    if request_hit and not response_hit:
        return "request"
    if response_hit and not request_hit:
        return "response"
    return "unknown"


def _section_context(table: Tag, limit: int = 4) -> str:
    """Collect nearby headings/captions so the table's role can be inferred."""
    parts: List[str] = []
    caption = table.find("caption")
    if caption:
        parts.append(_norm(caption.get_text()))
    node = table
    for _ in range(limit):
        node = node.find_previous(["h1", "h2", "h3", "h4", "h5", "strong", "b", "p", "div", "span"])
        if node is None:
            break
        text = _norm(node.get_text())
        if text and len(text) <= 120:
            parts.append(text)
    return " | ".join(part for part in parts if part)


def _header_map(table: Tag) -> Optional[Dict[str, int]]:
    """Map logical columns to indices, or None when this is not a field table."""
    header_row = table.find("tr")
    if header_row is None:
        return None
    cells = header_row.find_all(["th", "td"])
    if len(cells) < 2:
        return None

    mapping: Dict[str, int] = {}
    for index, cell in enumerate(cells):
        text = _norm(cell.get_text())
        if not text:
            continue
        if "name" not in mapping and _match_header(text, _NAME_HEADERS):
            mapping["name"] = index
        elif "description" not in mapping and _match_header(text, _DESC_HEADERS):
            mapping["description"] = index
        elif "type" not in mapping and _match_header(text, _TYPE_HEADERS):
            mapping["type"] = index
        elif "required" not in mapping and _match_header(text, _REQUIRED_HEADERS):
            mapping["required"] = index
        elif "sample" not in mapping and _match_header(text, _SAMPLE_HEADERS):
            mapping["sample"] = index

    # A name column plus at least one descriptive column is the minimum bar for
    # treating a table as a parameter listing rather than a data preview.
    if "name" not in mapping or len(mapping) < 2:
        return None
    return mapping


def _rows_from_table(table: Tag, mapping: Dict[str, int]) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    all_rows = table.find_all("tr")
    for row in all_rows[1:]:
        cells = row.find_all(["td", "th"])
        if not cells:
            continue
        name = _norm(cells[mapping["name"]].get_text()) if mapping["name"] < len(cells) else ""
        if not name:
            continue
        entry = {"name": name}
        for key in ("description", "type", "required", "sample"):
            index = mapping.get(key)
            entry[key] = (
                _norm(cells[index].get_text())
                if index is not None and index < len(cells)
                else UNVERIFIED
            )
        rows.append(entry)
    return rows


def _service_urls(soup: BeautifulSoup, html: str) -> List[str]:
    """Find declared call URLs, preferring labelled cells over loose text."""
    found: List[str] = []

    for row in soup.find_all("tr"):
        cells = row.find_all(["th", "td"])
        if len(cells) < 2:
            continue
        label = _norm(cells[0].get_text()).replace(" ", "").lower()
        if any(marker.replace(" ", "") in label for marker in _SERVICE_URL_LABELS):
            for candidate in re.findall(r"https?://[^\s\"'<>]+", _norm(cells[1].get_text())):
                if candidate not in found:
                    found.append(candidate)

    if not found:
        for candidate in re.findall(r"https?://[^\s\"'<>()]+", html):
            if re.search(r"/(api|openapi|service|rest)(/|\?|$)", candidate, re.IGNORECASE):
                if candidate not in found:
                    found.append(candidate)
    return found[:10]


def extract_api_rules(html: str, url: str = "") -> ExtractionResult:
    """Extract request/response rules from one agency documentation page."""
    result = ExtractionResult(url=url)
    if not html or not html.strip():
        result.evidence = {"reason": "empty_body"}
        return result

    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")
    result.tables_seen = len(tables)

    collected: List[ExtractedTable] = []
    for table in tables:
        mapping = _header_map(table)
        if mapping is None:
            continue
        rows = _rows_from_table(table, mapping)
        if not rows:
            continue
        context = _section_context(table)
        collected.append(
            ExtractedTable(section=_classify_section(context), caption=context, rows=rows)
        )

    result.parameter_tables = len(collected)

    # Tables whose role could not be read from surrounding text fall back to
    # document order: on these pages the request block precedes the response
    # block. Recorded in evidence so the assumption stays visible.
    unknown_resolved = 0
    for index, extracted in enumerate(collected):
        section = extracted.section
        if section == "unknown":
            unknown_resolved += 1
            section = "request" if index == 0 and len(collected) > 1 else "response"
        target = result.request_parameters if section == "request" else result.response_fields
        target.extend(extracted.rows)

    result.service_urls = _service_urls(soup, html)

    method_match = _METHOD_PATTERN.search(soup.get_text(" ", strip=True)[:4000])
    result.method = method_match.group(1) if method_match else UNVERIFIED

    if result.is_productive:
        result.endpoints = [
            {
                "method": result.method,
                "path": result.service_urls[0] if result.service_urls else UNVERIFIED,
                "description": _norm(soup.title.get_text()) if soup.title else UNVERIFIED,
                "parameters": [
                    {
                        "name": row["name"],
                        "description": row.get("description", UNVERIFIED),
                        "required": row.get("required", UNVERIFIED),
                        "type": row.get("type", UNVERIFIED),
                    }
                    for row in result.request_parameters
                ],
                "responses": [
                    {
                        "status_code": UNVERIFIED,
                        "description": f"{row['name']}: {row.get('description', '')}".strip(": "),
                    }
                    for row in result.response_fields
                ],
                "tags": [],
                "section": "link_agency_page",
            }
        ]

    result.evidence = {
        "reason": "parameter_tables_found" if result.is_productive else "no_parameter_table_in_static_html",
        "tables_seen": result.tables_seen,
        "parameter_tables": result.parameter_tables,
        "sections_inferred_by_order": unknown_resolved,
        "method_source": "page_text" if result.method != UNVERIFIED else UNVERIFIED,
        "needs_rendered_retry": not result.is_productive,
    }
    return result


__all__ = ["ExtractedTable", "ExtractionResult", "extract_api_rules", "UNVERIFIED"]
