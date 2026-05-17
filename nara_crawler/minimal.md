# 최소 API 문서 검색 서비스 계획

## 목표

자연어 질의 → 적절한 API 문서 반환

## 데이터 현황 (openapi_new 기준)

- 총 3,526개 JSON 파일
- 설명 보유: 200/200 (100%)
- 키워드 보유: 200/200 (100%)
- 엔드포인트 보유: 195/200 (97.5%)

## 파이프라인

```
01_raw/*.json
    │
    ▼ extract.py
documents.jsonl  (id, title, url, text)
    │
    ▼ embed.py
vectors.npy + meta.jsonl
    │
    ▼ search.py
top-k API 문서
```

## Step 1 — extract.py

**입력**: `data/01_raw/*/openapi_new/*.json`  
**출력**: `data/minimal/documents.jsonl`

각 JSON 파일에서 다음 필드를 이어 붙여 단일 텍스트 생성:

| 소스 필드 | 설명 |
|-----------|------|
| `info.목록명` | API 제목 |
| `info.설명` | 상세 설명 |
| `info.키워드` | 키워드 목록 |
| `info.분류체계` | 도메인 카테고리 (정규화 후 추가) |
| `info.제공기관` | 제공 기관명 |
| `endpoints[].method + path + description` | 엔드포인트 요약 (최대 5개) |
| `swagger_json.paths` 내 `summary` | swagger 엔드포인트 요약 |

### 분류체계 정규화 (category.md 활용)

`info.분류체계` 값(`"환경 - 환경일반"`)의 앞 단어를 추출해 16개 표준 카테고리로 매핑한 뒤 텍스트에 추가한다.

```python
CATEGORIES = [
    "공공행정", "과학기술", "교육", "교통물류", "국토관리",
    "농축수산", "문화관광", "법률", "보건의료", "사회복지",
    "산업고용", "식품건강", "재난안전", "재정금융", "통일외교안보", "환경기상",
]

def normalize_category(raw: str) -> str:
    # "환경 - 환경일반" -> "환경기상"
    primary = raw.split("-")[0].strip()
    for cat in CATEGORIES:
        if primary in cat or cat.startswith(primary):
            return cat
    return primary
```

`공통표준용어_최종.csv`, `공통표준단어_점검.csv`는 미사용.

> **이유**: 공통표준용어는 DB 컬럼 설계 기준이라 REST API 파라미터 description과 어휘가 달라 매칭률 5% 수준. 부처간 파라미터 표현 불일치(`sidoCd` / `SIDO_CD` / `region`)의 시멘틱 통일은 임베딩 모델(BAAI/bge-m3)이 벡터 공간에서 자연히 처리한다.

출력 레코드 스키마:

```json
{
  "id": "15001698",
  "title": "건강보험심사평가원_병원정보서비스",
  "url": "https://www.data.go.kr/data/15001698/openapi.do",
  "text": "건강보험심사평가원_병원정보서비스 건강보험심사평가원에서 관리하는 병원 정보를 조회하는 서비스입니다. ..."
}
```

## Step 2 — embed.py

**입력**: `data/minimal/documents.jsonl`  
**출력**: `data/minimal/vectors.npy`, `data/minimal/meta.jsonl`

- 모델: `BAAI/bge-m3` (한국어·영어 동시 처리, 무료)
- 배치 처리로 전체 3,526개 임베딩 생성
- `vectors.npy`: shape `(N, 1024)` float32
- `meta.jsonl`: id, title, url (검색 결과 반환용)

## Step 3 — search.py

**입력**: 자연어 쿼리 문자열  
**출력**: top-k API 메타데이터 목록

```
쿼리 → 임베딩 → FAISS 코사인 유사도 검색 → top-k 반환
```

- 인덱스: `faiss.IndexFlatIP` (내적 = 정규화 후 코사인)
- 기본 k=10

## 파일 구조

```
nara_crawler/
├── minimal/
│   ├── extract.py
│   ├── embed.py
│   └── search.py
└── data/
    └── minimal/
        ├── documents.jsonl
        ├── vectors.npy
        └── meta.jsonl
```

## 버리는 것 (기존 Stage2~4 대비)

| 기존 컴포넌트 | 제거 이유 |
|--------------|-----------|
| Stage2 agency / field 레코드 | 검색에 불필요 |
| Stage3 공통표준용어 매핑 | 임베딩 모델이 의미 처리 |
| Stage3 RULE_CONCEPTS | 임베딩 모델이 의미 처리 |
| Stage4 청크 3종 분리 | 단일 청크로 충분 |

## 이후 점진 개선 (성능 부족 시에만)

1. **엔드포인트별 청크 분리** — 기능이 많은 API 대응
2. **BM25 + 벡터 하이브리드** — 고유명사·기관명 키워드 정확도 보완
3. **Cross-encoder 리랭킹** — top-k 재정렬로 정밀도 향상

## 의존성

```
sentence-transformers
faiss-cpu
```
