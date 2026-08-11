import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

current_dir = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = current_dir
STAGE_DIR = current_dir

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
LIBS_DIR = Path(BASE_DIR).parents[1] / "libs"
if str(LIBS_DIR) not in sys.path:
    sys.path.insert(0, str(LIBS_DIR))

from domain.schemas import CrawlerConfig
from crawler.file_data_crawler import FileDataCrawler
from managers.crawl_run_manager import CrawlRunManager
from crawler.openapi_crawler import OpenAPICrawler
from crawler.standard_crawler import StandardCrawler
from nara_common.cli import interactive_argv, wants_interactive
from utils.metadata_csv import MetadataCsvReader
from utils.metadata_updater import maybe_update_metadata
from utils.url_utils import URLGenerator


DATA_TYPE_OUTPUT_DIRS = {
    "fileData": "02_fileData_results",
    "openapi": "01_openapi_results",
    "openapi_new": "01_openapi_results",
    "openapi_link": "01_openapi_results",
    "openapi_old": "01_openapi_results",
    "standard": "03_standard_results",
}

DEFAULT_WORKERS_BY_TYPE = {
    "fileData": 30,
    "openapi": 16,
    "openapi_new": 16,
    "openapi_link": 16,
    "openapi_old": 16,
    "standard": 30,
}

# 스캐너가 목록 CSV를 내려받는 곳이자 크롤러가 읽는 곳. 한 자리뿐이라 옵션이 아니다.
CSV_DIR = os.path.join(STAGE_DIR, "scanner", "database")

CSV_PREFIX_MAP = {
    "fileData": "metadata_file",
    "openapi": "metadata_api",
    "openapi_new": "metadata_api",
    "openapi_link": "metadata_api",
    "openapi_old": "metadata_api",
    "standard": "metadata_std",
}

CRAWLER_CLASSES = {
    "fileData": FileDataCrawler,
    "openapi": OpenAPICrawler,
    "openapi_new": OpenAPICrawler,
    "openapi_link": OpenAPICrawler,
    "openapi_old": OpenAPICrawler,
    "standard": StandardCrawler,
}

OPENAPI_SUBTYPES = {"openapi_new", "openapi_old", "openapi_link"}


# 심화 단계는 이번 크롤이 아니라 저장소를 읽는다(run_depth_stages 참고). 그래도 방금
# 크롤한 것과 무관한 단계를 묻는 것은 오해를 부르므로, **그 코퍼스를 만들 수 있는
# 실행에서만** 대화형 질문을 띄운다. 타입이 비면 심화 단독 실행이라 둘 다 묻는다.
def _may_produce_file_data(answers: Dict) -> bool:
    return bool(answers.get("full")) or (answers.get("type") or "") in ("", "fileData")


def _may_produce_link_docs(answers: Dict) -> bool:
    # openapi 크롤은 하위 타입을 크롤 후에 정하므로 LINK 문서를 만들어낸다.
    # openapi_link만 대상이라고 보면 `openapi --harvest`가 부당하게 막힌다.
    data_type = answers.get("type") or ""
    return bool(answers.get("full")) or not data_type or data_type.startswith("openapi")


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
    # openapi_new / openapi_old both come from non-LINK CSV rows; they are told
    # apart after fetching by whether inline swaggerJson parses successfully.
    if data_type in ("openapi_new", "openapi_old"):
        return lambda row: "LINK" not in get_api_type_value(row)
    return None


def get_default_output_dir(data_type: str) -> str:
    run_manager = CrawlRunManager(BASE_DIR)
    if is_openapi_type(data_type):
        # openapi는 file_storage가 api_type(openapi_new/openapi_old/openapi_link) 하위 폴더를 붙인다
        return str(run_manager.storage_dir)
    return str(run_manager.get_raw_output_dir(storage_data_type(data_type)))


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
):
    """Crawls a single data type with the given document-number range."""
    resolved_workers = resolve_workers(data_type, workers)
    print(f"\n{'=' * 80}")
    print(f"Starting {data_type.upper()} Crawling (Range: {start}-{end})")
    print(f"Workers: {resolved_workers}")
    print(f"{'=' * 80}")

    run_manager = CrawlRunManager(BASE_DIR)
    output_dir = output_dir or get_default_output_dir(data_type)
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

    run_manager.manifests_dir.mkdir(parents=True, exist_ok=True)
    summary_path = run_manager.manifests_dir / f"{crawl_run_id}_{data_type}_summary.json"

    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    manifest_part = {
        "data_type": data_type,
        "start_doc": start,
        "end_doc": end,
        "output_dir": str(output_dir),
        "summary_path": str(summary_path.relative_to(run_manager.storage_dir).as_posix()),
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



async def run_depth_stages(args, run_manager: CrawlRunManager, crawl_run_id: str) -> Dict[str, str]:
    """Runs the post-crawl depth pipeline over already-stored documents.

    Every stage here is opt-in. Nothing in this function runs during a plain
    crawl, because fetching data files and probing agency portals is far more
    intrusive than reading data.go.kr detail pages.
    """
    outputs: Dict[str, str] = {}
    storage = run_manager.storage_dir
    reports_dir = storage / "reports"

    if args.deep:
        from profiling import FetchPolicy, fetch_download_urls, infer_fetched_files

        records = _load_stored_records(storage / "fileData")
        download_urls: Dict[str, str] = {}
        for record in records:
            download_urls.update(record.get("download_urls") or {})
        if not download_urls:
            print("No fileData download URLs found; run a fileData crawl first.")
        else:
            print(f"Profiling {len(download_urls)} file(s) "
                  f"({'full download' if args.full_download else 'range sampling'})...")
            # 전량 수신은 받은 파일을 둘 곳이 있어야 한다 (fetcher가 output_dir을 요구한다).
            # 샘플링은 메모리에만 남으므로 디렉터리를 만들지 않는다.
            files_dir = storage / "files" / crawl_run_id if args.full_download else None
            fetched = await fetch_download_urls(
                download_urls,
                policy=FetchPolicy(full_download=args.full_download),
                output_dir=files_dir,
            )
            if files_dir is not None:
                print(f"  saved files to {files_dir}")
            # 이하 산출물은 전부 파일명(download_urls의 키)으로 색인한다. 리포트를
            # 배열로 두면 어느 파일에서 나온 지표인지 알 수 없다.
            schemas = infer_fetched_files(fetched)
            reports_dir.mkdir(parents=True, exist_ok=True)
            schema_path = reports_dir / f"{crawl_run_id}_file_schemas.json"
            _dump_json(schema_path, schemas)
            outputs["file_schemas"] = str(schema_path)

            # 아래 두 리포트는 이미 받아온 샘플을 후처리할 뿐이라 네트워크를
            # 더 쓰지 않는다. 따로 켜고 끌 이유가 없어 --deep에 포함한다.
            from profiling import (
                detect_address_columns,
                generate_quality_report,
                inspect_coordinate_columns,
            )

            # 품질 리포트는 스키마와 **그 스키마를 뽑은 바로 그 바이트**를 함께 본다.
            quality = {}
            for name, schema in schemas.items():
                result = fetched.get(name)
                if result is None or getattr(result, "status", None) != "ok":
                    continue
                quality[name] = generate_quality_report(
                    schema, result.sample, truncated=result.truncated
                )
            quality_path = reports_dir / f"{crawl_run_id}_quality.json"
            _dump_json(quality_path, quality)
            outputs["quality"] = str(quality_path)

            findings = {
                name: {
                    "address_columns": detect_address_columns(schema),
                    "coordinates": inspect_coordinate_columns(schema),
                }
                for name, schema in schemas.items()
            }
            address_path = reports_dir / f"{crawl_run_id}_address_geo.json"
            _dump_json(address_path, findings)
            outputs["address_geo"] = str(address_path)

    if args.harvest:
        from link_docs import collect_link_specs, result_to_dict, to_openapi_like

        records = _load_stored_records(storage / "openapi_link")
        reports_dir.mkdir(parents=True, exist_ok=True)

        # Stage 1 - the valuable one: visit the agency page each LINK document
        # points at (info['URL'], populated for the whole corpus) and recover its
        # API rules in the same endpoints[] shape openapi_new uses.
        print(f"Collecting API rules from {len(records)} LINK document(s)...")
        specs, spec_coverage = await collect_link_specs(records)
        if specs:
            spec_dir = storage / "openapi_link_spec"
            spec_dir.mkdir(parents=True, exist_ok=True)
            saved = 0
            for spec in specs:
                if spec.status == "ok":
                    _dump_json_quiet(spec_dir / f"{spec.api_id}.json", to_openapi_like(spec))
                    saved += 1
            coverage_path = reports_dir / f"{crawl_run_id}_link_spec_coverage.json"
            _dump_json(coverage_path, spec_coverage)
            _dump_json(
                reports_dir / f"{crawl_run_id}_link_spec_results.json",
                [result_to_dict(spec) for spec in specs],
            )
            outputs["link_specs"] = str(coverage_path)
            print(
                f"  static coverage {spec_coverage['static_extracted']}/{spec_coverage['documents']} "
                f"({spec_coverage['static_coverage_pct']}%) over {spec_coverage['hosts']} host(s); "
                f"{spec_coverage['needs_rendered_retry']} need rendering, "
                f"{spec_coverage['blocked_by_robots']} blocked by robots.txt"
            )
            print(f"  wrote {saved} spec document(s) to {spec_dir}")

        # Stage 2: host-level portal discovery. Secondary — it probes host roots
        # for CKAN/Swagger endpoints rather than reading the per-document pages.
        from portals import harvest_with_safe_transport

        with_urls = [r for r in records if r.get("external_endpoint_urls")]
        if with_urls:
            print(f"Probing portal protocols on up to {args.harvest_max_hosts} host(s)...")
            results, coverage = await harvest_with_safe_transport(
                with_urls, max_hosts=args.harvest_max_hosts
            )
            harvest_path = reports_dir / f"{crawl_run_id}_portal_harvest.json"
            _dump_json(harvest_path, {"coverage": coverage, "results": results})
            outputs["portal_harvest"] = str(harvest_path)

    return outputs


def _load_stored_records(directory) -> List[Dict]:
    """Reads stored crawl output JSON files; missing directory yields no records."""
    if not directory.is_dir():
        return []
    records = []
    for path in sorted(directory.glob("*.json")):
        try:
            with path.open(encoding="utf-8") as handle:
                records.append(json.load(handle))
        except (OSError, json.JSONDecodeError):
            continue
    return records


def _json_default(value):
    """Render dataclasses and other objects json cannot serialise natively."""
    if hasattr(value, "__dict__"):
        return {k: v for k, v in vars(value).items() if not k.startswith("_")}
    return str(value)


def _dump_json_quiet(path, payload) -> None:
    """Silent writer for per-document output; one log line per file would bury
    the run summary under thousands of lines."""
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=_json_default)


def _dump_json(path, payload) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=_json_default)
    print(f"  wrote {path}")


async def main():
    parser = argparse.ArgumentParser(description="Integrated Nara Crawler (FileData, OpenAPI, Standard)")

    # --full은 type/start/end를 대신한다. 대화형 순서는 아래 ask_first가 정하므로
    # 전체 크롤을 고른 사람에게 범위를 되묻지 않는다.
    parser.add_argument("--full", action="store_true", help="Crawl all types with full range from CSV")
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
    parser.add_argument(
        "--skip-update",
        action="store_true",
        help="Skip the auto metadata-list update check before crawling",
    )
    parser.add_argument(
        "--force-update",
        action="store_true",
        help="Force re-download of the metadata list CSV even if not newer",
    )

    # ── 심화 파이프라인 (크롤링 이후 단계) ────────────────────────────────
    # 기본값은 비활성이다. 파일 수신·외부 포털 접근은 명시적으로 켜야 한다.
    # 리포트를 따로 켜는 플래그는 두지 않는다: 비용은 전부 파일 수신에 있고
    # 품질·주소 분석은 같은 샘플을 후처리하는 것뿐이라 나눌 실익이 없다.
    parser.add_argument(
        "--deep",
        action="store_true",
        help="Fetch fileData samples and emit schema, quality and address reports",
    )
    parser.add_argument(
        "--full-download",
        action="store_true",
        help="With --deep, download whole files instead of sampling. Heavy on the portal.",
    )
    parser.add_argument(
        "--harvest",
        action="store_true",
        help="Harvest agency portals discovered from LINK-type external endpoint URLs",
    )
    parser.add_argument(
        "--harvest-max-hosts",
        type=int,
        default=4,
        help="Maximum distinct hosts to probe per harvest run (default: 4)",
    )

    argv = sys.argv[1:]
    if wants_interactive(argv):
        # type/-s/-e가 필수라 인자 없이 부르면 원래 usage 에러였다. 콘솔이면 그 자리에서
        # 물어보고, 비대화형(파이프·CI)이면 예전처럼 에러를 낸다.
        argv = interactive_argv(
            parser,
            ask_if={
                "type": "!full",
                "start": "!full",
                "end": "!full",
                "deep": _may_produce_file_data,
                "full_download": "deep",
                "harvest": _may_produce_link_docs,
                "harvest_max_hosts": "harvest",
            },
            # openapi_new/old/link은 openapi를 CSV에서 걸러낸 부분집합일 뿐이고,
            # 실제 하위 타입은 크롤 후 인라인 swagger 파싱 결과로 정해져 저장 폴더가
            # 어차피 셋으로 갈린다. 고를 것은 openapi 하나다. 명령줄로는 여전히 받는다.
            choices_for={"type": ["fileData", "openapi", "standard"]},
            # 무엇을 크롤할지는 답이 없으면 실행 자체가 불가능하니 하나씩 묻는다.
            # 나머지는 전부 기본값이 있는 곁가지라, 켤 것만 한 번에 고르게 한다.
            ask_first=["full", "type", "start", "end"],
        )
        if argv is None:
            return
    args = parser.parse_args(argv)
    if args.workers is not None and args.workers < 1:
        parser.error("--workers must be greater than 0")

    if args.full_download and not args.deep:
        parser.error("--full-download requires --deep")
    if args.harvest_max_hosts < 1:
        parser.error("--harvest-max-hosts must be greater than 0")

    # 심화 단계만 도는 경우 크롤이 없으므로 목록 CSV 갱신도 의미가 없다.
    # 사용자가 --skip-update를 매번 붙이지 않아도 되도록 여기서 자동 생략한다.
    depth_only = (args.deep or args.harvest) and not args.type and not args.full

    # 크롤 시작 전 목록 CSV 신규 여부 자동 확인 후 필요 시 다운로드
    if not args.skip_update and not depth_only:
        await maybe_update_metadata(CSV_DIR, force=args.force_update)

    crawl_run_id = CrawlRunManager.create_run_id()
    run_manager = CrawlRunManager(BASE_DIR)
    manifest = {
        "crawl_run_id": crawl_run_id,
        "source": "data.go.kr",
        "crawler_stage": "crawler",
        "started_at": CrawlRunManager.now_iso(),
        "runs": [],
    }

    if args.full:
        print("\n" + "=" * 80)
        print("FULL MODE: Crawling all types (openapi, fileData, standard)")
        print("=" * 80)
        print(f"Using metadata CSV directory: {CSV_DIR}")

        type_ranges = {}
        for data_type in ["openapi", "fileData", "standard"]:
            csv_path = find_latest_metadata_csv(CSV_DIR, CSV_PREFIX_MAP[data_type])
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
                csv_dir=CSV_DIR,
                crawl_run_id=crawl_run_id,
                output_dir=args.output_dir,
            )
            if result_manifest:
                manifest["runs"].append(result_manifest)

        manifest["ended_at"] = CrawlRunManager.now_iso()
        run_manager.save_manifest(crawl_run_id, manifest)
        print("\n" + "=" * 80)
        print("FULL MODE COMPLETE: All types crawled successfully")
        print(f"Manifest saved to {run_manager.manifests_dir / (crawl_run_id + '.json')}")
        print("=" * 80)
        await run_depth_stages(args, run_manager, crawl_run_id)
        return

    if depth_only:
        # 심화 단계는 이미 저장된 문서를 읽으므로 크롤 없이도 단독 실행된다.
        await run_depth_stages(args, run_manager, crawl_run_id)
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
        csv_dir=CSV_DIR,
        crawl_run_id=crawl_run_id,
        output_dir=args.output_dir,
    )
    if result_manifest:
        manifest["runs"].append(result_manifest)
    manifest["ended_at"] = CrawlRunManager.now_iso()
    run_manager.save_manifest(crawl_run_id, manifest)
    await run_depth_stages(args, run_manager, crawl_run_id)


if __name__ == "__main__":
    asyncio.run(main())
