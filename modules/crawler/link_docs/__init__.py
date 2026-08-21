"""Collect API rules from the agency pages that LINK-type documents point at."""

from .extractor import ExtractionResult, extract_api_rules
from .runner import (
    LinkDocResult,
    LinkDocTask,
    build_tasks,
    collect_link_specs,
    coverage,
    result_to_dict,
    to_openapi_like,
)

__all__ = [
    "ExtractionResult",
    "LinkDocResult",
    "LinkDocTask",
    "build_tasks",
    "collect_link_specs",
    "coverage",
    "extract_api_rules",
    "result_to_dict",
    "to_openapi_like",
]
