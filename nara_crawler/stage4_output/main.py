import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(CURRENT_DIR)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

KST = timezone(timedelta(hours=9))
STOPWORDS = {
    "정보",
    "서비스",
    "제공",
    "조회",
    "데이터",
    "공공",
    "관리",
    "현황",
    "대한",
    "위한",
    "및",
    "해당",
    "API",
}


def now_iso() -> str:
    return datetime.now(KST).isoformat()


def clean_text(value) -> str:
    if value is None:
        return ""
    text = str(value).replace("\n", " ").strip()
    return re.sub(r"\s+", " ", text)


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records


def atomic_write_jsonl(path: Path, records: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    os.replace(tmp_path, path)


def atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


def tokenize(text: str) -> list[str]:
    if not text:
        return []
    tokens = re.split(r"[\s,;/|()\[\]{}<>\"'`~!@#$%^&*+=:._-]+", text)
    cleaned = []
    seen = set()
    for token in tokens:
        token = token.strip()
        if len(token) < 2 or token in STOPWORDS:
            continue
        if token not in seen:
            seen.add(token)
            cleaned.append(token)
    return cleaned


def dedupe(values: Iterable[str], limit: int | None = None) -> list[str]:
    result = []
    seen = set()
    for value in values:
        value = clean_text(value)
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
        if limit and len(result) >= limit:
            break
    return result


def clip(text: str, limit: int = 800) -> str:
    text = clean_text(text)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def field_label(field: dict) -> str:
    parts = [
        field.get("field_name", ""),
        f"({field.get('field_type')})" if field.get("field_type") else "",
        "필수" if field.get("required") else "",
        field.get("description", ""),
    ]
    return clean_text(" ".join(part for part in parts if part))


class Stage4ServingBuilder:
    def __init__(self, base_dir: str | Path):
        self.base_dir = Path(base_dir)
        self.catalog_dir = self.base_dir / "data" / "02_catalog"
        self.semantic_dir = self.base_dir / "data" / "03_semantic"
        self.serving_dir = self.base_dir / "data" / "04_serving"

    def build(self) -> None:
        services = read_jsonl(self.catalog_dir / "services.jsonl")
        documents = read_jsonl(self.catalog_dir / "documents.jsonl")
        endpoints = read_jsonl(self.catalog_dir / "endpoints.jsonl")
        fields = read_jsonl(self.catalog_dir / "fields.jsonl")
        service_tags = read_jsonl(self.semantic_dir / "service_tags.jsonl")
        field_mappings = read_jsonl(self.semantic_dir / "field_mappings.jsonl")
        concepts = read_jsonl(self.semantic_dir / "concepts.jsonl")

        documents_by_service = {record.get("service_id"): record for record in documents}
        endpoints_by_service: dict[str, list[dict]] = defaultdict(list)
        fields_by_endpoint: dict[str, list[dict]] = defaultdict(list)
        fields_by_service: dict[str, list[dict]] = defaultdict(list)
        mappings_by_field = {record.get("field_id"): record for record in field_mappings}
        tags_by_service = {record.get("service_id"): record for record in service_tags}
        concepts_by_id = {record.get("concept_id"): record for record in concepts}

        for endpoint in endpoints:
            endpoints_by_service[endpoint.get("service_id")].append(endpoint)
        for field in fields:
            fields_by_endpoint[field.get("endpoint_id")].append(field)
            fields_by_service[field.get("service_id")].append(field)

        chunks = []
        tool_specs = []
        recommender = []
        missing_documents = 0
        not_toolable = 0
        semantic_tags_missing = 0

        for service in services:
            service_id = service.get("service_id")
            document = documents_by_service.get(service_id)
            if not document:
                missing_documents += 1
                document = {
                    "document_id": f"doc:{service_id}:overview",
                    "title": service.get("name", ""),
                    "body": service.get("description", ""),
                }

            service_endpoints = endpoints_by_service.get(service_id, [])
            service_fields = fields_by_service.get(service_id, [])
            tag = tags_by_service.get(service_id, {})
            if not tag:
                semantic_tags_missing += 1
            domain_ids = tag.get("domain_ids") or []
            concept_ids = tag.get("concept_ids") or []
            agency_ids = [service.get("provider_agency_id")] if service.get("provider_agency_id") else []
            search_keywords = self._build_search_keywords(
                service, document, service_endpoints, service_fields, concept_ids, concepts_by_id
            )

            overview_chunk_id = f"chunk:{service_id}:overview:0"
            overview_text = self._build_overview_text(service, document, search_keywords)
            overview_chunk = {
                "chunk_id": overview_chunk_id,
                "parent_chunk_id": None,
                "service_id": service_id,
                "document_id": document.get("document_id"),
                "chunk_type": "overview",
                "indexable": False,
                "text": overview_text,
                "display_text": clip(overview_text, 1000),
                "search_text": " ".join(search_keywords),
                "search_keywords": search_keywords,
                "domain_ids": domain_ids,
                "concept_ids": concept_ids,
                "agency_ids": agency_ids,
                "endpoint_ids": [endpoint.get("endpoint_id") for endpoint in service_endpoints],
                "field_ids": [field.get("field_id") for field in service_fields],
                "source_path": "data/02_catalog/documents.jsonl",
                "refined_path": service.get("refined_path"),
            }
            chunks.append(overview_chunk)

            summary_chunk = {
                "chunk_id": f"chunk:{service_id}:summary:0",
                "parent_chunk_id": overview_chunk_id,
                "service_id": service_id,
                "document_id": document.get("document_id"),
                "chunk_type": "summary",
                "indexable": True,
                "text": self._build_summary_text(service, document, search_keywords, concept_ids, concepts_by_id),
                "display_text": clip(document.get("body") or service.get("description") or service.get("name"), 600),
                "search_text": " ".join(search_keywords),
                "search_keywords": search_keywords,
                "domain_ids": domain_ids,
                "concept_ids": concept_ids,
                "agency_ids": agency_ids,
                "endpoint_ids": [endpoint.get("endpoint_id") for endpoint in service_endpoints],
                "field_ids": [],
                "source_path": "data/02_catalog/documents.jsonl",
                "refined_path": service.get("refined_path"),
            }
            chunks.append(summary_chunk)

            if service_endpoints or service_fields:
                api_schema_chunk = {
                    "chunk_id": f"chunk:{service_id}:api_schema:0",
                    "parent_chunk_id": overview_chunk_id,
                    "service_id": service_id,
                    "document_id": document.get("document_id"),
                    "chunk_type": "api_schema",
                    "indexable": True,
                    "text": self._build_api_schema_text(
                        service, service_endpoints, service_fields, fields_by_endpoint, mappings_by_field
                    ),
                    "display_text": self._build_api_schema_display(service_endpoints, service_fields),
                    "search_text": " ".join(search_keywords),
                    "search_keywords": search_keywords,
                    "domain_ids": domain_ids,
                    "concept_ids": concept_ids,
                    "agency_ids": agency_ids,
                    "endpoint_ids": [endpoint.get("endpoint_id") for endpoint in service_endpoints],
                    "field_ids": [field.get("field_id") for field in service_fields],
                    "source_path": "data/02_catalog/fields.jsonl",
                    "refined_path": service.get("refined_path"),
                }
                chunks.append(api_schema_chunk)

            service_tool_specs = self._build_tool_specs(service, service_endpoints, fields_by_endpoint)
            if not service_tool_specs:
                not_toolable += 1
            tool_specs.extend(service_tool_specs)

            recommender.append(
                {
                    "service_id": service_id,
                    "name": service.get("name", ""),
                    "description": service.get("description", ""),
                    "provider_agency_id": service.get("provider_agency_id"),
                    "provider_agency_name": service.get("provider_agency_name"),
                    "data_type": service.get("data_type"),
                    "domain_ids": domain_ids,
                    "concept_ids": concept_ids,
                    "search_keywords": search_keywords,
                    "chunk_ids": [chunk["chunk_id"] for chunk in chunks if chunk.get("service_id") == service_id],
                    "toolable": bool(service_tool_specs),
                    "updated_at": service.get("updated_at", ""),
                }
            )

        atomic_write_jsonl(self.serving_dir / "retrieval_chunks.jsonl", chunks)
        atomic_write_jsonl(self.serving_dir / "api_tool_specs.jsonl", tool_specs)
        atomic_write_jsonl(self.serving_dir / "recommender_catalog.jsonl", recommender)
        atomic_write_json(
            self.serving_dir / "quality_report.json",
            {
                "generated_at": now_iso(),
                "services_total": len(services),
                "chunks_total": len(chunks),
                "chunks_by_type": dict(Counter(chunk.get("chunk_type") for chunk in chunks)),
                "indexable_chunks_total": sum(1 for chunk in chunks if chunk.get("indexable", True) is not False),
                "tool_specs_total": len(tool_specs),
                "endpoints_total": len(endpoints),
                "fields_total": len(fields),
                "missing_documents": missing_documents,
                "missing_endpoints": sum(
                    1 for service in services if not endpoints_by_service.get(service.get("service_id"))
                ),
                "not_toolable": not_toolable,
                "semantic_tags_missing": semantic_tags_missing,
            },
        )

        print("Stage 4 complete")
        print(f"  services:          {len(services)}")
        print(f"  chunks:            {len(chunks)}")
        print(f"  indexable_chunks:  {sum(1 for chunk in chunks if chunk.get('indexable', True) is not False)}")
        print(f"  tool_specs:        {len(tool_specs)}")
        print(f"  output:            {self.serving_dir}")

    def _build_search_keywords(
        self,
        service: dict,
        document: dict,
        endpoints: list[dict],
        fields: list[dict],
        concept_ids: list[str],
        concepts_by_id: dict[str, dict],
    ) -> list[str]:
        concept_terms = [
            concepts_by_id.get(concept_id, {}).get("canonical_name", "")
            for concept_id in concept_ids
        ]
        values = [
            service.get("name", ""),
            service.get("description", ""),
            service.get("provider_agency_name", ""),
            service.get("category", ""),
            document.get("body", ""),
            " ".join(service.get("keywords") or []),
            " ".join(endpoint.get("summary", "") for endpoint in endpoints),
            " ".join(endpoint.get("path", "") for endpoint in endpoints),
            " ".join(field.get("field_name", "") for field in fields),
            " ".join(field.get("description", "") for field in fields),
            " ".join(concept_terms),
        ]
        keywords = tokenize(" ".join(values))
        if service.get("data_type") == "openapi":
            keywords.extend(["API", "REST", "endpoint", "응답", "필드"])
        elif service.get("data_type") == "fileData":
            keywords.extend(["파일", "다운로드"])
        elif service.get("data_type") == "standard":
            keywords.extend(["표준데이터"])
        return dedupe(keywords, 80)

    def _build_overview_text(self, service: dict, document: dict, keywords: list[str]) -> str:
        parts = [
            service.get("name", ""),
            document.get("body", ""),
            f"제공기관: {service.get('provider_agency_name', '')}",
            f"데이터 유형: {service.get('data_type', '')}",
            f"검색 키워드: {', '.join(keywords[:30])}",
        ]
        return clean_text(" ".join(part for part in parts if part))

    def _build_summary_text(
        self,
        service: dict,
        document: dict,
        keywords: list[str],
        concept_ids: list[str],
        concepts_by_id: dict[str, dict],
    ) -> str:
        concept_names = [
            concepts_by_id.get(concept_id, {}).get("canonical_name", concept_id)
            for concept_id in concept_ids[:20]
        ]
        parts = [
            service.get("name", ""),
            service.get("description", ""),
            document.get("body", ""),
            service.get("provider_agency_name", ""),
            service.get("category", ""),
            " ".join(service.get("keywords") or []),
            " ".join(concept_names),
            " ".join(keywords[:40]),
        ]
        return clean_text(" ".join(part for part in parts if part))

    def _build_api_schema_text(
        self,
        service: dict,
        endpoints: list[dict],
        fields: list[dict],
        fields_by_endpoint: dict[str, list[dict]],
        mappings_by_field: dict[str, dict],
    ) -> str:
        parts = [service.get("name", ""), "API schema"]
        for endpoint in endpoints:
            endpoint_id = endpoint.get("endpoint_id")
            parts.append(
                clean_text(
                    f"endpoint {endpoint.get('method', 'GET')} {endpoint.get('path', '')} "
                    f"{endpoint.get('summary', '')}"
                )
            )
            endpoint_fields = fields_by_endpoint.get(endpoint_id, [])
            request_fields = [field for field in endpoint_fields if field.get("field_role") == "request"]
            response_fields = [field for field in endpoint_fields if field.get("field_role") == "response"]
            if request_fields:
                parts.append("요청 필드 " + " ".join(field_label(field) for field in request_fields[:80]))
            if response_fields:
                parts.append("응답 필드 " + " ".join(field_label(field) for field in response_fields[:120]))
        mapped_terms = []
        for field in fields[:120]:
            mapping = mappings_by_field.get(field.get("field_id"), {})
            mapped_terms.extend([mapping.get("term_canonical_ko", ""), mapping.get("concept_id", "")])
            mapped_terms.extend(mapping.get("aliases") or [])
        if mapped_terms:
            parts.append("표준 용어 " + " ".join(dedupe(mapped_terms, 120)))
        return clean_text(" ".join(part for part in parts if part))

    def _build_api_schema_display(self, endpoints: list[dict], fields: list[dict]) -> str:
        endpoint_text = ", ".join(
            f"{endpoint.get('method', 'GET')} {endpoint.get('path', '')}" for endpoint in endpoints[:5]
        )
        request_count = sum(1 for field in fields if field.get("field_role") == "request")
        response_count = sum(1 for field in fields if field.get("field_role") == "response")
        return clean_text(
            f"{endpoint_text} 요청 필드 {request_count}개, 응답 필드 {response_count}개"
        )

    def _build_tool_specs(self, service: dict, endpoints: list[dict], fields_by_endpoint: dict) -> list[dict]:
        specs = []
        if service.get("data_type") != "openapi":
            return specs
        for endpoint in endpoints:
            endpoint_id = endpoint.get("endpoint_id")
            parameters = []
            for field in fields_by_endpoint.get(endpoint_id, []):
                if field.get("field_role") != "request":
                    continue
                parameters.append(
                    {
                        "name": field.get("field_name"),
                        "in": field.get("field_location") or "query",
                        "required": field.get("required", False),
                        "type": field.get("field_type", "string"),
                        "description": field.get("description", ""),
                    }
                )
            specs.append(
                {
                    "tool_id": f"tool:{endpoint_id}",
                    "service_id": service.get("service_id"),
                    "endpoint_id": endpoint_id,
                    "name": endpoint.get("operation_id") or endpoint.get("path"),
                    "description": endpoint.get("summary", ""),
                    "method": endpoint.get("method", "GET"),
                    "path": endpoint.get("path", ""),
                    "parameters": parameters,
                    "source": "data.go.kr",
                }
            )
        return specs


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 4: build serving JSONL from catalog and semantic JSONL")
    parser.add_argument("--keyword-mode", choices=["rule", "llm"], default="rule", help="Only rule mode is implemented in MVP")
    parser.add_argument("--no-llm", action="store_true", help="Compatibility option. Stage 4 defaults to no LLM.")
    args = parser.parse_args()
    if args.keyword_mode == "llm":
        print("LLM keyword mode is not implemented yet. Falling back to rule mode.")
    Stage4ServingBuilder(BASE_DIR).build()


if __name__ == "__main__":
    main()
