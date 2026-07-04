"""
서비스 상세조회 제공자.

우선순위:
1. catalog 산출물(services.jsonl 등)이 있으면 DataRepository + DocumentBuilder 사용
2. 없으면 평면 apidata JSON({api_id}_{date}.json)을 파싱하는 fallback

두 경로 모두 같은 상세조회 계약(service_id, name, description,
provider_agency_name, category, endpoints, request_fields,
response_fields, source)을 반환한다.
"""
import json
from pathlib import Path
from typing import Any

from ..core import config
from ..core.service_id import split_service_id
from .data_loader import DataRepository, clean_text
from .document_builder import DocumentBuilder


class DetailUnavailableError(RuntimeError):
    """상세조회 데이터 소스가 준비되지 않았을 때(503) 발생."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def _relative_to_base(path: str | Path) -> str:
    """응답에 로컬 절대 경로를 남기지 않도록 BASE_DIR 기준 상대 경로로 변환."""
    if not path:
        return ""
    try:
        return str(Path(path).resolve().relative_to(config.BASE_DIR))
    except (ValueError, OSError):
        return Path(str(path)).name


def _safe(d: Any, key: str, default: str = "") -> str:
    if not isinstance(d, dict):
        return default
    value = d.get(key, default)
    if value is None or value == "-":
        return default
    return str(value)


def _parse_endpoints(doc: dict[str, Any]) -> list[dict[str, Any]]:
    endpoints: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for ep in doc.get("endpoints") or []:
        if not isinstance(ep, dict):
            continue
        method = _safe(ep, "method").upper()
        path = _safe(ep, "path")
        if not path or (method, path) in seen:
            continue
        seen.add((method, path))
        endpoints.append(
            {
                "endpoint_id": f"{method} {path}".strip(),
                "method": method,
                "path": path,
                "summary": clean_text(_safe(ep, "description")),
                "operation_id": _safe(ep, "operation_id"),
                "tool_spec": None,
            }
        )

    swagger = doc.get("swagger_json") or {}
    for path, spec in (swagger.get("paths") or {}).items():
        if not isinstance(spec, dict):
            continue
        for method, op in spec.items():
            if not isinstance(op, dict):
                continue
            method_u = str(method).upper()
            if (method_u, str(path)) in seen:
                continue
            seen.add((method_u, str(path)))
            endpoints.append(
                {
                    "endpoint_id": f"{method_u} {path}".strip(),
                    "method": method_u,
                    "path": str(path),
                    "summary": clean_text(op.get("summary") or op.get("description") or ""),
                    "operation_id": _safe(op, "operationId"),
                    "tool_spec": None,
                }
            )
    return endpoints


def _parse_request_fields(doc: dict[str, Any]) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    swagger = doc.get("swagger_json") or {}
    for path, spec in (swagger.get("paths") or {}).items():
        if not isinstance(spec, dict):
            continue
        for method, op in spec.items():
            if not isinstance(op, dict):
                continue
            endpoint_id = f"{str(method).upper()} {path}".strip()
            for param in op.get("parameters") or []:
                if not isinstance(param, dict):
                    continue
                name = _safe(param, "name")
                if not name or (endpoint_id, name) in seen:
                    continue
                seen.add((endpoint_id, name))
                fields.append(
                    {
                        "field_id": f"{endpoint_id}:{name}",
                        "endpoint_id": endpoint_id,
                        "name": name,
                        "path": name,
                        "role": "request",
                        "type": _safe(param, "type") or _safe(param, "in"),
                        "required": bool(param.get("required")),
                        "description": clean_text(_safe(param, "description")),
                    }
                )
    return fields


def _parse_response_fields(doc: dict[str, Any]) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    seen: set[str] = set()
    swagger = doc.get("swagger_json") or {}
    for def_name, def_body in (swagger.get("definitions") or {}).items():
        if not isinstance(def_body, dict):
            continue
        for prop_name, prop_spec in (def_body.get("properties") or {}).items():
            if not isinstance(prop_spec, dict):
                continue
            field_path = f"{def_name}.{prop_name}"
            if field_path in seen:
                continue
            seen.add(field_path)
            fields.append(
                {
                    "field_id": field_path,
                    "endpoint_id": "",
                    "name": str(prop_name),
                    "path": field_path,
                    "role": "response",
                    "type": _safe(prop_spec, "type"),
                    "required": False,
                    "description": clean_text(_safe(prop_spec, "description")),
                }
            )
    return fields


def _build_flat_detail(canonical_id: str, doc: dict[str, Any], source_path: Path) -> dict[str, Any]:
    info = doc.get("info") or {}
    swagger_info = (doc.get("swagger_json") or {}).get("info") or {}
    endpoints = _parse_endpoints(doc)
    request_fields = _parse_request_fields(doc)
    response_fields = _parse_response_fields(doc)
    _, api_id = split_service_id(canonical_id)
    keywords = [k.strip() for k in _safe(info, "키워드").split(",") if k.strip()]

    return {
        "service_id": canonical_id,
        "api_type": "openapi_new",
        "data_type": "openapi",
        "name": clean_text(_safe(info, "목록명") or _safe(swagger_info, "title")),
        "description": clean_text(_safe(info, "설명") or _safe(swagger_info, "description")),
        "provider_agency_name": clean_text(_safe(info, "제공기관")),
        "category": clean_text(_safe(info, "분류체계")),
        "keywords": keywords,
        "updated_at": clean_text(_safe(info, "수정일")),
        "endpoints": endpoints,
        "request_fields": request_fields,
        "response_fields": response_fields,
        "source": {
            "source_portal": "data.go.kr",
            "source_object_id": api_id,
            "raw_path": _relative_to_base(source_path),
            "refined_path": "",
            "url": _safe(doc, "crawled_url"),
        },
        "counts": {
            "endpoints": len(endpoints),
            "request_fields": len(request_fields),
            "response_fields": len(response_fields),
        },
        "detail_source": "apidata_flat",
    }


class ServiceDetailProvider:
    def __init__(self) -> None:
        self._repo: DataRepository | None = None
        self._builder: DocumentBuilder | None = None
        self._catalog_checked = False

    def _catalog_builder(self) -> DocumentBuilder | None:
        """catalog 산출물이 존재할 때만 DocumentBuilder를 준비한다."""
        if not self._catalog_checked:
            self._catalog_checked = True
            repo = DataRepository()
            if repo.services:
                self._repo = repo
                self._builder = DocumentBuilder(repo)
        return self._builder

    def reload(self) -> None:
        self._repo = None
        self._builder = None
        self._catalog_checked = False

    def _find_flat_file(self, api_id: str) -> Path | None:
        apidata_dir = config.APIDATA_DIR
        if not apidata_dir.exists():
            return None
        for pattern in (f"{api_id}_*.json", f"{api_id}.json"):
            matches = sorted(apidata_dir.glob(f"**/{pattern}"))
            if matches:
                return matches[-1]  # 같은 api_id가 여러 날짜면 최신 파일
        return None

    def get_detail(self, canonical_id: str) -> dict[str, Any] | None:
        """정규화된 service_id의 상세 문서를 반환한다. 미존재 시 None.

        catalog와 apidata가 모두 준비되지 않았으면 DetailUnavailableError.
        """
        builder = self._catalog_builder()
        if builder is not None:
            payload = builder.build(canonical_id)
            if payload is not None:
                payload.setdefault("detail_source", "catalog")
                source = payload.get("source")
                if isinstance(source, dict):
                    for key in ("raw_path", "refined_path"):
                        if source.get(key):
                            source[key] = _relative_to_base(source[key])
                return payload

        _, api_id = split_service_id(canonical_id)
        flat_file = self._find_flat_file(api_id)
        if flat_file is None:
            if builder is None and not config.APIDATA_DIR.exists():
                raise DetailUnavailableError(
                    "no detail data source: catalog assets and apidata directory are both missing"
                )
            return None
        try:
            doc = json.loads(flat_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return _build_flat_detail(canonical_id, doc, flat_file)
