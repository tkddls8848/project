"""api_storage에 이미 쌓인 결과를 읽기 전용으로 요약한다."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from crawl_types import DOCUMENT_STORAGE_DIRS
from managers.crawl_run_manager import CrawlRunManager

from .run_service import BASE_DIR

# 크롤러가 문서를 떨어뜨리는 폴더들. 심화 산출물(reports, files)은 문서가 아니라 제외한다.
DOCUMENT_DIRS = DOCUMENT_STORAGE_DIRS


def _storage_dir() -> Path:
    return CrawlRunManager(BASE_DIR).storage_dir


def storage_overview() -> dict[str, Any]:
    storage = _storage_dir()
    counts = {}
    for name in DOCUMENT_DIRS:
        directory = storage / name
        counts[name] = len(list(directory.glob("*.json"))) if directory.is_dir() else 0
    return {
        "storage_dir": str(storage),
        "exists": storage.is_dir(),
        "documents": counts,
        "total_documents": sum(counts.values()),
    }


def recent_manifests(limit: int = 10) -> list[dict[str, Any]]:
    """매니페스트에서 지난 크롤 기록을 최신순으로 읽는다."""
    manifests_dir = _storage_dir() / "manifests"
    if not manifests_dir.is_dir():
        return []

    # `{run_id}_{type}_summary.json`은 실행 단위가 아니라 타입별 상세라 제외한다.
    paths = [
        path
        for path in manifests_dir.glob("*.json")
        if not path.stem.endswith("_summary")
    ]
    paths.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    records: list[dict[str, Any]] = []
    for path in paths[:limit]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        runs = payload.get("runs") or []
        records.append(
            {
                "crawl_run_id": payload.get("crawl_run_id", path.stem),
                "started_at": payload.get("started_at"),
                "ended_at": payload.get("ended_at"),
                "types": [run.get("data_type") for run in runs if isinstance(run, dict)],
                "total_success": sum(
                    int(run.get("total_success") or 0) for run in runs if isinstance(run, dict)
                ),
                "total_failed": sum(
                    int(run.get("total_failed") or 0) for run in runs if isinstance(run, dict)
                ),
                "modified_at": datetime.fromtimestamp(
                    path.stat().st_mtime, timezone.utc
                ).isoformat(),
            }
        )
    return records


__all__ = ["DOCUMENT_DIRS", "recent_manifests", "storage_overview"]
