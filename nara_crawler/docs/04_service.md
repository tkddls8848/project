# 자연어 API 문서 추천 웹 MVP 계획

최종 업데이트: 2026-05-09

## 목적

`stage1_raw`부터 `stage5_index`까지 정제한 공공데이터 API 카탈로그를 기반으로, 사용자가 자연어로 원하는 데이터를 입력하면 관련 API 문서를 찾아 보여주는 간단한 웹 서비스를 만든다.

MVP의 목표는 실제 API 호출 자동화가 아니라 **문서 탐색과 API 후보 추천**이다.

예시 입력:

```text
여행경보 목록을 보고 싶다
문화시설 근처 식당 정보
버스 정류소 위치
응답 필드가 있는 API
사업자등록번호로 조회 가능한 API
```

예시 출력:

```text
1. 외교부_여행경보제도
   - 추천 이유: 여행경보, 국가명, ISO 국가코드 필드가 검색됨
   - endpoint: GET /getTravelWarningListV3
   - 요청 파라미터: serviceKey, pageNo, numOfRows, cond[country_name::EQ], ...
   - 응답 필드: country_name, attention, control, limita, ban_note, ...
   - 원본: data.go.kr 문서/정제 JSON 경로
```

## 현재 사용 가능한 데이터

현재 파이프라인 산출물 기준:

| 산출물 | 역할 |
| --- | --- |
| `data/02_catalog/services.jsonl` | 서비스 기본 정보, 제공기관, 카테고리, 설명 |
| `data/02_catalog/documents.jsonl` | 검색/표시용 문서 본문 |
| `data/02_catalog/endpoints.jsonl` | API endpoint, method, path |
| `data/02_catalog/fields.jsonl` | 요청/응답 필드, 타입, 설명 |
| `data/03_semantic/service_tags.jsonl` | 서비스별 domain/concept 태그 |
| `data/03_semantic/field_mappings.jsonl` | 필드와 표준 용어 후보 매핑 |
| `data/04_serving/retrieval_chunks.jsonl` | ChromaDB 검색 대상 청크와 parent overview |
| `data/04_serving/api_tool_specs.jsonl` | endpoint 단위 API 문서 요약 |
| `data/04_serving/recommender_catalog.jsonl` | 서비스 추천용 요약 catalog |
| `data/05_indexes/chroma/` | ChromaDB 벡터 인덱스 |
| `data/99_reports/rag/retrieval_eval_report.json` | 샘플 질의 top-5 검증 결과 |

현재 ChromaDB에는 `indexable=true` 청크만 적재되어 있다.

```text
overview   indexable=false  사용자 표시/parent merge용
summary    indexable=true   자연어 검색용
api_schema indexable=true   endpoint/field 검색용
```

## MVP 범위

### 포함

- 자연어 검색 입력창
- 검색 결과 top-k API 문서 카드 표시
- 서비스명, 설명, 제공기관, 카테고리 표시
- endpoint/method/path 표시
- 요청 파라미터와 응답 필드 표시
- 검색 근거 표시
  - 매칭된 chunk type
  - domain/concept tag
  - search keyword
  - field match 여부
- 같은 `service_id` 중복 제거
- parent overview를 병합해 사용자에게 읽기 좋은 결과 제공
- 로컬 단일 프로세스로 실행 가능한 웹

### 제외

- 실제 공공데이터 API 호출 자동화
- 사용자 계정/로그인
- 결제/과금
- LLM 기반 답변 생성
- Neo4j/Qdrant 도입
- 사용자 검색 기록 장기 저장

MVP는 사용자 API 키나 OpenAI API 키를 요구하지 않는다. 공공데이터 `serviceKey`는 실제 API 호출 기능을 붙이는 후속 단계에서만 사용자가 직접 입력하게 한다.

## 핵심 판단

현재 `retrieval_eval_report.json`을 보면 dense vector 검색만으로는 정확 키워드 질의가 항상 원하는 API를 1순위로 올리지 못한다. 따라서 MVP 검색은 ChromaDB 단독이 아니라 다음 구조가 필요하다.

```text
사용자 질의
  -> ChromaDB top-N 검색
  -> JSONL lexical 후보 검색
  -> service_id 기준 병합
  -> 점수 보정
  -> API 문서 조립
  -> 웹 응답
```

점수 보정 우선순위:

1. endpoint path, field_name, field description 정확 일치
2. service name/keywords 부분 일치
3. semantic concept/domain 일치
4. ChromaDB distance
5. 같은 service의 summary/api_schema 동시 매칭

## 제안 기술 스택

간단한 로컬 웹으로 시작한다.

| 영역 | 선택 |
| --- | --- |
| Backend | FastAPI |
| Frontend | 정적 HTML/CSS/JS |
| Vector 검색 | 기존 ChromaDB |
| Lexical 검색 | Python 내장 정규화 토큰 매칭 |
| 데이터 저장 | 기존 JSONL + ChromaDB |
| 실행 방식 | `uvicorn service_web.main:app --reload` |

React/Vite는 MVP에서는 보류한다. 먼저 검색 품질과 결과 조립을 확인한 뒤, UI가 복잡해질 때 도입한다.

## 디렉터리 계획

```text
service_web/
  __init__.py
  main.py                 # FastAPI app
  config.py               # 경로/컬렉션명/검색 설정
  schemas.py              # request/response model
  data_loader.py          # JSONL 로딩과 service/endpoint/field 인덱스
  retriever.py            # ChromaDB 검색
  lexical.py              # 키워드/필드/path 기반 lexical 검색
  ranker.py               # 검색 후보 병합/점수 보정
  document_builder.py     # API 문서 응답 조립
  static/
    index.html
    app.js
    styles.css
```

기존 stage 코드는 건드리지 않고, 웹 레이어만 새로 둔다.

## API 설계

### `GET /`

정적 검색 화면을 반환한다.

### `GET /health`

서버와 인덱스 상태를 확인한다.

응답:

```json
{
  "ok": true,
  "services_total": 110,
  "chunks_total": 224,
  "index_collection_total": 114
}
```

### `POST /search`

자연어 질의로 API 문서 후보를 검색한다.

요청:

```json
{
  "query": "여행경보 목록",
  "top_k": 5
}
```

응답:

```json
{
  "query": "여행경보 목록",
  "results": [
    {
      "service_id": "openapi:15000827",
      "name": "외교부_여행경보제도",
      "description": "...",
      "provider_agency_name": "외교부",
      "category": "통일·외교 - 외교",
      "score": 0.91,
      "match_reasons": [
        "summary vector match",
        "endpoint field: country_name",
        "concept: diplomacy.travel_warning"
      ],
      "endpoints": [
        {
          "endpoint_id": "endpoint:openapi:15000827:get:/getTravelWarningListV3",
          "method": "GET",
          "path": "/getTravelWarningListV3",
          "summary": "여행경보제도 목록조회"
        }
      ],
      "request_fields": [
        {
          "name": "serviceKey",
          "type": "string",
          "required": true,
          "description": "공공데이터포털에서 받은 인증키"
        }
      ],
      "response_fields": [
        {
          "name": "country_name",
          "type": "string",
          "description": "국가명"
        }
      ],
      "source": {
        "refined_path": "data/refined_data/openapi_new/openapi_new_15000827_refined.json",
        "raw_path": "data/01_raw/..."
      }
    }
  ]
}
```

### `GET /services/{service_id}`

검색 결과 클릭 시 API 문서 상세를 반환한다.

상세에는 검색 없이도 다음을 표시한다.

- 서비스 기본 정보
- 제공기관
- 원본 data.go.kr URL 또는 refined/raw path
- endpoint 목록
- 요청/응답 필드
- semantic tag
- field mapping

## 검색 파이프라인 상세

### 1. 입력 정규화

- 앞뒤 공백 제거
- 2자 미만 질의 거부
- 최대 길이 제한: 300자
- HTML 태그 제거
- 한글/영문/숫자 토큰 분리

### 2. Vector 후보 검색

ChromaDB `public_services` 컬렉션에서 top-N을 조회한다.

초기값:

```text
vector_top_n = max(top_k * 4, 20)
```

Chroma 결과에서 가져올 정보:

- `chunk_id`
- `service_id`
- `chunk_type`
- `distance`
- `domain_ids`
- `concept_ids`

### 3. Lexical 후보 검색

JSONL 인덱스를 메모리에 올려 질의 토큰을 비교한다.

대상:

- `services.name`
- `services.description`
- `services.keywords`
- `endpoints.path`
- `endpoints.summary`
- `fields.field_name`
- `fields.description`
- `field_mappings.aliases`
- `service_tags.concept_ids`

가중치 초안:

| 매칭 위치 | 가중치 |
| --- | ---: |
| endpoint path 정확 일치 | +0.35 |
| field_name 정확 일치 | +0.30 |
| field description 부분 일치 | +0.25 |
| service name 부분 일치 | +0.25 |
| keyword 일치 | +0.18 |
| concept/domain 일치 | +0.12 |

### 4. 후보 병합

`service_id` 기준으로 vector 후보와 lexical 후보를 합친다.

```text
final_score =
  vector_score * 0.55
  + lexical_score * 0.35
  + schema_score * 0.10
```

ChromaDB distance는 낮을수록 좋으므로 `vector_score = 1 / (1 + distance)` 형태로 변환한다.

### 5. 문서 조립

결과 표시용 데이터는 Chroma metadata만으로 만들지 않는다. 반드시 JSONL source of truth에서 다시 조립한다.

조립 순서:

1. `services.jsonl`에서 서비스 기본 정보
2. `documents.jsonl`에서 본문/요약
3. `endpoints.jsonl`에서 endpoint 목록
4. `fields.jsonl`에서 요청/응답 필드
5. `field_mappings.jsonl`에서 표준 용어 후보
6. `service_tags.jsonl`에서 domain/concept
7. `retrieval_chunks.jsonl`에서 parent overview/display_text

## 화면 계획

첫 화면은 검색 도구 그 자체여야 한다.

```text
┌──────────────────────────────────────────────┐
│ [ 자연어로 찾을 API를 입력 ]        [검색]    │
└──────────────────────────────────────────────┘

추천 API 문서
────────────────────────────────────────────────
외교부_여행경보제도
외교부 · 통일외교안보 · GET /getTravelWarningListV3
여행경보, 국가명, ISO 국가코드 필드가 검색됨

요청 필드: serviceKey, pageNo, numOfRows, ...
응답 필드: country_name, attention, control, ...
[상세 보기]
```

MVP 화면 구성:

- 상단 검색 입력
- 좌측 결과 목록
- 우측 상세 패널 또는 하단 상세 영역
- endpoint/field는 접을 수 있는 섹션
- 점수는 내부 검증용으로 작게 표시하거나 개발 모드에서만 표시

## 구현 단계

### Phase 1. 검색 API 골격

완료 기준:

- `service_web/main.py` 생성
- `/health`, `/search`, `/services/{service_id}` 동작
- JSONL 로더가 stage 산출물을 읽음
- ChromaDB 연결 실패 시 명확한 오류 반환

### Phase 2. 결과 조립

완료 기준:

- 검색 결과에 서비스명/설명/기관/카테고리 표시
- endpoint path/method 표시
- request/response field 분리 표시
- parent overview 병합
- 같은 service 중복 제거

### Phase 3. Hybrid ranking

완료 기준:

- ChromaDB top-N 결과 사용
- lexical 후보 검색 추가
- endpoint path, field_name, field description 가중치 반영
- `retrieval_eval_report.json`의 9개 샘플 질의로 결과 확인

### Phase 4. 정적 웹 UI

완료 기준:

- `/`에서 검색 UI 제공
- 검색 중 loading 표시
- 결과 없음 상태 표시
- 결과 클릭 시 상세 표시
- 긴 필드 목록은 접기/펼치기 가능

### Phase 5. 운영 전 점검

완료 기준:

- 입력 길이 제한
- HTML escape 처리
- 에러 응답 형식 통일
- ChromaDB 미생성 시 stage5 실행 안내
- 데이터 갱신 후 서버 재시작 없이 reload 가능한지 결정

## 실행 명령 계획

개발 실행:

```powershell
python -m uvicorn service_web.main:app --reload --host 127.0.0.1 --port 8000
```

파이프라인 재생성:

```powershell
python stage2_catalog\main.py
python stage3_semantic\main.py
python stage4_output\main.py
python stage5_index\main.py --reset
```

검색 API 테스트:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/search `
  -ContentType "application/json" `
  -Body '{"query":"여행경보 목록","top_k":5}'
```

## 품질 기준

우선 다음 질의에서 기대 결과가 top-5 안에 들어오는지 본다.

| 질의 | 기대 결과 예시 |
| --- | --- |
| 여행경보 목록 | 외교부_여행경보제도 |
| 문화시설 식당 정보 | 문화시설 식당 API |
| 문화시설 여행지 상세 | 문화시설 여행지 API |
| 버스 정류소 위치 | 전주시 승강장/실시간 운행정보 |
| 응답 필드 | api_schema 청크가 있는 서비스 |
| endpoint path | endpoint path가 표시되는 문서 |
| 사업자등록번호 | field/standard term 기반 후보 또는 결과 없음 사유 |

결과 없음도 실패가 아니다. 중요한 것은 “왜 못 찾았는지”를 표시하는 것이다.

예:

```text
현재 정제된 fields.jsonl에는 사업자등록번호 필드가 없습니다.
표준 용어 사전에는 term:BIZRNO 후보가 있으므로, 해당 필드를 가진 API가 수집되면 매칭 가능합니다.
```

## 보안과 비용 원칙

- MVP에서는 LLM API를 사용하지 않는다.
- 사용자 API 키를 저장하지 않는다.
- 공공데이터 `serviceKey` 입력 기능은 후속 단계로 둔다.
- 입력 문자열은 길이 제한과 HTML escape를 적용한다.
- CORS는 로컬 개발 origin만 허용한다.
- 검색 API에는 간단한 rate limit을 둘 수 있게 구조만 열어둔다.

## 후속 확장

### 실제 API 호출

검색 결과에서 사용자가 `serviceKey`를 직접 입력하면 endpoint를 호출해 샘플 응답을 보여준다.

필요 조건:

- 공공데이터 포털 API 키를 브라우저 localStorage 또는 세션에만 저장
- 서버 로그에 serviceKey를 남기지 않음
- endpoint별 필수 파라미터 검증

### 사용자 친화 답변

LLM을 붙이더라도 기본 검색/문서 조립은 유지한다.

```text
검색 결과 JSON
  -> LLM 요약
  -> 사용자가 확인할 API 문서와 함께 표시
```

LLM API 키는 사용자가 직접 입력하는 BYOK 방식으로 둔다.

### BM25 도입

정확 키워드 질의가 계속 약하면 BM25를 추가한다.

도입 후보:

- `rank-bm25`
- SQLite FTS5
- DuckDB + token table

### 데이터 확대

현재 endpoint/field가 있는 서비스가 일부에 그치므로, stage1/2에서 더 많은 `openapi_new` Swagger를 수집할수록 검색 품질이 좋아진다.

## 최종 완료 기준

MVP 완료 상태:

```text
service_web/main.py                         FastAPI 앱 실행 가능
service_web/data_loader.py                  JSONL source of truth 로딩
service_web/retriever.py                    ChromaDB 검색
service_web/lexical.py                      path/field/name 키워드 검색
service_web/ranker.py                       service_id dedupe 및 점수 보정
service_web/document_builder.py             API 문서 응답 조립
service_web/static/index.html               검색 UI
GET  /health                                인덱스 상태 확인
POST /search                                자연어 API 문서 검색
GET  /services/{service_id}                 API 문서 상세
```

이 단계까지 완료되면, 사용자는 자연어로 공공데이터 API를 찾고 endpoint와 요청/응답 필드를 확인할 수 있다.
