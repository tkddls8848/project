"""Visit the agency page behind each LINK document and collect its API rules.

The URL comes from the stored record's ``info['URL']`` field, which data.go.kr
fills with the agency's own documentation page. That field is populated for the
whole LINK corpus, unlike ``external_endpoint_urls``, which is scraped from page
HTML and is therefore only present on records crawled after that extractor
landed.

All network access goes through ``portals.SafeHttpTransport`` so this module
inherits the same invariants the portal harvester runs under: robots.txt is
honoured, per-host concurrency is capped at 1-2, requests are spaced out, and
redirects are not followed across hosts.
"""

from __future__ import annotations

import asyncio
import collections
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlsplit

from portals.transport import SafeHttpTransport, TransportConfig
from utils.url_guard import literal_rejection_reason

from .extractor import ExtractionResult, extract_api_rules

# Skip work that is not an agency page: self-referential data.go.kr links carry
# no new information, and non-HTTP schemes are not fetchable.
_SELF_HOSTS = {"data.go.kr", "www.data.go.kr"}


@dataclass
class LinkDocTask:
    api_id: str
    url: str
    host: str
    title: str = ""


@dataclass
class LinkDocResult:
    api_id: str
    url: str
    host: str
    title: str = ""
    status: str = "pending"  # ok | empty | blocked | error | skipped
    http_status: Optional[int] = None
    endpoints: List[Dict[str, Any]] = field(default_factory=list)
    request_parameters: List[Dict[str, str]] = field(default_factory=list)
    response_fields: List[Dict[str, str]] = field(default_factory=list)
    service_urls: List[str] = field(default_factory=list)
    evidence: Dict[str, Any] = field(default_factory=dict)
    message: Optional[str] = None


def build_tasks(records: Iterable[Any]) -> List[LinkDocTask]:
    """Turn stored LINK records into fetch tasks, one per usable agency URL."""
    tasks: List[LinkDocTask] = []
    seen: set = set()
    for record in records:
        info = (record.get("info") if isinstance(record, dict) else None) or {}
        url = str(info.get("URL") or "").strip()
        if not url.lower().startswith(("http://", "https://")):
            continue
        host = (urlsplit(url).hostname or "").lower()
        if not host or host in _SELF_HOSTS:
            continue
        # 내부망을 가리키는 주소는 작업으로 만들지 않는다. 이름으로 적힌 것은
        # 요청 직전에 SafeHttpTransport가 이름을 풀어 다시 본다.
        if literal_rejection_reason(url) is not None:
            continue
        api_id = str(record.get("api_id") or "").strip()
        key = (api_id, url)
        if key in seen:
            continue
        seen.add(key)
        tasks.append(
            LinkDocTask(api_id=api_id, url=url, host=host, title=str(info.get("목록명") or ""))
        )
    return tasks


def coverage(results: Iterable[LinkDocResult]) -> Dict[str, Any]:
    """Measured static-pass coverage. This is what decides whether a rendered
    browser is worth adding: it reports the share of pages a static fetch could
    not extract rules from, broken down by host."""
    results = list(results)
    per_host: Dict[str, Dict[str, int]] = collections.defaultdict(
        lambda: {"total": 0, "ok": 0, "needs_render": 0, "blocked": 0, "error": 0}
    )
    for item in results:
        bucket = per_host[item.host]
        bucket["total"] += 1
        if item.status == "ok":
            bucket["ok"] += 1
        elif item.status == "empty":
            bucket["needs_render"] += 1
        elif item.status == "blocked":
            bucket["blocked"] += 1
        elif item.status == "error":
            bucket["error"] += 1

    total = len(results)
    ok = sum(1 for item in results if item.status == "ok")
    needs_render = sum(1 for item in results if item.status == "empty")
    return {
        "documents": total,
        "hosts": len(per_host),
        "static_extracted": ok,
        "static_coverage_pct": round(ok / total * 100, 1) if total else 0.0,
        "needs_rendered_retry": needs_render,
        "blocked_by_robots": sum(1 for item in results if item.status == "blocked"),
        "errors": sum(1 for item in results if item.status == "error"),
        "per_host": {
            host: dict(stats)
            for host, stats in sorted(per_host.items(), key=lambda kv: -kv[1]["total"])
        },
    }


async def _fetch_one(transport: SafeHttpTransport, task: LinkDocTask) -> LinkDocResult:
    result = LinkDocResult(api_id=task.api_id, url=task.url, host=task.host, title=task.title)
    try:
        decision = await transport.robots_decision(task.url)
        if not getattr(decision, "allowed", True):
            result.status = "blocked"
            result.message = "robots.txt disallows this path"
            result.evidence = {"reason": "robots_disallowed"}
            return result

        response = await transport.get(task.url)
        result.http_status = getattr(response, "status", None)
        html = getattr(response, "text", "") or ""
        if result.http_status is not None and result.http_status >= 400:
            result.status = "error"
            result.message = f"HTTP {result.http_status}"
            result.evidence = {"reason": "http_error"}
            return result

        extracted: ExtractionResult = extract_api_rules(html, task.url)
        result.endpoints = extracted.endpoints
        result.request_parameters = extracted.request_parameters
        result.response_fields = extracted.response_fields
        result.service_urls = extracted.service_urls
        result.evidence = extracted.evidence
        result.status = "ok" if extracted.is_productive else "empty"
        if result.status == "empty":
            # Not an error: the page loaded but its rules are not in the static
            # HTML. Recorded so a later rendered pass has an exact worklist.
            result.message = "no API rules in static HTML; candidate for rendered retry"
        return result
    except asyncio.TimeoutError:
        result.status = "error"
        result.message = "timeout"
        result.evidence = {"reason": "timeout"}
        return result
    except Exception as exc:  # noqa: BLE001 - one bad host must not stop the run
        result.status = "error"
        result.message = f"{type(exc).__name__}: {exc}"
        result.evidence = {"reason": "exception"}
        return result


async def collect_link_specs(
    records: Iterable[Any],
    *,
    limit: Optional[int] = None,
    transport_config: Optional[TransportConfig] = None,
) -> tuple[List[LinkDocResult], Dict[str, Any]]:
    """Fetch every agency page and return per-document results plus coverage.

    Work is grouped by host and hosts run concurrently, so the per-host delay
    never becomes a global bottleneck while each individual site still sees a
    slow, serialised visitor.
    """
    tasks = build_tasks(records)
    if limit is not None:
        tasks = tasks[:limit]
    if not tasks:
        return [], coverage([])

    by_host: Dict[str, List[LinkDocTask]] = collections.defaultdict(list)
    for task in tasks:
        by_host[task.host].append(task)

    results: List[LinkDocResult] = []
    async with SafeHttpTransport(transport_config or TransportConfig()) as transport:

        async def run_host(host_tasks: List[LinkDocTask]) -> List[LinkDocResult]:
            out: List[LinkDocResult] = []
            for task in host_tasks:
                out.append(await _fetch_one(transport, task))
            return out

        for chunk in await asyncio.gather(*(run_host(v) for v in by_host.values())):
            results.extend(chunk)

    return results, coverage(results)


def to_openapi_like(result: LinkDocResult) -> Dict[str, Any]:
    """Render one result in the same shape as a stored openapi_new document."""
    return {
        "api_id": result.api_id,
        "api_type": "openapi_link_spec",
        "crawled_url": result.url,
        "info": {"목록명": result.title, "URL": result.url, "제공기관_호스트": result.host},
        "swagger_json": None,
        "endpoints": result.endpoints,
        "service_urls": result.service_urls,
        "extraction_status": result.status,
        "extraction_evidence": result.evidence,
        "message": result.message,
    }


def result_to_dict(result: LinkDocResult) -> Dict[str, Any]:
    return asdict(result)


__all__ = [
    "LinkDocResult",
    "LinkDocTask",
    "build_tasks",
    "collect_link_specs",
    "coverage",
    "result_to_dict",
    "to_openapi_like",
]
