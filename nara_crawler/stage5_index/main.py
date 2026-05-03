"""
Stage 5: retrieval_chunks.jsonl → ChromaDB 적재

Usage:
    python stage5_index/main.py [--reset] [--batch-size 500] [--model MODEL]

Options:
    --reset         기존 컬렉션을 삭제 후 재생성 (재적재 시 사용)
    --batch-size N  upsert 배치 크기 (기본 500)
    --model NAME    sentence-transformers 모델명
                    기본: paraphrase-multilingual-MiniLM-L12-v2 (한국어 지원)
    --dry-run       실제 적재 없이 파일 파싱과 통계만 출력
"""
import argparse
import json
import os
import sys
from pathlib import Path
from typing import Iterable

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(CURRENT_DIR)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

COLLECTION_NAME = "public_services"
DEFAULT_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
DEFAULT_BATCH_SIZE = 500


# ── 파일 읽기 ──────────────────────────────────────────────────────────────

def read_jsonl(path: Path) -> list[dict]:
    records = []
    with path.open("r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"  [warn] {path.name}:{lineno} JSON 파싱 실패 — {e}")
    return records


# ── 메타데이터 변환 ────────────────────────────────────────────────────────
# ChromaDB metadata는 list 미지원 → comma 구분 문자열로 저장
# 조회: where={"agency_ids": {"$contains": "B552520"}}

def _list_to_str(values: list | None) -> str:
    if not values:
        return ""
    return ",".join(str(v) for v in values if v)


def build_metadata(chunk: dict) -> dict:
    service_id = chunk.get("service_id", "")
    data_type = service_id.split(":")[0] if ":" in service_id else ""
    return {
        "service_id":  service_id,
        "chunk_type":  chunk.get("chunk_type", "overview"),
        "data_type":   data_type,
        "agency_ids":  _list_to_str(chunk.get("agency_ids")),
        "domain_ids":  _list_to_str(chunk.get("domain_ids")),
        "concept_ids": _list_to_str(chunk.get("concept_ids")),
        "source_path": chunk.get("source_path", ""),
    }


# ── 배치 분할 ──────────────────────────────────────────────────────────────

def batched(items: list, size: int) -> Iterable[list]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


# ── 적재기 ────────────────────────────────────────────────────────────────

class ChromaLoader:
    def __init__(self, base_dir: Path, model: str, batch_size: int, reset: bool):
        self.batch_size = batch_size
        chroma_path = str(base_dir / "data" / "05_indexes" / "chroma")

        print(f"ChromaDB path : {chroma_path}")
        print(f"Embedding model: {model}")

        self.client = chromadb.PersistentClient(path=chroma_path)
        ef = SentenceTransformerEmbeddingFunction(model_name=model)

        if reset:
            try:
                self.client.delete_collection(COLLECTION_NAME)
                print(f"  기존 컬렉션 '{COLLECTION_NAME}' 삭제 완료")
            except Exception:
                pass

        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=ef,
            metadata={"hnsw:space": "cosine"},
        )
        print(f"  컬렉션 '{COLLECTION_NAME}' 현재 문서 수: {self.collection.count()}")

    def load(self, chunks: list[dict]) -> dict:
        total_input = len(chunks)

        # 텍스트 비어 있는 청크 제외
        valid = [c for c in chunks if c.get("text", "").strip()]
        skipped_empty = total_input - len(valid)

        # chunk_id 누락 청크 제외
        valid = [c for c in valid if c.get("chunk_id")]
        skipped_no_id = (total_input - skipped_empty) - len(valid)

        total = len(valid)
        print(f"\n  전체 청크: {total_input}")
        if skipped_empty:
            print(f"  텍스트 없음(인코딩 깨짐 등) 제외: {skipped_empty}")
        if skipped_no_id:
            print(f"  chunk_id 누락 제외: {skipped_no_id}")
        print(f"  적재 대상: {total}")

        upserted = 0
        for batch in batched(valid, self.batch_size):
            ids       = [c["chunk_id"] for c in batch]
            documents = [c.get("text", "") for c in batch]
            metadatas = [build_metadata(c) for c in batch]
            self.collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
            upserted += len(batch)
            print(f"  upsert {upserted}/{total} ...", end="\r")

        final_count = self.collection.count()
        print(f"\n  완료. 컬렉션 전체 문서 수: {final_count}")
        return {
            "total_input": total_input,
            "skipped_empty_text": skipped_empty,
            "skipped_no_id": skipped_no_id,
            "upserted": upserted,
            "collection_total": final_count,
        }


# ── 검색 샘플 테스트 ──────────────────────────────────────────────────────

def run_sample_query(collection, query: str, n: int = 3) -> None:
    print(f"\n[샘플 검색] '{query}'")
    results = collection.query(query_texts=[query], n_results=min(n, collection.count()))
    for i, (doc_id, doc, meta) in enumerate(zip(
        results["ids"][0],
        results["documents"][0],
        results["metadatas"][0],
    ), 1):
        snippet = doc[:80].replace("\n", " ")
        print(f"  {i}. [{meta.get('service_id')}] {snippet}...")


# ── 진입점 ────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 4: retrieval_chunks → ChromaDB")
    parser.add_argument("--reset",      action="store_true", help="기존 컬렉션 삭제 후 재생성")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE, metavar="N")
    parser.add_argument("--model",      default=DEFAULT_MODEL, help="sentence-transformers 모델명")
    parser.add_argument("--dry-run",    action="store_true", help="파싱/통계만 출력, 실제 적재 안 함")
    args = parser.parse_args()

    base_dir = Path(BASE_DIR)
    chunks_path = base_dir / "data" / "04_serving" / "retrieval_chunks.jsonl"

    if not chunks_path.exists():
        print(f"[error] 파일 없음: {chunks_path}")
        print("  먼저 stage4_output/main.py 를 실행하세요.")
        sys.exit(1)

    print(f"Reading: {chunks_path}")
    chunks = read_jsonl(chunks_path)
    print(f"  파싱된 청크 수: {len(chunks)}")

    if args.dry_run:
        valid = [c for c in chunks if c.get("text", "").strip() and c.get("chunk_id")]
        print(f"  [dry-run] 적재 대상: {len(valid)} / {len(chunks)}")
        print("  실제 적재 없이 종료합니다.")
        return

    loader = ChromaLoader(
        base_dir=base_dir,
        model=args.model,
        batch_size=args.batch_size,
        reset=args.reset,
    )
    stats = loader.load(chunks)

    # 적재 후 샘플 검색
    if stats["upserted"] > 0:
        run_sample_query(loader.collection, "소상공인 지원")
        run_sample_query(loader.collection, "도로 교통 정보")

    print("\nStage 4 complete")
    for k, v in stats.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
