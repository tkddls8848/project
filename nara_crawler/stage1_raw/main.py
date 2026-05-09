import argparse
import asyncio
import json
import os
import sys
from typing import Dict, List, Optional

current_dir = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(current_dir)
STAGE_DIR = current_dir

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from stage1_raw.domain.schemas import CrawlerConfig
from stage1_raw.crawler.file_data_crawler import FileDataCrawler
from stage1_raw.managers.index_manager import IndexManager
from stage1_raw.managers.crawl_run_manager import CrawlRunManager
from stage1_raw.crawler.openapi_crawler import OpenAPICrawler
from stage1_raw.crawler.standard_crawler import StandardCrawler
from stage1_raw.utils.metadata_csv import MetadataCsvReader
from stage1_raw.utils.url_utils import URLGenerator


DATA_TYPE_OUTPUT_DIRS = {
    "fileData": "02_fileData_results",
    "openapi": "01_openapi_results",
    "openapi_new": "01_openapi_results",
    "openapi_old": "01_openapi_results",
    "openapi_link": "01_openapi_results",
    "standard": "03_standard_results",
}

DEFAULT_WORKERS_BY_TYPE = {
    "fileData": 30,
    "openapi": 16,
    "openapi_new": 16,
    "openapi_old": 16,
    "openapi_link": 16,
    "standard": 30,
}

CSV_PREFIX_MAP = {
    "fileData": "metadata_file",
    "openapi": "metadata_api",
    "openapi_new": "metadata_api",
    "openapi_old": "metadata_api",
    "openapi_link": "metadata_api",
    "standard": "metadata_std",
}

CRAWLER_CLASSES = {
    "fileData": FileDataCrawler,
    "openapi": OpenAPICrawler,
    "openapi_new": OpenAPICrawler,
    "openapi_old": OpenAPICrawler,
    "openapi_link": OpenAPICrawler,
    "standard": StandardCrawler,
}

OPENAPI_SUBTYPES = {"openapi_new", "openapi_old", "openapi_link"}


def find_latest_metadata_csv(base_dir: str, prefix: str) -> Optional[str]:
    """Finds metadata CSV file with fixed filename, e.g. metadata_api.csv."""
    csv_path = os.path.join(base_dir, f"{prefix}.csv")
    return csv_path if os.path.exists(csv_path) else None


def get_csv_range(csv_path: str) -> tuple[Optional[int], Optional[int]]:
    """Extract min and max document numbers from a metadata CSV."""
    return MetadataCsvReader(csv_path).get_range()


def get_numbers_from_csv(csv_path: str, start: int, end: int, data_type: str) -> tuple[List[int], Dict[int, Dict]]:
    """Return document numbers and row metadata from a metadata CSV."""
    return MetadataCsvReader(csv_path).get_numbers_in_range(start, end, row_filter=get_csv_row_filter(data_type))


def is_openapi_type(data_type: str) -> bool:
    return data_type == "openapi" or data_type in OPENAPI_SUBTYPES


def storage_data_type(data_type: str) -> str:
    return "openapi" if data_type in OPENAPI_SUBTYPES else data_type


def url_data_type(data_type: str) -> str:
    return "openapi" if is_openapi_type(data_type) else data_type


def target_api_type(data_type: str) -> Optional[str]:
    return data_type if data_type in OPENAPI_SUBTYPES else None


def get_api_type_value(row: Dict) -> str:
    value = row.get("API 유형") or row.get("API유형") or row.get("API 타입") or row.get("API타입")
    if value is None:
        values = list(row.values())
        if len(values) >= 30:
            value = values[29]
    return str(value or "").strip().upper()


def get_csv_row_filter(data_type: str):
    if data_type == "openapi_link":
        return lambda row: "LINK" in get_api_type_value(row)
    if data_type in {"openapi_new", "openapi_old"}:
        return lambda row: "LINK" not in get_api_type_value(row)
    return None


def get_default_output_dir(data_type: str, crawl_run_id: str) -> str:
    run_manager = CrawlRunManager(BASE_DIR)
    if is_openapi_type(data_type):
        return str(run_manager.get_run_dir(crawl_run_id))
    return str(run_manager.get_raw_output_dir(crawl_run_id, storage_data_type(data_type)))


def resolve_workers(data_type: str, workers: Optional[int]) -> int:
    if workers is not None:
        return workers
    return DEFAULT_WORKERS_BY_TYPE[data_type]


async def crawl_single_type(
    data_type: str,
    start: int,
    end: int,
    workers: Optional[int],
    csv_dir: str,
    crawl_run_id: str,
    output_dir: Optional[str] = None,
    legacy_index: bool = False,
):
    """Crawls a single data type with the given document-number range."""
    resolved_workers = resolve_workers(data_type, workers)
    print(f"\n{'=' * 80}")
    print(f"Starting {data_type.upper()} Crawling (Range: {start}-{end})")
    print(f"Workers: {resolved_workers}")
    print(f"{'=' * 80}")

    run_manager = CrawlRunManager(BASE_DIR)
    output_dir = output_dir or get_default_output_dir(data_type, crawl_run_id)
    config = CrawlerConfig(
        start_num=start,
        end_num=end,
        output_dir=output_dir,
        max_workers=resolved_workers,
        csv_dir=csv_dir,
        target_api_type=target_api_type(data_type),
    )

    csv_path = find_latest_metadata_csv(csv_dir, CSV_PREFIX_MAP[data_type])
    if not csv_path:
        print(f"Error: No CSV found for {CSV_PREFIX_MAP[data_type]} in {csv_dir}")
        return None

    print(f"Using CSV: {csv_path}")

    valid_numbers, csv_data = get_numbers_from_csv(csv_path, start, end, data_type)
    if not valid_numbers:
        print(f"No documents found in range {start}-{end}")
        return None

    print(f"Found {len(valid_numbers)} documents to crawl.")

    urls = URLGenerator.generate_urls_from_numbers(valid_numbers, url_data_type(data_type))
    crawler = CRAWLER_CLASSES[data_type](config)
    results = await crawler.crawl(urls, csv_metadata=csv_data)

    saved_info = crawler.save_results(results)
    saved_count = saved_info.get("total_saved", 0)
    skipped_by_api_type = getattr(crawler, "skipped_by_api_type", 0)
    summary_results = [
        result
        for result in results
        if result.data is not None or not (target_api_type(data_type) and result.success)
    ]
    summary = crawler.generate_summary(
        summary_results,
        saved_info,
        extra_stats={
            "api_type_filter": {
                "requested_type": data_type,
                "target_api_type": target_api_type(data_type),
                "csv_candidates": len(valid_numbers),
                "saved_count": saved_count,
                "skipped_by_api_type": skipped_by_api_type,
            }
        },
        start_doc=start,
        end_doc=end,
    )

    run_dir = run_manager.get_run_dir(crawl_run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    summary_path = run_dir / f"{data_type}_summary.json"

    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    if legacy_index:
        raw_data_dir = os.path.join(BASE_DIR, "data", "raw_data")
        os.makedirs(raw_data_dir, exist_ok=True)
        IndexManager.save(results, os.path.join(raw_data_dir, "index.json"))

    manifest_part = {
        "data_type": data_type,
        "start_doc": start,
        "end_doc": end,
        "output_dir": str(output_dir),
        "summary_path": str(summary_path.relative_to(BASE_DIR).as_posix()),
        "total_results": len(results),
        "total_success": summary["crawling_summary"]["total_success"],
        "total_failed": summary["crawling_summary"]["total_failed"],
        "files": run_manager.build_file_records(saved_info.get("saved_files", [])),
    }

    print(f"\n{data_type.upper()} Crawling Complete.")
    print(f"Total: {len(results)}, Success: {summary['crawling_summary']['total_success']}")
    if skipped_by_api_type:
        print(f"Skipped by API type filter: {skipped_by_api_type}")
    print(f"Summary saved to {summary_path}")
    print(f"{'=' * 80}\n")
    return manifest_part


async def main():
    parser = argparse.ArgumentParser(description="Integrated Nara Crawler (FileData, OpenAPI, Standard)")

    parser.add_argument(
        "type",
        nargs="?",
        choices=["fileData", "openapi", "openapi_new", "openapi_old", "openapi_link", "standard"],
        help="Type of data to crawl",
    )
    parser.add_argument("-s", "--start", type=int, help="Start document number")
    parser.add_argument("-e", "--end", type=int, help="End document number")
    parser.add_argument("-o", "--output-dir", help="Output directory")
    parser.add_argument(
        "-w",
        "--workers",
        type=int,
        default=None,
        help="Number of workers. Defaults: fileData=30, openapi/openapi_* =16, standard=30",
    )
    parser.add_argument("--full", action="store_true", help="Crawl all types with full range from CSV")
    parser.add_argument("--crawl-run-id", help="Optional crawl run id. Defaults to current KST timestamp")
    parser.add_argument("--legacy-index", action="store_true", help="Also write legacy data/raw_data/index.json")

    default_csv_dir = os.path.join(STAGE_DIR, "scanner", "database")
    parser.add_argument("--csv-dir", default=default_csv_dir, help="Directory for CSV metadata")

    args = parser.parse_args()
    if args.workers is not None and args.workers < 1:
        parser.error("--workers must be greater than 0")

    crawl_run_id = args.crawl_run_id or CrawlRunManager.create_run_id()
    run_manager = CrawlRunManager(BASE_DIR)
    manifest = {
        "crawl_run_id": crawl_run_id,
        "source": "data.go.kr",
        "crawler_stage": "stage1_raw",
        "started_at": CrawlRunManager.now_iso(),
        "runs": [],
    }

    if args.full:
        print("\n" + "=" * 80)
        print("FULL MODE: Crawling all types (openapi, fileData, standard)")
        print("=" * 80)
        print(f"Using metadata CSV directory: {args.csv_dir}")

        type_ranges = {}
        for data_type in ["openapi", "fileData", "standard"]:
            csv_path = find_latest_metadata_csv(args.csv_dir, CSV_PREFIX_MAP[data_type])
            if not csv_path:
                print(f"Warning: No CSV found for {data_type}, skipping...")
                continue

            min_val, max_val = get_csv_range(csv_path)
            if min_val is not None and max_val is not None:
                type_ranges[data_type] = (min_val, max_val)
                print(f"{data_type:12s}: Range {min_val} - {max_val}")
            else:
                print(f"Warning: Could not extract range for {data_type}, skipping...")

        print("=" * 80 + "\n")

        for data_type in ["openapi", "fileData", "standard"]:
            if data_type not in type_ranges:
                continue

            start, end = type_ranges[data_type]
            result_manifest = await crawl_single_type(
                data_type=data_type,
                start=start,
                end=end,
                workers=args.workers,
                csv_dir=args.csv_dir,
                crawl_run_id=crawl_run_id,
                output_dir=args.output_dir,
                legacy_index=args.legacy_index,
            )
            if result_manifest:
                manifest["runs"].append(result_manifest)

        manifest["ended_at"] = CrawlRunManager.now_iso()
        run_manager.save_manifest(crawl_run_id, manifest)
        print("\n" + "=" * 80)
        print("FULL MODE COMPLETE: All types crawled successfully")
        print(f"Manifest saved to {run_manager.get_run_dir(crawl_run_id) / 'manifest.json'}")
        print("=" * 80)
        return

    if not args.type:
        parser.error("the following arguments are required: type (unless --full is used)")
    if args.start is None:
        parser.error("the following arguments are required: -s/--start (unless --full is used)")
    if args.end is None:
        parser.error("the following arguments are required: -e/--end (unless --full is used)")

    result_manifest = await crawl_single_type(
        data_type=args.type,
        start=args.start,
        end=args.end,
        workers=args.workers,
        csv_dir=args.csv_dir,
        crawl_run_id=crawl_run_id,
        output_dir=args.output_dir,
        legacy_index=args.legacy_index,
    )
    if result_manifest:
        manifest["runs"].append(result_manifest)
    manifest["ended_at"] = CrawlRunManager.now_iso()
    run_manager.save_manifest(crawl_run_id, manifest)


if __name__ == "__main__":
    asyncio.run(main())
