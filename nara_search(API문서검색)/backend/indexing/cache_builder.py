"""
서버 시작 시 자동 실행되는 캐시 빌더.
documents.jsonl + faiss.index + meta.jsonl 이 모두 있으면 스킵.
"""
import glob
import json
import urllib.request
from pathlib import Path

import numpy as np

from ..core import config

RAW_GLOB = str(config.BASE_DIR / "data" / "01_raw" / "*" / "openapi_new" / "*.json")
BATCH_SIZE = 32
MAX_TEXT_LEN = 2048

CATEGORIES = [
    "공공행정", "과학기술", "교육", "교통물류", "국토관리",
    "농축수산", "문화관광", "법률", "보건의료", "사회복지",
    "산업고용", "식품건강", "재난안전", "재정금융", "통일외교안보", "환경기상",
]


def normalize_category(raw: str) -> str:
    primary = raw.split("-")[0].strip()
    for cat in CATEGORIES:
        if primary in cat or cat.startswith(primary):
            return cat
    return primary


def _extract_text(raw: dict) -> str:
    info = raw.get("info") or {}
    swagger = raw.get("swagger_json") or {}
    endpoints = raw.get("endpoints") or []

    parts = [
        info.get("목록명", ""),
        info.get("설명", ""),
        info.get("키워드", ""),
        normalize_category(info.get("분류체계", "")),
        info.get("제공기관", ""),
    ]
    for ep in endpoints[:5]:
        parts.append(f"{ep.get('method','')} {ep.get('path','')} {ep.get('description','')}".strip())
    for path, spec in (swagger.get("paths") or {}).items():
        for method, op in spec.items():
            if not isinstance(op, dict):
                continue
            summary = op.get("summary") or op.get("description") or ""
            if summary:
                parts.append(f"{method.upper()} {path} {summary}")
            for param in op.get("parameters") or []:
                if isinstance(param, dict) and param.get("description"):
                    parts.append(param["description"])
    return " ".join(p for p in parts if p and p.strip() and p != "-")


def _embed_batch(texts: list[str]) -> np.ndarray:
    payload = json.dumps({"model": config.OLLAMA_EMBED_MODEL, "input": texts}).encode()
    req = urllib.request.Request(
        f"{config.OLLAMA_BASE_URL}/api/embed",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())
    vecs = np.array(data["embeddings"], dtype="float32")
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    return vecs / np.maximum(norms, 1e-9)


def extract(force: bool = False) -> int:
    if not force and config.MINIMAL_DOCS_PATH.exists():
        count = sum(1 for _ in config.MINIMAL_DOCS_PATH.open(encoding="utf-8") if _.strip())
        print(f"[cache] documents.jsonl 이미 존재 ({count}개) — 스킵")
        return count

    files = sorted(glob.glob(RAW_GLOB))
    if not files:
        print(f"[cache] 원시 데이터 없음: {RAW_GLOB}")
        return 0

    config.MINIMAL_DIR.mkdir(parents=True, exist_ok=True)
    count = 0
    with config.MINIMAL_DOCS_PATH.open("w", encoding="utf-8") as out:
        for fpath in files:
            with open(fpath, encoding="utf-8") as f:
                raw = json.load(f)
            info = raw.get("info") or {}
            api_id = raw.get("api_id", "")
            text = _extract_text(raw)
            if not api_id or not text:
                continue
            doc = {
                "id": api_id,
                "title": info.get("목록명", ""),
                "url": raw.get("crawled_url", ""),
                "provider": info.get("제공기관", ""),
                "category": normalize_category(info.get("분류체계", "")),
                "description": (info.get("설명") or "")[:500],
                "keywords": info.get("키워드", ""),
                "text": text,
            }
            out.write(json.dumps(doc, ensure_ascii=False) + "\n")
            count += 1

    print(f"[cache] 추출 완료: {count}개 → {config.MINIMAL_DOCS_PATH}")
    return count


def build_index(force: bool = False) -> bool:
    if not force and config.FAISS_INDEX_PATH.exists() and config.MINIMAL_META_PATH.exists():
        print("[cache] faiss.index 이미 존재 — 스킵")
        return True

    try:
        import faiss
    except ImportError:
        print("[cache] faiss-cpu 없음. pip install faiss-cpu")
        return False

    if not config.MINIMAL_DOCS_PATH.exists():
        print("[cache] documents.jsonl 없음. extract 먼저 실행 필요")
        return False

    docs = []
    with config.MINIMAL_DOCS_PATH.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                docs.append(json.loads(line))

    print(f"[cache] 임베딩 시작: {len(docs)}개 (모델: {config.OLLAMA_EMBED_MODEL})")
    all_vecs: list[np.ndarray] = []
    for i in range(0, len(docs), BATCH_SIZE):
        batch = docs[i : i + BATCH_SIZE]
        texts = [d["text"][:MAX_TEXT_LEN] for d in batch]
        try:
            vecs = _embed_batch(texts)
        except Exception as exc:
            print(f"[cache] 임베딩 오류: {exc}")
            return False
        all_vecs.append(vecs)
        done = min(i + BATCH_SIZE, len(docs))
        print(f"[cache]   {done}/{len(docs)}", end="\r")
    print()

    matrix = np.vstack(all_vecs)
    index = faiss.IndexFlatIP(matrix.shape[1])
    index.add(matrix)
    config.MINIMAL_DIR.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(config.FAISS_INDEX_PATH))
    print(f"[cache] FAISS 저장: {config.FAISS_INDEX_PATH} (dim={matrix.shape[1]}, n={index.ntotal})")

    with config.MINIMAL_META_PATH.open("w", encoding="utf-8") as f:
        for doc in docs:
            meta = {k: doc.get(k, "") for k in ("id", "title", "url", "provider", "category", "description", "keywords")}
            f.write(json.dumps(meta, ensure_ascii=False) + "\n")
    print(f"[cache] 메타 저장: {config.MINIMAL_META_PATH}")
    return True


def ensure_cache() -> None:
    """서버 시작 시 호출. 캐시가 없으면 자동 빌드."""
    extract()
    build_index()
