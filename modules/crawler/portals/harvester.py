"""Exact ordered protocol detection and harvesting for portal hosts."""

import asyncio
import json
from typing import Any, Iterable, List, Optional, Protocol
from urllib.parse import urljoin

from .adapters import CKANAdapter, GenericAdapter, JSONLDAdapter, OpenAPIAdapter, SitemapAdapter
from .inventory import build_host_inventory, coverage_report
from .models import CoverageReport, HarvestedItem, HostInventory, PortalResult, ProbeEvidence
from .transport import HttpResponse, SafeHttpTransport


class PortalTransport(Protocol):
    async def robots_decision(self, url: str) -> Any: ...
    async def get(self, url: str) -> HttpResponse: ...


OPENAPI_PATHS = OpenAPIAdapter.paths


class PortalHarvester:
    def __init__(self, transport: PortalTransport, max_hosts: int = 8):
        if max_hosts < 1:
            raise ValueError("max_hosts must be positive")
        self.transport = transport
        self.max_hosts = max_hosts

    async def harvest_records(self, records: Iterable[Any], host_limit: Optional[int] = None) -> tuple[List[PortalResult], CoverageReport]:
        if host_limit is not None and host_limit < 0:
            raise ValueError("host_limit must be non-negative")
        inventory = build_host_inventory(records)
        selected = inventory[:host_limit] if host_limit is not None else inventory
        semaphore = asyncio.Semaphore(self.max_hosts)

        async def limited(item: HostInventory) -> PortalResult:
            async with semaphore:
                return await self.harvest_host(item)

        results = await asyncio.gather(*(limited(item) for item in selected))
        return results, coverage_report(inventory, results)

    async def harvest_host(self, host: HostInventory) -> PortalResult:
        evidence: List[ProbeEvidence] = []

        # Safety gate: this is the sole mandatory request before protocol probes.
        root_decision = await self.transport.robots_decision(host.base_url + "/")
        evidence.append(ProbeEvidence("robots", host.base_url + "/robots.txt", "allowed" if root_decision.allowed else "blocked", root_decision.reason))

        result = await self._probe_json(
            host, CKANAdapter.paths[0], CKANAdapter, evidence
        )
        if result:
            return result

        for path in OPENAPI_PATHS:
            result = await self._probe_json(host, path, OpenAPIAdapter, evidence)
            if result:
                return result

        result = await self._probe_sitemap(host, evidence, tuple(getattr(root_decision, "sitemaps", ()) or ()))
        if result:
            return result

        homepage = await self._fetch(host.base_url + "/", "jsonld", evidence)
        if homepage is not None and homepage.status == 200:
            datasets = JSONLDAdapter.datasets(homepage.text)
            if datasets:
                items = JSONLDAdapter.items(datasets, host.base_url, host.base_url + "/")
                evidence.append(ProbeEvidence("jsonld", host.base_url + "/", "matched", f"schema.org Dataset objects={len(items)}", 200))
                return self._result(host, "jsonld", True, items, evidence)
            evidence.append(ProbeEvidence("jsonld", host.base_url + "/", "not_matched", "no schema.org Dataset JSON-LD", 200))

        # Generic deliberately reuses the homepage response; no additional probe.
        items = GenericAdapter.items(homepage.text, host.base_url, host.base_url + "/") if homepage and homepage.status == 200 else []
        evidence.append(ProbeEvidence("generic", host.base_url + "/", "fallback", "all ordered protocol probes failed or were blocked; metadata is unverified"))
        return self._result(host, "generic", False, items, evidence)

    async def _probe_json(self, host: HostInventory, path: str, adapter, evidence: List[ProbeEvidence]) -> Optional[PortalResult]:
        protocol = adapter.name
        url = urljoin(host.base_url + "/", path.lstrip("/"))
        response = await self._fetch(url, protocol, evidence)
        if response is None:
            return None
        if response.status != 200:
            evidence.append(ProbeEvidence(protocol, url, "not_matched", f"HTTP {response.status}", response.status))
            return None
        try:
            payload = json.loads(response.text)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            evidence.append(ProbeEvidence(protocol, url, "not_matched", f"invalid JSON: {exc}", response.status))
            return None
        if not adapter.matches(payload):
            evidence.append(ProbeEvidence(protocol, url, "not_matched", "JSON shape did not match protocol", response.status))
            return None
        items = adapter.items(payload, host.base_url, url)
        evidence.append(ProbeEvidence(protocol, url, "matched", f"validated {protocol} response", response.status))
        return self._result(host, protocol, True, items, evidence)

    async def _probe_sitemap(self, host: HostInventory, evidence: List[ProbeEvidence], declared: tuple[str, ...]) -> Optional[PortalResult]:
        urls = list(declared[:1]) or [urljoin(host.base_url + "/", "sitemap.xml")]
        url = urls[0]
        response = await self._fetch(url, "sitemap", evidence)
        if response is None:
            return None
        if response.status != 200:
            evidence.append(ProbeEvidence("sitemap", url, "not_matched", f"HTTP {response.status}", response.status))
            return None
        try:
            items = SitemapAdapter.items(response.text, host.base_url, url)
        except Exception as exc:
            evidence.append(ProbeEvidence("sitemap", url, "not_matched", f"invalid XML: {exc}", response.status))
            return None
        if not items:
            evidence.append(ProbeEvidence("sitemap", url, "not_matched", "XML contains no loc entries", response.status))
            return None
        evidence.append(ProbeEvidence("sitemap", url, "matched", f"sitemap locations={len(items)}", response.status))
        return self._result(host, "sitemap", True, items, evidence)

    async def _fetch(self, url: str, probe: str, evidence: List[ProbeEvidence]) -> Optional[HttpResponse]:
        try:
            return await self.transport.get(url)
        except PermissionError as exc:
            evidence.append(ProbeEvidence(probe, url, "blocked", f"robots: {exc}"))
        except Exception as exc:
            evidence.append(ProbeEvidence(probe, url, "error", f"{type(exc).__name__}: {exc}"))
        return None

    @staticmethod
    def _result(host: HostInventory, protocol: str, verified: bool, items: List[HarvestedItem], evidence: List[ProbeEvidence]) -> PortalResult:
        return PortalResult(host.host, host.base_url, host.record_count, protocol, verified, items, list(evidence))


async def harvest_with_safe_transport(records: Iterable[Any], *, host_limit: Optional[int] = None, max_hosts: int = 8, transport_config=None) -> tuple[List[PortalResult], CoverageReport]:
    """Convenience entry point for coordinator-owned CLI wiring."""
    async with SafeHttpTransport(transport_config) as transport:
        return await PortalHarvester(transport, max_hosts=max_hosts).harvest_records(records, host_limit)
