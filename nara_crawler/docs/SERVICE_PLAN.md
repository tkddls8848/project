# Nara 공공데이터 서비스 — 통합 계획서

작성일: 2026-05-24
통합 대상: `01_DATA_ORGANIZATION_PLAN.md`, `07. AGUI.md`, `08. io.md`
핵심 전략: **한 번에 거대한 시스템을 만들지 않는다.** 독립적으로 동작·검증 가능한 서브프로젝트(SP) 단위로 구현하고, 각 SP가 안정화된 뒤 통합 레이어에서 하나의 서비스로 합친다.

---

## 0. 서비스 비전

### 0.1 한 줄 정의

자연어 질의 한 줄로 여러 공공기관의 API·파일데이터·표준데이터에서 필요한 공공서비스를 찾아 추천하고, 에이전트가 실제로 호출할 수 있도록 도구화하는 인프라.

### 0.2 핵심 문제

단순 수집이 아닌 **부처 간 사일로 해소**가 본질이다. 같은 의미가 기관마다 다른 용어·필드명·설명으로 나타나기 때문에, 데이터·인덱스·UI 어디에서든 의미 통합을 전제로 설계해야 한다.

### 0.3 사용자 경험 목표

- 자연어 입력 → 에이전트의 사고 과정과 결과 레이아웃이 동시에 흐르는 UX
- 쿼리 성격(단일 정보 / 비교 / 절차)에 따라 카드·그리드·플로우가 자동으로 선택되는 Generative UI
- 결과 카드 → API 호출 도구로 자연스럽게 연결되는 흐름

### 0.4 최종 결정 (3개 문서 종합)

- 운영 DB(PostgreSQL/Neo4j)는 MVP 단계에서 도입하지 않는다. 기준 데이터는 JSONL.
- 분석 엔진은 DuckDB, 키워드 검색은 BM25, 벡터 검색은 ChromaDB(또는 현행 FAISS) — 모두 재생성 가능한 인덱스로 취급한다.
- AG-UI 데모는 기존 운영 코드(`/query/stream`, `/workflow/*`)를 건드리지 않고 **별도 엔드포인트·별도 페이지**로 분리한다.
- 모든 서브프로젝트는 **단방향 데이터 의존**을 따른다(아래 §3.3 참조).

---

## 1. 전체 아키텍처

### 1.1 데이터 흐름 (5계층)

```
[01_raw] → [02_catalog] → [03_semantic] → [04_output] → [05_indexes]
   원본       통합 메타       의미 통합       서비스 산출물     검색 인덱스
```

| 번호 | 폴더 | 역할 |
| --- | --- | --- |
| `01` | `01_raw/` | 수집 원본 (불변, crawl_run 단위) |
| `02` | `02_catalog/` | 통합 메타데이터 카탈로그 (JSONL 기준 데이터) |
| `03` | `03_semantic/` | 표준 개념·기관별 별칭·필드 매핑 (사일로 해소 자산) |
| `04` | `04_output/` | 추천 카탈로그·RAG 청크·API 도구 명세 (서비스 직결) |
| `05` | `05_indexes/` | DuckDB / BM25 / ChromaDB 인덱스 (재생성 가능) |
| `99` | `99_reports/` | 진단·품질·감사 리포트 |

### 1.2 서비스 흐름 (런타임)

```
사용자 자연어
  → [쿼리 분석 + 분류]   (Ollama / 휴리스틱)
  → [벡터 검색]          (FAISS / ChromaDB)
  → [관계 탐색]          (Neo4j 데모 시드, 절차형에만)
  → [레이아웃 결정]      (single / grid / flow)
  → [LLM 응답 생성]      (NDJSON 토큰 스트림)
  → [결과 카드/플로우]   (React Flow + 카드 그리드)
  → [노드 클릭]          (서비스 상세 + endpoint)
```

### 1.3 기술 역할 요약

| 기술 | 역할 | 위치 |
| --- | --- | --- |
| JSONL | 기준 데이터 (단일 진실) | `02_catalog`, `03_semantic`, `04_output` |
| DuckDB | 로컬 SQL 조회·검증·리포트 | `05_indexes/duckdb/` |
| BM25 | 키워드 검색 + 하이브리드 후보군 축소 | `05_indexes/bm25/` |
| ChromaDB | 벡터 인덱스 (RAG 청크 전용) | `05_indexes/chroma/` |
| FAISS | 현행 운영 벡터 검색 (단계적 ChromaDB 이행 검토) | `models/` |
| Neo4j | 절차형 시연용 가짜 노드 그래프 | 컨테이너 |
| Ollama (`gemma4:e4b`) | 로컬 쿼리 분류기 | host.docker.internal:11434 |

---

## 2. 서브프로젝트 분할 원칙

거대한 단일 프로젝트로 만들지 않는다. 다음 원칙을 따른다.

1. **독립 실행 가능성**: 각 SP는 단독으로 빌드·테스트·시연이 가능해야 한다.
2. **명확한 산출물**: SP의 완료는 코드가 아니라 **검증 가능한 파일/엔드포인트/화면**으로 정의한다.
3. **단방향 의존**: 후행 SP는 선행 SP의 산출물(파일·엔드포인트)만 소비한다. 코드 직접 의존 금지.
4. **공통 ID 체계**: `service_id`, `endpoint_id`, `agency_id`, `concept_id`를 모든 SP에서 동일하게 사용한다.
5. **인터페이스 우선**: SP 경계의 JSON 스키마와 envelope을 먼저 합의하고 구현은 그 다음.
6. **`is_demo` 플래그 분리**: 시연 전용 데이터는 운영 데이터와 같은 저장소에 있어도 플래그로 분리한다.
7. **버전 명시**: 산출물 파일에는 생성 시각·스키마 버전·`crawl_run_id`를 기록한다.

---

## 3. 서브프로젝트 카탈로그

총 9개 SP. SP1~SP3은 데이터 백본, SP4~SP6은 서비스 레이어, SP7~SP8은 운영 품질, SP9는 통합.

### 3.1 SP 일람

| ID | 이름 | 책임 | 선행 의존 |
| --- | --- | --- | --- |
| SP1 | Raw & Catalog Foundation | 원본 보존, 통합 카탈로그 생성 | — |
| SP2 | Semantic Layer | 표준 개념·별칭·필드 매핑 | SP1 |
| SP3 | Output & Index Build | RAG 청크·추천 카탈로그·DuckDB/BM25/Chroma 인덱스 | SP1, SP2 |
| SP4 | AGUI Streaming Service | NDJSON 사고과정 스트리밍 + 검색 결과 | SP3 |
| SP5 | Generative UI Layout | 쿼리 분류 + Single/Grid/Flow 레이아웃 + Neo4j 시드 | SP4 |
| SP6 | Workflow API Discovery | API 조합 노드·LLM 분석 노드 | SP3 |
| SP7 | Security & Auth Hardening | 인증/인가, BYO API Key, Rate Limit, CORS | SP4 가용 후 적용 |
| SP8 | Operations Automation | 권한 갱신 자동화, HTML 정제, 동적 라우팅 | SP1 |
| SP9 | Integration Layer | 메인·검색·워크플로우 단일 데모 통합 | SP1~SP8 MVP 통과 |

### 3.2 의존 그래프

```
SP1 ──────┬──> SP2 ──> SP3 ──┬──> SP4 ──> SP5 ──┐
          │                  │                   │
          └──> SP8           └──> SP6 ──────────┤
                                                 ▼
                              SP7 ──────────> SP9
```

### 3.3 의존 규칙 (금지 패턴 포함)

- SP4가 SP1의 원본 JSON을 직접 읽지 않는다. 반드시 SP3 산출물을 거친다.
- SP5는 SP4의 envelope을 확장하기만 한다. SP4의 내부 모듈을 import 하지 않는다.
- SP6는 SP3 카탈로그를 읽지만, 새로운 raw 데이터를 만들지 않는다(필요 시 SP1으로 회수).
- SP7은 어느 SP의 비즈니스 로직도 수정하지 않는다. 미들웨어·게이트웨이 레벨에서 처리한다.
- SP9는 모든 SP의 소비자. 어떤 SP도 SP9 산출물을 참조하지 않는다.

---

## 4. SP1 — Raw & Catalog Foundation

### 4.1 목적

수집 원본을 불변으로 보존하고, 데이터 타입에 묶이지 않는 `service_id` 중심의 통합 카탈로그를 만든다.

### 4.2 In Scope

- `data/01_raw/crawl_runs/{crawl_run_id}/` 디렉터리 규약 + `manifest.json`
- `02_catalog/` 6종 JSONL 생성 파이프라인
- `crawl_history.jsonl`(append-only) + `crawl_latest.jsonl`(재생성)
- DuckDB로 JSONL 조회/검증 쿼리 묶음

### 4.3 Out of Scope

- 데이터 타입별 폴더 신설(`bronze`, `02_refined` 등)
- 부처/기관별 디렉터리 분리 (메타데이터로만 관리)
- 의미 매핑 (SP2)

### 4.4 산출물

```
data/01_raw/crawl_runs/2026-05-02T10-30-00/
  manifest.json
  openapi/  filedata/  standard/
data/02_catalog/
  agencies.jsonl
  services.jsonl
  endpoints.jsonl
  fields.jsonl
  documents.jsonl
  crawl_history.jsonl
  crawl_latest.jsonl
scripts/
  build_catalog.py
  duckdb_smoke.sql
```

### 4.5 완료 기준

- 신규 수집 1회를 `crawl_run_id` 단위로 저장 + manifest 작성
- `02_catalog/*.jsonl`이 DuckDB `read_json_auto`로 즉시 조회 가능
- `crawl_latest.jsonl`이 `crawl_history.jsonl`에서 재생성 가능 (스크립트 멱등 보장)
- `change_status`(new/unchanged/changed/deleted/failed)가 카탈로그에 반영

### 4.6 리스크

- 기존 `data/raw_data/`와의 병행 운영 기간이 길어질 수 있음 → 점진 마이그레이션, 강제 삭제 금지.
- 부처명 변경/조직 개편 → 폴더가 아니라 `agencies.jsonl`에서 이력 관리.

---

## 5. SP2 — Semantic Layer

### 5.1 목적

부처 간 사일로 해소를 위한 의미 통합 자산을 축적한다. 추천 품질의 핵심 자산.

### 5.2 In Scope

- 도메인 분류(`taxonomy.json`)
- 표준 개념(`concepts.jsonl`) + 기관별 별칭(`aliases.jsonl`)
- 필드 매핑: `service_id + endpoint_id + field_name` 단위
- 서비스 태그·개념 관계·기관별 용어집·질의 예시

### 5.3 Out of Scope

- 전체 자동 매핑 — 초기에는 규칙 + LLM 후보 + 수동 검수 혼용
- ChromaDB 적재 (SP3)

### 5.4 산출물

```
data/03_semantic/
  taxonomy.json
  concepts.jsonl
  aliases.jsonl
  field_mappings.jsonl
  service_tags.jsonl
  concept_relations.jsonl
  agency_glossary.jsonl
  query_examples.jsonl
```

### 5.5 완료 기준

- 최소 1개 도메인(예: `welfare`)에 대해 개념 20+ / 별칭 50+ / 필드 매핑 30+ 확보
- 자동 매핑 항목 전부에 `confidence`, `source`, `review_status` 부여
- DuckDB로 `services.jsonl ⋈ service_tags.jsonl ⋈ concepts.jsonl` 조인이 1초 이내

### 5.6 주의

- 필드명은 기관 단위로 합치지 않는다. 같은 `주소`라도 거주지/사업장/신청지일 수 있다.
- 동의어 사전을 도메인 파일로 고정하지 않는다 (중복 폭증).

---

## 6. SP3 — Output & Index Build

### 6.1 목적

검색·추천·에이전트 도구 호출에 바로 쓰는 산출물을 만들고, 재생성 가능한 인덱스를 빌드한다.

### 6.2 In Scope

- `retrieval_chunks.jsonl`: 사용자가 검색할 만한 문장으로 재구성한 RAG 청크 + 온톨로지 태그
- `recommender_catalog.jsonl`: 랭킹용 통합 카탈로그
- `api_tool_specs.jsonl`: 에이전트 호출용 도구 명세
- `cross_ref/service_relations.jsonl`: 동일/대체/보완/선행/상하위 관계
- 인덱스 빌드: DuckDB `.duckdb`, BM25, ChromaDB collection `public_services`
- 품질 리포트 `quality_report.json`

### 6.3 Out of Scope

- 도메인별/기관별 뷰는 **요청 발생 시에만** 생성 (DuckDB SQL로 대체 가능)
- 새로운 의미 매핑 (SP2로 회수)

### 6.4 ChromaDB 운용 규칙

- 단일 컬렉션 `public_services`만 사용. 도메인별 컬렉션 금지(중복·관리비).
- metadata에는 ID만 (`chunk_id`, `service_id`, `domain_ids`, `concept_ids`).
- 배열 metadata 불안정 시 `domain_ids_text` 등 fallback 필드 추가.
- ChromaDB를 정답 DB로 보지 않는다. `retrieval_chunks.jsonl`에서 항상 재생성.

### 6.5 완료 기준

- `retrieval_chunks.jsonl` → ChromaDB 적재 → 자연어 질의 → `service_id` 회수 → DuckDB로 상세 조회 한 사이클이 자동화 스크립트로 동작
- 동일 입력에 대해 인덱스 재빌드 결과가 결정적(checksum 동일)
- 시드 질의 5종에서 top-10 회수율 측정 가능

### 6.6 운영 메모

- 현재 운영 검색은 FAISS 기반. ChromaDB로의 이행은 SP4 시연이 안정화된 뒤 단계적으로 검토(파이프라인은 모두 `retrieval_chunks.jsonl`을 입력으로 받게 일관화).

---

## 7. SP4 — AGUI Streaming Service

### 7.1 목적

자연어 입력에 대해 에이전트의 사고 과정을 NDJSON 스트림으로 보여주는 데모 페이지를 만든다. **기존 운영 코드는 건드리지 않는다.**

### 7.2 신규 엔드포인트 / 페이지

| 위치 | 신규 |
| --- | --- |
| 백엔드 | `POST /agui/search`, `GET /agui/node/{service_id}` |
| 프론트 | `/demo` (Next.js 라우트) |

### 7.3 NDJSON Envelope (단일 진실)

```json
{ "type": "<event_type>", "ts": <epoch_ms>, "payload": { ... } }
```

이벤트 타입: `step`, `documents`, `layout`, `token`, `done`, `error`
에러 코드: `LLM_TIMEOUT`, `LLM_PARSE_ERROR`, `NEO4J_UNAVAILABLE`, `INTERNAL_ERROR`

### 7.4 단계 시퀀스 (SP4 기준)

```
step  query_analysis  running → done
step  vector_search   running → done   (detail: "N건 후보")
step  graph_lookup    running → done   (detail: "관계 M개" 또는 "관계 데이터 없음")
documents             [검색 결과]
step  llm_generation  running
token (반복)
step  llm_generation  done
done
```

단계 간 최소 150ms 지연 — 사용자가 시각적으로 인지하도록.

### 7.5 부팅 검증

`app/main.py` startup에서 Ollama `/api/tags` 호출 → `gemma4:e4b` 부재 시 **부팅 중단**. 휴리스틱은 런타임 일시 실패의 안전망일 뿐, 모델 부재의 대체가 아니다.

### 7.6 산출물

```
nara_service/backend/app/routes/agui.py
nara_service/frontend/app/demo/
  page.tsx
  components/ThinkingTimeline.tsx
  components/ResultPanel.tsx
  lib/streamClient.ts
  lib/types.ts
```

### 7.7 완료 기준

- `/demo`에서 검색 1회 실행 시 좌측 단계 인디케이터가 순차 점등
- 우측에 검색 결과 카드 + 토큰 단위 답변 스트림
- 시드 쿼리 3종(단일/비교/절차) 모두에서 오류 없이 동작

---

## 8. SP5 — Generative UI Layout

### 8.1 목적

쿼리 성격에 따라 결과 레이아웃을 자동 선택한다.

### 8.2 In Scope

- `query_classifier.py`: Ollama `gemma4:e4b`, 타임아웃 1초, 휴리스틱 fallback
- envelope에 `layout` 이벤트 추가 (`single | grid | flow`)
- React Flow(`@xyflow/react`) 기반 절차형 레이아웃
- Neo4j 데모 시드: **외국인 운전면허 시나리오 4 노드**(`is_demo: true`)
- `/agui/node/{service_id}`: `is_demo` 분기 → 시드 그대로 반환 / 기존 detail 위임

### 8.3 휴리스틱 fallback 규칙

- 결과 1건 → `single`
- 키워드(절차, 순서, 방법, 단계, 하려면, 따려면, 어떻게) 매칭 → `flow`
- 그 외 → `grid`

### 8.4 Neo4j 시드 스키마

```json
{
  "service_id": "DEMO_S1",
  "name": "출입국·외국인청_체류자격조회",
  "agency": "출입국외국인청",
  "category": "외국인행정",
  "description": "외국인의 체류 자격을 조회하는 API",
  "endpoints": [{"path":"/api/visa/status","method":"GET","desc":"체류자격 상태 조회"}],
  "step_order": 1,
  "is_demo": true
}
```

관계 타입: `PRECEDES` (절차 선후), `RELATED_TO` (도메인 연계, 예약).

### 8.5 산출물

```
nara_service/backend/
  app/services/query_classifier.py
  scripts/seed_neo4j_demo.py
  scripts/seed_data/demo_graph.json
nara_service/frontend/app/demo/components/
  ResultLayoutRouter.tsx
  ResultLayoutSingle.tsx
  ResultLayoutGrid.tsx
  ResultLayoutFlow.tsx
  NodeDetailDrawer.tsx
```

### 8.6 완료 기준

- 시드 쿼리 3종 각각에서 서로 다른 레이아웃이 마운트됨
- Flow 노드 클릭 → `/agui/node/{service_id}` → endpoint 사이드 패널 표시
- `layout` 이벤트가 `documents`보다 먼저 도착해도 화면이 깨지지 않음

### 8.7 제약

- 시연 외 절차형 쿼리는 Neo4j 매칭 없으면 FAISS 결과를 직선 연결로 fallback.
- 시드 노드는 실재 카탈로그와 매칭하지 않는다(가짜 노드 명시).

---

## 9. SP6 — Workflow API Discovery

### 9.1 목적

개별 API 검색을 넘어, 여러 API를 논리 노드로 연결해 **단일 문서로는 알 수 없는 활용 방안**을 LLM이 도출하도록 한다.

### 9.2 노드 카탈로그

| 종류 | 노드 |
| --- | --- |
| Source | API 문서 노드 (스키마·도메인·기관 메타 포함) |
| Logic | Merge / Join / Filter / If / Semantic Search |
| Analysis | LLM Analysis / Schema Diff / Domain Cluster |
| Output | Export / Save Workflow |

### 9.3 가치의 원천

시스템 가치의 70%는 노드 구조가 아니라 **LLM에게 넘기는 컨텍스트의 품질**. 따라서:

- API 필드명 그대로가 아닌 **의미 단위 스키마**를 넘긴다 (SP2 자산 활용)
- 도메인 레이블을 함께 주입해 이종 조합 발견율을 높인다
- 시맨틱 임베딩으로 이종 후보를 미리 좁혀 LLM 입력 크기 절감

### 9.4 단계

1. **PoC (1~2일)**: Merge 노드 1개 + LLM 노드 1개, "이 둘을 조합하면?" 고정 프롬프트.
2. **논리 노드 확장 (1~2주)**: Filter/If/Join + 노드 실행 상태(UI) + 데이터 전달 규약.
3. **실행 엔진 (2~3주)**: DAG 위상 정렬 기반 순차 실행, `POST /workflow/run`, 실행 이력 저장.

### 9.5 좋은/나쁜 조합 가이드

- 나쁜 예: 관광지 API + 관광 코스 API (동일 도메인, 자명)
- 좋은 예: 복지 수급자 API + 의료기관 API + 교통 노선 API → "거동 불편 노인 맞춤 병원 이동 지원"

### 9.6 완료 기준

- 이종 도메인 API 3개를 묶어 LLM 분석 결과를 받아오는 데모 1건
- 동일 워크플로우를 JSON으로 저장/재실행 가능

---

## 10. SP7 — Security & Auth Hardening

### 10.1 목적

`08. io.md`에 적시된 보안 갭(인증 없음, API 키 노출, CORS 과개방, Rate Limit 없음, 입력 검증 부족, swagger 명세 공개)을 일괄 해소한다.

### 10.2 결정 사항

| 항목 | 결정 |
| --- | --- |
| LLM API 키 | **BYO(Bring Your Own)** — 사용자가 직접 발급/입력. 운영자 크레딧 차감 모델 도입 보류. |
| 인증 | 기존 `X-API-Key` 헤더 유지. 데모 페이지 인증 정책은 SP4 착수 전 확정. |
| Rate Limit | 기존 `slowapi` 패턴(예: 10/min) 일관 적용. |
| Swagger | 운영 환경에서는 비공개(또는 화이트리스트). 개발 환경에서만 노출. |
| 백엔드 직접 API 노출 | 점진적으로 프론트 프록시 경유로 전환 검토. |

### 10.3 In Scope

- 미들웨어 레벨에서 인증·Rate Limit·CORS 일관화
- 입력 검증 스키마(Pydantic) 라우트 단위 정착
- 시크릿 관리(.env + 시크릿 매니저 전환 검토)

### 10.4 Out of Scope

- 비즈니스 로직 수정 (다른 SP 책임)
- 결제/구독 시스템 (장기 과제)

### 10.5 완료 기준

- 미인증/Rate Limit 초과/잘못된 입력에 대해 일관된 에러 응답
- swagger가 의도된 환경에서만 노출
- 데모 페이지 401 시연 사고를 streamClient에서 자동 차단

---

## 11. SP8 — Operations Automation

### 11.1 목적

수동 운영 비용이 큰 항목을 자동화/정형화한다.

### 11.2 In Scope

- **API 사용 승인 자동 갱신**: `https://www.data.go.kr/iim/api/selectAcountList.do`에 등록된 수만 건 문서의 연 1회 갱신 자동화 (법/약관 검토 선행 필수)
- **HTML/특수문자 정제**: 크롤링 데이터의 `<br>`, 태그·엔티티 일괄 정규화
- **엔드포인트 동적 라우팅**: 백엔드에서 엔드포인트별 라우트를 일일이 만들지 않고, 파라미터를 내부에서 처리하는 단일 라우트로 전환
- **데이터 타입 일괄 규격화**: standard 타입 getAll/getEach + 다른 4종(general/swagger/fileData/link) 정합

### 11.3 Out of Scope

- 검색 품질 자체의 개선 (SP3)
- 추천 알고리즘 변경 (SP3)

### 11.4 완료 기준

- 자동 갱신 스크립트가 dry-run 모드로 전수 점검 후 실제 갱신 1회 통과
- 라우트 수가 데이터 타입 × 엔드포인트 수에 비례하지 않음
- 정제 규칙 단위 테스트 통과(예: HTML 태그 잔존 0건)

### 11.5 주의

- 자동 갱신은 약관 검토 결과에 따라 범위가 바뀔 수 있음. **법/약관 점검을 SP8 진입 조건으로 명시**.

---

## 12. SP9 — Integration Layer

### 12.1 목적

SP1~SP8의 산출물을 묶어 **하나의 거대 프로젝트**로 통합한다. 메인 페이지 검색과 RAG 검색이 결국 하나로 합쳐져야 한다는 `08. io.md`의 방향을 실행한다.

### 12.2 착수 조건

SP1~SP8이 각자 MVP 완료 기준을 통과한 시점. 기준 미달 SP가 있으면 통합 시작하지 않는다.

### 12.3 In Scope

- 메인 페이지 ↔ 검색 페이지 통합 (API 문서 RAG + 청크 RAG를 단일 검색 표면으로)
- AGUI 데모(`/demo`)를 정식 검색 화면으로 승격하는 단계적 계획
- 워크플로우 결과(SP6)를 검색 결과 카드와 연결
- 통합 회귀 테스트

### 12.4 Out of Scope

- 새로운 데이터 종류 추가 (각 원천 SP 책임)
- 신청 자동화(본인인증 포함) — 별도 트랙

### 12.5 완료 기준

- 시드 질의 5종에 대해 단일 검색 표면에서 카드/그리드/플로우/워크플로우가 일관되게 제공
- 통합 회귀 테스트가 CI에서 통과

---

## 13. 로드맵 (참고)

기간은 1인 개발 기준 러프 추정. SP는 가능한 병렬화한다.

| 시점 | 활동 |
| --- | --- |
| 0주차 | 약관/라이선스 검토, 공통 스키마 확정, 신규 페이지·엔드포인트 경로 합의 |
| 1개월차 | SP1 안정화 → SP2 착수, SP4 Phase 0 (Neo4j 시드 + envelope 합의) |
| 2개월차 | SP2 MVP, SP3 MVP, SP4 MVP |
| 3개월차 | SP5 MVP, SP6 PoC, SP8 일부 항목 |
| 4개월차 | SP7 하드닝, SP6 논리 노드 확장 |
| 5개월차~ | SP9 통합 착수 |

---

## 14. 공통 ID·스키마 규약

모든 SP가 공유한다. 다른 결정보다 먼저 합의한다.

| 엔티티 | 키 | 비고 |
| --- | --- | --- |
| Agency | `agency_id` | 기관명 변경 이력 보존 |
| Service | `service_id` | 데이터 타입과 무관한 통합 키 |
| Endpoint | `endpoint_id` | `service_id`에 종속 |
| Field | `(service_id, endpoint_id, field_name)` | 기관 단위 합치기 금지 |
| Concept | `concept_id` | 도메인 prefix (예: `benefit.medical_expense_support`) |
| Chunk | `chunk_id` | `svc-{service_id}-{slot}` 형식 권장 |
| CrawlRun | `crawl_run_id` | ISO 시각, 예: `2026-05-02T10-30-00` |

자동 추론 관계에는 항상 `confidence`, `source`, `review_status`.

---

## 15. 오픈 이슈 (08 흡수, 미결정)

본문에서 결정되지 않았거나 추가 조사·합의가 필요한 항목. **착수 전 별도 결정**.

### 15.1 사업 모델

- 과금 모델: 소액 결제 + 사용자 제공 컨텐츠(독특한 글/컨텍스트) 기여 모델 검토
- Piku, 인디아 프로젝트 등 유사 사례 벤치마크 정리 필요
- mermaidchart 식 그레이드별 보안 기능 모델 검토(확장 시 보안 인력 필요 시점)
- 익스텐션/OpenWebUI 응용 가능성

### 15.2 데이터/검색 품질

- `index.json`을 "문학적 시각" 기반 태깅 자산으로 발전시키는 방향
- `search_context` 전략 구현 (MCP 활용 여부 포함)
- 네이버 기사 ↔ API 키워드 유사 비교 보정
- 키워드/디스크립션의 연출(콘텐츠 큐레이션)
- 외부 프로젝트 활용 검토: `yeongseon/kpubdata`, `StatPan/kr-data-portal-client` (래퍼/프로바이더 후보)
- Scale AI 식 데이터 태깅 비즈니스 모델 적용 가능성

### 15.3 운영/보안

- API 사용 승인 자동 갱신의 약관상 허용 범위
- 백엔드 직접 API 노출 vs 프론트 프록시 전환 결정
- 데모 페이지 인증 정책(공개 vs 데모 키 발급)
- 개인화 장기 기억 정보(계정 + 정보 보안 기본)
- 채팅 그룹/대시보드 개인 저장 + 채팅 기록 저장 정책

### 15.4 검색 통합

- Neo4j 활용 범위 재정의: 현행 메인 검색은 FAISS만 사용, Neo4j는 부가 기능(Related/Context Insights)에 한정 → 절차형 시연/관계 보강 외 적극 사용 시점 결정
- 메인 페이지 검색(문서 단위)과 RAG 검색(청크 단위)의 단일 검색 표면화 전략 (SP9에서 본격 다룸)
- 크롤링 시 키워드 생성 스킵 → Neo4j 적재 후 그래프 기반 일괄 생성 옵션 검토
- 대시보드 다중 노드 연결 이슈(한 노드가 여러 노드의 소스/타겟이 되지 못함)

### 15.5 UX 참고

- Google AI Mode(`udm=50`) 류 동적 결과 구도 참고
- 사용자 페르소나 정의 (착수 전 합의 필요)
- 디테일 페이지 표시 내용 다듬기

---

## 16. 리스크 & 대응

| 리스크 | 영향 | 대응 |
| --- | --- | --- |
| Ollama `gemma4:e4b` 부재 | SP4 부팅 실패 | 0주차 환경 점검 + README 가이드 + startup 검증 |
| 시드 시나리오와 실재 카탈로그 불일치 | 시연 외 신뢰성 저하 | `is_demo: true` 명시, README 한정 명시, fallback 흐름 제공 |
| 운영/데모 데이터 혼재 | 향후 충돌 | 모든 데모 노드 `is_demo: true` + 삭제 스크립트 동봉 |
| envelope 스키마 변경 시 동기화 비용 | 리팩토링 비용 | `types.ts` 단일 진실 + 백엔드 Pydantic 모델 수동 동기화(자동화는 SP5 이후) |
| ChromaDB 배열 metadata 불안정 | 검색 필터 실패 | `*_text` fallback 필드 빌드 시 추가 |
| SP 간 코드 직접 의존 발생 | 통합 깨짐 | 의존 그래프(§3.2) 위반 PR 거부 |
| 약관 검토 누락 상태에서 자동 갱신 진행 | 서비스 정지 위험 | SP8 진입 조건에 약관 검토 산출물 강제 |
| FAISS→ChromaDB 이행 중간 상태 | 검색 결과 불일치 | 두 인덱스를 같은 `retrieval_chunks.jsonl`에서 빌드 + A/B 비교 기간 확보 |

---

## 17. 진행 체크리스트 (요약)

각 SP 안에서 다음 4단계를 거쳐야 "완료"로 본다.

1. 스키마/인터페이스 합의 (산출물 형식·envelope·DB 시드 결정)
2. 데이터/엔드포인트 생성
3. 검증 (스크립트·시드 질의·회귀)
4. 다른 SP가 소비할 수 있는 형태로 문서화

---

## 18. 결론

- 거대한 단일 빌드 대신 **9개 서브프로젝트**를 단방향 의존으로 쌓는다.
- 데이터 계층(SP1~SP3)은 JSONL 기준 데이터 + 재생성 가능한 인덱스로, 운영 DB 도입을 미룬다.
- 서비스 계층(SP4~SP6)은 기존 운영 코드와 격리된 `/agui/*`·`/demo`에서 검증한 뒤 SP9에서 통합한다.
- 운영 품질(SP7~SP8)은 비즈니스 로직 밖에서 일관 적용한다.
- 오픈 이슈는 §15에 격리해 추적하고, 결정될 때마다 본문 해당 SP로 흡수한다.

핵심은 SP2(의미 통합)와 SP3(인덱스 빌드 표준화)의 자산이 꾸준히 축적되는 것이다. 부처 간 사일로 문제는 폴더 구조만으로 해결되지 않으며, 이 자산이 곧 추천 품질이자 통합 레이어의 결합 강도가 된다.
