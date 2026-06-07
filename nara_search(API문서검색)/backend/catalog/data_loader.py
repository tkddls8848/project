import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from ..core import config


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = re.sub(r"<[^>]+>", " ", str(value))
    text = text.replace("\n", " ").replace("\r", " ")
    return re.sub(r"\s+", " ", text).strip()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records


def _make_minimal_service(doc: dict[str, Any]) -> dict[str, Any]:
    service_id = f"openapi_new:{doc['id']}"
    return {
        "service_id": service_id,
        "source_portal": "data.go.kr",
        "data_type": "openapi",
        "api_type": "openapi_new",
        "source_object_id": doc["id"],
        "name": doc.get("title", ""),
        "description": doc.get("description", ""),
        "provider_agency_id": f"agency:{doc.get('provider', 'unknown')}",
        "provider_agency_name": doc.get("provider", ""),
        "category": doc.get("category", ""),
        "keywords": [k.strip() for k in doc.get("keywords", "").split(",") if k.strip()],
        "updated_at": "",
        "raw_path": "",
        "refined_path": "",
    }


class DataRepository:
    def __init__(self) -> None:
        self.reload()

    def reload(self) -> None:
        self.services = read_jsonl(config.CATALOG_DIR / "services.jsonl")
        self.documents = read_jsonl(config.CATALOG_DIR / "documents.jsonl")
        self.endpoints = read_jsonl(config.CATALOG_DIR / "endpoints.jsonl")
        self.fields = read_jsonl(config.CATALOG_DIR / "fields.jsonl")
        self.service_tags = read_jsonl(config.SEMANTIC_DIR / "service_tags.jsonl")
        self.field_mappings = read_jsonl(config.SEMANTIC_DIR / "field_mappings.jsonl")
        self.concepts = read_jsonl(config.SEMANTIC_DIR / "concepts.jsonl")
        self.chunks = read_jsonl(config.SERVING_DIR / "retrieval_chunks.jsonl")
        self.tool_specs = read_jsonl(config.SERVING_DIR / "api_tool_specs.jsonl")
        self.recommender = read_jsonl(config.SERVING_DIR / "recommender_catalog.jsonl")

        # minimal/documents.jsonl 을 항상 병합 (Stage2 데이터와 ID 충돌 없음)
        # Stage2 service_id: "openapi:{id}", minimal service_id: "openapi_new:{id}"
        self._minimal_service_ids: set[str] = set()
        if config.MINIMAL_DOCS_PATH.exists():
            minimal_docs = read_jsonl(config.MINIMAL_DOCS_PATH)
            existing_ids = {s.get("service_id") for s in self.services}
            for d in minimal_docs:
                svc = _make_minimal_service(d)
                sid = svc["service_id"]
                if sid in existing_ids:
                    continue
                self.services.append(svc)
                self.documents.append({
                    "document_id": f"doc:{sid}:overview",
                    "service_id": sid,
                    "title": d.get("title", ""),
                    "body": d.get("text", ""),
                })
                self._minimal_service_ids.add(sid)

        self.services_by_id = {record.get("service_id"): record for record in self.services}
        self.documents_by_service = {record.get("service_id"): record for record in self.documents}
        self.tags_by_service = {record.get("service_id"): record for record in self.service_tags}
        self.concepts_by_id = {record.get("concept_id"): record for record in self.concepts}
        self.chunks_by_id = {record.get("chunk_id"): record for record in self.chunks}

        self.endpoints_by_service: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.fields_by_service: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.fields_by_endpoint: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.mappings_by_field = {}
        self.mappings_by_service: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.chunks_by_service: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.tool_specs_by_endpoint = {}

        for endpoint in self.endpoints:
            self.endpoints_by_service[endpoint.get("service_id")].append(endpoint)
        for field in self.fields:
            self.fields_by_service[field.get("service_id")].append(field)
            self.fields_by_endpoint[field.get("endpoint_id")].append(field)
        for mapping in self.field_mappings:
            self.mappings_by_field[mapping.get("field_id")] = mapping
            self.mappings_by_service[mapping.get("service_id")].append(mapping)
        for chunk in self.chunks:
            self.chunks_by_service[chunk.get("service_id")].append(chunk)
        for spec in self.tool_specs:
            self.tool_specs_by_endpoint[spec.get("endpoint_id")] = spec

        self.search_blobs = {
            service_id: self._build_search_blob(service_id)
            for service_id in self.services_by_id
        }

    def health(self) -> dict[str, Any]:
        return {
            "services_total": len(self.services),
            "documents_total": len(self.documents),
            "endpoints_total": len(self.endpoints),
            "fields_total": len(self.fields),
            "chunks_total": len(self.chunks),
            "indexable_chunks_total": sum(1 for c in self.chunks if c.get("indexable", True) is not False),
        }

    def _build_search_blob(self, service_id: str) -> dict[str, str]:
        # minimal 서비스는 document.body(=full text)를 all로 바로 사용
        if service_id in self._minimal_service_ids:
            service = self.services_by_id.get(service_id, {})
            document = self.documents_by_service.get(service_id, {})
            body = document.get("body", "")
            return {
                "all": clean_text(body),
                "service_name": clean_text(service.get("name", "")),
                "keywords": clean_text(" ".join(service.get("keywords") or [])),
                "endpoint_paths": "",
                "endpoint_summaries": "",
                "field_names": "",
                "field_descriptions": "",
                "field_paths": "",
                "semantic": clean_text(service.get("category", "")),
            }

        service = self.services_by_id.get(service_id, {})
        document = self.documents_by_service.get(service_id, {})
        tag = self.tags_by_service.get(service_id, {})
        endpoints = self.endpoints_by_service.get(service_id, [])
        fields = self.fields_by_service.get(service_id, [])
        mappings = self.mappings_by_service.get(service_id, [])
        chunks = self.chunks_by_service.get(service_id, [])

        concept_names = [
            self.concepts_by_id.get(concept_id, {}).get("canonical_name", concept_id)
            for concept_id in tag.get("concept_ids", [])
        ]
        field_names = " ".join(clean_text(field.get("field_name")) for field in fields)
        field_descriptions = " ".join(clean_text(field.get("description")) for field in fields)
        field_paths = " ".join(clean_text(field.get("field_path")) for field in fields)
        mapping_aliases = " ".join(
            clean_text(alias)
            for mapping in mappings
            for alias in (mapping.get("aliases") or [])
        )

        return {
            "all": clean_text(
                " ".join(
                    [
                        service.get("name", ""),
                        service.get("description", ""),
                        " ".join(service.get("keywords") or []),
                        service.get("category", ""),
                        service.get("provider_agency_name", ""),
                        document.get("body", ""),
                        " ".join(endpoint.get("path", "") for endpoint in endpoints),
                        " ".join(endpoint.get("summary", "") for endpoint in endpoints),
                        field_names,
                        field_descriptions,
                        field_paths,
                        mapping_aliases,
                        " ".join(tag.get("domain_ids") or []),
                        " ".join(tag.get("concept_ids") or []),
                        " ".join(concept_names),
                        " ".join(chunk.get("search_text", "") for chunk in chunks),
                    ]
                )
            ),
            "service_name": clean_text(service.get("name")),
            "keywords": clean_text(" ".join(service.get("keywords") or [])),
            "endpoint_paths": clean_text(" ".join(endpoint.get("path", "") for endpoint in endpoints)),
            "endpoint_summaries": clean_text(" ".join(endpoint.get("summary", "") for endpoint in endpoints)),
            "field_names": field_names,
            "field_descriptions": field_descriptions,
            "field_paths": field_paths,
            "semantic": clean_text(" ".join([*(tag.get("domain_ids") or []), *(tag.get("concept_ids") or []), *concept_names])),
        }

    def service_exists(self, service_id: str) -> bool:
        return service_id in self.services_by_id
