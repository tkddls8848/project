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


def _safe_field_key(value: Any) -> str:
    text = _clean_text(value)
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^0-9A-Za-z가-힣_.\[\]:-]+", "_", text)
    return text.strip("._:-") or "unknown"


def _required(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    return text in {"true", "1", "y", "yes", "required", "필수"}


def _field_type_from_schema(schema: Any, default: str = "string") -> str:
    if not isinstance(schema, dict):
        return default
    if schema.get("type"):
        return str(schema["type"])
    if schema.get("$ref"):
        return "object"
    return default


def _resolve_ref(swagger: Dict[str, Any], ref: str) -> Dict[str, Any]:
    if not ref.startswith("#/"):
        return {}
    current: Any = swagger
    for part in ref[2:].split("/"):
        if not isinstance(current, dict):
            return {}
        current = current.get(part)
    return current if isinstance(current, dict) else {}


def _iter_schema_properties(
    swagger: Dict[str, Any],
    schema: Dict[str, Any],
    parent_path: str = "",
    visited_refs: Optional[set[str]] = None,
):
    visited_refs = visited_refs or set()
    if not isinstance(schema, dict):
        return

    ref = schema.get("$ref")
    if ref:
        if ref in visited_refs:
            return
        visited_refs.add(ref)
        resolved = _resolve_ref(swagger, ref)
        yield from _iter_schema_properties(swagger, resolved, parent_path, visited_refs)
        return

    if schema.get("type") == "array" and isinstance(schema.get("items"), dict):
        yield from _iter_schema_properties(swagger, schema["items"], parent_path, visited_refs)
        return

    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return

    required_names = set(schema.get("required") or [])
    for name, child_schema in properties.items():
        if not isinstance(child_schema, dict):
            child_schema = {}
        field_path = f"{parent_path}.{name}" if parent_path else str(name)
        yield {
            "name": str(name),
            "field_path": field_path,
            "field_type": _field_type_from_schema(child_schema),
            "description": child_schema.get("description", ""),
            "required": name in required_names,
        }
        yield from _iter_schema_properties(swagger, child_schema, field_path, visited_refs.copy())


def _iter_operation_param_fields(params: list[dict], parent_path: str = ""):
    for param in params or []:
        if not isinstance(param, dict):
            continue
        name = param.get("paramtrNm") or param.get("name") or param.get("field_name")
        if not name:
            continue
        field_path = f"{parent_path}.{name}" if parent_path else str(name)
        yield {
            "name": str(name),
            "field_path": field_path,
            "field_type": param.get("paramtrTy") or param.get("type") or "string",
            "description": param.get("paramtrDc") or param.get("description") or "",
            "required": _required(param.get("paramtrDivision") or param.get("required")),
        }
        yield from _iter_operation_param_fields(param.get("subParam") or [], field_path)


def _make_field_record(
    service_id: str,
    endpoint_id: str,
    field_name: str,
    field_role: str,
    field_type: str,
    required: bool,
    description: str,
    source_path: str,
    field_path: str | None = None,
    field_location: str | None = None,
    source_detail: str | None = None,
) -> Dict[str, Any]:
    field_path = field_path or field_name
    record = {
        "field_id": f"field:{endpoint_id}:{field_role}:{_safe_field_key(field_path)}",
        "service_id": service_id,
        "endpoint_id": endpoint_id,
        "field_name": _clean_text(field_name),
        "field_role": field_role,
        "field_type": _clean_text(field_type) or "string",
        "required": bool(required),
        "description": _clean_text(description),
        "source_path": source_path,
    }
    if field_path and field_path != field_name:
        record["field_path"] = _clean_text(field_path)
    if field_location:
        record["field_location"] = _clean_text(field_location)
    if source_detail:
        record["source_detail"] = source_detail
    return record


def _upsert_field(records: list[Dict[str, Any]], seen: dict[str, Dict[str, Any]], record: Dict[str, Any]) -> None:
    key = record["field_id"]
    existing = seen.get(key)
    if not existing:
        seen[key] = record
        records.append(record)
        return
    for field in ("description", "field_type", "field_location", "field_path", "source_detail", "source_path"):
        if not existing.get(field) and record.get(field):
            existing[field] = record[field]
    existing["required"] = bool(existing.get("required") or record.get("required"))


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
    endpoint_by_operation = {e.get("operation_id"): e["endpoint_id"] for e in endpoint_records if e.get("operation_id")}
    endpoint_by_path_only = {e["path"]: e["endpoint_id"] for e in endpoint_records}
    default_endpoint_id = endpoint_records[0]["endpoint_id"] if endpoint_records else f"endpoint:{service_id}:get:/"
    source_path = refined.get("raw_path", "")
    records = []
    seen: dict[str, Dict[str, Any]] = {}

    for endpoint in refined.get("content", {}).get("endpoints", []) or []:
        path = endpoint.get("path") or endpoint.get("url") or ""
        method = str(endpoint.get("method") or "GET").upper()
        endpoint_id = endpoint_by_path.get((method, path), f"endpoint:{service_id}:{method.lower()}:{path}")
        for param in endpoint.get("parameters", []) or []:
            name = param.get("name") or param.get("field_name")
            if not name:
                continue
            _upsert_field(
                records,
                seen,
                _make_field_record(
                    service_id=service_id,
                    endpoint_id=endpoint_id,
                    field_name=name,
                    field_role="request",
                    field_type=param.get("type") or param.get("param_type") or "string",
                    required=_required(param.get("required")),
                    description=param.get("description", ""),
                    source_path=source_path,
                    field_location=param.get("in") or param.get("field_location") or "query",
                    source_detail="content.endpoints.parameters",
                ),
            )

    swagger = refined.get("swagger_json") if isinstance(refined.get("swagger_json"), dict) else {}
    for path, path_spec in (swagger.get("paths") or {}).items():
        if not isinstance(path_spec, dict):
            continue
        path_parameters = path_spec.get("parameters") or []
        for method, method_spec in path_spec.items():
            if method.lower() not in {"get", "post", "put", "delete", "patch"}:
                continue
            method_spec = method_spec if isinstance(method_spec, dict) else {}
            endpoint_id = endpoint_by_path.get((method.upper(), path), endpoint_by_path_only.get(path, default_endpoint_id))
            parameters = list(path_parameters) + list(method_spec.get("parameters") or [])
            for param in parameters:
                if not isinstance(param, dict):
                    continue
                name = param.get("name")
                if not name:
                    continue
                schema = param.get("schema") if isinstance(param.get("schema"), dict) else {}
                _upsert_field(
                    records,
                    seen,
                    _make_field_record(
                        service_id=service_id,
                        endpoint_id=endpoint_id,
                        field_name=name,
                        field_role="request",
                        field_type=param.get("type") or _field_type_from_schema(schema),
                        required=_required(param.get("required")),
                        description=param.get("description", ""),
                        source_path=source_path,
                        field_location=param.get("in") or "query",
                        source_detail=f"swagger.paths.{path}.{method}.parameters",
                    ),
                )

            for response_code, response in (method_spec.get("responses") or {}).items():
                if not isinstance(response, dict):
                    continue
                schema = response.get("schema")
                if not isinstance(schema, dict):
                    continue
                for field in _iter_schema_properties(swagger, schema):
                    _upsert_field(
                        records,
                        seen,
                        _make_field_record(
                            service_id=service_id,
                            endpoint_id=endpoint_id,
                            field_name=field["name"],
                            field_role="response",
                            field_type=field["field_type"],
                            required=field["required"],
                            description=field["description"],
                            source_path=source_path,
                            field_path=field["field_path"],
                            source_detail=f"swagger.paths.{path}.{method}.responses.{response_code}.schema",
                        ),
                    )

    for operation in swagger.get("swaggerOprtinVOs") or []:
        if not isinstance(operation, dict):
            continue
        endpoint_id = (
            endpoint_by_operation.get(operation.get("operationId"))
            or endpoint_by_operation.get(operation.get("gwSvcNm"))
            or default_endpoint_id
        )
        for field in _iter_operation_param_fields(operation.get("reqList") or []):
            _upsert_field(
                records,
                seen,
                _make_field_record(
                    service_id=service_id,
                    endpoint_id=endpoint_id,
                    field_name=field["name"],
                    field_role="request",
                    field_type=field["field_type"],
                    required=field["required"],
                    description=field["description"],
                    source_path=source_path,
                    field_path=field["field_path"],
                    field_location="query",
                    source_detail="swagger.swaggerOprtinVOs.reqList",
                ),
            )
        for field in _iter_operation_param_fields(operation.get("resList") or []):
            _upsert_field(
                records,
                seen,
                _make_field_record(
                    service_id=service_id,
                    endpoint_id=endpoint_id,
                    field_name=field["name"],
                    field_role="response",
                    field_type=field["field_type"],
                    required=field["required"],
                    description=field["description"],
                    source_path=source_path,
                    field_path=field["field_path"],
                    source_detail="swagger.swaggerOprtinVOs.resList",
                ),
            )

    return records
