import asyncio
import json
from dataclasses import dataclass

import pytest

from portals.harvester import OPENAPI_PATHS, PortalHarvester
from portals.inventory import build_host_inventory, coverage_report
from portals.models import HostInventory
from portals.transport import HttpResponse, RobotsDecision, TransportConfig


def response(url, status=200, body="", content_type="text/html; charset=utf-8"):
    return HttpResponse(url, status, {"Content-Type": content_type}, body.encode("utf-8"))


@dataclass
class FakeTransport:
    fixtures: dict
    blocked: set = None

    def __post_init__(self):
        self.blocked = self.blocked or set()
        self.calls = []
        self.robot_calls = []

    async def robots_decision(self, url):
        self.robot_calls.append(url)
        allowed = url not in self.blocked
        return RobotsDecision(allowed, "fixture_allowed" if allowed else "fixture_disallowed")

    async def get(self, url):
        if url in self.blocked:
            raise PermissionError("fixture_disallowed")
        self.calls.append(url)
        value = self.fixtures.get(url)
        if isinstance(value, Exception):
            raise value
        return value or response(url, 404, "not found")


def inventory(host="catalog.example", count=3):
    return HostInventory(host, f"https://{host}", count, [f"https://{host}/api/items"])


def test_ckan_matches_first_and_stops_after_one_protocol_probe():
    url = "https://catalog.example/api/3/action/package_list"
    transport = FakeTransport({url: response(url, body=json.dumps({"success": True, "result": ["air", "water"]}))})

    result = asyncio.run(PortalHarvester(transport).harvest_host(inventory()))

    assert result.protocol == "ckan"
    assert result.verified is True
    assert [item.title for item in result.items] == ["air", "water"]
    assert transport.calls == [url]
    assert transport.robot_calls[0] == "https://catalog.example/"


def test_openapi_probe_order_is_exact_and_stops_on_first_match():
    base = "https://catalog.example"
    fixtures = {
        base + "/api/3/action/package_list": response(base, 404),
        base + OPENAPI_PATHS[0]: response(base, 404),
        base + OPENAPI_PATHS[1]: response(
            base,
            body=json.dumps({"swagger": "2.0", "info": {"title": "Fixture API"}, "paths": {"/rows": {}}}),
            content_type="application/json",
        ),
    }
    transport = FakeTransport(fixtures)

    result = asyncio.run(PortalHarvester(transport).harvest_host(inventory()))

    assert result.protocol == "openapi"
    assert transport.calls == [
        base + "/api/3/action/package_list",
        base + "/v2/api-docs",
        base + "/swagger.json",
    ]


def test_sitemap_adapter_runs_after_all_openapi_paths():
    base = "https://catalog.example"
    sitemap_url = base + "/sitemap.xml"
    transport = FakeTransport({
        sitemap_url: response(sitemap_url, body="""<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://catalog.example/dataset/a</loc></url></urlset>""", content_type="application/xml")
    })

    result = asyncio.run(PortalHarvester(transport).harvest_host(inventory()))

    assert result.protocol == "sitemap"
    assert transport.calls[-1] == sitemap_url
    assert len(transport.calls) == 1 + len(OPENAPI_PATHS) + 1


def test_jsonld_and_generic_share_one_homepage_fetch_and_preserve_evidence():
    base = "https://catalog.example"
    html = """<html><head><title>Catalog</title><script type="application/ld+json">{"@graph":[{"@type":"Dataset","name":"Population","url":"https://catalog.example/d/pop"}]}</script></head></html>"""
    transport = FakeTransport({base + "/": response(base + "/", body=html)})

    result = asyncio.run(PortalHarvester(transport).harvest_host(inventory()))

    assert result.protocol == "jsonld"
    assert result.items[0].title == "Population"
    assert transport.calls.count(base + "/") == 1
    assert any(entry.probe == "sitemap" and entry.outcome == "not_matched" for entry in result.evidence)

    generic_html = "<html><head><title>Fallback</title></head><body><table><tr><th>A</th><td>B</td></tr></table></body></html>"
    generic_transport = FakeTransport({base + "/": response(base + "/", body=generic_html)})
    generic = asyncio.run(PortalHarvester(generic_transport).harvest_host(inventory()))
    assert generic.protocol == "generic"
    assert generic.verified is False
    assert generic.items[0].verified is False
    assert generic_transport.calls.count(base + "/") == 1
    assert generic.evidence[-1].outcome == "fallback"


def test_robots_block_is_explicit_and_never_calls_blocked_url():
    base = "https://catalog.example"
    blocked = {
        base + "/api/3/action/package_list",
        *(base + path for path in OPENAPI_PATHS),
        base + "/sitemap.xml",
        base + "/",
    }
    transport = FakeTransport({}, blocked=blocked)

    result = asyncio.run(PortalHarvester(transport).harvest_host(inventory()))

    assert result.protocol == "generic"
    assert result.verified is False
    assert transport.calls == []
    # Root is recorded once as the safety gate and once as the JSON-LD probe.
    assert sum(entry.outcome == "blocked" for entry in result.evidence) == len(blocked) + 1


def test_inventory_is_record_weighted_sorted_and_coverage_is_measured():
    records = [
        {"api_id": "1", "external_endpoint_urls": ["https://B.example/api/a", "https://b.example/api/b"]},
        {"api_id": "2", "external_endpoint_urls": ["http://a.example/service"]},
        {"api_id": "3", "external_endpoint_urls": ["https://b.example/openapi"]},
        {"api_id": "4", "external_endpoint_urls": ["mailto:nobody@example.com", "bad"]},
    ]
    hosts = build_host_inventory(records)
    assert [(host.host, host.record_count) for host in hosts] == [("b.example", 2), ("a.example", 1)]

    ckan = PortalHarvester._result(hosts[0], "ckan", True, [], [])
    generic = PortalHarvester._result(hosts[1], "generic", False, [], [])
    report = coverage_report(hosts, [ckan, generic])
    assert report.total_hosts == 2
    assert report.total_records == 3
    assert report.host_coverage == 0.5
    assert report.record_coverage == pytest.approx(2 / 3)
    assert report.protocol_records == {"ckan": 2, "generic": 1}


def test_transport_config_enforces_host_concurrency_cap():
    with pytest.raises(ValueError, match="1 or 2"):
        TransportConfig(per_host_concurrency=3)
