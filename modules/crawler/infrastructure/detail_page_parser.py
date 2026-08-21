"""Read the key/value metadata block of a data.go.kr detail page.

The 2026-08 portal renewal replaced the table layout every crawler used to read

    <table><tr><th>제공기관</th><td>국토교통부</td></tr></table>

with a key/value block that is shared by all detail page types:

    <li class="half">
        <strong class="key">제공기관</strong>
        <div class="value">국토교통부</div>
    </li>

openapi, fileData and standard pages all render this same block, so the three
crawlers read it through this one function instead of the three near-identical
table scanners they each carried before.

Documents captured before the renewal still parse: when a page has no
``strong.key`` block the legacy table scan runs instead, so re-reading stored
HTML and mixed-vintage fixtures keeps working.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional, Union

from bs4 import BeautifulSoup, NavigableString, Tag

Source = Union[str, BeautifulSoup, Tag]

# The renewal moved the phone number out of the markup: the value element is
# rendered empty and filled in by an inline script. The number is only readable
# from that script's source, under a name that changed with the renewal.
_TEL_PATTERNS = (
    r'var\s+apiTelNo\s*=\s*"([^"]+)"',
    r'var\s+telNo\s*=\s*"([^"]+)"',
)
_TEL_KEYS = ("관리부서 전화번호", "관리부서전화번호")


def extract_detail_info(source: Source, html: str = "") -> Dict[str, str]:
    """Return the page's metadata as a ``{키: 값}`` dict.

    ``html`` is the unparsed page. It is optional but should be passed when
    available: values injected by inline scripts, such as the phone number, are
    not in the DOM at all and can only be recovered from the raw source.
    """
    soup = _make_soup(source)
    if soup is None:
        return {}

    info = _from_key_blocks(soup)
    if not info:
        info = _from_legacy_tables(soup)

    tel_no = extract_tel_no(html or _raw_html(source))
    if tel_no:
        for key in _TEL_KEYS:
            if key in info and not info[key]:
                info[key] = tel_no
                break
        else:
            info.setdefault(_TEL_KEYS[0], tel_no)

    return info


def _from_key_blocks(soup: Union[BeautifulSoup, Tag]) -> Dict[str, str]:
    """Parse the renewed ``strong.key`` / ``div.value`` pairs."""
    info: Dict[str, str] = {}
    for key_node in soup.select("strong.key"):
        key = _clean(_text_without_scripts(key_node))
        if not key:
            continue

        value_node = key_node.find_next_sibling(class_="value")
        if value_node is None:
            container = key_node.find_parent("li") or key_node.parent
            if container is None:
                continue
            value = _clean(_text_without_scripts(container))
            # The container includes its own label; drop that prefix so only
            # the value is kept.
            if value.startswith(key):
                value = _clean(value[len(key):])
        else:
            value = _clean(_text_without_scripts(value_node))

        # A repeated key means the page renders the same label in more than one
        # place. Keep the first non-empty reading rather than letting an empty
        # duplicate overwrite a real value.
        if key not in info or (not info[key] and value):
            info[key] = value
    return info


def _from_legacy_tables(soup: Union[BeautifulSoup, Tag]) -> Dict[str, str]:
    """Parse the pre-renewal ``<th>`` / ``<td>`` table rows."""
    info: Dict[str, str] = {}
    for table in soup.select("table"):
        for row in table.find_all("tr"):
            th = row.find("th")
            td = row.find("td")
            if not (th and td):
                continue
            key = _clean(th.get_text())
            if not key:
                continue
            value = _text_without_scripts(td)
            # Older pages leaked inline script source into the cell text.
            value = re.sub(r"`\s*var\s+.*$", "", value, flags=re.DOTALL).strip()
            value = re.sub(r"`$", "", value).strip()
            info[key] = _clean(value)
    return info


def extract_tel_no(html: str) -> Optional[str]:
    """Return the phone number injected by the page's inline script."""
    if not html:
        return None
    for pattern in _TEL_PATTERNS:
        match = re.search(pattern, html)
        if not match:
            continue
        digits = re.sub(r"\D", "", match.group(1))
        if not digits or set(digits) == {"0"}:
            continue
        return _format_tel(digits)
    return None


def _format_tel(digits: str) -> str:
    if digits.startswith("02") and len(digits) >= 9:
        return f"{digits[:2]}-{digits[2:-4]}-{digits[-4:]}"
    if len(digits) >= 10:
        return f"{digits[:3]}-{digits[3:-4]}-{digits[-4:]}"
    return digits


def _text_without_scripts(element: Any) -> str:
    """Text of ``element`` with any script/style source left out.

    The nodes are read rather than removed so the caller's tree is not mutated.
    """
    if isinstance(element, NavigableString):
        return str(element)
    parts = [
        str(node)
        for node in element.descendants
        if isinstance(node, NavigableString)
        and node.find_parent(["script", "style"]) is None
    ]
    return " ".join(parts)


def _make_soup(source: Source) -> Optional[Union[BeautifulSoup, Tag]]:
    if isinstance(source, (BeautifulSoup, Tag)):
        return source
    if isinstance(source, str) and source.strip():
        return BeautifulSoup(source, "lxml")
    return None


def _raw_html(source: Source) -> str:
    return source if isinstance(source, str) else ""


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


__all__ = ["extract_detail_info", "extract_tel_no"]
