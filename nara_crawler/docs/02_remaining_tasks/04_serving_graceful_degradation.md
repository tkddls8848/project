# 04. Serving Graceful Degradation

## 목적

`03_semantic`은 선택 계층이다. 따라서 `03_semantic`이 없어도 serving 생성은 실패하면 안 된다.

## 정책

```text
03_semantic 없음
  -> 02_catalog만 사용
  -> domain_ids = []
  -> concept_ids = []

03_semantic 있음
  -> 있는 파일만 반영

03_semantic 일부 파일 깨짐
  -> 해당 파일만 무시
  -> quality_report.json에 기록
  -> 전체 생성은 계속 진행
```

## 구현할 코드

현재 구조 유지 시:

```text
stage3_serving/main.py
```

추후 분리 시 권장 이름:

```text
stage4_serving/main.py
```

`stage4_output`이라는 이름은 사용하지 않는다.

## 실행 명령

```powershell
python .\stage3_serving\main.py
```

## 완료 기준

`data/03_semantic` 폴더가 비어 있어도 아래 파일이 생성된다.

```text
data/04_serving/retrieval_chunks.jsonl
data/04_serving/recommender_catalog.jsonl
data/04_serving/api_tool_specs.jsonl
data/04_serving/quality_report.json
```

