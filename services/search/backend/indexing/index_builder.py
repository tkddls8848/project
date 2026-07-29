"""
FAISS 인덱스 빌드 로직. build_index.py 와 동일한 기능을 서비스 내부에서 제공한다.
"""
import json
import threading
import time
from pathlib import Path

from ..core import config, faiss_io


# ── 데이터 경로 탐색 ─────────────────────────────────────────────────────────

def get_apidata_dir() -> Path:
    d = config.APIDATA_DIR
    if not d.exists():
        raise FileNotFoundError(f"apidata 디렉터리가 없습니다: {d}")
    return d


# ── 디바이스 선택 ────────────────────────────────────────────────────────────

def resolve_device(device: str) -> str:
    """요청 디바이스('cpu'/'gpu'/'cuda')를 SentenceTransformer용 값으로 정규화.

    GPU 요청 시 CUDA 가용성을 확인하고, 사용할 수 없으면 명확한 오류를 낸다.
    """
    value = (device or "cpu").strip().lower()
    if value in ("cpu", ""):
        return "cpu"
    if value in ("gpu", "cuda"):
        try:
            import torch
        except ImportError as exc:  # pragma: no cover - 환경 의존
            raise RuntimeError(
                "GPU 빌드를 위해 CUDA 지원 torch가 필요하지만 torch를 불러올 수 없습니다."
            ) from exc
        if not torch.cuda.is_available():
            raise RuntimeError(
                "GPU 빌드를 요청했지만 사용 가능한 CUDA 디바이스가 없습니다. "
                "CPU 빌드를 사용하거나 CUDA 지원 torch를 설치하세요."
            )
        return "cuda"
    raise ValueError(f"알 수 없는 디바이스: {device!r} (cpu 또는 gpu)")


# ── 텍스트 추출 헬퍼 ─────────────────────────────────────────────────────────

def _safe_get(d, key, default=""):
    if not isinstance(d, dict):
        return default
    v = d.get(key, default)
    return default if (v is None or v == "-") else v


def _extract_field_descriptions(swagger_json):
    if not isinstance(swagger_json, dict):
        return []
    out = []
    for def_body in (swagger_json.get("definitions") or {}).values():
        if not isinstance(def_body, dict):
            continue
        for field_spec in (def_body.get("properties") or {}).values():
            if not isinstance(field_spec, dict):
                continue
            desc = field_spec.get("description", "")
            if desc and desc != "-":
                out.append(desc)
    return out


def _group_text_items(items, max_chars=None):
    """긴 엔드포인트·필드 목록을 임베딩 가능한 크기의 묶음으로 나눈다."""
    limit = max_chars or config.VECTOR_CHUNK_MAX_CHARS
    groups, current, current_len = [], [], 0
    for raw_item in items:
        item = str(raw_item or "").strip()
        if not item:
            continue
        pieces = [item[i : i + limit] for i in range(0, len(item), limit)]
        for piece in pieces:
            projected = current_len + len(piece) + (1 if current else 0)
            if current and projected > limit:
                groups.append(current)
                current, current_len = [], 0
            current.append(piece)
            current_len += len(piece) + (1 if current_len else 0)
    if current:
        groups.append(current)
    return groups


def _build_search_chunks(doc):
    """서비스 문서를 개요·엔드포인트·응답필드 검색 청크로 구성한다.

    모든 청크에 제목·기관·분류·키워드를 반복해 긴 설명 때문에 API 인터페이스
    정보가 모델 입력 뒤쪽에서 잘리는 문제를 피한다.
    """
    info = doc.get("info") or {}
    swagger = doc.get("swagger_json") or {}
    swagger_info = swagger.get("info") or {}

    title       = _safe_get(info, "목록명") or _safe_get(swagger_info, "title")
    provider    = _safe_get(info, "제공기관")
    category    = _safe_get(info, "분류체계")
    keywords    = _safe_get(info, "키워드")
    description = _safe_get(info, "설명") or _safe_get(swagger_info, "description")

    identity = []
    if title:    identity.append(f"[제목] {title}")
    if provider: identity.append(f"[기관] {provider}")
    if category: identity.append(f"[분류] {category}")
    if keywords: identity.append(f"[키워드] {keywords}")

    endpoint_lines = []
    for ep in (doc.get("endpoints") or []):
        line = f"- {ep.get('method','')} {ep.get('path','')}"
        if ep.get("description"):
            line += f" : {ep['description']}"
        endpoint_lines.append(line)
    field_descs = _extract_field_descriptions(swagger)

    description_groups = _group_text_items([description]) if description else [[]]
    endpoint_groups = _group_text_items(endpoint_lines)
    field_groups = _group_text_items(field_descs)

    chunks = []
    for index in range(
        max(len(description_groups), len(endpoint_groups), len(field_groups))
    ):
        if index < len(description_groups):
            overview = [*identity]
            if description_groups[index]:
                overview.extend(["[설명]", *description_groups[index]])
            if overview:
                chunks.append(("overview", "\n".join(overview)))
        if index < len(endpoint_groups):
            chunks.append(
                ("endpoints", "\n".join([*identity, "[엔드포인트]", *endpoint_groups[index]]))
            )
        if index < len(field_groups):
            chunks.append(
                ("response_fields", "\n".join([*identity, "[응답필드]", *field_groups[index]]))
            )
    return chunks[: config.VECTOR_MAX_CHUNKS_PER_DOCUMENT]


def _build_search_text(doc):
    """이전 호출부 호환용 단일 텍스트 표현."""
    return "\n".join(text for _, text in _build_search_chunks(doc))


def _extract_metadata(doc, source_path):
    info = doc.get("info") or {}
    swagger_info = (doc.get("swagger_json") or {}).get("info") or {}
    description = _safe_get(info, "설명") or _safe_get(swagger_info, "description")
    return {
        "api_id":         doc.get("api_id", ""),
        "title":          _safe_get(info, "목록명") or _safe_get(swagger_info, "title"),
        "provider":       _safe_get(info, "제공기관"),
        "category":       _safe_get(info, "분류체계"),
        "keywords":       _safe_get(info, "키워드"),
        "description":    description,
        "url":            doc.get("crawled_url", ""),
        "endpoint_count": len(doc.get("endpoints") or []),
        "source_path":    str(source_path),
    }


# ── 빌드 상태 ────────────────────────────────────────────────────────────────

class BuildStatus:
    def __init__(self):
        self._lock = threading.Lock()
        self.state    = "idle"   # idle / running / done / error
        self.step     = 0        # 1~4
        self.step_name = ""
        self.progress = 0
        self.total    = 0
        self.message  = ""
        self.data_path = ""
        self.device   = ""      # cpu / cuda
        self.started_at: float | None  = None
        self.finished_at: float | None = None

    def update(self, **kwargs):
        with self._lock:
            for k, v in kwargs.items():
                setattr(self, k, v)

    def to_dict(self) -> dict:
        with self._lock:
            elapsed = None
            if self.started_at:
                end = self.finished_at or time.time()
                elapsed = round(end - self.started_at, 1)
            return {
                "state":     self.state,
                "step":      self.step,
                "step_name": self.step_name,
                "progress":  self.progress,
                "total":     self.total,
                "message":   self.message,
                "data_path": self.data_path,
                "device":    self.device,
                "elapsed_s": elapsed,
            }


build_status = BuildStatus()


# ── 빌드 실행 ────────────────────────────────────────────────────────────────

def run_build(on_complete=None, device="cpu"):
    """백그라운드 스레드에서 실행. 완료 후 on_complete() 호출.

    device: 'cpu' 또는 'gpu'/'cuda'. 임베딩 단계를 지정한 디바이스에서 수행한다.
    """
    s = build_status
    s.update(state="running", started_at=time.time(), finished_at=None,
             step=0, progress=0, total=0, device="", message="시작 중...")
    try:
        # 무거운 의존성은 빌드 시작 시점에만 import (미설치 시 build 오류로 보고)
        import faiss
        from sentence_transformers import SentenceTransformer

        resolved_device = resolve_device(device)
        s.update(device=resolved_device)

        # 1단계: 파일 탐색
        s.update(step=1, step_name="파일 탐색")
        openapi_dir = get_apidata_dir()
        s.update(data_path=str(openapi_dir), message=f"탐색 중: {openapi_dir}")
        json_files = sorted(openapi_dir.glob("**/*.json"))
        if not json_files:
            raise FileNotFoundError("JSON 파일이 없습니다.")
        s.update(total=len(json_files), message=f"{len(json_files)}개 파일 발견")

        # 2단계: JSON 파싱
        s.update(step=2, step_name="JSON 파싱", progress=0)
        texts, vector_metadata, service_metadata, skipped = [], [], [], 0
        for i, fp in enumerate(json_files):
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    doc = json.load(f)
                chunks = _build_search_chunks(doc)
                if not chunks:
                    skipped += 1
                else:
                    metadata = _extract_metadata(doc, fp)
                    service_metadata.append(metadata)
                    for chunk_index, (chunk_type, text) in enumerate(chunks):
                        texts.append(text)
                        vector_metadata.append(
                            {
                                **metadata,
                                "chunk_type": chunk_type,
                                "chunk_index": chunk_index,
                            }
                        )
            except Exception:
                skipped += 1
            s.update(progress=i + 1,
                     message=f"파싱 중 {i+1}/{len(json_files)} (스킵 {skipped})")

        s.update(
            message=(
                f"파싱 완료: 서비스 {len(service_metadata)}건 / "
                f"벡터 청크 {len(texts)}건 / 스킵 {skipped}건"
            )
        )

        # 3단계: 임베딩
        s.update(step=3, step_name=f"임베딩 생성 ({resolved_device})",
                 progress=0, total=len(texts))
        model_path = config.ensure_local_model()
        model = SentenceTransformer(model_path, device=resolved_device)
        model.max_seq_length = config.MODEL_MAX_SEQ_LENGTH

        batch_size = 64
        import numpy as np
        all_embeddings = []
        for start in range(0, len(texts), batch_size):
            batch = texts[start:start + batch_size]
            emb = model.encode(
                batch,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            ).astype("float32")
            all_embeddings.append(emb)
            done = min(start + batch_size, len(texts))
            s.update(progress=done, message=f"임베딩 {done}/{len(texts)} ({resolved_device})")
        embeddings = np.vstack(all_embeddings)

        # 4단계: 인덱스 저장
        s.update(step=4, step_name="인덱스 저장", progress=0, total=1)
        dim = embeddings.shape[1]
        index = faiss.IndexFlatIP(dim)
        index.add(embeddings)

        out_dir = config.STORAGE_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        # 한글 경로에 직접 쓰면 faiss가 EILSEQ로 실패하므로 헬퍼로 저장한다.
        faiss_io.write_index(index, out_dir / "faiss.index")
        with open(out_dir / "metadata.jsonl", "w", encoding="utf-8") as f:
            for m in service_metadata:
                f.write(json.dumps(m, ensure_ascii=False) + "\n")
        with open(out_dir / "vector_metadata.jsonl", "w", encoding="utf-8") as f:
            for m in vector_metadata:
                f.write(json.dumps(m, ensure_ascii=False) + "\n")

        s.update(
            state="done", step=4, progress=1,
            finished_at=time.time(),
            message=(
                f"완료: 서비스 {len(service_metadata)}건 / "
                f"벡터 청크 {index.ntotal}건 (스킵 {skipped}개)"
            ),
        )
        if on_complete:
            on_complete()

    except Exception as exc:
        s.update(state="error", finished_at=time.time(), message=str(exc))
