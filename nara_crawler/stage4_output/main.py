import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone, timedelta
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
}


def now_iso() -> str:
    return datetime.now(KST).isoformat()


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


def atomic_write_json(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
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


def build_search_keywords(service: dict, document: dict, endpoints: list[dict], fields: list[dict]) -> list[str]:
    values = [
        service.get("name", ""),
        service.get("description", ""),
        service.get("provider_agency_name", ""),
        service.get("category", ""),
        document.get("body", ""),
        " ".join(service.get("keywords") or []),
        " ".join(endpoint.get("summary", "") for endpoint in endpoints),
        " ".join(field.get("field_name", "") for field in fields),
    ]
    keywords = tokenize(" ".join(values))
    if service.get("data_type") == "openapi":
        keywords.extend(["API", "REST", "연계"])
    elif service.get("data_type") == "fileData":
        keywords.extend(["파일", "다운로드"])
    elif service.get("data_type") == "standard":
        keywords.extend(["표준데이터"])
    deduped = []
    seen = set()
    for keyword in keywords:
        if keyword not in seen:
            seen.add(keyword)
            deduped.append(keyword)
    return deduped[:50]


class Stage3ServingBuilder:
    def __init__(self, base_dir: str | Path):
        self.base_dir = Path(base_dir)
        self.catalog_dir = self.base_dir / "data" / "02_catalog"
        self.serving_dir = self.base_dir / "data" / "04_serving"

    def build(self) -> None:
        services = read_jsonl(self.catalog_dir / "services.jsonl")
        documents = read_jsonl(self.catalog_dir / "documents.jsonl")
        endpoints = read_jsonl(self.catalog_dir / "endpoints.jsonl")
        fields = read_jsonl(self.catalog_dir / "fields.jsonl")

        documents_by_service = {record.get("service_id"): record for record in documents}
        endpoints_by_service = defaultdict(list)
        for endpoint in endpoints:
            endpoints_by_service[endpoint.get("service_id")].append(endpoint)
        fields_by_endpoint = defaultdict(list)
        fields_by_service = defaultdict(list)
        for field in fields:
            fields_by_endpoint[field.get("endpoint_id")].append(field)
            fields_by_service[field.get("service_id")].append(field)

        chunks = []
        tool_specs = []
        recommender = []
        missing_documents = 0
        not_toolable = 0

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
            search_keywords = build_search_keywords(service, document, service_endpoints, service_fields)
            search_text = " ".join(search_keywords)
            text = self._build_chunk_text(service, document, search_keywords)
            chunk_id = f"chunk:{service_id}:overview:0"
            chunk = {
                "chunk_id": chunk_id,
                "service_id": service_id,
                "document_id": document.get("document_id"),
                "chunk_type": "overview",
                "text": text,
                "search_text": search_text,
                "search_keywords": search_keywords,
                "agency_ids": [service.get("provider_agency_id")] if service.get("provider_agency_id") else [],
                "domain_ids": [],
                "concept_ids": [],
                "source_path": "data/02_catalog/documents.jsonl",
                "refined_path": service.get("refined_path"),
            }
            chunks.append(chunk)

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
                    "domain_ids": [],
                    "concept_ids": [],
                    "search_keywords": search_keywords,
                    "chunk_ids": [chunk_id],
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
                "tool_specs_total": len(tool_specs),
                "missing_documents": missing_documents,
                "missing_endpoints": sum(1 for service in services if not endpoints_by_service.get(service.get("service_id"))),
                "not_toolable": not_toolable,
                "semantic_tags_missing": len(services),
            },
        )

        print("Stage 3 complete")
        print(f"  services:   {len(services)}")
        print(f"  chunks:     {len(chunks)}")
        print(f"  tool_specs: {len(tool_specs)}")
        print(f"  output:     {self.serving_dir}")

    def _build_chunk_text(self, service: dict, document: dict, keywords: list[str]) -> str:
        parts = [
            service.get("name", ""),
            document.get("body", ""),
            f"제공기관: {service.get('provider_agency_name', '')}",
            f"데이터 유형: {service.get('data_type', '')}",
            f"검색 키워드: {', '.join(keywords[:20])}",
        ]
        return re.sub(r"\s+", " ", " ".join(part for part in parts if part)).strip()

    def _build_tool_specs(self, service: dict, endpoints: list[dict], fields_by_endpoint: dict) -> list[dict]:
        specs = []
        if service.get("data_type") != "openapi":
            return specs
        for endpoint in endpoints:
            endpoint_id = endpoint.get("endpoint_id")
            parameters = []
            for field in fields_by_endpoint.get(endpoint_id, []):
                parameters.append(
                    {
                        "name": field.get("field_name"),
                        "in": field.get("field_role", "query"),
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
    parser = argparse.ArgumentParser(description="Stage 3: build serving JSONL from catalog JSONL")
    parser.add_argument("--keyword-mode", choices=["rule", "llm"], default="rule", help="Only rule mode is implemented in MVP")
    parser.add_argument("--no-llm", action="store_true", help="Compatibility option. Stage 3 defaults to no LLM.")
    args = parser.parse_args()
    if args.keyword_mode == "llm":
        print("LLM keyword mode is not implemented yet. Falling back to rule mode.")
    Stage3ServingBuilder(BASE_DIR).build()


if __name__ == "__main__":
    main()
