# 03. 03_semantic 최소 구현

## 목적

부처 간 용어 차이, 필드명 차이, 서비스 의미 차이를 관리할 최소 semantic 계층을 만든다.

## 구현할 코드

```text
stage3_semantic/
  __init__.py
  main.py
  utils/
    __init__.py
    jsonl.py
    text_rules.py
```

## 출력

```text
data/03_semantic/taxonomy.json
data/03_semantic/concepts.jsonl
data/03_semantic/aliases.jsonl
data/03_semantic/service_tags.jsonl
data/03_semantic/agency_glossary.jsonl
```

## MVP 규칙

- LLM은 쓰지 않는다.
- 규칙 기반으로만 만든다.
- 확신이 낮은 것은 `review_status: "pending"`으로 둔다.

## 실행 명령

```powershell
python .\stage3_semantic\main.py
```

## 완료 기준

아래 파일이 비어 있지 않다.

```text
data/03_semantic/taxonomy.json
data/03_semantic/concepts.jsonl
data/03_semantic/service_tags.jsonl
```

