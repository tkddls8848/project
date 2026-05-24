"""
SentenceTransformer + FAISS 기반 검색기.
"""
import json

import faiss
from sentence_transformers import SentenceTransformer

from . import config
from .index_builder import find_latest_openapi_dir


class FAISSRetriever:
    def __init__(self) -> None:
        self._index = None
        self._metadata: list[dict] = []
        self._model = None
        self._last_error = ""
        self._openapi_dir = ""
        self._load()

    def _load(self) -> None:
        try:
            openapi_dir = find_latest_openapi_dir(config.DATA_DIR)
            self._openapi_dir = str(openapi_dir)
            print(f"[retriever] 데이터 경로: {openapi_dir}")
            if self._model is None:
                model_path = config.ensure_local_model()
                print(f"[retriever] 모델 로딩: {model_path}")
                self._model = SentenceTransformer(model_path)
            print(f"[retriever] 인덱스 로딩: {config.FAISS_INDEX_PATH}")
            self._index = faiss.read_index(str(config.FAISS_INDEX_PATH))
            with config.STORAGE_META_PATH.open(encoding="utf-8") as f:
                self._metadata = [json.loads(line) for line in f if line.strip()]
            print(f"[retriever] 준비 완료. {self._index.ntotal}개 문서")
            self._last_error = ""
        except Exception as exc:
            self._last_error = str(exc)
            self._openapi_dir = ""
            print(f"[retriever] 로딩 실패: {exc}")

    def reload(self) -> None:
        """빌드 완료 후 인덱스·메타데이터만 다시 읽는다. 모델은 재사용."""
        print("[retriever] 인덱스 리로드 중...")
        self._load()

    def collection_count(self) -> int | None:
        return None if self._index is None else self._index.ntotal

    def last_error(self) -> str:
        return self._last_error

    def search(self, query: str, top_k: int = 10) -> list[dict]:
        if self._index is None or self._model is None:
            return []
        try:
            q_vec = self._model.encode(
                [query], convert_to_numpy=True, normalize_embeddings=True
            ).astype("float32")
            k = min(top_k, self._index.ntotal)
            scores, ids = self._index.search(q_vec, k)
            results = []
            for score, idx in zip(scores[0], ids[0]):
                if idx == -1 or idx >= len(self._metadata):
                    continue
                r = dict(self._metadata[idx])
                r["score"] = float(score)
                results.append(r)
            return results
        except Exception as exc:
            self._last_error = str(exc)
            return []
