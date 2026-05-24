from typing import Any

from .data_loader import DataRepository, clean_text


class DocumentBuilder:
    def __init__(self, repo: DataRepository) -> None:
        self.repo = repo

    def build(self, service_id: str, candidate: dict[str, Any] | None = None, compact: bool = False) -> dict[str, Any] | None:
        service = self.repo.services_by_id.get(service_id)
        if not service:
            return None
        candidate = candidate or {}
        document = self.repo.documents_by_service.get(service_id, {})
        endpoints = self.repo.endpoints_by_service.get(service_id, [])
        fields = self.repo.fields_by_service.get(service_id, [])
        tag = self.repo.tags_by_service.get(service_id, {})
        chunks = self.repo.chunks_by_service.get(service_id, [])
        overview = next((chunk for chunk in chunks if chunk.get("chunk_type") == "overview"), {})

        request_fields = [self._field_payload(field) for field in fields if field.get("field_role") == "request"]
        response_fields = [self._field_payload(field) for field in fields if field.get("field_role") == "response"]
        endpoint_payloads = [self._endpoint_payload(endpoint) for endpoint in endpoints]

        payload = {
            "service_id": service_id,
            "name": clean_text(service.get("name")),
            "description": clean_text(service.get("description") or document.get("body")),
            "provider_agency_id": service.get("provider_agency_id"),
            "provider_agency_name": service.get("provider_agency_name"),
            "category": service.get("category"),
            "data_type": service.get("data_type"),
            "api_type": service.get("api_type"),
            "updated_at": service.get("updated_at"),
            "score": round(float(candidate.get("score", 0.0)), 4),
            "vector_score": round(float(candidate.get("vector_score", 0.0)), 4),
            "lexical_score": round(float(candidate.get("lexical_score", 0.0)), 4),
            "schema_score": round(float(candidate.get("schema_score", 0.0)), 4),
            "match_reasons": candidate.get("match_reasons", []),
            "matched_chunks": candidate.get("matched_chunks", []),
            "domain_ids": tag.get("domain_ids", []),
            "concept_ids": tag.get("concept_ids", []),
            "display_text": clean_text(overview.get("display_text") or document.get("body") or service.get("description")),
            "endpoints": endpoint_payloads,
            "request_fields": request_fields[:20] if compact else request_fields,
            "response_fields": response_fields[:30] if compact else response_fields,
            "field_mappings": self._field_mappings(service_id, limit=15 if compact else None),
            "source": {
                "source_portal": service.get("source_portal"),
                "source_object_id": service.get("source_object_id"),
                "raw_path": service.get("raw_path") or document.get("source_path"),
                "refined_path": service.get("refined_path") or document.get("refined_path"),
            },
            "counts": {
                "endpoints": len(endpoints),
                "request_fields": len(request_fields),
                "response_fields": len(response_fields),
            },
        }
        return payload

    def _endpoint_payload(self, endpoint: dict[str, Any]) -> dict[str, Any]:
        return {
            "endpoint_id": endpoint.get("endpoint_id"),
            "method": endpoint.get("method"),
            "path": endpoint.get("path"),
            "summary": clean_text(endpoint.get("summary")),
            "operation_id": endpoint.get("operation_id"),
            "tool_spec": self.repo.tool_specs_by_endpoint.get(endpoint.get("endpoint_id")),
        }

    def _field_payload(self, field: dict[str, Any]) -> dict[str, Any]:
        mapping = self.repo.mappings_by_field.get(field.get("field_id"), {})
        return {
            "field_id": field.get("field_id"),
            "endpoint_id": field.get("endpoint_id"),
            "name": field.get("field_name"),
            "path": field.get("field_path"),
            "role": field.get("field_role"),
            "type": field.get("field_type"),
            "required": bool(field.get("required")),
            "description": clean_text(field.get("description")),
            "concept_id": mapping.get("concept_id"),
            "term_canonical_ko": mapping.get("term_canonical_ko"),
            "match_source": mapping.get("match_source"),
            "review_status": mapping.get("review_status"),
        }

    def _field_mappings(self, service_id: str, limit: int | None = None) -> list[dict[str, Any]]:
        records = []
        for mapping in self.repo.mappings_by_service.get(service_id, []):
            records.append(
                {
                    "field_id": mapping.get("field_id"),
                    "field_name": mapping.get("field_name"),
                    "field_role": mapping.get("field_role"),
                    "concept_id": mapping.get("concept_id"),
                    "term_canonical_ko": mapping.get("term_canonical_ko"),
                    "aliases": mapping.get("aliases", [])[:8],
                    "confidence": mapping.get("confidence"),
                    "review_status": mapping.get("review_status"),
                    "match_source": mapping.get("match_source"),
                }
            )
            if limit and len(records) >= limit:
                break
        return records
