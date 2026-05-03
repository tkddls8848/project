# 08. ChromaDB 인덱스 생성

## 목적

사용자 자연어 질문과 RAG chunk를 벡터 검색으로 매칭하기 위해 ChromaDB 인덱스를 만든다.

## requirements 추가

```text
chromadb
```

## 입력

```text
data/04_serving/retrieval_chunks.jsonl
```

## 출력

```text
data/05_indexes/chroma/
```

## Collection 이름

```text
public_services
```

## 실행 명령

```powershell
python .\stage5_indexes\main.py --build chroma
```

## 완료 기준

ChromaDB collection에 `retrieval_chunks.jsonl`의 chunk가 적재된다.

