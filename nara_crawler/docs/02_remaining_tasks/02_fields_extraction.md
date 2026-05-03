# 02. fields.jsonl 추출 보강

## 목적

`field_mappings.jsonl`을 만들려면 먼저 `02_catalog/fields.jsonl`에 충분한 필드가 들어와야 한다.

## 구현할 코드

```text
stage2_catalog/managers/catalog_extractors.py
```

## 보강 대상

- Swagger request parameter
- Swagger request body
- Swagger response schema
- `openapi_old`의 `api_details`
- standard grid/table field

## 이번 단계에서 하지 않을 일

아직 `field_mappings.jsonl`은 만들지 않는다. 먼저 `fields.jsonl` 자체를 풍부하게 만든다.

## 실행 명령

```powershell
python .\stage2_catalog\main.py --include-legacy --data-type openapi
```

## 완료 기준

- `data/02_catalog/fields.jsonl`이 비어 있지 않다.
- `data/99_reports/catalog/field_frequency.json`에서 상위 필드를 확인할 수 있다.

