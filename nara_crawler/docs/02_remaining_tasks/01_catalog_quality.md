# 01. Stage 2 Catalog 품질 확인

## 목적

`03_semantic`과 `04_serving`은 `02_catalog`를 기반으로 만든다. 따라서 먼저 catalog 품질을 확인해야 한다.

## 구현할 코드

```text
stage2_catalog/reports/
  __init__.py
  catalog_quality_report.py
```

## 입력

```text
data/02_catalog/services.jsonl
data/02_catalog/documents.jsonl
data/02_catalog/endpoints.jsonl
data/02_catalog/fields.jsonl
```

## 출력

```text
data/99_reports/catalog/catalog_quality_report.json
data/99_reports/catalog/field_frequency.json
data/99_reports/catalog/field_extraction_quality.json
```

## 확인 항목

- services/documents/endpoints/fields 건수
- service_id 중복 여부
- endpoint 없는 openapi 서비스 수
- field 없는 endpoint 수
- 필수 메타데이터 누락 수
- 한글 깨짐 의심 텍스트 수

## 실행 명령

```powershell
python .\stage2_catalog\main.py --include-legacy --data-type openapi
python .\stage2_catalog\reports\catalog_quality_report.py
```

## 완료 기준

`data/99_reports/catalog/catalog_quality_report.json`과 `field_frequency.json`이 생성된다.

