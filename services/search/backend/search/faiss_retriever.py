"""
SentenceTransformer + FAISS 기반 검색기.

faiss / sentence_transformers는 이 모듈 import 시점이 아니라 실제 로딩
시점에 import한다. 의존성·데이터·모델·인덱스가 없어도 앱은 기동하고,
/health가 원인을 진단할 수 있는 오류 문자열을 노출한다.
"""
import json
import re

from ..core import config, faiss_io


_QUERY_CONNECTOR_RE = re.compile(
    r"(?:\s*[,/+\n]\s*|\s+(?:및|또는|하고)\s+|(?<=[가-힣])(?:와|과)\s+)"
)


def split_query_intents(query: str) -> list[str]:
    """복합 질의를 원문과 하위 의도로 확장한다."""
    normalized = " ".join(str(query or "").split())
    if not normalized:
        return []
    parts = [part.strip() for part in _QUERY_CONNECTOR_RE.split(normalized) if len(part.strip()) >= 2]
    if len(parts) < 2:
        return [normalized]
    return list(dict.fromkeys([normalized, *parts]))


class FAISSRetriever:
    def __init__(self, eager: bool = True) -> None:
        self._index = None
        self._metadata: list[dict] = []
        self._model = None
        self._last_error = ""
        self._last_search = {}
        self._openapi_dir = ""
        self._metadata_path = None
        if eager:
            self._load()

    def _load(self) -> None:
        try:
            self._openapi_dir = str(config.APIDATA_DIR) if config.APIDATA_DIR.exists() else ""

            # 모델 다운로드 전에 인덱스 존재부터 확인해 원인을 명확히 한다.
            if not config.FAISS_INDEX_PATH.exists():
                raise FileNotFoundError(
                    f"FAISS 인덱스가 없습니다: {config.FAISS_INDEX_PATH.name} — POST /build로 생성하세요"
                )
            metadata_path = (
                config.VECTOR_META_PATH
                if config.VECTOR_META_PATH.exists()
                else config.STORAGE_META_PATH
            )
            if not metadata_path.exists():
                raise FileNotFoundError(
                    f"메타데이터 파일이 없습니다: {metadata_path.name} — POST /build로 생성하세요"
                )

            import faiss
            from sentence_transformers import SentenceTransformer

            if self._model is None:
                model_path = config.ensure_local_model()
                print(f"[retriever] 모델 로딩: {model_path}")
                self._model = SentenceTransformer(model_path)
            self._model.max_seq_length = config.MODEL_MAX_SEQ_LENGTH
            print(f"[retriever] 인덱스 로딩: {config.FAISS_INDEX_PATH}")
            # 한글 경로는 faiss가 직접 읽지 못하므로 헬퍼로 읽는다.
            self._index = faiss_io.read_index(config.FAISS_INDEX_PATH)
            with metadata_path.open(encoding="utf-8") as f:
                self._metadata = [json.loads(line) for line in f if line.strip()]
            if self._index.ntotal != len(self._metadata):
                raise ValueError(
                    "FAISS 인덱스와 벡터 메타데이터 개수가 다릅니다: "
                    f"{self._index.ntotal} != {len(self._metadata)} — POST /build로 다시 생성하세요"
                )
            self._metadata_path = metadata_path
            print(
                f"[retriever] 준비 완료. 서비스 {self.service_count()}건 / "
                f"벡터 청크 {self._index.ntotal}건"
            )
            self._last_error = ""
        except ImportError as exc:
            self._index = None
            self._last_error = f"검색 의존성이 설치되지 않았습니다: {exc.name} (pip install -r backend/requirements.txt)"
            print(f"[retriever] 로딩 실패: {self._last_error}")
        except Exception as exc:
            self._index = None
            self._last_error = str(exc)
            print(f"[retriever] 로딩 실패: {exc}")

    def reload(self) -> None:
        """빌드 완료 후 인덱스·메타데이터만 다시 읽는다. 모델은 재사용."""
        print("[retriever] 인덱스 리로드 중...")
        self._load()

    def collection_count(self) -> int | None:
        return None if self._index is None else self._index.ntotal

    def last_error(self) -> str:
        return self._last_error

    def service_count(self) -> int | None:
        if self._index is None:
            return None
        return len({str(row.get("api_id", "")) for row in self._metadata if row.get("api_id")})

    def search_diagnostics(self) -> dict:
        return dict(self._last_search)

    def diagnostics(self) -> dict:
        """health 응답용 준비 상태 진단."""
        from pathlib import Path

        model_dir = Path(config.LOCAL_MODEL_PATH)
        return {
            "apidata_exists": config.APIDATA_DIR.exists(),
            "index_exists": config.FAISS_INDEX_PATH.exists(),
            "metadata_exists": config.STORAGE_META_PATH.exists(),
            "vector_metadata_exists": config.VECTOR_META_PATH.exists(),
            "model_max_seq_length": config.MODEL_MAX_SEQ_LENGTH,
            "vector_min_score": config.VECTOR_MIN_SCORE,
            "model_exists": model_dir.exists() and any(model_dir.iterdir()),
        }

    def search(self, query: str, top_k: int = 10) -> list[dict]:
        if self._index is None or self._model is None:
            self._last_search = {
                "query_intents": 0,
                "raw_candidates": 0,
                "accepted_services": 0,
                "min_score": config.VECTOR_MIN_SCORE,
            }
            return []
        try:
            intents = split_query_intents(query)
            q_vec = self._model.encode(
                intents, convert_to_numpy=True, normalize_embeddings=True
            ).astype("float32")
            k = min(
                max(top_k, top_k * config.VECTOR_OVERSAMPLE),
                self._index.ntotal,
            )
            scores, ids = self._index.search(q_vec, k)
            best_by_service: dict[str, dict] = {}
            matched_intents: dict[str, set[str]] = {}
            raw_candidates = 0
            for intent_index, intent in enumerate(intents):
                for score, idx in zip(scores[intent_index], ids[intent_index]):
                    if idx == -1 or idx >= len(self._metadata):
                        continue
                    raw_candidates += 1
                    numeric_score = float(score)
                    if numeric_score < config.VECTOR_MIN_SCORE:
                        continue
                    record = self._metadata[idx]
                    api_id = str(record.get("api_id", "") or "")
                    if not api_id:
                        continue
                    matched_intents.setdefault(api_id, set()).add(intent)
                    current = best_by_service.get(api_id)
                    if current is None or numeric_score > current["score"]:
                        best_by_service[api_id] = {
                            **record,
                            "score": numeric_score,
                            "matched_chunk_type": record.get("chunk_type", "document"),
                        }

            results = sorted(
                best_by_service.values(),
                key=lambda row: row["score"],
                reverse=True,
            )[: max(1, top_k)]
            for result in results:
                result["matched_intents"] = sorted(matched_intents[result["api_id"]])
            self._last_search = {
                "query_intents": len(intents),
                "raw_candidates": raw_candidates,
                "accepted_services": len(best_by_service),
                "min_score": config.VECTOR_MIN_SCORE,
            }
            self._last_error = ""
            return results
        except Exception as exc:
            self._last_error = str(exc)
            self._last_search = {"error": str(exc)}
            return []
