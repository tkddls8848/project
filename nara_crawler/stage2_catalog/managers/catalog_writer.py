import json
import os
from pathlib import Path
from typing import Dict, Iterable, List


class CatalogWriter:
    def __init__(self, base_dir: str | Path):
        self.base_dir = Path(base_dir)
        self.catalog_dir = self.base_dir / "data" / "02_catalog"
        self.catalog_dir.mkdir(parents=True, exist_ok=True)

    def append_jsonl(self, filename: str, records: Iterable[dict]) -> None:
        path = self.catalog_dir / filename
        with path.open("a", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def upsert_jsonl(self, filename: str, records: Iterable[dict], key_fields: List[str]) -> None:
        path = self.catalog_dir / filename
        merged: Dict[tuple, dict] = {}
        if path.exists():
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    record = json.loads(line)
                    merged[tuple(record.get(k) for k in key_fields)] = record

        for record in records:
            merged[tuple(record.get(k) for k in key_fields)] = record

        self._atomic_write_jsonl(path, merged.values())

    def rebuild_crawl_latest(self) -> None:
        history_path = self.catalog_dir / "crawl_history.jsonl"
        latest_path = self.catalog_dir / "crawl_latest.jsonl"
        latest: Dict[tuple, dict] = {}
        if history_path.exists():
            with history_path.open("r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    record = json.loads(line)
                    key = (
                        record.get("source_portal"),
                        record.get("data_type"),
                        record.get("source_object_id"),
                    )
                    previous = latest.get(key)
                    if previous is None or (
                        record.get("processed_at", ""),
                        record.get("collected_at", ""),
                    ) >= (
                        previous.get("processed_at", ""),
                        previous.get("collected_at", ""),
                    ):
                        latest[key] = {
                            "source_portal": record.get("source_portal"),
                            "data_type": record.get("data_type"),
                            "source_object_id": record.get("source_object_id"),
                            "latest_crawl_run_id": record.get("crawl_run_id"),
                            "latest_raw_path": record.get("raw_path"),
                            "latest_checksum": record.get("checksum"),
                            "latest_collected_at": record.get("collected_at"),
                            "latest_processed_at": record.get("processed_at"),
                            "latest_change_status": record.get("change_status"),
                            "latest_transform_status": record.get("transform_status"),
                        }
        self._atomic_write_jsonl(latest_path, latest.values())

    def load_latest_index(self) -> Dict[tuple, dict]:
        path = self.catalog_dir / "crawl_latest.jsonl"
        latest = {}
        if not path.exists():
            return latest
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                record = json.loads(line)
                latest[
                    (
                        record.get("source_portal"),
                        record.get("data_type"),
                        record.get("source_object_id"),
                    )
                ] = record
        return latest

    def write_catalog_records(
        self,
        agencies: Iterable[dict],
        services: Iterable[dict],
        documents: Iterable[dict],
        endpoints: Iterable[dict],
        fields: Iterable[dict],
        history: Iterable[dict],
    ) -> None:
        self.append_jsonl("crawl_history.jsonl", history)
        self.upsert_jsonl("agencies.jsonl", agencies, ["agency_id"])
        self.upsert_jsonl("services.jsonl", services, ["service_id"])
        self.upsert_jsonl("documents.jsonl", documents, ["document_id"])
        self.upsert_jsonl("endpoints.jsonl", endpoints, ["endpoint_id"])
        self.upsert_jsonl("fields.jsonl", fields, ["field_id"])
        self.rebuild_crawl_latest()

    def _atomic_write_jsonl(self, path: Path, records: Iterable[dict]) -> None:
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            for record in sorted(records, key=lambda r: json.dumps(r, ensure_ascii=False, sort_keys=True)):
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        os.replace(tmp_path, path)
