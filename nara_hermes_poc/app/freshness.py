"""Read-only crawler-manifest freshness checks for selected API documents."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .schemas import DocumentFreshness


@dataclass(frozen=True)
class _ManifestEntry:
    crawled_at: datetime
    crawled_at_text: str
    checksum: str | None


def _parse_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None


def _document_path(service_id: str) -> str | None:
    source, separator, api_id = service_id.partition(":")
    return f"{source}/{api_id}.json" if separator and source and api_id else None


def _manifest_entries(storage_dir: Path, paths: set[str]) -> dict[str, list[_ManifestEntry]]:
    found = {path: [] for path in paths}
    manifests_dir = storage_dir / "manifests"
    if not manifests_dir.is_dir():
        return found
    for manifest_path in manifests_dir.glob("*.json"):
        if manifest_path.name.endswith("_summary.json"):
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        crawled_at_text = str(manifest.get("started_at") or "")
        crawled_at = _parse_time(crawled_at_text)
        if crawled_at is None:
            continue
        for run in manifest.get("runs") or []:
            if not isinstance(run, dict):
                continue
            for file_info in run.get("files") or []:
                if not isinstance(file_info, dict):
                    continue
                path = str(file_info.get("path") or "").replace("\\", "/")
                if path in found:
                    found[path].append(_ManifestEntry(
                        crawled_at=crawled_at,
                        crawled_at_text=crawled_at_text,
                        checksum=str(file_info["checksum"]) if file_info.get("checksum") else None,
                    ))
    for entries in found.values():
        entries.sort(key=lambda entry: entry.crawled_at)
    return found


def check_document_freshness(
    service_ids: list[str], storage_dir: Path, index_built_at: str,
) -> list[DocumentFreshness]:
    """Report only evidence-backed freshness states; never refreshes data."""
    unique_ids = list(dict.fromkeys(service_ids))
    index_time = _parse_time(index_built_at)
    paths = {path for service_id in unique_ids if (path := _document_path(service_id))}
    entries_by_path = _manifest_entries(storage_dir, paths) if index_time else {}
    reports: list[DocumentFreshness] = []
    for service_id in unique_ids:
        document_path = _document_path(service_id)
        if document_path is None:
            reports.append(DocumentFreshness(service_id=service_id, status="unverified", message="service_id 형식이 source:api_id가 아니어서 매니페스트를 확인할 수 없습니다."))
            continue
        if index_time is None:
            reports.append(DocumentFreshness(service_id=service_id, status="unverified", message="검색 인덱스 빌드 시각이 설정되지 않아 문서 최신성을 확인할 수 없습니다."))
            continue
        entries = entries_by_path.get(document_path, [])
        if not entries:
            reports.append(DocumentFreshness(service_id=service_id, status="unverified", index_built_at=index_built_at, message="선택 문서의 크롤러 매니페스트 항목을 찾지 못했습니다."))
            continue
        baseline = [entry for entry in entries if entry.crawled_at <= index_time]
        latest = entries[-1]
        if not baseline:
            reports.append(DocumentFreshness(service_id=service_id, status="unverified", index_built_at=index_built_at, latest_crawl_at=latest.crawled_at_text, checksum=latest.checksum, message="인덱스 빌드 이전의 매니페스트가 없어 이후 변경 여부를 판단할 수 없습니다."))
            continue
        indexed = baseline[-1]
        changed_after_index = latest.crawled_at > index_time and latest.checksum != indexed.checksum
        reports.append(DocumentFreshness(
            service_id=service_id,
            status="stale" if changed_after_index else "fresh",
            index_built_at=index_built_at,
            latest_crawl_at=latest.crawled_at_text,
            checksum=latest.checksum,
            message=("인덱스 빌드 뒤 크롤러 매니페스트의 문서 체크섬이 변경되었습니다. 상세 조회 근거로만 판단하세요." if changed_after_index else "알려진 매니페스트에서 인덱스 빌드 이후 문서 체크섬 변경이 확인되지 않았습니다."),
        ))
    return reports


__all__ = ["check_document_freshness"]