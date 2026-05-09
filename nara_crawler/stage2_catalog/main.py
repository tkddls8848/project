import argparse
import hashlib
import json
import logging
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(CURRENT_DIR)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from stage2_catalog.managers.catalog_extractors import (
    extract_agency_record,
    extract_document_record,
    extract_endpoint_records,
    extract_field_records,
    extract_service_record,
    refine_raw_record,
)
from stage2_catalog.managers.catalog_writer import CatalogWriter
from stage2_catalog.managers.raw_source_discovery import RawFileRef, discover_raw_files
from stage2_catalog.managers.raw_source_discovery import discover_refined_files


KST = timezone(timedelta(hours=9))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def now_iso() -> str:
    return datetime.now(KST).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def rel_path(base_dir: Path, path: Path) -> str:
    try:
        return path.relative_to(base_dir).as_posix()
    except ValueError:
        return path.as_posix()


def read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


class Stage2CatalogProcessor:
    def __init__(self, base_dir: str | Path, include_legacy: bool = False, data_type: str | None = None, crawl_run_id: str | None = None):
        self.base_dir = Path(base_dir)
        self.include_legacy = include_legacy
        self.data_type = data_type
        self.crawl_run_id = crawl_run_id
        self.refined_dir = self.base_dir / "data" / "refined_data"
        self.writer = CatalogWriter(self.base_dir)
        self.previous_latest = self.writer.load_latest_index()

    def process_all(self) -> None:
        refs = discover_raw_files(
            self.base_dir,
            data_type=self.data_type,
            crawl_run_id=self.crawl_run_id,
            include_legacy=self.include_legacy,
        )
        if not refs and not self.crawl_run_id:
            refs = discover_refined_files(self.base_dir, data_type=self.data_type)
            if refs:
                logger.info("No raw files found. Falling back to %s refined files.", len(refs))
        logger.info("Stage 2 starting: %s raw files", len(refs))

        agencies: dict[str, dict] = {}
        services: dict[str, dict] = {}
        documents: dict[str, dict] = {}
        endpoints: dict[str, dict] = {}
        fields: dict[str, dict] = {}
        history: list[dict] = []

        for raw_ref in refs:
            try:
                checksum = sha256_file(raw_ref.raw_path) if raw_ref.raw_path.exists() else None
            except Exception:
                checksum = None
            try:
                result = self.process_one(raw_ref, checksum)
                if result["agency"]:
                    agencies[result["agency"]["agency_id"]] = result["agency"]
                services[result["service"]["service_id"]] = result["service"]
                documents[result["document"]["document_id"]] = result["document"]
                for endpoint in result["endpoints"]:
                    endpoints[endpoint["endpoint_id"]] = endpoint
                for field in result["fields"]:
                    fields[field["field_id"]] = field
                history.append(result["history"])
            except Exception as exc:
                logger.exception("Failed processing %s", raw_ref.raw_path)
                history.append(self._history_record(raw_ref, "failed", "catalog_failed", checksum=checksum, collected_at="", error=str(exc)))

        self.writer.write_catalog_records(
            agencies=agencies.values(),
            services=services.values(),
            documents=documents.values(),
            endpoints=endpoints.values(),
            fields=fields.values(),
            history=history,
        )
        self._write_quality_reports(
            services=services,
            documents=documents,
            endpoints=endpoints,
            fields=fields,
        )

        logger.info("Stage 2 complete")
        logger.info("  services:  %s", len(services))
        logger.info("  agencies:  %s", len(agencies))
        logger.info("  documents: %s", len(documents))
        logger.info("  endpoints: %s", len(endpoints))
        logger.info("  fields:    %s", len(fields))
        logger.info("  history:   %s", len(history))

    def process_one(self, raw_ref: RawFileRef, checksum: str | None = None) -> dict:
        raw = read_json(raw_ref.raw_path)
        if raw_ref.is_refined:
            return self._process_refined(raw, raw_ref, checksum)
        collected_at = raw.get("crawled_time") or raw.get("crawled_at") or ""
        raw_rel_path = rel_path(self.base_dir, raw_ref.raw_path)
        refined = refine_raw_record(raw, raw_ref, raw_rel_path)
        refined_path = self._save_refined(refined, raw_ref)

        agency = extract_agency_record(refined)
        service = extract_service_record(refined, raw_ref, refined_path)
        document = extract_document_record(refined, raw_ref, refined_path)
        endpoint_records = extract_endpoint_records(refined, raw_ref)
        field_records = extract_field_records(refined, raw_ref)
        history = self._history_record(raw_ref, self._change_status(raw_ref, checksum), "done", checksum=checksum, collected_at=collected_at)

        return {
            "agency": agency,
            "service": service,
            "document": document,
            "endpoints": endpoint_records,
            "fields": field_records,
            "history": history,
        }

    def _process_refined(self, refined: dict, raw_ref: RawFileRef, checksum: str | None = None) -> dict:
        collected_at = refined.get("crawled_time") or refined.get("crawled_at") or ""
        refined_path = Path(rel_path(self.base_dir, raw_ref.raw_path))
        agency = extract_agency_record(refined)
        service = extract_service_record(refined, raw_ref, refined_path)
        document = extract_document_record(refined, raw_ref, refined_path)
        endpoint_records = extract_endpoint_records(refined, raw_ref)
        field_records = extract_field_records(refined, raw_ref)
        history = self._history_record(raw_ref, self._change_status(raw_ref, checksum), "done", checksum=checksum, collected_at=collected_at)

        return {
            "agency": agency,
            "service": service,
            "document": document,
            "endpoints": endpoint_records,
            "fields": field_records,
            "history": history,
        }

    def _save_refined(self, refined: dict, raw_ref: RawFileRef) -> Path:
        output_type = raw_ref.api_type if raw_ref.data_type == "openapi" else raw_ref.data_type
        output_dir = self.refined_dir / output_type
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{output_type}_{refined['api_id']}_refined.json"
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(refined, f, ensure_ascii=False, indent=2)
        return output_path.relative_to(self.base_dir)

    def _change_status(self, raw_ref: RawFileRef, checksum: str | None) -> str:
        key = ("data.go.kr", raw_ref.data_type, raw_ref.source_object_id)
        previous = self.previous_latest.get(key)
        if not previous:
            return "new"
        return "unchanged" if previous.get("latest_checksum") == checksum else "changed"

    def _history_record(self, raw_ref: RawFileRef, change_status: str, transform_status: str, checksum: str | None = None, collected_at: str = "", error: str | None = None) -> dict:
        key = ("data.go.kr", raw_ref.data_type, raw_ref.source_object_id)
        previous = self.previous_latest.get(key) or {}
        record = {
            "source_portal": "data.go.kr",
            "data_type": raw_ref.data_type,
            "source_object_id": raw_ref.source_object_id,
            "crawl_run_id": raw_ref.crawl_run_id,
            "raw_path": rel_path(self.base_dir, raw_ref.raw_path),
            "checksum": checksum,
            "collected_at": collected_at,
            "processed_at": now_iso(),
            "change_status": change_status,
            "previous_crawl_run_id": previous.get("latest_crawl_run_id"),
            "previous_checksum": previous.get("latest_checksum"),
            "transform_status": transform_status,
        }
        if error:
            record["error"] = error
        return record

    def _semantic_files_empty(self) -> bool:
        semantic_dir = self.base_dir / "data" / "03_semantic"
        if not semantic_dir.exists():
            return True
        files = list(semantic_dir.glob("*.jsonl"))
        if not files:
            return True
        return all(path.stat().st_size == 0 for path in files)

    def _write_json_report(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)

    def _write_quality_reports(
        self,
        services: dict[str, dict],
        documents: dict[str, dict],
        endpoints: dict[str, dict],
        fields: dict[str, dict],
    ) -> None:
        report_dir = self.base_dir / "data" / "99_reports" / "catalog"
        endpoints_by_service: dict[str, list[dict]] = defaultdict(list)
        fields_by_endpoint: dict[str, list[dict]] = defaultdict(list)
        for endpoint in endpoints.values():
            endpoints_by_service[endpoint.get("service_id")].append(endpoint)
        for field in fields.values():
            fields_by_endpoint[field.get("endpoint_id")].append(field)

        openapi_services = [service for service in services.values() if service.get("data_type") == "openapi"]
        quality_report = {
            "generated_at": now_iso(),
            "services_total": len(services),
            "documents_total": len(documents),
            "endpoints_total": len(endpoints),
            "fields_total": len(fields),
            "openapi_without_endpoint": sum(
                1 for service in openapi_services if not endpoints_by_service.get(service.get("service_id"))
            ),
            "endpoint_without_fields": sum(
                1 for endpoint in endpoints.values() if not fields_by_endpoint.get(endpoint.get("endpoint_id"))
            ),
            "semantic_files_empty": self._semantic_files_empty(),
            "services_by_data_type": dict(Counter(service.get("data_type", "unknown") for service in services.values())),
            "services_by_api_type": dict(Counter(service.get("api_type", "unknown") for service in services.values())),
        }
        self._write_json_report(report_dir / "catalog_quality_report.json", quality_report)

        endpoint_reports = []
        for endpoint in sorted(endpoints.values(), key=lambda item: item.get("endpoint_id", "")):
            endpoint_fields = fields_by_endpoint.get(endpoint.get("endpoint_id"), [])
            endpoint_reports.append(
                {
                    "endpoint_id": endpoint.get("endpoint_id"),
                    "service_id": endpoint.get("service_id"),
                    "method": endpoint.get("method"),
                    "path": endpoint.get("path"),
                    "fields_total": len(endpoint_fields),
                    "request_fields": sum(1 for field in endpoint_fields if field.get("field_role") == "request"),
                    "response_fields": sum(1 for field in endpoint_fields if field.get("field_role") == "response"),
                }
            )
        self._write_json_report(
            report_dir / "field_extraction_quality.json",
            {
                "generated_at": now_iso(),
                "endpoints_total": len(endpoints),
                "fields_total": len(fields),
                "endpoint_without_fields": quality_report["endpoint_without_fields"],
                "endpoints": endpoint_reports,
            },
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 2: refine raw crawl data and build catalog JSONL")
    parser.add_argument("--crawl-run-id", help="Process only one crawl run id")
    parser.add_argument("--include-legacy", action="store_true", help="Also process legacy data/raw_data")
    parser.add_argument("--data-type", choices=["openapi", "fileData", "standard"], help="Limit processing to one data type")
    parser.add_argument("--skip-keywords", action="store_true", help="Deprecated no-op. Stage 2 never generates LLM keywords.")
    args = parser.parse_args()

    if args.skip_keywords:
        logger.warning("--skip-keywords is deprecated and ignored. Stage 2 does not generate keywords.")

    processor = Stage2CatalogProcessor(
        BASE_DIR,
        include_legacy=args.include_legacy,
        data_type=args.data_type,
        crawl_run_id=args.crawl_run_id,
    )
    processor.process_all()


if __name__ == "__main__":
    main()
