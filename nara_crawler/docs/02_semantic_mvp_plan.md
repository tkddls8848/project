# nara_crawler 시맨틱 MVP 통합 계획

최종 업데이트: 2026-05-09

## 문서 목적

이 문서는 `docs/02_REMAINING_TASKS.md`와 `docs/03_remain.md`를 비교하여, 현재 구현된 크롤링 데이터에서 바로 검증 가능한 시맨틱/검색 계획을 정리한다.

목표는 두 가지다.

1. 현재 수집된 카탈로그와 serving 산출물을 깨지 않고 개선한다.
2. 추후 부처 간 유사의미 통합을 위한 데이터 정제와 동일성 식별 기반을 만들되, 초기 단계에서는 오버엔지니어링을 피한다.

## 두 문서 비교

| 항목 | `02_REMAINING_TASKS.md` | `03_remain.md` | 통합 판단 |
| --- | --- | --- | --- |
| 성격 | 남은 작업 목차와 단계 순서 | Stage 4 청킹 상세 구현 계획 | `02`의 단계성을 유지하고 `03`의 청킹 구조는 축소 적용한다. |
| 현재 구현 반영 | stage1, stage2, 일부 serving 생성 상태를 반영 | Qdrant, parent/child, graph까지 목표 구조를 전제 | 현재 코드는 ChromaDB와 overview 청크만 있으므로 Qdrant/graph는 후순위로 둔다. |
| semantic 접근 | 규칙 기반 최소 구현 | semantic metadata 병합 전제 | 먼저 규칙 기반 `service_tags`와 최소 concept만 만든다. |
| 검색 기술 | DuckDB, BM25, ChromaDB 순차 추가 | Qdrant local + bge-m3 hybrid | 초기 검증은 이미 구현된 ChromaDB로 하고, BM25는 키워드 보강 후 추가한다. |
| Graph | 직접 언급 적음 | NetworkX/Neo4j 산출물 계획 | 초기에는 graph DB를 쓰지 않고 JSONL 관계 후보만 남긴다. |
| 청킹 | 상세 없음 | overview, summary, target, benefit, api_schema | MVP는 `overview`, `summary`, `api_schema`부터 시작하고 target/benefit은 데이터가 안정된 뒤 분리한다. |

## 현재 구현/데이터 상태

2026-05-09 기준 로컬 산출물은 다음 상태다.

| 산출물 | 상태 |
| --- | --- |
| `data/02_catalog/services.jsonl` | 91건 |
| `data/02_catalog/documents.jsonl` | 91건 |
| `data/02_catalog/endpoints.jsonl` | 4건 |
| `data/02_catalog/fields.jsonl` | 0건 |
| `data/03_semantic/*.jsonl` | 대부분 0건 |
| `data/04_serving/retrieval_chunks.jsonl` | 91건, 전부 `overview` 단일 청크 |
| `data/04_serving/api_tool_specs.jsonl` | 4건 |
| `data/05_indexes/chroma/` | ChromaDB 인덱스 생성 흔적 존재 |

현재 가장 큰 병목은 `fields.jsonl`이 비어 있다는 점이다. 부처 간 유사의미 통합에서 중요한 대상은 서비스명뿐 아니라 `사업자등록번호`, `법인등록번호`, `기관코드`, `행정동코드` 같은 필드 단위 의미인데, 현재는 필드 기반 검증이 불가능하다.

## Stage 0 입력: 행정 표준 용어/단어 사전

부처 간 유사의미 통합과 필드 매핑의 정답 후보를 외부에서 먼저 확보한다. 정규식과 규칙 기반 추출보다 행정안전부 표준이 우선이다.

입력 파일 (`stage0_term_definition/data/term_definition_fileData/`):

| 파일 | 단위 | 행 예시 |
| --- | --- | --- |
| `공통표준용어_최종.csv` | 용어(필드 후보) | 1회섭취참고량명 / RAFOS_NM / 명V100 / 100자리 이내 문자 |
| `공통표준단어_점검.csv` | 단어(용어 구성요소) | 1회섭취참고량 / RAFOS / Reference Amount For One Serving |
| `category.md` | data.go.kr 16개 카테고리 | 공공행정, 과학기술, 교육, … 환경기상 |

현재 Stage 0의 필수 기준 파일은 위 3개다. `목록개방현황`과 `목록 메타정보`는 전체 카탈로그의 분류체계/키워드/요청변수/출력결과를 보강하기 위한 참조 파일이며, 표준 용어 사전의 직접 원천은 아니다. `행정표준코드 전체(15092039)`는 `행정표준코드명`을 실제 코드 목록과 조인해야 할 때 쓰는 후속 보강 파일로 둔다.

| Stage 0 파일 | 현재 역할 | MVP 반영 수준 |
| --- | --- | --- |
| `category.md` | data.go.kr UI 16개 카테고리의 정규 domain 기준 | 필수 |
| `공통표준용어_최종.csv` | API 필드/컬럼 후보를 표준 용어로 매핑하는 1차 기준 | 필수 |
| `공통표준단어_점검.csv` | 표준 용어를 구성 단어로 분해하고 형식단어 접미어를 판정하는 기준 | 필수 |
| `목록개방현황` CSV | 서비스 카탈로그의 분류체계/키워드 보강 | 선택 |
| `목록 메타정보` CSV | 요청변수/출력결과 보강 및 `fields.jsonl` 보조 추출 | 선택 |
| `행정표준코드 전체` CSV | `행정표준코드명`과 실제 코드 목록 조인 | 후속 |

용어는 `field_name ↔ concept_id` 매칭에, 단어는 `concept` 한글 정규명·영문약어 사전과 형식단어 접미어 정규화에 쓴다.

권장 수준까지 매핑하는 컬럼 — 필수와 권장만 적재하고 거버넌스/금칙어는 제외한다.

| 등급 | 용어 CSV 컬럼 | 단어 CSV 컬럼 | 매핑 대상 |
| --- | --- | --- | --- |
| 필수 | 공통표준용어명 | 공통표준단어명 | concept canonical |
| 필수 | 공통표준용어영문약어명 | 공통표준단어영문약어명 | field_name 매칭 키 |
| 필수 | 공통표준용어설명 | 공통표준단어 설명 | concept description / 임베딩 보강 |
| 필수 | 공통표준도메인명 | 공통표준도메인분류명 | domain_id 정규화 |
| 필수 | 용어 이음동의어 목록 | 이음동의어 목록 | aliases.jsonl |
| 권장 | 저장 형식 | — | field_type |
| 권장 | 표현 형식 | — | format |
| 권장 | 허용값 | — | allowed_values (enum) |
| 권장 | 행정표준코드명 | — | code_link (15092039 조인 키) |
| 권장 | 소관기관명 | — | owner_agency |
| 보조 | — | 공통표준단어 영문명 | concept 영문 풀네임 |
| 보조 | — | 형식단어여부 | suffix 정규화 사전 (Y인 단어만) |
| 제외 | 제정차수, 개정구분명/항목/사유 | 제정차수, 개정구분명/항목/사유, 금칙어 목록 | 거버넌스 메타 (검색 무관) |

산출물:

```text
data/03_semantic/term_dictionary.jsonl      # 단어 사전 (구성요소)
data/03_semantic/term_definitions.jsonl     # 용어 정의 (필드 후보)
data/03_semantic/category_taxonomy.json     # 16개 카테고리 + 도메인 정규화 표
data/03_semantic/suffix_words.json          # 형식단어여부=Y 단어 사전 (명/코드/일자/수 등)
```

### term_dictionary.jsonl 권장 스키마

```json
{
  "word_id": "word:RAFOS",
  "name_ko": "1회섭취참고량",
  "abbr_en": "RAFOS",
  "name_en": "Reference Amount For One Serving",
  "description": "만 3세 이상 소비계층이 통상적으로 소비하는 식품별 1회 섭취량…",
  "domain_class": "산업고용",
  "is_format_word": false,
  "aliases": []
}
```

### term_definitions.jsonl 권장 스키마

```json
{
  "term_id": "term:RAFOS_NM",
  "name_ko": "1회섭취참고량명",
  "abbr_en": "RAFOS_NM",
  "description": "만 3세 이상 소비계층이 통상적으로 소비하는 식품별 1회 섭취량…의 이름",
  "domain": "명V100",
  "field_type": "char",
  "field_format": "100자리 이내 문자",
  "display_format": null,
  "allowed_values": [],
  "code_link": null,
  "owner_agency": null,
  "aliases": ["1회섭취참고량이름", "1회섭취참고량명칭"],
  "constituent_words": ["word:RAFOS", "word:NM"]
}
```

`constituent_words`는 영문약어를 underscore로 분리해 단어 사전과 조인하여 채운다 (예: `RAFOS_NM` → `[RAFOS, NM]`). 단어 사전에 없는 토큰은 비워둔다 — 무리한 추정은 하지 않는다.

### category_taxonomy.json 권장 스키마

`category.md` 16개 + 표준 도메인 분류명을 dot path로 정규화한다.

```json
{
  "ui_categories": ["공공행정", "과학기술", "교육", "교통물류", "국토관리", "농축수산", "문화관광", "법률", "보건의료", "사회복지", "산업고용", "식품건강", "재난안전", "재정금융", "통일외교안보", "환경기상"],
  "ui_to_domain": {
    "공공행정": "public_admin",
    "과학기술": "science_tech",
    "산업고용": "industry",
    "환경기상": "environment_weather"
  },
  "term_domain_to_id": {
    "산업고용": "industry",
    "식품건강": "food_health"
  }
}
```

서비스 카탈로그의 카테고리, 표준용어의 `공통표준도메인명`, 표준단어의 `공통표준도메인분류명`을 동일한 `domain_id`로 수렴시킨다.

## 기술 선택 원칙

초기 MVP에서는 다음을 선택한다.

| 영역 | 선택 | 이유 |
| --- | --- | --- |
| Source of truth | JSONL | 이미 파이프라인 산출물이 JSONL이며 재생성이 쉽다. |
| 표준 용어/단어 | 행안부 공통표준 CSV 우선 | 부처 간 표기 차이 통합의 정답 후보를 외부에서 확보. 정규식보다 표준이 우선. |
| Semantic 생성 | 규칙 기반 + 표준 사전 lookup | 데이터가 작고 LLM 비용 단계가 아니다. 매칭은 표준 사전의 영문약어/이음동의어가 1차 정답. |
| 벡터 DB | ChromaDB 유지 | 이미 `stage5_index/main.py`가 있고 로컬 검증이 빠르다. |
| 임베딩 | 기존 `paraphrase-multilingual-MiniLM-L12-v2` 유지 | 품질 최고 모델은 아니지만 설치와 재현성이 좋다. |
| 키워드 검색 | 정규식 토큰화 우선, 이후 BM25 | `kiwipiepy`/BM25는 필드와 키워드가 확보된 뒤 붙인다. |
| 청킹 | 구조 기반, splitter 최소화 | 데이터가 짧고 명시적 필드가 중요하므로 무조건 분할하지 않는다. |
| Graph | JSONL 관계 후보만 생성 | Neo4j/NetworkX는 관계 품질이 보일 때 추가한다. |

초기 MVP에서는 다음을 선택하지 않는다.

| 보류 항목 | 보류 이유 | 도입 조건 |
| --- | --- | --- |
| Qdrant + bge-m3 hybrid | 운영 목표로는 적합하지만 현재 데이터 품질 검증보다 앞서 있다. | parent/child 청크와 semantic tag가 안정되고 ChromaDB 한계가 확인된 뒤 |
| Neo4j | 관계 데이터가 아직 비어 있고 운영 query 요구가 없다. | service/concept/field 관계가 수천 건 이상 쌓인 뒤 |
| LLM tagging | 정답셋이 없어 품질 판정이 어렵다. | 규칙 기반 결과와 사람이 검수한 샘플셋이 생긴 뒤 |
| LangChain TextSplitter | 현재 청크가 짧고 필드 중심 구조화가 더 중요하다. | 긴 API schema 또는 문서 본문이 실제로 검색 품질을 떨어뜨릴 때 |
| endpoint/keywords 독립 청크 | 지금은 chunk_type 증가보다 검증 루프가 우선이다. | endpoint path 질의와 alias 질의가 실패 사례로 누적될 때 |

## MVP 산출물 목표

### 1. Catalog 품질 리포트

먼저 입력 데이터가 어떤 상태인지 숫자로 고정한다.

출력:

```text
data/99_reports/catalog/catalog_quality_report.json
data/99_reports/catalog/field_extraction_quality.json
```

필수 지표:

```json
{
  "services_total": 91,
  "documents_total": 91,
  "endpoints_total": 4,
  "fields_total": 0,
  "openapi_without_endpoint": 87,
  "endpoint_without_fields": 4,
  "semantic_files_empty": true
}
```

### 2. fields.jsonl 추출 보강

`field_mappings.jsonl`보다 `fields.jsonl`을 먼저 채운다.

우선순위:

1. `openapi_new` Swagger request parameter
2. `openapi_new` response schema
3. `openapi_old`의 API 상세/입출력 항목
4. `openapi_link`는 링크 안내형이면 tool/spec 대상에서 제외 또는 `deprecated_like=true` 표시

필드 레코드에는 최소한 다음 키를 유지한다.

```json
{
  "field_id": "field:endpoint:...:bizrno",
  "service_id": "openapi:15000000",
  "endpoint_id": "endpoint:...",
  "field_name": "bizrno",
  "field_role": "request",
  "field_type": "string",
  "required": false,
  "description": "사업자등록번호",
  "source_path": "data/01_raw/..."
}
```

### 3. 규칙 기반 semantic 최소 구현

처음부터 완전한 ontology를 만들지 않는다. 검색 품질과 부처 간 유사 의미 통합에 필요한 최소 키만 만든다. **Stage 0 표준 용어/단어 사전을 우선 매칭하고, 표준 사전에 없는 항목만 규칙으로 보완한다.**

출력:

```text
data/03_semantic/taxonomy.json          # category_taxonomy.json을 입력으로 사용
data/03_semantic/concepts.jsonl
data/03_semantic/service_tags.jsonl
data/03_semantic/aliases.jsonl
data/03_semantic/field_mappings.jsonl
```

매칭 우선순위:

1. `term_definitions.jsonl`의 영문약어 ↔ 카탈로그 `field_name` 정확 일치 (대소문자 무시, underscore 정규화)
2. `term_definitions.jsonl`의 한글 정규명/이음동의어 ↔ 필드 description 부분 일치
3. `term_dictionary.jsonl` 단어 사전을 통한 분해 매칭 (예: `BIZRNO_DTL` → `BIZRNO` + `DTL`)
4. 위 3단계가 모두 실패한 경우에만 규칙 기반 후보 생성 (`review_status="pending"`)

초기 concept 범위 — 표준 사전 도메인을 먼저 사용하고 부족한 영역만 임시 concept를 추가한다.

| 범위 | 표준 사전 도메인 / 카테고리 | 보완 예시 |
| --- | --- | --- |
| 산업/고용 | `산업고용` 도메인 + 단어 | 에너지, 발전, 연료, 창업, 채용 |
| 교통 | `교통물류` 도메인 + 단어 | 버스, 노선, 정류소, 위치 |
| 문화/관광 | `문화관광` 도메인 + 단어 | 여행지, 문화시설, 식당, 쇼핑 |
| 행정 식별자 | `공공행정` 도메인 + `사업자등록번호`, `법인등록번호` 등 표준용어 | 비표준 alias만 규칙으로 보강 |

`review_status`를 필수로 둔다.

```json
{
  "service_id": "openapi:15000957",
  "domain_ids": ["industry"],
  "concept_ids": ["term:FUEL_IMPORT_QTY"],
  "evidence": ["name", "keywords", "category", "term_dictionary"],
  "confidence": 0.85,
  "review_status": "rule_accepted"
}
```

확신이 낮은 것은 버리지 말고 `pending`으로 둔다. 표준 사전 매칭이 성공한 경우 권장 등급 메타(타입/포맷/허용값/코드/소관기관)도 함께 적재한다.

```json
{
  "field_id": "field:endpoint:openapi:15000123:request:bizrno",
  "field_name": "bizrno",
  "concept_id": "term:BIZRNO",
  "term_canonical_ko": "사업자등록번호",
  "aliases": ["사업자등록번호", "사업자번호", "bizrno", "b_no"],
  "field_type": "char",
  "field_format": "10자리 숫자",
  "display_format": "###-##-#####",
  "allowed_values": [],
  "code_link": null,
  "owner_agency": "국세청",
  "match_source": "term_definitions.abbr_en",
  "confidence": 0.95,
  "review_status": "rule_accepted"
}
```

`match_source`는 `term_definitions.abbr_en`, `term_definitions.alias`, `term_dictionary.compose`, `rule_only` 중 하나로 둔다 — 후속 검수와 confidence 튜닝의 기준이 된다.

### 4. Serving v2 청크 생성

`03_remain.md`의 parent/child 구조는 유지하되 MVP chunk_type을 줄인다.

초기 chunk_type:

```text
overview     indexable=false
summary      indexable=true
api_schema   indexable=true, fields 또는 endpoints가 있을 때만 생성
```

후속 chunk_type:

```text
target
benefit
endpoint
keywords
```

이유:

- 현재 서비스 설명과 문서 본문은 이미 있으므로 `summary`는 바로 만들 수 있다.
- 필드가 확보되면 `api_schema`는 부처 간 유사 필드 통합 검증의 핵심 청크가 된다.
- `target`/`benefit`은 현재 데이터에서 안정적으로 분리할 구조화 필드가 부족하므로, 먼저 summary 안에 포함한다.

권장 schema:

```json
{
  "chunk_id": "chunk:openapi:15000957:summary:0",
  "parent_chunk_id": "chunk:openapi:15000957:overview:0",
  "service_id": "openapi:15000957",
  "document_id": "doc:openapi:15000957:overview",
  "chunk_type": "summary",
  "indexable": true,
  "text": "검색 인덱싱용 텍스트",
  "display_text": "사용자 표시용 요약",
  "search_keywords": ["연료", "도입실적", "LNG"],
  "domain_ids": ["industry.energy"],
  "concept_ids": ["energy.fuel_import"],
  "agency_ids": ["B552520"],
  "endpoint_ids": [],
  "field_ids": [],
  "source_path": "data/02_catalog/documents.jsonl"
}
```

ChromaDB 적재는 `indexable != false`인 청크만 대상으로 바꾼다. 기존 데이터와의 호환을 위해 `indexable`이 없는 청크는 true로 간주할 수 있다.

### 5. 검색 검증 루프

초기 검증은 새 DB를 붙이는 것이 아니라 같은 입력에 대해 결과가 좋아지는지 확인한다.

필수 테스트 질의:

```text
연료 도입 실적
연료 소비량
버스 정류소 위치
문화시설 식당 정보
여행경보 목록
사업자등록번호
법인등록번호
endpoint path
응답 필드
```

검증 방식:

1. `retrieval_chunks.jsonl`을 생성한다.
2. ChromaDB에 `indexable=true` 청크만 적재한다.
3. 질의별 top-5 결과를 JSON 리포트로 저장한다.
4. 같은 `service_id`가 중복으로 나오면 최고 점수 청크만 남긴다.
5. parent overview를 병합하여 사용자 표시 결과를 만든다.

출력:

```text
data/99_reports/rag/retrieval_eval_report.json
```

## 구현 순서

### Phase 0. 현재 상태 고정

목표:

- 현재 데이터 수량과 결손을 리포트로 저장한다.
- 이후 변경이 개선인지 회귀인지 판단할 기준을 만든다.

완료 기준:

- `catalog_quality_report.json` 생성
- `fields_total=0`, `semantic_tags_total=0`, `chunks_total=91` 같은 현재 결손이 명확히 기록됨

### Phase 1. 필드 추출 보강 + 표준 용어 사전 적재

목표:

- `fields.jsonl`을 비어 있지 않게 만든다.
- endpoint 4건에 대해 request/response field가 가능한 만큼 추출된다.
- Stage 0 표준 용어/단어 CSV를 권장 등급까지 JSONL로 적재한다.

완료 기준:

- `data/02_catalog/fields.jsonl` 1건 이상
- `field_extraction_quality.json`에 endpoint별 field 수 기록
- `term_dictionary.jsonl`, `term_definitions.jsonl`, `category_taxonomy.json`, `suffix_words.json` 생성
- 표준 사전 적재 시 권장 등급(저장 형식/표현 형식/허용값/행정표준코드명/소관기관명) 컬럼이 누락 없이 매핑됨

### Phase 2. 규칙 기반 semantic 생성

목표:

- 서비스와 필드에 최소 concept/domain tag를 부여한다.
- 부처별 표현 차이를 alias 후보로 모은다.
- **표준 용어 사전을 1차 정답으로 두고 규칙은 보완에 한정한다.**

완료 기준:

- `service_tags.jsonl`이 비어 있지 않음
- `concepts.jsonl`이 비어 있지 않음
- `field_mappings.jsonl`은 필드가 있는 경우에만 생성
- 모든 semantic record에 `confidence`, `review_status`, `evidence`, `match_source` 포함
- field_mappings 중 표준 사전과 매칭된 레코드는 `field_type`, `field_format`, `allowed_values`, `code_link`, `owner_agency` 권장 필드를 채움
- `domain_ids`는 `category_taxonomy.json`의 정규화 ID(예: `industry`, `food_health`)만 허용

### Phase 3. Serving v2 생성

목표:

- overview 단일 청크에서 parent/child 구조로 이동한다.
- 검색용 `text`와 표시용 `display_text`를 분리한다.

완료 기준:

- 서비스당 `overview` 1개
- 서비스당 `summary` 1개
- field 또는 endpoint가 있는 서비스에 `api_schema` 생성
- `indexable=false` overview는 ChromaDB 적재에서 제외 가능
- `domain_ids`, `concept_ids`, `search_keywords`가 semantic 파일이 있을 때 채워짐

### Phase 4. ChromaDB 기반 빠른 검증

목표:

- 새 청크 구조가 현재 검색보다 나은지 확인한다.

완료 기준:

- ChromaDB 재적재 성공
- 샘플 질의 top-5 리포트 생성
- 최소 5개 질의에서 기대 service가 top-5에 포함되는지 수동 확인 가능

### Phase 5. BM25 또는 Qdrant 도입 판단

BM25 도입 조건:

- `사업자등록번호`, `bizrno`, endpoint path처럼 정확 키워드 질의가 벡터 검색에서 약할 때
- `fields.jsonl`과 `field_mappings.jsonl`이 충분히 채워졌을 때

Qdrant + bge-m3 도입 조건:

- ChromaDB + 간단 lexical 보강으로 부족한 실패 사례가 확인될 때
- dense/sparse hybrid가 필요한 질의 유형이 리포트로 축적될 때
- payload schema가 안정되어 인덱스 재생성 비용이 낮을 때

Graph 도입 조건:

- `Service-Agency-Concept-Field` 관계가 충분히 쌓이고 관계 설명이 실제 UI/API 요구사항이 될 때

## 모듈 위치 결정

현재 코드에는 `stage4_output/main.py`가 serving 생성을 담당하고, 문서 일부에는 `stage3_serving` 또는 `stage4_serving`이 언급된다.

MVP에서는 불필요한 rename을 하지 않는다.

```text
현재 구현 유지:
  stage4_output/main.py

추후 정리 후보:
  stage4_serving/main.py
```

단, 문서와 CLI 메시지에는 실제 위치인 `stage4_output/main.py`를 기준으로 기록한다.

## 데이터 동일성 식별 규칙

부처 간 유사의미 통합을 위해 초기부터 아래 ID를 안정적으로 유지한다.

| 대상 | ID 규칙 | 목적 |
| --- | --- | --- |
| Service | 기존 `service_id` 유지 | 검색 결과 dedup과 parent merge |
| Agency | 기존 `provider_agency_id` 유지 | 기관별 alias/용어 분석 |
| Endpoint | 기존 `endpoint_id` 유지 | API 도구화와 endpoint 검색 |
| Field | `field:{endpoint_id}:{field_role}:{field_name}` | 필드 단위 유사의미 매핑 |
| Concept | 사람이 읽을 수 있는 dot path | 부처 간 의미 통합 기준 |
| Alias | 원문 표현 + concept_id | 질의 확장과 표준화 |

초기에는 완전 자동 통합을 하지 않는다. 같은 의미로 보이는 필드는 `field_mappings.jsonl`에 후보로 남기고 `review_status`로 상태를 관리한다.

## 최종 완료 기준

MVP 완료는 다음 상태를 의미한다.

```text
data/02_catalog/fields.jsonl                    비어 있지 않음
data/03_semantic/term_dictionary.jsonl          표준단어 CSV 적재 (필수+보조 컬럼)
data/03_semantic/term_definitions.jsonl         표준용어 CSV 적재 (필수+권장 컬럼)
data/03_semantic/category_taxonomy.json         16개 카테고리 + 도메인 정규화 표
data/03_semantic/suffix_words.json              형식단어여부=Y 단어 사전
data/03_semantic/concepts.jsonl                 비어 있지 않음 (term 기반 + 규칙 보완)
data/03_semantic/service_tags.jsonl             비어 있지 않음, domain_ids는 정규화 ID만 사용
data/03_semantic/aliases.jsonl                  표준 이음동의어 + 부처별 변형 수집
data/03_semantic/field_mappings.jsonl           표준 사전 매칭 레코드는 권장 필드(타입/포맷/허용값/코드/소관기관) 포함
data/04_serving/retrieval_chunks.jsonl          overview + summary + 조건부 api_schema
data/04_serving/recommender_catalog.jsonl       semantic tag 반영
data/04_serving/api_tool_specs.jsonl            endpoint/field 기반 생성
data/04_serving/quality_report.json             chunk/semantic 결손 기록
data/05_indexes/chroma/                         indexable chunk 적재
data/99_reports/rag/retrieval_eval_report.json  샘플 질의 결과 기록
```

## 한 줄 결론

현재 단계에서는 Qdrant, Neo4j, LLM보다 **표준 용어 사전 적재**, `fields.jsonl` 복구, **표준 사전 우선 매칭**, parent/child serving v2, ChromaDB 재검증이 먼저다. 이 순서가 부처 간 유사의미 통합으로 확장될 수 있으면서도 가장 빠르게 검증 가능한 경로다.
