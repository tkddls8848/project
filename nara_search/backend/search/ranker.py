from collections import defaultdict
from typing import Any

from ..core import config
from ..catalog.data_loader import DataRepository
from ..catalog.document_builder import DocumentBuilder
from .lexical import LexicalSearcher, tokenize
from .retriever import ChromaRetriever


SCHEMA_TERMS = {"api", "endpoint", "path", "필드", "응답", "요청", "파라미터", "parameter", "field", "schema"}


class HybridSearchEngine:
    def __init__(self, repo: DataRepository, retriever: ChromaRetriever) -> None:
        self.repo = repo
        self.retriever = retriever
        self.lexical = LexicalSearcher(repo)
        self.builder = DocumentBuilder(repo)

    def search(self, query: str, top_k: int = config.DEFAULT_TOP_K, use_vector: bool = True) -> dict[str, Any]:
        vector_top_n = max(top_k * 4, config.VECTOR_TOP_N_MIN)
        vector_candidates = self.retriever.query(query, vector_top_n) if use_vector else []
        lexical_candidates = self.lexical.search(query, limit=max(top_k * 6, 30))

        merged = self._merge(query, vector_candidates, lexical_candidates)
        ranked = sorted(merged.values(), key=lambda item: item["score"], reverse=True)

        results = []
        for candidate in ranked[:top_k]:
            document = self.builder.build(candidate["service_id"], candidate, compact=True)
            if document:
                results.append(document)

        return {
            "query": query,
            "results": results,
            "diagnostics": {
                "vector_enabled": use_vector,
                "vector_candidates": len(vector_candidates),
                "lexical_candidates": len(lexical_candidates),
                "vector_error": self.retriever.last_error() if use_vector and not vector_candidates else "",
            },
        }

    def _merge(
        self,
        query: str,
        vector_candidates: list[dict[str, Any]],
        lexical_candidates: list[dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        candidates: dict[str, dict[str, Any]] = defaultdict(lambda: {
            "service_id": "",
            "vector_score": 0.0,
            "lexical_score": 0.0,
            "schema_score": 0.0,
            "matched_chunks": [],
            "match_reasons": [],
        })

        for item in vector_candidates:
            service_id = item.get("service_id")
            if not service_id:
                continue
            candidate = candidates[service_id]
            candidate["service_id"] = service_id
            candidate["vector_score"] = max(candidate["vector_score"], float(item.get("vector_score", 0.0)))
            candidate["matched_chunks"].append(
                {
                    "chunk_id": item.get("chunk_id"),
                    "chunk_type": item.get("chunk_type"),
                    "distance": item.get("distance"),
                }
            )
            candidate["match_reasons"].extend(item.get("reasons", []))

        for item in lexical_candidates:
            service_id = item.get("service_id")
            if not service_id:
                continue
            candidate = candidates[service_id]
            candidate["service_id"] = service_id
            candidate["lexical_score"] = max(candidate["lexical_score"], min(float(item.get("lexical_score", 0.0)), 1.5))
            candidate["match_reasons"].extend(item.get("reasons", []))

        query_tokens = set(tokenize(query))
        for service_id, candidate in candidates.items():
            candidate["schema_score"] = self._schema_score(service_id, query_tokens)
            candidate["match_reasons"] = self._dedupe(candidate["match_reasons"])[:10]
            candidate["score"] = (
                candidate["vector_score"] * 0.55
                + min(candidate["lexical_score"], 1.0) * 0.35
                + candidate["schema_score"] * 0.10
            )
        return dict(candidates)

    def _schema_score(self, service_id: str, query_tokens: set[str]) -> float:
        if not query_tokens.intersection(SCHEMA_TERMS):
            return 0.0
        endpoints = self.repo.endpoints_by_service.get(service_id, [])
        fields = self.repo.fields_by_service.get(service_id, [])
        if endpoints and fields:
            return 1.0
        if endpoints or fields:
            return 0.5
        return 0.0

    def _dedupe(self, values: list[str]) -> list[str]:
        result = []
        seen = set()
        for value in values:
            if value and value not in seen:
                seen.add(value)
                result.append(value)
        return result
