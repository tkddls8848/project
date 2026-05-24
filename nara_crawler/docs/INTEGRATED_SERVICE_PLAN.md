# Nara Crawler 통합 서비스 계획서

작성일: 2026-05-24

참조 문서:

- `docs/01_DATA_ORGANIZATION_PLAN.md`
- `docs/07. AGUI.md`
- `docs/08. io.md`

## 1. 통합 목표

이 프로젝트의 최종 목표는 공공데이터포털, 정부24, 기관별 공공 API와 서비스 메타데이터를 수집·정리한 뒤, 사용자가 자연어로 필요한 공공서비스를 찾고 실행 준비까지 이어갈 수 있는 공공 API 에이전트 인프라를 만드는 것이다.

핵심은 단순 크롤러나 검색 UI가 아니다. 여러 부처와 기관에 흩어진 API, 파일데이터, 표준데이터, 정부24 링크, 민원 절차, 기관 관계를 공통 ID와 의미 계층으로 연결하고, 사용자의 생활 사건 단위 질문에 대해 다음을 함께 제공하는 서비스가 목표다.

- 관련 공공서비스와 API 후보
- 사용자가 따라야 할 절차와 단계
- 기관, 서비스, API 사이의 관계
- 정부24 또는 기관 페이지 딥링크
- 에이전트가 호출 가능한 API 도구 명세
- 자연어 답변과 검색 근거
- 쿼리 성격에 맞는 동적 UI

최종 제품 정의:

> 자연어 민원 의도를 받아 시나리오를 찾고, 관련 공공서비스·API·정부24 링크·기관 관계를 조합해 에이전트와 사용자에게 제공하는 공공 API 실행 준비 인프라.

## 2. 개발 전략

전체 구현 범위가 크므로 한 번에 거대 프로젝트로 완성하지 않는다. 초기에는 여러 개의 수행 가능한 서브프로젝트로 나누어 각각 독립적으로 구현하고 정교화한다. 각 서브프로젝트는 공통 ID, 공통 스키마, 출처 관리 규칙을 지키며 파일 또는 API 산출물로만 연결한다.

후기에는 별도 통합 레이어를 만들어 서브프로젝트 산출물을 하나의 서비스로 묶는다.

이 전략의 이유는 다음과 같다.

- 데이터 수집, 의미 통합, MCP 도구화, 그래프, UI는 실패 지점과 검증 방식이 다르다.
- 한 모듈의 설계 변경이 전체 구현을 막지 않도록 해야 한다.
- 실제 호출 가능한 API와 법적 사용 가능 범위를 먼저 검증해야 한다.
- 데모 UI는 운영 검색 API와 분리해서 빠르게 검증해야 한다.
- P5 통합 레이어는 원천 데이터를 만들지 않고, 각 서브프로젝트의 검증된 산출물만 소비해야 한다.

## 3. 전체 아키텍처

```text
사용자 자연어 질의
  -> P5 Integration Layer
      -> P1 Civic Scenario Catalog
      -> P2 GovAPI MCP Server
      -> P3 Gov Service Graph
      -> P4 Gov24 Link Resolver
      -> Data Foundation
          -> 01_raw
          -> 02_catalog
          -> 03_semantic
          -> 04_output
          -> 05_indexes
  -> AG-UI Demo / API Response
```

데이터 흐름은 다음 순서를 따른다.

```text
01_raw
  -> 02_catalog
  -> 03_semantic
  -> 04_output
  -> 05_indexes
  -> P1/P2/P3/P4 산출물
  -> P5 Integration Layer
  -> AG-UI / API / 에이전트
```

서브프로젝트 의존 방향은 다음처럼 고정한다.

```text
P4 Gov24 Link Resolver
  -> P1 Civic Scenario Catalog
  -> P2 GovAPI MCP Server
  -> P3 Gov Service Graph
  -> P5 Integration Layer
```

`P3`는 그래프 sink로 취급한다. 원천 데이터를 새로 만들지 않고 P1, P2, P4 및 데이터 기반 계층의 산출물을 그래프 노드와 관계로 변환한다.

`P5`는 최종 소비자다. P1~P4 어느 것도 P5에 의존하지 않는다.

## 4. 공통 데이터 기반

공통 데이터 기반은 모든 서브프로젝트가 공유하는 기준 계층이다. 운영 DB를 먼저 도입하지 않고 JSONL을 기준 데이터로 둔다. DuckDB, BM25, ChromaDB는 재생성 가능한 조회·검색 인덱스로만 사용한다.

권장 구조:

```text
data/
  01_raw/
    crawl_runs/
      {crawl_run_id}/
        manifest.json
        openapi/
        filedata/
        standard/

  02_catalog/
    agencies.jsonl
    services.jsonl
    endpoints.jsonl
    fields.jsonl
    documents.jsonl
    crawl_history.jsonl
    crawl_latest.jsonl

  03_semantic/
    taxonomy.json
    concepts.jsonl
    aliases.jsonl
    field_mappings.jsonl
    service_tags.jsonl
    concept_relations.jsonl
    agency_glossary.jsonl
    query_examples.jsonl

  04_output/
    recommender_catalog.jsonl
    retrieval_chunks.jsonl
    api_tool_specs.jsonl
    domain_views/
    agency_views/
    cross_ref/
      service_relations.jsonl
    quality_report.json

  05_indexes/
    duckdb/
      nara.duckdb
    bm25/
    chroma/

  99_reports/
```

### 4.1 원칙

1. 원본은 `01_raw`에 불변으로 보존한다.
2. 수집 실행 단위는 `crawl_run_id`로 추적한다.
3. 수집 이력은 `crawl_history.jsonl`에 append-only로 기록한다.
4. 최신 상태는 `crawl_latest.jsonl`로 재생성한다.
5. 기관과 부처는 폴더 경로가 아니라 메타데이터로 관리한다.
6. 추천과 검색은 `service_id` 중심 통합 카탈로그를 기준으로 한다.
7. 의미 통합은 `03_semantic`에 분리한다.
8. RAG 청크와 검색 인덱스는 재생성 가능한 산출물로 취급한다.
9. PostgreSQL과 Neo4j는 MVP 이후 필요성이 명확할 때 도입한다.

### 4.2 핵심 계층

`02_catalog`는 원본 복사본이 아니라 통합 메타데이터 카탈로그다.

주요 엔티티:

- Agency
- Service
- Endpoint
- Field
- Document
- CrawlHistory
- CrawlLatest

`03_semantic`은 부처 간 사일로 해소를 위한 핵심 자산이다.

주요 데이터:

- 표준 개념
- 기관별 별칭
- 필드명 의미 매핑
- 서비스 태그
- 개념 관계
- 기관별 용어집
- 사용자 질의 예시

`04_output`은 실제 추천, RAG, MCP 도구화, API 응답에 쓰는 빌드 산출물이다.

주요 산출물:

- `recommender_catalog.jsonl`
- `retrieval_chunks.jsonl`
- `api_tool_specs.jsonl`
- `service_relations.jsonl`
- `quality_report.json`

## 5. 서브프로젝트 구성

### 5.1 P0. Foundation and Governance

모든 서브프로젝트 착수 전에 완료해야 하는 사전 작업이다.

목적:

- 공통 ID 체계 확정
- 공통 최소 스키마 확정
- 라이선스와 재가공 가능 범위 검토
- 실제 호출 가능한 API 후보 검증
- 데이터 저장 구조와 산출물 계약 고정

주요 작업:

- 공공데이터포털 API 이용약관 검토
- 정부24 OpenAPI 및 딥링크 사용 가능 범위 검토
- 크롤링 데이터 가공·재공개 조건 정리
- startup_cafe 시나리오 기준 호출 가능한 API 3개 이상 검증
- 공통 JSON Schema 작성
- ID 네이밍 규칙 문서화
- README 템플릿 작성

산출물:

```text
docs/licensing_review.md
docs/id_naming.md
schemas/common_schema.json
data/04_output/startup_cafe_callable_apis.jsonl
```

완료 기준:

- 법적·라이선스 리스크가 문서화되어 있다.
- 실제 호출 가능한 API 3개 이상이 검증되어 있다.
- 모든 서브프로젝트가 사용할 최소 ID와 스키마 규칙이 있다.

### 5.2 P1. Civic Scenario Catalog

사용자의 생활 사건을 기준으로 민원·서비스 절차를 정리하는 시나리오 카탈로그다.

예시 시나리오:

- 카페 창업
- 외국인 운전면허 취득
- 소상공인 지원금 찾기
- 의료비 지원 신청
- 여행 경보 확인

목적:

- 사용자의 자연어 의도를 생활 사건 단위 시나리오로 연결한다.
- 서비스와 API를 절차 단계에 배치한다.
- P2가 사용할 Scenario Tool의 입력 데이터를 제공한다.

입력:

- `02_catalog/services.jsonl`
- `03_semantic/concepts.jsonl`
- `03_semantic/service_tags.jsonl`
- P4의 `gov24_service_metadata.jsonl`

산출물:

```text
projects/p1_civic_scenario_catalog/
  scenarios.jsonl
  scenario_steps.jsonl
  scenario_service_links.jsonl
  scenario_query_examples.jsonl
```

최소 스키마:

```json
{
  "scenario_id": "startup_cafe",
  "name": "카페 창업",
  "description": "카페 창업에 필요한 주요 행정 절차",
  "domain_ids": ["business", "food_service"],
  "source": "manual",
  "review_status": "reviewed"
}
```

완료 기준:

- MVP 시나리오 5개가 작성되어 있다.
- 각 시나리오는 단계, 관련 기관, 관련 서비스, 링크 후보를 가진다.
- 모든 연결은 공통 ID를 사용한다.
- P4 산출물을 소비하되 P4에 역의존하지 않는다.

### 5.3 P2. GovAPI MCP Server

공공 API를 에이전트가 호출 가능한 MCP 도구로 변환하는 프로젝트다.

목적:

- 검증된 공공 API를 에이전트 도구로 노출한다.
- API 명세, 인증 방식, 요청 파라미터, 응답 스키마를 도구 계약으로 변환한다.
- 신청 자동화가 아니라 조회와 실행 준비를 지원한다.

입력:

- `02_catalog/endpoints.jsonl`
- `02_catalog/fields.jsonl`
- `04_output/api_tool_specs.jsonl`
- P1의 `scenario_steps.jsonl`
- P4의 링크 메타데이터
- P0의 호출 가능 API 검증 결과

산출물:

```text
projects/p2_govapi_mcp_server/
  tools/
  tool_specs.jsonl
  callable_api_registry.jsonl
  mcp_server/
```

완료 기준:

- 실제 호출 검증된 API 5개가 MCP 도구로 노출된다.
- startup_cafe 시나리오에 필요한 도구 최소 1~2개가 동작한다.
- 각 도구는 출처, 인증 필요 여부, 호출 제한, 실패 처리를 명시한다.
- 민감정보를 저장하지 않는다.

### 5.4 P3. Gov Service Graph

기관, 서비스, API, 시나리오, 개념 사이의 관계를 그래프로 구성하는 프로젝트다.

목적:

- 서비스 간 대체·보완·선행 관계를 표현한다.
- 시나리오 단계와 실제 API/기관 관계를 탐색 가능하게 만든다.
- AG-UI의 flow 레이아웃과 P5 통합 응답에 관계 데이터를 제공한다.

입력:

- `02_catalog/agencies.jsonl`
- `02_catalog/services.jsonl`
- `02_catalog/endpoints.jsonl`
- `03_semantic/concepts.jsonl`
- `03_semantic/concept_relations.jsonl`
- `03_semantic/service_tags.jsonl`
- `04_output/cross_ref/service_relations.jsonl`
- P1, P2, P4 산출물

산출물:

```text
projects/p3_gov_service_graph/
  graph_nodes.jsonl
  graph_edges.jsonl
  neo4j_import/
  graph_quality_report.json
```

관계 유형:

- `PRECEDES`
- `RELATED_TO`
- `SAME_CONCEPT`
- `ALTERNATIVE`
- `COMPLEMENTARY`
- `PREREQUISITE`
- `BROADER`
- `NARROWER`

완료 기준:

- startup_cafe 그래프가 구성되어 있다.
- 외국인 운전면허 데모용 절차 그래프가 구성되어 있다.
- 그래프 노드와 관계는 모두 원천 ID와 출처를 가진다.
- P3는 sink로만 동작하고 원천 시나리오나 API를 새로 만들지 않는다.

### 5.5 P4. Gov24 Link Resolver

정부24 또는 기관 페이지 링크를 서비스와 시나리오 단계에 연결하는 프로젝트다.

목적:

- CappBizCD 또는 정부24 메타데이터를 기반으로 딥링크 후보를 만든다.
- 사용자가 실제 신청·확인 페이지로 이동할 수 있는 링크를 제공한다.
- P1 시나리오 단계에 링크를 주입할 수 있는 파일 산출물을 만든다.

입력:

- 정부24 메타데이터
- 기관 링크 후보
- `02_catalog/services.jsonl`
- `03_semantic/aliases.jsonl`

산출물:

```text
projects/p4_gov24_link_resolver/
  gov24_service_metadata.jsonl
  gov24_link_candidates.jsonl
  link_resolution_report.json
```

완료 기준:

- CappBizCD 또는 동등한 식별자 기반 링크 100개가 정리되어 있다.
- 각 링크는 출처, 신뢰도, 검수 상태를 가진다.
- P4는 다른 프로젝트에 의존하지 않는다.

### 5.6 P5. Integration Layer

P1~P4와 공통 데이터 기반 산출물을 결합하는 최종 통합 레이어다.

목적:

- 자연어 질의 한 줄에서 시나리오, API 도구, 그래프, 링크, 추천 결과를 통합 응답으로 만든다.
- AG-UI 데모와 운영 API가 사용할 통합 응답 계약을 제공한다.
- 각 서브프로젝트의 산출물을 소비하되 원천 데이터를 새로 만들지 않는다.

입력:

- P1 시나리오 산출물
- P2 MCP 도구 산출물
- P3 그래프 산출물
- P4 링크 산출물
- `04_output/recommender_catalog.jsonl`
- `04_output/retrieval_chunks.jsonl`
- `05_indexes` 검색 인덱스

산출물:

```text
projects/p5_integration_layer/
  integration_api/
  demo_ui/
  integration_tests/
  response_schema.json
```

대표 질의:

```text
카페를 창업하려면 무엇을 해야 해?
```

통합 응답에 포함할 내용:

- 시나리오 식별: `startup_cafe`
- 단계 출력: 사업자등록, 영업신고, 위생교육, 4대보험
- 관련 기관 출력
- 정부24·기관 딥링크 출력
- 호출 가능한 공공 API 도구 출력
- 기관·서비스 관계 그래프 출력
- 자연어 요약 답변

완료 기준:

- startup_cafe 통합 데모가 end-to-end로 동작한다.
- P1~P4 산출물이 바뀌어도 P5는 계약 파일/API를 통해서만 갱신된다.
- 통합 테스트가 서브프로젝트 산출물 호환성을 검증한다.

## 6. AG-UI 데모 계획

AG-UI는 최종 서비스의 사용자 경험을 빠르게 검증하기 위한 별도 데모다. 기존 운영 코드(`/query/stream`, `/workflow/*`)를 건드리지 않고 별도 엔드포인트와 별도 페이지로 분리한다.

대상 범위:

```text
nara_service/backend
nara_service/frontend
```

신규 엔드포인트:

```text
POST /agui/search
GET /agui/node/{service_id}
```

신규 프론트 페이지:

```text
/demo
```

스트리밍 형식:

```json
{
  "type": "<event_type>",
  "ts": 1737432901000,
  "payload": {}
}
```

이벤트 타입:

- `step`
- `layout`
- `documents`
- `token`
- `done`
- `error`

에러 코드:

- `LLM_TIMEOUT`
- `LLM_PARSE_ERROR`
- `NEO4J_UNAVAILABLE`
- `INTERNAL_ERROR`

### 6.1 Phase 0. 데모 준비

작업:

- Ollama `gemma4:e4b` 모델 존재 확인
- Neo4j 컨테이너 기동 확인
- 데모용 가짜 노드 시드 적재
- NDJSON envelope 타입 정의
- 데모 인증 정책 확정

시드 쿼리 3종:

| 유형 | 쿼리 | 기대 레이아웃 |
| --- | --- | --- |
| 단일형 | 여행경보 어디서 봐? | single |
| 비교형 | 날씨 관련 API 뭐 있어? | grid |
| 절차형 | 외국인 운전면허 따는 절차 | flow |

데모 그래프 노드:

```text
DEMO_S1 출입국·외국인청_체류자격조회
DEMO_S2 도로교통공단_운전면허시험접수
DEMO_S3 도로교통공단_운전면허시험결과조회
DEMO_S4 도로교통공단_면허증발급내역
```

관계:

```text
DEMO_S1 -> DEMO_S2 -> DEMO_S3 -> DEMO_S4
```

### 6.2 Phase 1. Thinking Steps

목적:

- 사용자가 검색을 실행하면 좌측에 사고 과정이 단계별로 표시된다.
- 우측에는 검색 결과 카드와 답변 텍스트 스트림이 표시된다.

백엔드:

- `routes/agui.py` 작성
- `/agui/search` 스트리밍 골격 구현
- `/agui/node/{service_id}` 골격 구현
- 기존 RAG 검색 호출 전후로 step 이벤트 emit

프론트엔드:

- `/demo/page.tsx`
- `ThinkingTimeline.tsx`
- `ResultPanel.tsx`
- `streamClient.ts`
- `types.ts`

단계:

```text
query_analysis
vector_search
graph_lookup
llm_generation
```

완료 기준:

- 검색 1회 실행 시 단계가 순차적으로 켜진다.
- 검색 결과와 답변 토큰이 우측에 표시된다.
- 단계 사이 최소 150ms 지연이 적용된다.

### 6.3 Phase 2. Generative UI

목적:

- 쿼리 성격에 따라 single, grid, flow 레이아웃을 자동 선택한다.

쿼리 분류:

- 모델: Ollama `gemma4:e4b`
- 타임아웃: 1초
- 실패 시 휴리스틱 fallback
- 모델 부재 시 백엔드 부팅 실패

분류 결과:

```json
{
  "kind": "single",
  "confidence": 0.87
}
```

레이아웃 이벤트:

```json
{
  "kind": "flow",
  "nodes": [],
  "edges": []
}
```

프론트엔드 컴포넌트:

```text
ResultLayoutRouter.tsx
ResultLayoutSingle.tsx
ResultLayoutGrid.tsx
ResultLayoutFlow.tsx
NodeDetailDrawer.tsx
```

완료 기준:

- 시드 쿼리 3종에서 서로 다른 레이아웃이 표시된다.
- flow 노드 클릭 시 endpoint 상세가 표시된다.
- layout 이벤트가 documents보다 먼저 와도 UI가 깨지지 않는다.

### 6.4 Phase 3. 통합 데모 다듬기

작업:

- lucide 아이콘 적용
- 상태별 색상 적용
- 레이아웃 전환 150ms fade-in
- 시드 쿼리 버튼 추가
- 데모 영상 또는 GIF 캡처
- `nara_service/docs/agui_demo.md` 작성

완료 기준:

- 데모 시나리오가 문서만 보고 재현 가능하다.
- 시연 중 입력창 disable, 오류 메시지, 인증키 처리까지 정리되어 있다.

## 7. 공통 계약

### 7.1 ID 규칙

모든 엔티티는 안정적인 ID를 가진다.

권장 접두어:

```text
agency:{agency_code}
service:{source_portal}:{source_object_id}
endpoint:{service_id}:{method}:{path_hash}
field:{endpoint_id}:{field_role}:{field_name}
concept:{domain}.{name}
scenario:{slug}
step:{scenario_id}:{step_order}
tool:{service_id}:{operation}
link:{source}:{external_id}
```

### 7.2 출처와 검수 상태

자동 생성되거나 추론된 데이터는 반드시 다음 필드를 가진다.

```json
{
  "source": "manual|crawler|llm|rule|api",
  "source_path": "data/02_catalog/services.jsonl",
  "confidence": 0.91,
  "review_status": "pending|reviewed|rejected"
}
```

### 7.3 신청 자동화와 신청 준비 구분

이 프로젝트는 MVP 단계에서 본인인증, 실제 신청 제출, 민감정보 입력 자동화를 하지 않는다.

허용:

- 신청 절차 안내
- 조회형 API 호출
- 필요한 서류와 조건 안내
- 정부24 또는 기관 링크 제공
- 에이전트 도구용 조회 API 제공

금지:

- 본인인증 자동화
- 신청서 자동 제출
- 주민등록번호 등 민감정보 저장
- 사용자 동의 없는 개인정보 처리

## 8. 추천 개발 일정

### 0주차. 사전 작업

목표:

- 라이선스 검토
- 조회 가능 API 사전 매핑
- 공통 ID·스키마 확정
- 기존 데이터 구조 정리

산출물:

- `licensing_review.md`
- `startup_cafe_callable_apis.jsonl`
- `common_schema.json`
- `id_naming.md`

### 1개월차. 서브프로젝트 착수

1주차:

- 0주차 산출물 리뷰
- 데이터 폴더 구조 생성
- `02_catalog` 최소 파일 생성

2주차:

- P4 Gov24 Link Resolver 초안
- 링크 후보 수집과 식별자 정리

3주차:

- P1 Civic Scenario Catalog 초안
- startup_cafe 시나리오 작성

4주차:

- P2 MCP Tool 1~2개
- P3 그래프 스키마 초안
- AG-UI Phase 0 준비

### 2개월차. 각 프로젝트 MVP

P4:

- CappBizCD 또는 정부24 링크 100개

P1:

- 시나리오 5개 완성

P2:

- MCP tool 5개

P3:

- startup_cafe 그래프
- 외국인 운전면허 데모 그래프

AG-UI:

- Phase 1 Thinking Steps
- Phase 2 Generative UI

### 3개월차. P5 통합 레이어

목표:

- startup_cafe end-to-end 통합 데모
- 자연어 질의 → 시나리오 → 링크 → API 도구 → 그래프 → 답변

작업:

- `integration_api` 작성
- `demo_ui` 작성
- `integration_tests` 작성
- AG-UI와 P5 응답 계약 연결

완료 기준:

- “카페를 창업하려면 무엇을 해야 해?” 질의가 통합 응답으로 처리된다.
- P1~P4 산출물 변경 시 통합 테스트가 호환성을 검증한다.

## 9. 리스크와 대응

| 리스크 | 영향 | 대응 |
| --- | --- | --- |
| 실제 호출 가능한 API 부족 | P2 지연 | P0에서 3개 이상 사전 검증 후 착수 |
| 라이선스/재배포 범위 불명확 | 공개·배포 제한 | `licensing_review.md` 선작성 |
| 기관별 용어 차이 | 검색·추천 품질 저하 | `03_semantic`에 aliases, concepts, field_mappings 축적 |
| 프로젝트 간 순환 의존 | 통합 불안정 | P4→P1→P2→P3→P5 방향 고정 |
| AG-UI가 운영 코드에 영향 | 회귀 위험 | `/agui/*`, `/demo`로 완전 분리 |
| Ollama 모델 부재 | 데모 부팅 실패 | Phase 0 환경 점검, 명확한 오류 처리 |
| Neo4j 운영 데이터 없음 | flow 데모 빈약 | 데모용 `is_demo=true` 시드 노드 별도 적재 |
| ChromaDB metadata 제약 | 필터 검색 불안정 | 배열 미지원 시 text fallback 필드 생성 |
| 자동 추론 오류 | 잘못된 서비스 추천 | `confidence`, `review_status` 필수화 |

## 10. 우선순위

가장 먼저 해야 할 작업:

1. `data/02_catalog` 최소 카탈로그 생성
2. 공통 ID·스키마 문서화
3. startup_cafe 기준 호출 가능한 API 검증
4. P4 링크 후보 수집
5. P1 startup_cafe 시나리오 작성
6. AG-UI 데모 Phase 0 준비

초기에는 완성도보다 계약 안정성이 중요하다. 공통 ID와 산출물 스키마가 흔들리면 P1~P5가 모두 다시 흔들리므로, 구현보다 먼저 파일 계약을 고정한다.

## 11. 최종 방향

이 프로젝트는 다음 순서로 성장시킨다.

```text
데이터 기반 정리
  -> 의미 통합
  -> 서브프로젝트별 MVP
  -> AG-UI 데모 검증
  -> P5 통합 레이어
  -> 운영 API/검색/에이전트 인프라
```

최종 통합은 하나의 거대한 코드베이스를 처음부터 만드는 방식이 아니라, 잘 정의된 서브프로젝트들의 산출물을 P5가 소비하는 방식으로 진행한다.

각 서브프로젝트는 독립적으로 구현·검증·정교화할 수 있어야 하며, 통합 시점에는 코드 의존이 아니라 데이터 파일과 API 계약으로만 연결되어야 한다.

이 방향을 지키면 프로젝트가 커져도 다음을 유지할 수 있다.

- 원본 데이터 추적 가능성
- 부처 간 의미 통합 가능성
- API 도구화 가능성
- 그래프 확장 가능성
- UI 실험의 안전성
- PostgreSQL, Neo4j 등 운영 DB로의 단계적 전환 가능성

계획서 끝.
