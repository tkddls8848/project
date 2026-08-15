"""목록 CSV 상태와 문서번호 범위를 조회한다.

범위 조회는 CSV 전체를 파싱한다. metadata_file.csv는 100MB를 넘으므로
페이지를 열 때마다 훑지 않고, 요청이 있을 때만 계산해 캐시한다.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# main.py가 CSV 위치와 타입별 접두어의 유일한 출처다. 여기서 다시 정의하지 않는다.
from main import CSV_DIR, CSV_PREFIX_MAP, find_latest_metadata_csv, get_csv_range

# 범위를 물어볼 수 있는 타입. openapi 하위 타입은 같은 CSV를 공유하므로 제외한다.
RANGE_TYPES = ("openapi", "fileData", "standard")

# (경로, mtime_ns, size) -> (min, max). CSV가 바뀌면 키가 달라져 자동으로 무효화된다.
_RANGE_CACHE: dict[tuple[str, int, int], tuple[int | None, int | None]] = {}


def _csv_path(data_type: str) -> Path | None:
    prefix = CSV_PREFIX_MAP.get(data_type)
    if not prefix:
        return None
    found = find_latest_metadata_csv(CSV_DIR, prefix)
    return Path(found) if found else None


def csv_status(data_type: str) -> dict[str, Any]:
    """범위 파싱 없이 알 수 있는 것만 즉시 돌려준다."""
    path = _csv_path(data_type)
    if path is None or not path.is_file():
        return {
            "type": data_type,
            "csv": CSV_PREFIX_MAP.get(data_type, ""),
            "exists": False,
            "size_bytes": 0,
            "modified_at": None,
        }
    stat = path.stat()
    return {
        "type": data_type,
        "csv": path.name,
        "exists": True,
        "size_bytes": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
    }


def overview() -> dict[str, Any]:
    return {
        "csv_dir": str(CSV_DIR),
        "types": [csv_status(data_type) for data_type in RANGE_TYPES],
    }


def _range_blocking(data_type: str) -> dict[str, Any]:
    path = _csv_path(data_type)
    if path is None or not path.is_file():
        return {"type": data_type, "available": False, "reason": "목록 CSV가 없습니다."}

    stat = path.stat()
    key = (str(path), stat.st_mtime_ns, stat.st_size)
    if key not in _RANGE_CACHE:
        _RANGE_CACHE[key] = get_csv_range(str(path))
    minimum, maximum = _RANGE_CACHE[key]
    if minimum is None or maximum is None:
        return {"type": data_type, "available": False, "reason": "CSV에서 문서번호를 읽지 못했습니다."}
    return {"type": data_type, "available": True, "min": minimum, "max": maximum}


async def document_range(data_type: str) -> dict[str, Any]:
    """CSV 파싱은 CPU/IO를 오래 잡으므로 이벤트 루프 밖에서 돌린다."""
    if data_type not in RANGE_TYPES:
        return {"type": data_type, "available": False, "reason": "범위를 조회할 수 없는 타입입니다."}
    return await asyncio.to_thread(_range_blocking, data_type)


__all__ = ["RANGE_TYPES", "csv_status", "document_range", "overview"]
