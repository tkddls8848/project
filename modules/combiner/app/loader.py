"""services.jsonl 또는 apidata/*.json 에서 공공 API 메타데이터를 로드·캐시."""
import json
import logging
from pathlib import Path

from .config import NARA_DATA_DIR
from .schemas import Service

logger = logging.getLogger(__name__)

_CACHE: dict[str, dict] = {}
_LOAD_FAILURES: list[tuple[str, str]] = []


def _parse_file(raw: dict) -> dict | None:
    info = raw.get("info", {})
    swagger_info = raw.get("swagger_json", {}).get("info", {})

    name = (info.get("목록명") or swagger_info.get("title") or "").strip()
    if not name:
        return None

    keywords_raw = info.get("키워드") or ""
    keywords = [k.strip() for k in keywords_raw.split(",") if k.strip()]

    return {
        "api_id":      raw.get("api_id", ""),
        "name":        name,
        "agency":      (info.get("제공기관") or "").strip(),
        "domain":      (info.get("분류체계") or "").strip(),
        "keywords":    keywords,
        "description": (info.get("설명") or swagger_info.get("description", "")).strip()[:500],
        "endpoints":   raw.get("endpoints", [])[:5],
    }


def load_all(data_dir: Path | None = None) -> dict[str, dict]:
    """전체 API 문서를 로드해 api_id → dict 캐시로 반환."""
    global _CACHE, _LOAD_FAILURES
    if _CACHE:
        return _CACHE

    target = data_dir or NARA_DATA_DIR
    _LOAD_FAILURES = []
    if not target.exists():
        logger.warning("데이터 디렉터리 없음: %s", target)
        return {}

    loaded = 0
    for f in target.glob("*.json"):
        try:
            raw = json.loads(f.read_text(encoding="utf-8"))
            parsed = _parse_file(raw)
            if parsed and parsed["api_id"]:
                _CACHE[parsed["api_id"]] = parsed
                loaded += 1
        except Exception as exc:
            _LOAD_FAILURES.append(
                (f.name, f"{type(exc).__name__}: {exc}")
            )

    if _LOAD_FAILURES:
        summary = "; ".join(
            f"{filename}: {reason}" for filename, reason in _LOAD_FAILURES
        )
        logger.warning(
            "문서 로드 실패 %d건 (%s): %s",
            len(_LOAD_FAILURES),
            target,
            summary,
        )

    logger.info("로드 완료: %d건 (%s)", loaded, target)
    return _CACHE


def load_failure_count() -> int:
    """최근 캐시 로드에서 예외로 건너뛴 파일 수."""
    return len(_LOAD_FAILURES)


# Search가 노출하는 정식 service_id prefix. 경계에서 내부 api_id로 변환만 하고
# 그 외 재해석은 하지 않는다 (누락 보고는 호출자가 보낸 원본 문자열 기준).
CANONICAL_PREFIX = "openapi_new:"


def _internal_id(raw: str) -> str:
    if raw.startswith(CANONICAL_PREFIX):
        return raw[len(CANONICAL_PREFIX):]
    return raw


def get_services(ids: list[str]) -> tuple[list[Service], list[str]]:
    """id 목록으로 Service 객체 반환. 누락 ID는 두 번째 원소로.

    순수 api_id("15000827")와 정식 service_id("openapi_new:15000827")를
    모두 허용한다.
    """
    catalog = load_all()
    found: list[Service] = []
    missing: list[str] = []

    for id_ in ids:
        key = _internal_id(id_.strip())
        if key in catalog:
            found.append(Service(**catalog[key]))
        else:
            logger.warning("ID 없음: %s", id_)
            missing.append(id_)

    return found, missing


def reset_cache() -> None:
    """테스트용 캐시 초기화."""
    global _CACHE, _LOAD_FAILURES
    _CACHE = {}
    _LOAD_FAILURES = []
