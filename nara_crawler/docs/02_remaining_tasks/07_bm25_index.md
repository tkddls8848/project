# 07. BM25 인덱스 생성

## 목적

명확한 키워드 기반 후보 검색을 위해 BM25 인덱스를 만든다.

## 토크나이저 결정

MVP 기본 토크나이저:

```text
kiwipiepy
```

이유:

- Python 패키지로 설치가 비교적 단순하다.
- KoNLPy처럼 Java/JVM 의존성이 없다.
- 개인 MVP 관리 비용이 낮다.

fallback:

```text
kiwipiepy 설치 실패
  -> 정규식 기반 토큰화 사용
  -> quality report에 기록
```

## requirements 추가

```text
rank-bm25
kiwipiepy
```

## 출력

```text
data/05_indexes/bm25/services/
data/05_indexes/bm25/retrieval_chunks/
```

## 실행 명령

```powershell
python .\stage5_indexes\main.py --build bm25
```

## 완료 기준

BM25 index와 id mapping 파일이 생성된다.

