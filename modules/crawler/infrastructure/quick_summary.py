"""Collect the portal's AI-written Quick Summary for a document.

The 2026-08 renewal added a "Quick AI Summary" block to every detail page. The
served HTML only contains the empty shell

    <div class="quick-summary">
        <div class="tit">Quick<span>AI</span>Summary</div>
        <div class="con" id="quickSummary"></div>
    </div>

which the page fills in from its own script:

    POST /tcs/dss/getOrCreateQuickSummary.do
    Content-Type: application/json
        {"publicDataPk": "<api_id>"}

The answer is ``{"code": 200, "message": "OK", "result": "<markdown>"}``. The
same call serves every document type — openapi (new/old/link), fileData and
standard alike — verified live on 15000063, 15000863, 15001702, 15000249 and
15072622 on 2026-08-05.

Three things about the contract are easy to get wrong:

* The page's ``executeSearch(pk)`` call passes no ``dType`` even though the
  function accepts one, and sending one changes nothing — the responses are
  byte-identical with and without it. So only ``publicDataPk`` is sent here.
* The response's Content-Type is ``text/html`` while the body is JSON, the same
  trap as ``selectApiLinkUrl.do``. It is parsed as JSON directly.
* "getOrCreate" is literal: an unsummarised document is generated on demand and
  took ~5.5s live, against ~0.03s once cached. A document the portal cannot
  summarise answers HTTP 500 with the same JSON envelope, so a 500 is an
  ordinary outcome to record, not a crawl failure.

``result`` is markdown rendered client-side with marked.js. It reads as several
``<b>제목</b>`` use-case sections, which is what makes it worth indexing: it
states what a dataset is *for* in prose the metadata never contains.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit, urlunsplit

from bs4 import BeautifulSoup

QUICK_SUMMARY_PATH = "/tcs/dss/getOrCreateQuickSummary.do"

_HEADING_RE = re.compile(r"<b>(.*?)</b>", re.IGNORECASE | re.DOTALL)


async def fetch_quick_summary(
    session: Any, page_url: str, api_id: str
) -> Dict[str, Any]:
    """Asks the portal for a document's Quick Summary.

    Runs on the caller's session, and inside whatever concurrency slot the
    caller already holds. Never raises: every outcome is a ``status`` in the
    returned record, because a missing summary must not cost a document the
    metadata that was already collected.
    """
    parsed_page = urlsplit(page_url)
    request_url = urlunsplit((
        parsed_page.scheme or "https",
        parsed_page.netloc or "www.data.go.kr",
        QUICK_SUMMARY_PATH,
        "",
        "",
    ))

    try:
        async with session.post(request_url, json={"publicDataPk": api_id}) as response:
            status = response.status
            body = await response.text()
    except asyncio.TimeoutError:
        # Generation is slow on a cold document; the session's total timeout can
        # land in the middle of it.
        return {"status": "timeout"}
    except Exception as exc:
        return {"status": "request_failed", "message": str(exc)}

    record = parse_quick_summary(body)
    if status != 200:
        # The 500 body carries the portal's own message, which is worth keeping,
        # but the HTTP status is the more precise outcome.
        message = record.get("message")
        record = {"status": f"http_{status}"}
        if message:
            record["message"] = message
    return record


def parse_quick_summary(body: str) -> Dict[str, Any]:
    """Turns a Quick Summary response body into a stored record.

    Kept separate from the request so the response contract can be tested
    without a network or a session.
    """
    try:
        payload = json.loads(body)
    except (ValueError, TypeError):
        return {"status": "unreadable_body"}
    if not isinstance(payload, dict):
        return {"status": "unreadable_body"}

    message = str(payload.get("message") or "").strip()
    result = payload.get("result")
    if not isinstance(result, str) or not result.strip():
        record: Dict[str, Any] = {"status": "empty"}
        if message and message != "OK":
            record["message"] = message
        return record

    return {
        "status": "ok",
        # The response as sent, so a later reader can re-render the markdown
        # exactly as the portal's own page does.
        "markdown": result,
        "text": to_plain_text(result),
        "headings": headings(result),
    }


def to_plain_text(markdown: str) -> str:
    """Strips the inline HTML and normalises whitespace for indexing."""
    text = BeautifulSoup(markdown, "lxml").get_text()
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def headings(markdown: str) -> List[str]:
    """Lists the ``<b>`` use-case titles, the summary's own section names."""
    found: List[str] = []
    for raw in _HEADING_RE.findall(markdown):
        title = re.sub(r"\s+", " ", BeautifulSoup(raw, "lxml").get_text()).strip()
        if title and title not in found:
            found.append(title)
    return found


def summary_text(record: Optional[Dict[str, Any]]) -> str:
    """Convenience accessor for consumers that only want the indexable text."""
    if not isinstance(record, dict):
        return ""
    return str(record.get("text") or "")


__all__ = [
    "QUICK_SUMMARY_PATH",
    "fetch_quick_summary",
    "parse_quick_summary",
    "to_plain_text",
    "headings",
    "summary_text",
]
