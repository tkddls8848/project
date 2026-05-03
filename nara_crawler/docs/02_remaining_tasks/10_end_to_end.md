# 10. 전체 End-to-End 검증

## 목적

크롤링부터 semantic, serving, index까지 전체 파이프라인을 검증한다.

## 실행 명령

```powershell
python .\stage1_raw\main.py openapi -s 15000017 -e 15000020
python .\stage2_catalog\main.py --crawl-run-id {crawl_run_id}
python .\stage3_semantic\main.py
python .\stage3_serving\main.py
python .\stage5_indexes\main.py --build duckdb
python .\stage5_indexes\main.py --build bm25
python .\stage5_indexes\main.py --build chroma
```

## 최종 확인 파일

```text
data/01_raw/crawl_runs/{crawl_run_id}/manifest.json
data/02_catalog/services.jsonl
data/02_catalog/fields.jsonl
data/03_semantic/concepts.jsonl
data/03_semantic/service_tags.jsonl
data/04_serving/retrieval_chunks.jsonl
data/04_serving/recommender_catalog.jsonl
data/05_indexes/duckdb/nara.duckdb
data/05_indexes/bm25/
data/05_indexes/chroma/
data/99_reports/
```

## 완료 기준

위 파일들이 생성되고, `stage3_serving`이 semantic 유무와 관계없이 동작한다.

