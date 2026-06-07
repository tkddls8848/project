# Gov24 Link Resolver 구현 계획서

작성일: 2026-05-24
위치: `D:\project\nara_gov24_link_resolver`
참조: `D:\project\nara_gov24_link_resolver_crawler\docs\08. io.md`

## 1. 목적

Gov24 Link Resolver는 정부24 또는 기관 페이지의 서비스 링크와 메타데이터를 공통 ID 체계로 정리해, 이후 Civic Scenario Catalog(P1), GovAPI Tool/MCP(P2), Gov Service Graph(P3), Integration Layer(P5)가 재사용할 수 있는 독립 산출물을 만드는 소형 프로젝트다.

MVP 목표는 자동 신청이나 본인인증 연동이 아니다. 사용자가 어떤 생활 사건을 수행할 때 이동해야 할 정부24/기관 안내 링크를 안정적으로 찾아 제공할 수 있는 링크 후보 데이터셋을 만드는 것이다.

## 2. 08. io.md 기준 역할

`08. io.md`의 의존 방향은 다음과 같다.

```text
P4 Gov24 Link Resolver
  -> P1 Civic Scenario Catalog
  -> P2 GovAPI MCP Server
  -> P3 Gov Service Graph
  -> P5 Integration Layer
```

따라서 P4는 독립 프로젝트다.

- P4는 P1/P2/P3/P5 산출물을 참조하지 않는다.
- P4는 정부24 링크, CappBizCD, 기관 링크, 서비스 메타데이터만 다룬다.
- P1은 P4 산출물인 `gov24_service_metadata.jsonl`을 소비할 수 있다.
- P4가 P1 시나리오를 기준으로 링크를 큐레이션하면 안 된다.

## 3. MVP 범위

### In Scope

- 정부24 서비스 링크 후보 수집
- 기관 안내 페이지 링크 후보 수집
- CappBizCD 또는 대체 식별자 기반 매핑
- 공공데이터 서비스 ID와 링크 후보 간 느슨한 연결
- 링크 신뢰도, 출처, 검수 상태 기록
- startup_cafe 검증에 필요한 링크 후보 우선 정리

### Out of Scope

- 정부24 로그인 또는 본인인증 자동화
- 신청서 자동 제출
- 사용자 개인정보 저장
- P1 시나리오 생성
- P2 API 도구 생성
- P3 그래프 생성
- P5 통합 API 구현

## 4. 권장 디렉터리 구조

```text
D:\project\nara_gov24_link_resolver\
  gov24_link_resolver\
    README.md
    data\
      raw\
        gov24_pages.jsonl
        agency_pages.jsonl
      working\
        link_candidates.jsonl
        service_name_matches.jsonl
      output\
        gov24_service_metadata.jsonl
        gov24_link_candidates.jsonl
        link_resolution_report.json
    schemas\
      gov24_service_metadata.schema.json
      gov24_link_candidate.schema.json
    scripts\
      collect_manual_seed.py
      normalize_links.py
      match_services.py
      validate_outputs.py
    tests\
      test_schema.py
      test_link_format.py
```

## 5. 산출물 정의

### 5.1 gov24_service_metadata.jsonl

P1/P2/P5가 소비할 최종 메타데이터 파일이다.

```json
{
  "link_id": "gov24:service:biz_registration",
  "source": "gov24",
  "external_id": "CAPP_BIZ_CD_OR_SERVICE_ID",
  "title": "사업자등록 신청",
  "url": "https://www.gov.kr/...",
  "link_type": "application|guide|info|agency",
  "domain_ids": ["business"],
  "related_service_ids": ["service:data.go.kr:..."],
  "related_agency_ids": ["agency:nts"],
  "keywords": ["사업자등록", "창업", "세무서"],
  "confidence": 0.85,
  "review_status": "pending|reviewed|rejected",
  "collected_at": "2026-05-24T15:00:00+09:00",
  "source_url": "https://www.gov.kr/...",
  "notes": "수동 확인 필요"
}
```

### 5.2 gov24_link_candidates.jsonl

검수 전 후보 파일이다. 자동/수동 수집 결과를 모두 보존한다.

```json
{
  "candidate_id": "candidate:gov24:001",
  "title": "사업자등록 신청",
  "url": "https://www.gov.kr/...",
  "source": "manual|search|crawler|api",
  "matched_query": "사업자등록",
  "matched_service_name": "국세청 사업자등록 상태조회",
  "match_reason": "title_keyword_overlap",
  "confidence": 0.72,
  "review_status": "pending"
}
```

### 5.3 link_resolution_report.json

품질 리포트다.

```json
{
  "generated_at": "2026-05-24T15:00:00+09:00",
  "total_candidates": 120,
  "reviewed": 35,
  "accepted": 28,
  "rejected": 7,
  "broken_links": 3,
  "missing_external_id": 42,
  "top_domains": ["business", "food_service"]
}
```

## 6. 구현 단계

### Phase 0. 사전 확인

목표:

- 정부24 링크 사용 가능 범위 확인
- 스크래핑이 필요한지, 수동 링크 안내만으로 충분한지 결정
- CappBizCD 또는 대체 식별자를 실제로 확보할 수 있는지 확인

작업:

- 정부24 이용약관 확인
- 링크 제공 방식 정리
- 자동 수집 가능 범위와 금지 범위 구분
- `docs/licensing_review.md` 초안 작성

완료 기준:

- 링크를 저장해도 되는 범위가 문서화되어 있다.
- 신청 자동화는 범위 밖으로 명시되어 있다.

### Phase 1. 수동 seed 데이터셋

목표:

- 자동화 전에 startup_cafe에 필요한 링크 후보를 수동으로 20~30개 정리한다.

작업:

- 사업자등록
- 통신판매업 신고
- 식품영업 신고
- 위생교육
- 4대보험 사업장 가입
- 지방세/국세 안내
- 관할 기관 안내 페이지

완료 기준:

- `data/working/link_candidates.jsonl` 생성
- 각 후보에 `title`, `url`, `source`, `review_status`가 있다.
- 깨진 URL이 없다.

### Phase 2. 정규화와 스키마 검증

목표:

- 링크 후보를 공통 스키마로 정규화한다.

작업:

- URL canonicalization
- 중복 링크 제거
- `link_type` 분류
- 키워드 추출
- JSON Schema 검증

완료 기준:

- `gov24_link_candidate.schema.json` 작성
- `validate_outputs.py` 통과
- 중복 URL 리포트 생성

### Phase 3. 서비스 메타데이터 연결

목표:

- 링크 후보를 공공서비스/기관/도메인과 느슨하게 연결한다.

입력 후보:

- `D:\project\nara_gov24_link_resolver_crawler\data\02_catalog\services.jsonl`
- `D:\project\nara_gov24_link_resolver_crawler\data\02_catalog\agencies.jsonl`
- `D:\project\nara_gov24_link_resolver_crawler\data\03_semantic\aliases.jsonl`

작업:

- 서비스명 키워드 매칭
- 기관명 매칭
- 도메인 키워드 매칭
- confidence 산정
- 수동 검수 상태 부여

완료 기준:

- `data/output/gov24_service_metadata.jsonl` 생성
- 각 레코드에 `confidence`, `review_status`, `source_url` 포함
- 자동 매칭 결과는 기본 `pending`으로 둔다.

### Phase 4. 품질 리포트

목표:

- P1/P5가 사용할 수 있는 품질 기준을 제공한다.

작업:

- URL 유효성 검사
- 중복 검사
- 필수 필드 누락 검사
- 신뢰도 분포 계산
- 검수 상태 통계 생성

완료 기준:

- `data/output/link_resolution_report.json` 생성
- accepted/pending/rejected 개수 확인 가능

## 7. 최소 구현 우선순위

1. `gov24_link_resolver/README.md`
2. `schemas/gov24_link_candidate.schema.json`
3. `data/working/link_candidates.jsonl` 수동 seed 20개
4. `scripts/validate_outputs.py`
5. `data/output/gov24_service_metadata.jsonl`
6. `data/output/link_resolution_report.json`

MVP에서는 자동 크롤러보다 수동 seed + 정규화 + 검증을 우선한다. 링크 수집 자동화는 법적 범위와 구조가 확인된 뒤 추가한다.

## 8. P1/P5 연동 계약

P1은 다음 필드만 믿고 사용할 수 있어야 한다.

```text
link_id
title
url
link_type
domain_ids
keywords
confidence
review_status
```

P1은 `review_status = reviewed`인 링크를 우선 사용한다. `pending` 링크는 후보로만 보여주고, 자동 추천의 근거로 강하게 사용하지 않는다.

P5는 `gov24_service_metadata.jsonl`을 읽어 통합 응답의 `links` 섹션에 붙인다.

```json
{
  "links": [
    {
      "title": "사업자등록 신청",
      "url": "https://www.gov.kr/...",
      "type": "application",
      "confidence": 0.85
    }
  ]
}
```

## 9. 리스크와 대응

| 리스크 | 영향 | 대응 |
| --- | --- | --- |
| 정부24 링크 구조 변경 | 링크 깨짐 | URL 검증 리포트 주기 실행 |
| CappBizCD 확보 어려움 | 식별자 매핑 약화 | URL/title/기관명 기반 fallback |
| 스크래핑 제한 | 자동 수집 불가 | 수동 seed와 공개 링크 안내 중심으로 시작 |
| 잘못된 링크 연결 | 사용자 오안내 | confidence와 review_status 필수화 |
| P1 시나리오와 결합 과다 | 순환 의존 | P4는 시나리오를 참조하지 않고 범용 링크만 만든다 |

## 10. 완료 기준

MVP 완료 기준:

- startup_cafe 관련 링크 후보 20개 이상
- 검수 완료 링크 10개 이상
- JSON Schema 검증 통과
- URL 유효성 검사 통과율 90% 이상
- `gov24_service_metadata.jsonl`을 P1이 바로 읽을 수 있음
- P4가 P1/P2/P3/P5 산출물에 의존하지 않음

## 11. 다음 작업

1. `gov24_link_resolver` 디렉터리 생성
2. README와 schema 작성
3. startup_cafe 수동 seed 링크 작성
4. 검증 스크립트 작성
5. P1에서 읽을 수 있는 output JSONL 생성

계획서 끝.
