"""크롤 결과 유형의 단일 레지스트리와 파생 계약."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CrawlTypeSpec:
    cli_name: str
    csv_prefix: str
    crawler_class: str
    url_kind: str
    storage_dir: str | None
    is_subtype: bool
    supports_range: bool
    default_workers: int
    full_order: int | None = None
    storage_order: int | None = None
    ui_order: int = 0
    subtype_kind: str | None = None

    def resolve_crawler_class(self) -> type[Any]:
        """순환 import 없이 실제 crawler class를 필요할 때만 읽는다."""
        module_name, class_name = self.crawler_class.rsplit(".", 1)
        return getattr(import_module(module_name), class_name)


CRAWL_TYPE_SPECS = (
    CrawlTypeSpec(
        cli_name="fileData",
        csv_prefix="metadata_file",
        crawler_class="crawler.file_data_crawler.FileDataCrawler",
        url_kind="fileData",
        storage_dir="fileData",
        is_subtype=False,
        supports_range=True,
        default_workers=30,
        full_order=1,
        storage_order=3,
        ui_order=1,
    ),
    CrawlTypeSpec(
        cli_name="openapi",
        csv_prefix="metadata_api",
        crawler_class="crawler.openapi_crawler.OpenAPICrawler",
        url_kind="openapi",
        storage_dir=None,
        is_subtype=False,
        supports_range=True,
        default_workers=16,
        full_order=0,
        ui_order=0,
    ),
    CrawlTypeSpec(
        cli_name="openapi_new",
        csv_prefix="metadata_api",
        crawler_class="crawler.openapi_crawler.OpenAPICrawler",
        url_kind="openapi",
        storage_dir="openapi_new",
        is_subtype=True,
        supports_range=False,
        default_workers=16,
        storage_order=0,
        ui_order=3,
        subtype_kind="swagger",
    ),
    CrawlTypeSpec(
        cli_name="openapi_old",
        csv_prefix="metadata_api",
        crawler_class="crawler.openapi_crawler.OpenAPICrawler",
        url_kind="openapi",
        storage_dir="openapi_old",
        is_subtype=True,
        supports_range=False,
        default_workers=16,
        storage_order=1,
        ui_order=4,
        subtype_kind="legacy",
    ),
    CrawlTypeSpec(
        cli_name="openapi_link",
        csv_prefix="metadata_api",
        crawler_class="crawler.openapi_crawler.OpenAPICrawler",
        url_kind="openapi",
        storage_dir="openapi_link",
        is_subtype=True,
        supports_range=False,
        default_workers=16,
        storage_order=2,
        ui_order=5,
        subtype_kind="link",
    ),
    CrawlTypeSpec(
        cli_name="standard",
        csv_prefix="metadata_std",
        crawler_class="crawler.standard_crawler.StandardCrawler",
        url_kind="standard",
        storage_dir="standard",
        is_subtype=False,
        supports_range=True,
        default_workers=30,
        full_order=2,
        storage_order=4,
        ui_order=2,
    ),
)

CRAWL_TYPES = {spec.cli_name: spec for spec in CRAWL_TYPE_SPECS}
CLI_CRAWL_TYPES = tuple(CRAWL_TYPES)
UI_CRAWL_TYPES = tuple(
    spec.cli_name for spec in sorted(CRAWL_TYPE_SPECS, key=lambda item: item.ui_order)
)
FULL_CRAWL_TYPES = tuple(
    spec.cli_name
    for spec in sorted(
        (item for item in CRAWL_TYPE_SPECS if item.full_order is not None),
        key=lambda item: item.full_order,
    )
)
RANGE_CRAWL_TYPES = tuple(
    spec.cli_name
    for spec in sorted(
        (item for item in CRAWL_TYPE_SPECS if item.supports_range),
        key=lambda item: item.full_order,
    )
)
DOCUMENT_STORAGE_DIRS = tuple(
    spec.storage_dir
    for spec in sorted(
        (item for item in CRAWL_TYPE_SPECS if item.storage_order is not None),
        key=lambda item: item.storage_order,
    )
)
OPENAPI_SUBTYPES = frozenset(spec.cli_name for spec in CRAWL_TYPE_SPECS if spec.is_subtype)

CSV_DIR = Path(__file__).resolve().parent / "scanner" / "database"


def get_crawl_type(data_type: str) -> CrawlTypeSpec:
    return CRAWL_TYPES[data_type]


def detect_openapi_subtype(api_type_value: str, has_swagger: bool) -> str:
    if "LINK" in api_type_value.upper():
        subtype_kind = "link"
    elif has_swagger:
        subtype_kind = "swagger"
    else:
        subtype_kind = "legacy"
    return next(
        spec.cli_name for spec in CRAWL_TYPE_SPECS if spec.subtype_kind == subtype_kind
    )


def csv_row_matches(data_type: str, api_type_value: str) -> bool:
    spec = get_crawl_type(data_type)
    if spec.subtype_kind == "link":
        return "LINK" in api_type_value.upper()
    if spec.is_subtype:
        return "LINK" not in api_type_value.upper()
    return True


def storage_subdirectory(api_type: str) -> str | None:
    spec = CRAWL_TYPES.get(api_type)
    return spec.storage_dir if spec and spec.is_subtype else None


__all__ = [
    "CLI_CRAWL_TYPES",
    "CRAWL_TYPES",
    "CRAWL_TYPE_SPECS",
    "CSV_DIR",
    "CrawlTypeSpec",
    "DOCUMENT_STORAGE_DIRS",
    "FULL_CRAWL_TYPES",
    "OPENAPI_SUBTYPES",
    "RANGE_CRAWL_TYPES",
    "UI_CRAWL_TYPES",
    "csv_row_matches",
    "detect_openapi_subtype",
    "get_crawl_type",
    "storage_subdirectory",
]
