# 05. Semantic 태그를 Serving에 반영

## 목적

검색과 추천 품질을 높이기 위해 `03_semantic`의 개념 태그를 `04_serving` 산출물에 반영한다.

## 입력

```text
data/03_semantic/service_tags.jsonl
data/03_semantic/aliases.jsonl
data/03_semantic/field_mappings.jsonl
```

## 반영 위치

```text
retrieval_chunks.jsonl
  domain_ids
  concept_ids
  search_keywords
  search_text

recommender_catalog.jsonl
  domain_ids
  concept_ids
  search_keywords
```

## 실행 명령

```powershell
python .\stage3_semantic\main.py
python .\stage3_serving\main.py
```

## 완료 기준

일부 chunk라도 다음 필드가 채워진다.

```json
{
  "domain_ids": ["business"],
  "concept_ids": ["target.small_business_owner"]
}
```

