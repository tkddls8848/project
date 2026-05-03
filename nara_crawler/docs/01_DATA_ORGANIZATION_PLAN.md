# 공공데이터 크롤링 저장 구조 계획

## 목표

이 프로젝트의 목표는 공공데이터 포털 등에서 제공하는 여러 공공기관/부처의 API 명세, 파일데이터, 표준데이터를 수집한 뒤 일반 사용자가 자연어로 필요한 공공서비스를 찾고 추천받을 수 있게 만드는 것이다.

핵심 문제는 단순 수집이 아니라 **부처 간 사일로 해소**다. 같은 의미가 기관마다 다른 용어, 다른 필드명, 다른 서비스 설명으로 나타나기 때문에, 저장 구조도 데이터 타입별 적재소가 아니라 의미 통합과 추천을 전제로 설계해야 한다.

개인 MVP 단계에서는 운영 DB를 먼저 도입하지 않는다. 기준 데이터는 JSONL 파일로 관리하고, DuckDB는 JSONL을 SQL로 조회/검증/리포트 생성하는 로컬 분석 엔진으로, ChromaDB는 RAG 청크의 벡터 검색 인덱스로 사용한다.

## 현재 구조의 한계

현재 데이터는 대체로 `data/raw_data` 아래에 데이터 타입별로 쌓인다.

```text
data/
  raw_data/
    01_openapi_results/
    02_fileData_results/
    03_standard_results/
    openapi_summary.json
    fileData_summary.json
    standard_summary.json
  index.json
```

이 구조는 초기 수집에는 편하지만 다음 한계가 있다.

- 수집 실행 단위, 크롤러 버전, 응답 상태, checksum 추적이 약하다.
- `openapi`, `filedata`, `standard`가 분리되어 있어 하나의 서비스 관점으로 보기 어렵다.
- 기관별 용어 차이와 필드명 차이를 별도 지식으로 축적하기 어렵다.
- 자연어 추천/RAG에 필요한 문서 조각과 메타데이터가 원본 구조에 섞이기 쉽다.
- 도메인별 보기, 기관별 보기, 연관 서비스 그래프가 파일 중복으로 흩어질 수 있다.

## 최종 결정

이 문서는 기존 `data_structure_plan.md`의 의견을 통합한 최종 기준 문서다.

최종 결정은 다음과 같다.

- `bronze` 또는 `02_refined` 같은 독립 정제 단계는 두지 않는다. 개인 MVP에서는 내용이 적고 관리 비용이 더 크다.
- `01_raw`의 원본에서 바로 `02_catalog`를 생성한다.
- `02_catalog`는 원본의 복사본이 아니라 통합 메타데이터 카탈로그다.
- 수집 이력은 덮어쓰지 않고 `crawl_history.jsonl`에 append-only로 보존한다.
- 최신 조회용 상태는 `crawl_latest.jsonl`로 별도 생성한다.
- `03_semantic`은 부처 간 사일로 해소를 위한 핵심 계층이다.
- `04_output`은 실제 추천, RAG, API 도구화에 바로 쓰는 산출물이다.
- `05_indexes`에는 DuckDB, BM25, ChromaDB가 만든 재생성 가능한 인덱스만 둔다.
- PostgreSQL과 Neo4j는 MVP 이후 필요성이 명확해질 때 검토한다.

## 설계 원칙

1. 원본은 불변으로 보존한다.
2. 수집 실행 단위와 원본 출처를 추적 가능하게 남긴다.
3. 부처/기관은 폴더 경로보다 메타데이터로 관리한다.
4. 데이터 타입별 원본 구조는 유지하되, 추천 시스템은 통합 카탈로그를 기준으로 사용한다.
5. 사일로 해소를 위한 의미 계층은 원본/카탈로그 데이터와 분리한다.
6. 도메인별/기관별 구조는 원본 저장소가 아니라 재생성 가능한 뷰로 다룬다.
7. RAG 청크와 검색 색인은 재생성 가능한 산출물로 취급한다.
8. 최상위 폴더는 처리 순서가 보이도록 숫자 접두어를 붙이되, 숫자만으로 의미를 숨기지 않고 역할명을 함께 쓴다.

## 번호 체계

최상위 폴더는 두 자리 숫자 접두어를 사용한다. 파일 탐색기에서도 처리 순서대로 정렬되어 관리하기 쉽다.

| 번호 | 폴더 | 의미 |
| --- | --- | --- |
| `01` | `01_raw/` | 수집 원본 |
| `02` | `02_catalog/` | 통합 메타데이터 카탈로그 |
| `03` | `03_semantic/` | 의미/용어/개념 통합 |
| `04` | `04_output/` | 추천/RAG/API 도구화용 빌드 산출물 |
| `05` | `05_indexes/` | DuckDB/BM25/ChromaDB 인덱스 |
| `99` | `99_reports/` | 리포트, 감사, 품질 진단 |

## 권장 디렉터리 구조

```text
data/
  01_raw/
    crawl_runs/
      2026-05-02T10-30-00/
        manifest.json
        openapi/
          15000001.json
        filedata/
          15000002.json
        standard/
          15012890.json

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
      welfare.jsonl
      transport.jsonl
    agency_views/
      MOIS.jsonl
      MOHW.jsonl
    cross_ref/
      service_relations.jsonl
    quality_report.json

  05_indexes/
    duckdb/
      nara.duckdb
    bm25/
      services/
      retrieval_chunks/
    chroma/
      chroma.sqlite3
      collections/

  99_reports/
    crawl_runs/
    catalog/
    semantic_conflicts/
    rag/
```

## 기술 역할

### JSONL

JSONL은 기준 데이터의 원본이다. `02_catalog`, `03_semantic`, `04_output`의 JSONL 파일을 신뢰 가능한 기준 데이터로 둔다.

장점:

- Git diff와 백업이 쉽다.
- DuckDB로 바로 조회할 수 있다.
- PostgreSQL, Neo4j, Parquet, ChromaDB로 나중에 변환하기 쉽다.

### DuckDB

DuckDB는 MVP 단계의 로컬 분석 엔진이다. 기준 데이터를 DuckDB 안에만 가두지 않고, JSONL을 읽어서 SQL 조회, 조인, 검증, 리포트 생성을 수행한다.

주요 역할:

- `02_catalog/*.jsonl` 조회
- `03_semantic/*.jsonl` 조회
- 카탈로그와 의미 매핑 조인
- 중복, 누락, 변경 감지 리포트 생성
- `04_output` 산출물 생성 전 품질 검증

예시:

```sql
SELECT service_id, name, agency_id
FROM read_json_auto('data/02_catalog/services.jsonl');
```

```sql
SELECT s.service_id, s.name, t.concept_id
FROM read_json_auto('data/02_catalog/services.jsonl') s
JOIN read_json_auto('data/03_semantic/service_tags.jsonl') t
  ON s.service_id = t.service_id
WHERE t.concept_id = 'target.small_business_owner';
```

`crawl_latest.jsonl`은 유지한다. DuckDB에서 `crawl_latest` VIEW를 만들 수는 있지만, JSONL 파일을 별도로 두면 DuckDB 없이도 최신 수집 상태를 확인하고 다른 스크립트에서 재사용하기 쉽다.

Parquet은 필수 형식이 아니다. 성능 문제가 실제로 생기면 `02_catalog`의 읽기 중심 파일을 빌드 산출물로 Parquet 변환할 수 있지만, 기준 데이터는 JSONL로 둔다.

### BM25

BM25는 키워드 검색용 고정 인덱스다. DuckDB FTS 등 다른 키워드 검색 대안은 MVP 범위에서 고려하지 않는다.

주요 역할:

- 서비스명, 설명, 태그 기반 키워드 검색
- 벡터 검색 전 후보군 축소
- ChromaDB 결과와 결합한 hybrid ranking
- 자연어 질의에서 명시 키워드가 강한 경우의 보완 검색

BM25 인덱스는 `02_catalog/services.jsonl`, `02_catalog/documents.jsonl`, `04_output/retrieval_chunks.jsonl`에서 재생성한다.

### ChromaDB

ChromaDB는 자연어 검색용 벡터 인덱스다. 전체 카탈로그를 ChromaDB에 넣지 않는다. `04_output/retrieval_chunks.jsonl`만 ChromaDB collection에 적재한다.

ChromaDB metadata에는 상세 데이터 전체를 넣지 않는다. 검색 후 DuckDB/JSONL에서 상세 정보를 다시 조회할 수 있도록 최소 ID만 넣는다.

MVP에서는 단일 컬렉션 `public_services`를 사용한다. 도메인별 컬렉션은 서비스 중복과 관리 비용이 커지므로 사용하지 않는다.

권장 metadata:

```json
{
  "chunk_id": "svc-15000001-overview",
  "service_id": "15000001",
  "domain_ids": ["finance", "small_business"],
  "concept_ids": ["target.small_business_owner"]
}
```

ChromaDB 버전이 배열 metadata와 `$contains` 필터를 지원하면 `domain_ids`, `concept_ids`, `agency_ids`는 배열로 저장한다. 사용하는 버전에서 배열 metadata가 불안정하면 빌드 단계에서 `domain_ids_text`, `concept_ids_text` 같은 구분 문자열 필드를 추가하는 fallback을 둔다.

검색 흐름:

```text
사용자 질문
  -> ChromaDB에서 관련 chunk 검색
  -> chunk의 service_id 추출
  -> DuckDB/JSONL에서 서비스 상세 조회
  -> 추천 결과 구성
```

### PostgreSQL과 Neo4j

MVP 초기에는 사용하지 않는다.

PostgreSQL은 사용자 계정, 검색 로그, 검수 UI, 동시 쓰기, 운영 API 서버가 필요해질 때 검토한다.

Neo4j는 관계 탐색 자체가 제품의 핵심 기능이 되었을 때 검토한다. 지금은 `concept_relations.jsonl`, `service_tags.jsonl`, `field_mappings.jsonl`, `service_relations.jsonl`을 ID 기반으로 잘 관리해 두면 나중에 Neo4j로 변환할 수 있다.

## 계층별 역할

### `01_raw/`

수집한 원본 응답을 그대로 보관하는 영역이다. 파싱 오류가 있더라도 수정하지 않는다.

권장 방식:

- `crawl_runs/{crawl_run_id}/` 단위로 저장한다.
- `crawl_run_id`는 `2026-05-02T10-30-00`처럼 시간까지 포함한다.
- `manifest.json`에 수집 시각, 수집기 버전, 요청 URL, 응답 상태, 파일 목록, checksum을 기록한다.

예시 `manifest.json`:

```json
{
  "crawl_run_id": "2026-05-02T10-30-00",
  "started_at": "2026-05-02T10:30:00+09:00",
  "source": "data.go.kr",
  "crawler_stage": "stage1_raw",
  "files": [
    {
      "data_type": "openapi",
      "source_object_id": "15000001",
      "path": "openapi/15000001.json",
      "http_status": 200,
      "checksum": "sha256:..."
    }
  ]
}
```

### `02_catalog/`

추천과 검색을 위해 여러 데이터 타입을 하나의 통합 메타데이터 카탈로그로 정리하는 영역이다.

이 계층부터는 데이터 타입보다 `service_id` 중심으로 다룬다. `01_raw/crawl_runs/`의 원본을 직접 읽어 생성하며, 별도 표준화 중간 단계 없이 원본에서 카탈로그로 바로 변환한다.

주요 파일:

- `agencies.jsonl`: 기관, 부처, 상위 기관, 기관 코드, 기관명 변경 이력
- `services.jsonl`: 서비스/API/데이터셋 단위의 통합 메타데이터
- `endpoints.jsonl`: API endpoint, method, URL, 인증 방식, 호출 가능 여부
- `fields.jsonl`: 요청/응답 필드, 타입, 필수 여부, 설명, 출처
- `documents.jsonl`: 서비스 설명, API 설명, 원본 설명문을 검색 가능한 문서 단위로 정리
- `crawl_history.jsonl`: 수집 이력 전체를 append-only로 보존하는 원장
- `crawl_latest.jsonl`: 최신 수집 결과만 모아 둔 재생성 가능한 조회용 스냅샷

수집 이력은 덮어쓰지 않는다. 수집 결과는 `crawl_history.jsonl`에 매번 새 레코드로 추가한다. 최신 상태 조회가 필요하면 `crawl_history.jsonl`을 기준으로 `crawl_latest.jsonl`을 재생성한다.

예시 `crawl_history.jsonl`:

```json
{
  "source_portal": "data.go.kr",
  "data_type": "openapi",
  "source_object_id": "15000001",
  "crawl_run_id": "2026-05-02T10-30-00",
  "raw_path": "01_raw/crawl_runs/2026-05-02T10-30-00/openapi/15000001.json",
  "checksum": "sha256:...",
  "collected_at": "2026-05-02T10:30:15+09:00",
  "http_status": 200,
  "change_status": "changed",
  "previous_crawl_run_id": "2026-05-01T10-30-00",
  "previous_checksum": "sha256:old...",
  "transform_status": "done"
}
```

예시 `crawl_latest.jsonl`:

```json
{
  "source_portal": "data.go.kr",
  "data_type": "openapi",
  "source_object_id": "15000001",
  "latest_crawl_run_id": "2026-05-02T10-30-00",
  "latest_raw_path": "01_raw/crawl_runs/2026-05-02T10-30-00/openapi/15000001.json",
  "latest_checksum": "sha256:...",
  "latest_collected_at": "2026-05-02T10:30:15+09:00",
  "latest_change_status": "changed"
}
```

변경 상태는 다음 값을 사용한다.

- `new`: 처음 발견된 항목
- `unchanged`: 이전 수집과 checksum이 동일한 항목
- `changed`: 이전 수집과 checksum이 다른 항목
- `deleted`: 이전에는 있었지만 최신 수집에서 사라진 항목
- `failed`: 수집 실패 항목

`02_catalog/fields.jsonl`이 먼저 안정화되어야 `03_semantic/field_mappings.jsonl`을 안전하게 만들 수 있다.

### `03_semantic/`

부처 간 사일로 문제를 해결하기 위한 의미 통합 계층이다. 기존 `data_structure_plan.md`의 `03_ontology/` 아이디어를 이 계층으로 통합한다.

주요 파일:

- `taxonomy.json`: 복지, 교통, 환경, 부동산, 교육 등 도메인 분류 체계
- `concepts.jsonl`: 표준 개념 목록
- `aliases.jsonl`: 기관별 표현, 동의어, 약어, 원문 용어와 표준 개념의 연결
- `field_mappings.jsonl`: API 필드와 표준 개념의 연결
- `service_tags.jsonl`: 서비스별 대상, 혜택, 자격, 지역, 절차 태그
- `concept_relations.jsonl`: 상하위/유사/관련 개념 관계
- `agency_glossary.jsonl`: 기관별 원본 용어집
- `query_examples.jsonl`: 사용자가 입력할 법한 질문 예시와 의도/개념 라벨

예시 `concepts.jsonl`:

```json
{"concept_id":"benefit.medical_expense_support","canonical_name":"의료비지원","domain":"welfare","description":"의료비, 진료비, 건강보험 관련 비용 지원"}
```

예시 `aliases.jsonl`:

```json
{"alias":"의료급여","concept_id":"benefit.medical_expense_support","agency_id":"MOHW","domain":"welfare","confidence":0.91,"source_service_id":"api_001","review_status":"pending"}
```

예시 `field_mappings.jsonl`:

```json
{"service_id":"15000001","endpoint_id":"15000001.getList","field_name":"bizrno","field_role":"request","concept_id":"identifier.business_registration_number","meaning":"사업자등록번호","confidence":0.96}
```

필드명 매핑은 기관 단위로 바로 합치지 않는다. `주소`, `주소지`, `소재지`는 서비스 맥락에 따라 거주지, 사업장 소재지, 기관 주소, 신청지 주소가 될 수 있으므로 `service_id + endpoint_id + field_name` 단위로 매핑한다.

예시 `query_examples.jsonl`:

```json
{"query":"자영업자가 받을 수 있는 지원금 찾아줘","intent":"find_benefit","concept_ids":["target.small_business_owner","benefit.financial_support"],"domain_ids":["small_business","finance"]}
```

### `04_output/`

실제 추천, 검색, RAG, 에이전트 API 호출에서 바로 소비하는 서비스용 데이터 영역이다. 기존 `data_structure_plan.md`의 `04_knowledge_base/`, `05_rag/`, `cross_ref` 아이디어를 이 계층으로 통합한다.

주요 파일:

- `recommender_catalog.jsonl`: 추천 랭킹에 필요한 통합 서비스 카탈로그
- `retrieval_chunks.jsonl`: ChromaDB에 적재할 RAG/자연어 검색용 문서 조각
- `api_tool_specs.jsonl`: 에이전트가 실제 API 호출 도구로 사용할 수 있는 명세
- `domain_views/*.jsonl`: 사용자 관점의 도메인별 뷰. 필요할 때만 생성하는 선택 산출물
- `agency_views/*.jsonl`: 기관별 뷰. 필요할 때만 생성하는 선택 산출물
- `cross_ref/service_relations.jsonl`: 기관 간 연관 서비스, 대체 서비스, 보완 서비스 관계
- `quality_report.json`: 누락 필드, 중복 서비스, 의미 충돌, 파싱 실패 통계

`domain_views/`와 `agency_views/`는 원본 저장 위치가 아니라 `02_catalog/`와 `03_semantic/`에서 재생성하는 선택 뷰다. DuckDB SQL로도 대체할 수 있으므로 프론트/API/검수 화면에서 실제 파일이 필요할 때만 만든다. 한 서비스가 여러 도메인에 걸치는 경우에도 원본 레코드는 중복하지 않고, 뷰에서만 여러 번 나타날 수 있다.

### `05_indexes/`

DuckDB, BM25, ChromaDB가 생성하는 재생성 가능한 인덱스 영역이다. 기준 데이터는 이 폴더가 아니라 JSONL에 있다.

주요 하위 폴더:

- `duckdb/`: JSONL 조회/검증/리포트 생성을 빠르게 하기 위한 DuckDB 파일
- `bm25/`: 서비스명, 설명, 청크 텍스트 기반 키워드 검색 인덱스
- `chroma/`: `04_output/retrieval_chunks.jsonl`을 적재한 ChromaDB 영속 저장소

`05_indexes/duckdb/nara.duckdb`는 필요할 때 재생성할 수 있어야 한다.

`05_indexes/bm25/`는 `02_catalog/documents.jsonl`과 `04_output/retrieval_chunks.jsonl`에서 다시 만들 수 있어야 한다. BM25는 이 프로젝트의 키워드 검색 표준으로 사용한다.

`05_indexes/chroma/`도 `04_output/retrieval_chunks.jsonl`에서 다시 만들 수 있어야 한다. ChromaDB를 정답 DB로 보지 않는다.

### `99_reports/`

수집, 카탈로그 생성, 의미 통합, RAG 청킹 과정의 진단 리포트를 보관한다.

예시:

- 수집 성공/실패 통계
- API 명세 파싱 실패 목록
- 필수 메타데이터 누락 목록
- 동일 의미로 추정되는 용어 후보
- 서로 다른 의미로 쓰인 동일 용어 후보
- LLM 자동 매핑 후 수동 검수가 필요한 항목
- ChromaDB 적재 실패 목록
- DuckDB 검증 쿼리 결과

## 부처/기관을 폴더로 깊게 나누지 않는 이유

부처나 기관 기준 폴더 구조는 직관적이지만 장기 운영에는 불리하다.

- 정부 조직 개편으로 부처명이 바뀔 수 있다.
- 하나의 서비스가 여러 기관과 연결될 수 있다.
- 위탁 기관, 운영 기관, 소관 기관이 다를 수 있다.
- 자연어 추천에서는 기관보다 사용자 의도, 대상, 혜택, 자격, 지역이 더 중요하다.
- 동일한 개념이 여러 부처에서 다른 이름으로 나타난다.

따라서 부처와 기관은 경로가 아니라 메타데이터로 관리한다.

```json
{
  "service_id": "15000001",
  "provider_agency_id": "MOIS",
  "provider_agency_name": "행정안전부",
  "managing_agency_id": "LOCAL_GOV",
  "source_portal": "data.go.kr",
  "data_type": "openapi",
  "domain_ids": ["welfare", "local_government"]
}
```

## 자연어 추천을 위한 RAG 청크

`retrieval_chunks.jsonl`에는 API 명세를 그대로 넣기보다, 사용자가 검색할 만한 문장으로 재구성한 텍스트를 넣는다. 청크에는 반드시 온톨로지 태그와 도메인 분류를 메타데이터로 포함한다.

```json
{
  "chunk_id": "svc-15000001-overview",
  "service_id": "15000001",
  "source_api_id": "api_001",
  "agency_ids": ["MSS"],
  "domain_ids": ["finance", "small_business"],
  "concept_ids": [
    "target.small_business_owner",
    "identifier.business_registration_number",
    "benefit.policy_fund"
  ],
  "ontology_tags": ["소상공인", "자영업자", "정책자금", "사업자등록번호"],
  "text": "소상공인 또는 자영업자가 지원 가능한 정책자금 정보를 조회할 수 있는 공공 API입니다. 지역, 업종, 사업자등록번호 등의 조건으로 검색할 수 있습니다.",
  "search_text": "소상공인 자영업자 정책자금 지원 사업자등록번호 지역 업종",
  "source_path": "data/02_catalog/services.jsonl"
}
```

ChromaDB 적재 시에는 `text`를 document로 사용하고, `chunk_id`, `service_id`, `domain_ids`, `concept_ids`를 metadata로 사용한다.

BM25 적재 시에는 `text`, `search_text`, `ontology_tags`, 서비스명, 기관명, 도메인명을 키워드 검색 대상으로 사용한다.

## 관계 데이터와 향후 DB 전환

나중에 PostgreSQL이나 Neo4j로 옮기기 쉽게 하려면 모든 엔티티와 관계를 ID 중심으로 관리해야 한다.

원칙:

- Agency, Service, Endpoint, Field, Concept는 안정적인 ID를 가진다.
- 관계 데이터는 별도 JSONL로 분리한다.
- 관계 레코드는 문자열 설명이 아니라 `from_id`, `to_id`, `relation_type` 또는 명확한 ID 필드를 가진다.
- 자동 추론된 관계에는 `confidence`, `source`, `review_status`를 둔다.
- 이름, 설명, 별칭은 ID가 아니라 속성으로 둔다.

Neo4j 전환 시 예상 매핑:

```text
02_catalog/agencies.jsonl                  -> (:Agency)
02_catalog/services.jsonl                  -> (:Service)
02_catalog/endpoints.jsonl                 -> (:Endpoint)
02_catalog/fields.jsonl                    -> (:Field)
03_semantic/concepts.jsonl                 -> (:Concept)
03_semantic/aliases.jsonl                  -> (:Alias)
03_semantic/field_mappings.jsonl           -> (:Field)-[:MAPS_TO]->(:Concept)
03_semantic/service_tags.jsonl             -> (:Service)-[:TAGGED_AS]->(:Concept)
03_semantic/concept_relations.jsonl        -> (:Concept)-[:RELATED_TO]->(:Concept)
04_output/cross_ref/service_relations.jsonl -> (:Service)-[:RELATED_TO]->(:Service)
```

## 기존 `data_structure_plan.md` 반영 사항

기존 문서의 다음 아이디어는 최종안에 반영한다.

| 기존 아이디어 | 최종 반영 |
| --- | --- |
| 사일로 해소 레이어 분리 | `03_semantic/` |
| 부처별 동의어 사전 | `03_semantic/aliases.jsonl`, `03_semantic/agency_glossary.jsonl` |
| 필드명 통합 매핑 | `03_semantic/field_mappings.jsonl` |
| 동일 개념 서비스 클러스터 | `03_semantic/service_tags.jsonl`, `04_output/cross_ref/service_relations.jsonl` |
| 도메인 기준 재편성 | `04_output/domain_views/` |
| 기관별 뷰 | `04_output/agency_views/` |
| RAG 청크 분리 | `04_output/retrieval_chunks.jsonl` |
| 온톨로지 태그 포함 | RAG 청크와 추천 카탈로그의 필수 메타데이터 |

그대로 채택하지 않는 항목은 다음과 같다.

- `02_refined/`: 독립 단계로 두기에는 역할이 약하다.
- `synonyms/{domain}.json`: 도메인별 파일에 동의어를 고정하면 중복이 커진다.
- `by_domain/복지/의료지원.json`: 원본처럼 관리하면 중복과 변경 비용이 커진다.
- `chunks/openapi`, `chunks/filedata`: 최종 RAG 청크는 데이터 타입보다 사용자 의도와 서비스 개념 중심으로 관리한다.

## 이행 계획

### 1단계: 기존 구조 보존

현재 `data/raw_data`는 바로 삭제하거나 대규모 이동하지 않는다. 신규 구조를 추가하고, 기존 데이터는 점진적으로 읽어 들인다.

```text
data/
  raw_data/
  01_raw/
  02_catalog/
  03_semantic/
  04_output/
  05_indexes/
  99_reports/
```

### 2단계: 수집 실행 단위 도입

새로운 수집부터 `data/01_raw/crawl_runs/{crawl_run_id}/`에 저장하고 `manifest.json`을 만든다.

### 3단계: 통합 카탈로그 생성

`raw_data`와 `01_raw`를 읽어 다음 파일을 우선 만든다.

- `02_catalog/agencies.jsonl`
- `02_catalog/services.jsonl`
- `02_catalog/endpoints.jsonl`
- `02_catalog/fields.jsonl`
- `02_catalog/crawl_history.jsonl`
- `02_catalog/crawl_latest.jsonl`

이 단계가 먼저 안정화되어야 의미 매핑과 RAG 청킹이 흔들리지 않는다.

### 4단계: 의미 통합 계층 구축

`03_semantic/taxonomy.json`, `03_semantic/concepts.jsonl`, `03_semantic/aliases.jsonl`, `03_semantic/field_mappings.jsonl`을 만든다.

초기에는 규칙 기반, LLM 후보 생성, 수동 검수를 섞는다. 자동 생성 결과에는 반드시 `confidence`와 `review_status`를 둔다.

예시:

- `소상공인`, `자영업자`, `영세사업자` -> `target.small_business_owner`
- `사업자번호`, `사업자등록번호`, `bizrno` -> `identifier.business_registration_number`
- `의료급여`, `건강보험지원`, `의료비지원사업` -> `benefit.medical_expense_support`

### 5단계: 서비스용 산출물 생성

`02_catalog/`와 `03_semantic/`을 조합해 다음 파일을 만든다.

- `04_output/recommender_catalog.jsonl`
- `04_output/retrieval_chunks.jsonl`
- `04_output/domain_views/*.jsonl`
- `04_output/agency_views/*.jsonl`
- `04_output/cross_ref/service_relations.jsonl`
- `04_output/quality_report.json`

연관 서비스 관계는 다음 유형을 구분한다.

- `same_concept`: 같은 서비스 개념
- `alternative`: 대체 가능한 서비스
- `complementary`: 함께 쓰면 좋은 서비스
- `prerequisite`: 선행 조건 또는 선행 서비스
- `broader` / `narrower`: 상하위 관계

### 6단계: DuckDB, BM25, ChromaDB 인덱스 생성

DuckDB는 JSONL 조회와 리포트 생성을 위해 만든다.

```text
05_indexes/duckdb/nara.duckdb
```

BM25는 서비스명, 설명, RAG 청크 텍스트의 키워드 검색을 위해 만든다.

```text
05_indexes/bm25/
```

ChromaDB는 `04_output/retrieval_chunks.jsonl`에서 재생성한다.

```text
05_indexes/chroma/
```

추천 랭킹에는 다음 신호를 사용할 수 있다.

- 사용자 자연어 질의와 문서 조각의 유사도
- BM25 키워드 매칭 점수
- 질의에서 추출한 대상/지역/혜택/자격 개념
- API의 호출 가능 여부
- 최신 갱신일
- 기관 신뢰도 또는 공식성
- 필수 파라미터 충족 가능성
- 동일 서비스 중복 제거 점수
- 동일 개념/대체 서비스/보완 서비스 관계

## 우선 적용할 최소 구조

처음부터 전체 구조를 모두 구현하기 부담스럽다면 아래 최소 구조부터 적용한다.

```text
data/
  raw_data/
  01_raw/
    crawl_runs/
  02_catalog/
    agencies.jsonl
    services.jsonl
    endpoints.jsonl
    fields.jsonl
    crawl_history.jsonl
    crawl_latest.jsonl
  03_semantic/
    taxonomy.json
    concepts.jsonl
    aliases.jsonl
    field_mappings.jsonl
  04_output/
    retrieval_chunks.jsonl
    recommender_catalog.jsonl
  05_indexes/
    duckdb/
    bm25/
    chroma/
```

이 최소 구조만 있어도 원본 보존, 통합 카탈로그, 의미 통합, 자연어 검색을 시작할 수 있다.

## 결론

최종 저장 구조는 `01_raw → 02_catalog → 03_semantic → 04_output → 05_indexes` 흐름을 기준으로 한다.

개인 MVP 단계에서는 JSONL을 기준 데이터로 두고, DuckDB, BM25, ChromaDB를 재생성 가능한 보조 인덱스로 사용한다. 이 방식은 구현과 관리가 쉽고, PostgreSQL이나 Neo4j로 옮겨야 하는 시점이 와도 데이터 구조를 크게 바꾸지 않아도 된다.

핵심은 `03_semantic/` 계층에서 표준 개념, 기관별 별칭, 필드 매핑, 서비스 태그를 꾸준히 축적하는 것이다. 부처 간 사일로 문제는 폴더 구조만으로 해결할 수 없으며, 이 의미 계층이 추천 품질의 핵심 자산이 된다.
