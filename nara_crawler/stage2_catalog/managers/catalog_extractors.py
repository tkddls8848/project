import re
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from stage2_catalog.managers.raw_source_discovery import RawFileRef


def _first(mapping: Dict[str, Any], keys: Iterable[str], default: Any = "") -> Any:
    for key in keys:
        value = mapping.get(key)
        if value not in (None, ""):
            return value
    return default


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("<br/>", " ").replace("\n", " ").strip()
    return re.sub(r"\s+", " ", text)


def _split_keywords(value: Any) -> list[str]:
    if not value or value == "-":
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [part.strip() for part in re.split(r"[,;/|]", str(value)) if part.strip()]


def normalize_agency_name(name: str) -> str:
    name = re.sub(r"\([^)]*\)", "", name or "")
    name = re.sub(r"\s+", "", name.strip())
    name = re.sub(r"[^0-9A-Za-z가-힣]", "", name)
    return name.lower()


def make_agency_id(code: str, name: str) -> str:
    if code and code != "-":
        return str(code).strip()
    normalized = normalize_agency_name(name)
    return f"agency:{normalized or 'unknown'}"


def make_service_id(data_type: str, source_object_id: str) -> str:
    return f"{data_type}:{source_object_id}"


def refine_raw_record(raw: Dict[str, Any], raw_ref: RawFileRef, raw_rel_path: str) -> Dict[str, Any]:
    info = raw.get("info") or {}
    source_object_id = str(raw.get("api_id") or raw_ref.source_object_id)
    title = _clean_text(_first(info, ["목록명", "title"], source_object_id))
    agency_name = _clean_text(_first(info, ["제공기관", "provider"], ""))
    agency_code = _clean_text(_first(info, ["제공기관코드", "provider_number"], ""))
    description = _clean_text(_first(info, ["설명", "description"], ""))
    keywords = _split_keywords(_first(info, ["키워드", "keywords"], []))
    update_date = _clean_text(_first(info, ["수정일", "update_date", "updated_at"], ""))
    category = _clean_text(_first(info, ["분류체계", "category"], ""))

    endpoints = raw.get("endpoints") or []
    if not endpoints and isinstance(raw.get("swagger_json"), dict):
        endpoints = _endpoints_from_swagger(raw["swagger_json"])

    content: Dict[str, Any] = {
        "data_type": raw_ref.data_type,
        "endpoints": endpoints,
    }
    if raw_ref.data_type == "fileData":
        content["download_urls"] = raw.get("data") or raw.get("download_urls") or {}
    if raw_ref.data_type == "standard":
        content["standard_grid_table"] = raw.get("standard_grid_table") or []

    return {
        "api_id": source_object_id,
        "api_type": raw.get("api_type") or raw_ref.api_type,
        "data_type": raw_ref.data_type,
        "crawled_url": raw.get("crawled_url") or _first(info, ["목록 URL"], ""),
        "crawled_time": raw.get("crawled_time") or raw.get("crawled_at") or "",
        "metadata": {
            "title": title,
            "provider": agency_name,
            "provider_number": agency_code,
            "category": category,
            "description": description,
            "keywords": keywords,
            "registration_date": _clean_text(_first(info, ["등록일"], "")),
            "update_date": update_date,
            "format": _clean_text(_first(info, ["확장자(데이터포맷)", "데이터포맷"], "")),
        },
        "content": content,
        "swagger_json": raw.get("swagger_json"),
        "raw_path": raw_rel_path,
    }


def _endpoints_from_swagger(swagger: Dict[str, Any]) -> list[Dict[str, Any]]:
    endpoints = []
    for path, path_spec in (swagger.get("paths") or {}).items():
        if not isinstance(path_spec, dict):
            continue
        for method, method_spec in path_spec.items():
            if method.lower() not in {"get", "post", "put", "delete", "patch"}:
                continue
            method_spec = method_spec if isinstance(method_spec, dict) else {}
            endpoints.append(
                {
                    "path": path,
                    "method": method.upper(),
                    "description": method_spec.get("summary") or method_spec.get("description") or "",
                    "parameters": method_spec.get("parameters") or path_spec.get("parameters") or [],
                    "operation_id": method_spec.get("operationId"),
                }
            )
    return endpoints


def extract_agency_record(refined: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    meta = refined.get("metadata", {})
    agency_name = _clean_text(meta.get("provider", ""))
    agency_code = _clean_text(meta.get("provider_number", ""))
    if not agency_name and not agency_code:
        return None
    agency_id = make_agency_id(agency_code, agency_name)
    return {
        "agency_id": agency_id,
        "agency_name": agency_name or agency_id,
        "agency_code": agency_code,
        "source_portal": "data.go.kr",
    }


def extract_service_record(refined: Dict[str, Any], raw_ref: RawFileRef, refined_path: Path) -> Dict[str, Any]:
    meta = refined.get("metadata", {})
    source_object_id = refined["api_id"]
    agency = extract_agency_record(refined) or {}
    return {
        "service_id": make_service_id(raw_ref.data_type, source_object_id),
        "source_portal": "data.go.kr",
        "data_type": raw_ref.data_type,
        "api_type": refined.get("api_type", raw_ref.api_type),
        "source_object_id": source_object_id,
        "name": meta.get("title", ""),
        "description": meta.get("description", ""),
        "provider_agency_id": agency.get("agency_id", "agency:unknown"),
        "provider_agency_name": meta.get("provider", ""),
        "category": meta.get("category", ""),
        "keywords": meta.get("keywords", []),
        "updated_at": meta.get("update_date", ""),
        "raw_path": refined.get("raw_path", ""),
        "refined_path": refined_path.as_posix(),
        "latest_crawl_run_id": raw_ref.crawl_run_id,
    }


def extract_document_record(refined: Dict[str, Any], raw_ref: RawFileRef, refined_path: Path) -> Dict[str, Any]:
    meta = refined.get("metadata", {})
    source_object_id = refined["api_id"]
    service_id = make_service_id(raw_ref.data_type, source_object_id)
    body_parts = [
        meta.get("title", ""),
        meta.get("description", ""),
        " ".join(meta.get("keywords", [])),
        meta.get("provider", ""),
        raw_ref.data_type,
    ]
    return {
        "document_id": f"doc:{service_id}:overview",
        "service_id": service_id,
        "source_portal": "data.go.kr",
        "data_type": raw_ref.data_type,
        "source_object_id": source_object_id,
        "document_type": "overview",
        "title": meta.get("title", ""),
        "body": _clean_text(" ".join(part for part in body_parts if part)),
        "language": "ko",
        "source_path": refined.get("raw_path", ""),
        "refined_path": refined_path.as_posix(),
        "updated_at": meta.get("update_date", ""),
        "latest_crawl_run_id": raw_ref.crawl_run_id,
    }


def extract_endpoint_records(refined: Dict[str, Any], raw_ref: RawFileRef) -> list[Dict[str, Any]]:
    if raw_ref.api_type == "openapi_link":
        return []
    service_id = make_service_id(raw_ref.data_type, refined["api_id"])
    records = []
    for index, endpoint in enumerate(refined.get("content", {}).get("endpoints", []) or []):
        path = endpoint.get("path") or endpoint.get("url") or f"/endpoint-{index}"
        method = str(endpoint.get("method") or "GET").upper()
        endpoint_id = f"endpoint:{service_id}:{method.lower()}:{path}"
        records.append(
            {
                "endpoint_id": endpoint_id,
                "service_id": service_id,
                "method": method,
                "path": path,
                "operation_id": endpoint.get("operation_id") or endpoint.get("operationId") or f"op_{index}",
                "summary": endpoint.get("description") or endpoint.get("summary") or "",
                "source_path": refined.get("raw_path", ""),
            }
        )
    return records


def extract_field_records(refined: Dict[str, Any], raw_ref: RawFileRef) -> list[Dict[str, Any]]:
    if raw_ref.api_type == "openapi_link":
        return []
    service_id = make_service_id(raw_ref.data_type, refined["api_id"])
    endpoint_records = extract_endpoint_records(refined, raw_ref)
    endpoint_by_path = {(e["method"], e["path"]): e["endpoint_id"] for e in endpoint_records}
    records = []
    for endpoint in refined.get("content", {}).get("endpoints", []) or []:
        path = endpoint.get("path") or endpoint.get("url") or ""
        method = str(endpoint.get("method") or "GET").upper()
        endpoint_id = endpoint_by_path.get((method, path), f"endpoint:{service_id}:{method.lower()}:{path}")
        for param in endpoint.get("parameters", []) or []:
            name = param.get("name") or param.get("field_name")
            if not name:
                continue
            role = param.get("in") or param.get("field_role") or "request"
            records.append(
                {
                    "field_id": f"field:{service_id}:{endpoint_id}:{role}:{name}",
                    "service_id": service_id,
                    "endpoint_id": endpoint_id,
                    "field_name": name,
                    "field_role": role,
                    "field_type": param.get("type") or param.get("param_type") or "string",
                    "required": bool(param.get("required", False)),
                    "description": param.get("description", ""),
                }
            )
    return records
