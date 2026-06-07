"""
Ollama + FAISS retriever. nomic-embed-text 모델로 쿼리를 임베딩해 FAISS 검색.
"""
import json
import urllib.request
from typing import Any

import numpy as np

from ..core import config


class OllamaFAISSRetriever:
    def __init__(self) -> None:
        self._index = None
        self._meta: list[dict] = []
        self._last_error = ""

    def _load(self) -> bool:
        if self._index is not None:
            return True
        if not config.FAISS_INDEX_PATH.exists():
            self._last_error = f"FAISS 인덱스 없음: {config.FAISS_INDEX_PATH}"
            return False
        if not config.MINIMAL_META_PATH.exists():
            self._last_error = f"메타 파일 없음: {config.MINIMAL_META_PATH}"
            return False
        try:
            import faiss
            self._index = faiss.read_index(str(config.FAISS_INDEX_PATH))
            with config.MINIMAL_META_PATH.open(encoding="utf-8") as f:
                self._meta = [json.loads(line) for line in f if line.strip()]
            return True
        except Exception as exc:
            self._last_error = str(exc)
            return False

    def _embed(self, text: str) -> np.ndarray | None:
        try:
            payload = json.dumps({"model": config.OLLAMA_EMBED_MODEL, "input": [text]}).encode()
            req = urllib.request.Request(
                f"{config.OLLAMA_BASE_URL}/api/embed",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
            vec = np.array(data["embeddings"][0], dtype="float32")
            norm = np.linalg.norm(vec)
            return vec / max(norm, 1e-9)
        except Exception as exc:
            self._last_error = str(exc)
            return None

    def collection_count(self) -> int | None:
        if not self._load():
            return None
        return self._index.ntotal

    def last_error(self) -> str:
        return self._last_error

    def query(self, query: str, n_results: int) -> list[dict[str, Any]]:
        if not self._load():
            return []
        vec = self._embed(query)
        if vec is None:
            return []

        k = min(n_results, self._index.ntotal)
        scores, indices = self._index.search(vec.reshape(1, -1), k)

        candidates = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self._meta):
                continue
            meta = self._meta[idx]
            doc_id = meta.get("id", "")
            service_id = f"openapi_new:{doc_id}"
            candidates.append({
                "service_id": service_id,
                "chunk_id": f"chunk:{service_id}:overview:0",
                "chunk_type": "overview",
                "distance": float(1.0 - score),
                "vector_score": float(max(score, 0.0)),
                "document": meta.get("title", ""),
                "metadata": {
                    "service_id": service_id,
                    "chunk_type": "overview",
                    "title": meta.get("title", ""),
                    "url": meta.get("url", ""),
                    "provider": meta.get("provider", ""),
                    "category": meta.get("category", ""),
                },
                "reasons": ["vector similarity (nomic-embed-text)"],
            })
        return candidates
