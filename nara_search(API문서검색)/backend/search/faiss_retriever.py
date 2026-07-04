"""
SentenceTransformer + FAISS 기반 검색기.

faiss / sentence_transformers는 이 모듈 import 시점이 아니라 실제 로딩
시점에 import한다. 의존성·데이터·모델·인덱스가 없어도 앱은 기동하고,
/health가 원인을 진단할 수 있는 오류 문자열을 노출한다.
"""
import json

from ..core import config


class FAISSRetriever:
    def __init__(self, eager: bool = True) -> None:
        self._index = None
        self._metadata: list[dict] = []
        self._model = None
        self._last_error = ""
        self._openapi_dir = ""
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
            if not config.STORAGE_META_PATH.exists():
                raise FileNotFoundError(
                    f"메타데이터 파일이 없습니다: {config.STORAGE_META_PATH.name} — POST /build로 생성하세요"
                )

            import faiss
            from sentence_transformers import SentenceTransformer

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

    def diagnostics(self) -> dict:
        """health 응답용 준비 상태 진단."""
        from pathlib import Path

        model_dir = Path(config.LOCAL_MODEL_PATH)
        return {
            "apidata_exists": config.APIDATA_DIR.exists(),
            "index_exists": config.FAISS_INDEX_PATH.exists(),
            "metadata_exists": config.STORAGE_META_PATH.exists(),
            "model_exists": model_dir.exists() and any(model_dir.iterdir()),
        }

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
