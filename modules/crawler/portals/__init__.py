"""Protocol-driven harvesting for external institutional data portals."""

from .harvester import PortalHarvester, harvest_with_safe_transport
from .inventory import build_host_inventory, coverage_report
from .models import (
    CoverageReport,
    HarvestedItem,
    HostInventory,
    PortalResult,
    ProbeEvidence,
)
from .transport import SafeHttpTransport, TransportConfig

__all__ = [
    "CoverageReport",
    "HarvestedItem",
    "HostInventory",
    "PortalHarvester",
    "PortalResult",
    "ProbeEvidence",
    "SafeHttpTransport",
    "TransportConfig",
    "build_host_inventory",
    "harvest_with_safe_transport",
    "coverage_report",
]
