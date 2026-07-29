"""대시보드용 경량 카탈로그 목록 (GET /catalog).

apidata 평면 JSON을 스캔해 문서별 요약(fields/endpoints 포함)을 만들고 메모리에 캐시한다.
인덱스 빌드 완료 시 main._on_complete가 reload()로 캐시를 비운다.
"""
import json
from pathlib import Path
from typing import Any

from ..core import config
from ..core.service_id import to_canonical
from .detail_service import _build_flat_detail


def latest_apidata_files() -> dict[str, Path]:
    """api_id → 최신 파일. 파일명 {api_id}_{date}.json이 정렬로 최신이 뒤에 온다."""
    latest: dict[str, Path] = {}
    if not config.APIDATA_DIR.exists():
        return latest
    for path in sorted(config.APIDATA_DIR.glob("*.json")):
        latest[path.stem.split("_")[0]] = path
    return latest


class CatalogListing:
    def __init__(self) -> None:
        self._cache: list[dict[str, Any]] | None = None

    def reload(self) -> None:
        self._cache = None

    def list_docs(self) -> list[dict[str, Any]]:
        if self._cache is None:
            self._cache = self._scan()
        return self._cache

    def _scan(self) -> list[dict[str, Any]]:
        docs: list[dict[str, Any]] = []
        for api_id, path in sorted(latest_apidata_files().items()):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                detail = _build_flat_detail(to_canonical(api_id), raw, path)
            except (OSError, json.JSONDecodeError, AttributeError, TypeError):
                continue
            docs.append({
                "service_id": detail["service_id"],
                "api_id": api_id,
                "name": detail["name"],
                "provider": detail["provider_agency_name"],
                "category": detail["category"],
                "keywords": detail["keywords"],
                "description": detail["description"],
                "fields": [
                    {"key": f["name"], "desc": f["description"] or f["name"]}
                    for f in detail["response_fields"]
                ],
                "endpoints": [
                    {"method": e["method"], "path": e["path"], "description": e["summary"]}
                    for e in detail["endpoints"]
                ],
            })
        return docs
