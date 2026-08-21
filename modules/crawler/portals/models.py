"""Data contracts for portal detection, harvesting, and coverage reporting."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ProbeEvidence:
    probe: str
    url: str
    outcome: str
    detail: str
    status: Optional[int] = None


@dataclass
class HarvestedItem:
    title: str
    url: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    verified: bool = True


@dataclass
class HostInventory:
    host: str
    base_url: str
    record_count: int = 0
    source_urls: List[str] = field(default_factory=list)
    record_ids: List[str] = field(default_factory=list)


@dataclass
class PortalResult:
    host: str
    base_url: str
    source_record_count: int
    protocol: str
    verified: bool
    items: List[HarvestedItem] = field(default_factory=list)
    evidence: List[ProbeEvidence] = field(default_factory=list)


@dataclass
class CoverageReport:
    total_hosts: int
    total_records: int
    processed_hosts: int
    processed_records: int
    verified_hosts: int
    verified_records: int
    protocol_hosts: Dict[str, int]
    protocol_records: Dict[str, int]
    host_results: List[Dict[str, Any]]

    @property
    def host_coverage(self) -> float:
        return self.verified_hosts / self.total_hosts if self.total_hosts else 0.0

    @property
    def record_coverage(self) -> float:
        return self.verified_records / self.total_records if self.total_records else 0.0

    def as_dict(self) -> Dict[str, Any]:
        return {
            "total_hosts": self.total_hosts,
            "total_records": self.total_records,
            "processed_hosts": self.processed_hosts,
            "processed_records": self.processed_records,
            "verified_hosts": self.verified_hosts,
            "verified_records": self.verified_records,
            "host_coverage": self.host_coverage,
            "record_coverage": self.record_coverage,
            "protocol_hosts": dict(self.protocol_hosts),
            "protocol_records": dict(self.protocol_records),
            "host_results": list(self.host_results),
        }
