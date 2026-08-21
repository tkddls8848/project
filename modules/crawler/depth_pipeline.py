"""저장된 전체 corpus를 읽어 실행하는 opt-in 심화 단계."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

from managers.crawl_run_manager import CrawlRunManager


def _load_stored_records(directory: Path) -> List[Dict[str, Any]]:
    """읽을 수 있는 JSON 객체만 반환하고 건너뛴 사유를 한 줄로 집계한다."""
    if not directory.is_dir():
        return []

    records: List[Dict[str, Any]] = []
    skipped: Counter[str] = Counter()
    for path in sorted(directory.glob("*.json")):
        try:
            with path.open(encoding="utf-8") as handle:
                payload = json.load(handle)
        except OSError:
            skipped["read error"] += 1
            continue
        except (json.JSONDecodeError, UnicodeError):
            skipped["invalid JSON"] += 1
            continue
        if not isinstance(payload, dict):
            skipped["non-object JSON"] += 1
            continue
        records.append(payload)

    if skipped:
        reasons = ", ".join(f"{reason}: {count}" for reason, count in skipped.items())
        print(
            f"Skipped {sum(skipped.values())} stored document(s) from {directory}: {reasons}"
        )
    return records


async def run_file_profiling(
    args, run_manager: CrawlRunManager, crawl_run_id: str
) -> Dict[str, str]:
    """저장소 전체 fileData 문서의 파일을 받아 profiling 리포트를 만든다."""
    from profiling import FetchPolicy, fetch_download_urls, infer_fetched_files

    storage = run_manager.storage_dir
    records = _load_stored_records(storage / "fileData")
    download_urls: Dict[str, str] = {}
    for record in records:
        download_urls.update(record.get("download_urls") or {})
    if not download_urls:
        print("No fileData download URLs found; run a fileData crawl first.")
        return {}

    print(
        f"Profiling {len(download_urls)} file(s) "
        f"({'full download' if args.full_download else 'range sampling'})..."
    )
    files_dir = storage / "files" / crawl_run_id if args.full_download else None
    fetched = await fetch_download_urls(
        download_urls,
        policy=FetchPolicy(full_download=args.full_download),
        output_dir=files_dir,
    )
    if files_dir is not None:
        print(f"  saved files to {files_dir}")

    schemas = infer_fetched_files(fetched)
    reports_dir = storage / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    outputs: Dict[str, str] = {}
    schema_path = reports_dir / f"{crawl_run_id}_file_schemas.json"
    _dump_json(schema_path, schemas)
    outputs["file_schemas"] = str(schema_path)

    from profiling import (
        detect_address_columns,
        generate_quality_report,
        inspect_coordinate_columns,
    )

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
    return outputs


async def run_link_harvest(
    args, run_manager: CrawlRunManager, crawl_run_id: str
) -> Dict[str, str]:
    """저장소 전체 LINK 문서의 페이지와 host-root 프로토콜을 수집한다."""
    from link_docs import collect_link_specs, result_to_dict, to_openapi_like

    storage = run_manager.storage_dir
    records = _load_stored_records(storage / "openapi_link")
    reports_dir = storage / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    outputs: Dict[str, str] = {}

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

    from portals import harvest_with_safe_transport

    with_urls = [record for record in records if record.get("external_endpoint_urls")]
    if with_urls:
        print(f"Probing portal protocols on up to {args.harvest_max_hosts} host(s)...")
        results, coverage = await harvest_with_safe_transport(
            with_urls, max_hosts=args.harvest_max_hosts
        )
        harvest_path = reports_dir / f"{crawl_run_id}_portal_harvest.json"
        _dump_json(harvest_path, {"coverage": coverage, "results": results})
        outputs["portal_harvest"] = str(harvest_path)
    return outputs


async def run_depth_stages(
    args, run_manager: CrawlRunManager, crawl_run_id: str
) -> Dict[str, str]:
    """명시적으로 켠 단계만 저장소 전체 corpus에 실행한다."""
    outputs: Dict[str, str] = {}
    if args.deep:
        outputs.update(await run_file_profiling(args, run_manager, crawl_run_id))
    if args.harvest:
        outputs.update(await run_link_harvest(args, run_manager, crawl_run_id))
    return outputs


def _json_default(value: Any):
    if hasattr(value, "__dict__"):
        return {key: item for key, item in vars(value).items() if not key.startswith("_")}
    return str(value)


def _dump_json_quiet(path: Path, payload: Any) -> None:
    """문서별 파일은 요약 로그를 묻지 않도록 조용히 쓴다."""
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=_json_default)


def _dump_json(path: Path, payload: Any) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=_json_default)
    print(f"  wrote {path}")


__all__ = ["run_depth_stages", "run_file_profiling", "run_link_harvest"]
