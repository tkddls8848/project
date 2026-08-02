"""Cluster LINK endpoint URLs by host and measure weighted coverage."""

from collections import Counter
from typing import Any, Dict, Iterable, List, Mapping
from urllib.parse import urlsplit, urlunsplit

from .models import CoverageReport, HostInventory, PortalResult


def _value(record: Any, name: str, default: Any = None) -> Any:
    if isinstance(record, Mapping):
        return record.get(name, default)
    return getattr(record, name, default)


def build_host_inventory(records: Iterable[Any]) -> List[HostInventory]:
    """Return a largest-first host inventory from CrawlData-like records.

    ``record_count`` counts records, not URLs, so a record exposing several URLs on
    one host is not over-weighted. Invalid and non-HTTP(S) URLs are ignored.
    """
    hosts: Dict[str, HostInventory] = {}
    for record in records:
        record_id = str(_value(record, "api_id", "") or "")
        per_record_hosts = set()
        for raw_url in _value(record, "external_endpoint_urls", []) or []:
            try:
                parsed = urlsplit(str(raw_url).strip())
                host = (parsed.hostname or "").lower().rstrip(".")
                if parsed.scheme.lower() not in {"http", "https"} or not host:
                    continue
                port = parsed.port
            except (TypeError, ValueError):
                continue
            host_key = f"{host}:{port}" if port else host
            scheme = parsed.scheme.lower()
            base_url = urlunsplit((scheme, host_key, "", "", ""))
            inventory = hosts.setdefault(host_key, HostInventory(host_key, base_url))
            normalized = urlunsplit((scheme, parsed.netloc.lower(), parsed.path or "/", parsed.query, ""))
            if normalized not in inventory.source_urls:
                inventory.source_urls.append(normalized)
            if host_key not in per_record_hosts:
                inventory.record_count += 1
                if record_id and record_id not in inventory.record_ids:
                    inventory.record_ids.append(record_id)
                per_record_hosts.add(host_key)
    return sorted(hosts.values(), key=lambda item: (-item.record_count, item.host))


def coverage_report(inventory: Iterable[HostInventory], results: Iterable[PortalResult]) -> CoverageReport:
    inventory_list = list(inventory)
    result_list = list(results)
    protocol_hosts = Counter(result.protocol for result in result_list)
    protocol_records = Counter()
    for result in result_list:
        protocol_records[result.protocol] += result.source_record_count
    verified = [result for result in result_list if result.verified]
    return CoverageReport(
        total_hosts=len(inventory_list),
        total_records=sum(item.record_count for item in inventory_list),
        processed_hosts=len(result_list),
        processed_records=sum(item.source_record_count for item in result_list),
        verified_hosts=len(verified),
        verified_records=sum(item.source_record_count for item in verified),
        protocol_hosts=dict(protocol_hosts),
        protocol_records=dict(protocol_records),
        host_results=[
            {
                "host": result.host,
                "source_record_count": result.source_record_count,
                "protocol": result.protocol,
                "verified": result.verified,
                "item_count": len(result.items),
                "evidence": [vars(entry) for entry in result.evidence],
            }
            for result in result_list
        ],
    )
