# 06. DuckDB 인덱스 생성

## 목적

JSONL을 SQL로 조회하고 품질 검증하기 위해 DuckDB 파일을 만든다.

## 구현할 코드

```text
stage5_indexes/
  __init__.py
  main.py
  builders/
    __init__.py
    duckdb_builder.py
```

## requirements 추가

```text
duckdb
```

## 출력

```text
data/05_indexes/duckdb/nara.duckdb
```

## 실행 명령

```powershell
python .\stage5_indexes\main.py --build duckdb
```

## 완료 기준

`nara.duckdb`가 생성되고 `services`, `documents`, `retrieval_chunks`를 조회할 수 있다.

