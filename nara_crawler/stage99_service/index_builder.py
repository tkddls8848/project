"""
FAISS 인덱스 빌드 로직. build_index.py 와 동일한 기능을 서비스 내부에서 제공한다.
"""
import json
import threading
import time
from pathlib import Path

import faiss
from sentence_transformers import SentenceTransformer

from . import config


# ── 데이터 경로 탐색 ─────────────────────────────────────────────────────────

def find_latest_openapi_dir(data_dir: Path) -> Path:
    raw_dir = data_dir / "01_raw"
    if not raw_dir.exists():
        raise FileNotFoundError(f"01_raw 디렉터리가 없습니다: {raw_dir}")
    candidates = sorted(
        (p for p in raw_dir.iterdir() if p.is_dir() and (p / "openapi_new").is_dir()),
        key=lambda p: p.name,
    )
    if not candidates:
        raise FileNotFoundError(f"openapi_new 폴더를 가진 디렉터리가 없습니다: {raw_dir}")
    return candidates[-1] / "openapi_new"


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


def _build_search_text(doc):
    info = doc.get("info") or {}
    swagger = doc.get("swagger_json") or {}
    swagger_info = swagger.get("info") or {}

    title       = _safe_get(info, "목록명") or _safe_get(swagger_info, "title")
    provider    = _safe_get(info, "제공기관")
    category    = _safe_get(info, "분류체계")
    keywords    = _safe_get(info, "키워드")
    description = _safe_get(info, "설명") or _safe_get(swagger_info, "description")

    parts = []
    if title:       parts.append(f"[제목] {title}")
    if provider:    parts.append(f"[기관] {provider}")
    if category:    parts.append(f"[분류] {category}")
    if keywords:    parts.append(f"[키워드] {keywords}")
    if description: parts.append(f"[설명] {description}")

    endpoint_lines = []
    for ep in (doc.get("endpoints") or []):
        line = f"- {ep.get('method','')} {ep.get('path','')}"
        if ep.get("description"):
            line += f" : {ep['description']}"
        endpoint_lines.append(line)
    if endpoint_lines:
        parts.append("[엔드포인트]\n" + "\n".join(endpoint_lines))

    field_descs = _extract_field_descriptions(swagger)
    if field_descs:
        parts.append("[응답필드] " + ", ".join(field_descs))

    return "\n".join(parts)


def _extract_metadata(doc, source_path):
    info = doc.get("info") or {}
    swagger_info = (doc.get("swagger_json") or {}).get("info") or {}
    description = _safe_get(info, "설명") or _safe_get(swagger_info, "description")
    return {
        "api_id":         doc.get("api_id", ""),
        "title":          _safe_get(info, "목록명") or _safe_get(swagger_info, "title"),
        "provider":       _safe_get(info, "제공기관"),
        "category":       _safe_get(info, "분류체계"),
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
                "elapsed_s": elapsed,
            }


build_status = BuildStatus()


# ── 빌드 실행 ────────────────────────────────────────────────────────────────

def run_build(on_complete=None):
    """백그라운드 스레드에서 실행. 완료 후 on_complete() 호출."""
    s = build_status
    s.update(state="running", started_at=time.time(), finished_at=None,
             step=0, progress=0, total=0, message="시작 중...")
    try:
        # 1단계: 파일 탐색
        s.update(step=1, step_name="파일 탐색")
        openapi_dir = find_latest_openapi_dir(config.DATA_DIR)
        s.update(data_path=str(openapi_dir), message=f"탐색 중: {openapi_dir}")
        json_files = sorted(openapi_dir.glob("**/*.json"))
        if not json_files:
            raise FileNotFoundError("JSON 파일이 없습니다.")
        s.update(total=len(json_files), message=f"{len(json_files)}개 파일 발견")

        # 2단계: JSON 파싱
        s.update(step=2, step_name="JSON 파싱", progress=0)
        texts, metadata_list, skipped = [], [], 0
        for i, fp in enumerate(json_files):
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    doc = json.load(f)
                text = _build_search_text(doc)
                if not text.strip():
                    skipped += 1
                else:
                    texts.append(text)
                    metadata_list.append(_extract_metadata(doc, fp))
            except Exception:
                skipped += 1
            s.update(progress=i + 1,
                     message=f"파싱 중 {i+1}/{len(json_files)} (스킵 {skipped})")

        s.update(message=f"파싱 완료: {len(texts)}건 / 스킵 {skipped}건")

        # 3단계: 임베딩
        s.update(step=3, step_name="임베딩 생성", progress=0, total=len(texts))
        model = SentenceTransformer(config.LOCAL_MODEL_PATH)

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
            s.update(progress=done, message=f"임베딩 {done}/{len(texts)}")
        embeddings = np.vstack(all_embeddings)

        # 4단계: 인덱스 저장
        s.update(step=4, step_name="인덱스 저장", progress=0, total=1)
        dim = embeddings.shape[1]
        index = faiss.IndexFlatIP(dim)
        index.add(embeddings)

        out_dir = config.STORAGE_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        faiss.write_index(index, str(out_dir / "faiss.index"))
        with open(out_dir / "metadata.jsonl", "w", encoding="utf-8") as f:
            for m in metadata_list:
                f.write(json.dumps(m, ensure_ascii=False) + "\n")

        s.update(
            state="done", step=4, progress=1,
            finished_at=time.time(),
            message=f"완료: {index.ntotal}개 문서 인덱싱 (스킵 {skipped}개)",
        )
        if on_complete:
            on_complete()

    except Exception as exc:
        s.update(state="error", finished_at=time.time(), message=str(exc))
