# 남은 구현 과제 목차

이 파일은 남은 구현 과제의 목차다. 실제 구현 계획은 단계별 파일로 분리한다.

## 현재 상태

```text
stage1_raw      -> data/01_raw 생성
stage2_catalog  -> data/02_catalog 생성
stage3_serving  -> data/04_serving 일부 생성
```

## 분할 문서

1. [Catalog 품질 확인](03_remaining_tasks/01_catalog_quality.md)
2. [fields.jsonl 추출 보강](03_remaining_tasks/02_fields_extraction.md)
3. [03_semantic 최소 구현](03_remaining_tasks/03_semantic_minimum.md)
4. [Serving graceful degradation](03_remaining_tasks/04_serving_graceful_degradation.md)
5. [Semantic 태그를 Serving에 반영](03_remaining_tasks/05_serving_semantic_tags.md)
6. [DuckDB 인덱스 생성](03_remaining_tasks/06_duckdb_index.md)
7. [BM25 인덱스 생성](03_remaining_tasks/07_bm25_index.md)
8. [ChromaDB 인덱스 생성](03_remaining_tasks/08_chromadb_index.md)
9. [deleted 판정 추가](03_remaining_tasks/09_deleted_detection.md)
10. [전체 end-to-end 검증](03_remaining_tasks/10_end_to_end.md)

## 추천 진행 순서

처음에는 아래 5개만 진행한다.

```text
01_catalog_quality
02_fields_extraction
03_semantic_minimum
04_serving_graceful_degradation
05_serving_semantic_tags
```

그 다음 검색 인덱스를 붙인다.

```text
06_duckdb_index
07_bm25_index
08_chromadb_index
```

마지막에 삭제 감지를 붙인다.

```text
09_deleted_detection
10_end_to_end
```

