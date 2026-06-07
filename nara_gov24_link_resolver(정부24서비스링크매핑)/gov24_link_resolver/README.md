# Gov24 Link Resolver

정부24 및 관련 기관 서비스 링크를 공통 ID 체계로 정리하는 독립 데이터 프로젝트.

## 목적

- 생활 사건(창업, 신고, 납세 등) 수행 시 이동해야 할 정부 서비스 링크를 안정적으로 제공
- P1(Civic Scenario Catalog), P2(GovAPI MCP), P5(Integration Layer)가 재사용할 수 있는 링크 데이터셋 생성

## 출력 산출물

| 파일 | 용도 |
|---|---|
| `data/output/gov24_service_metadata.jsonl` | P1/P5가 소비하는 최종 메타데이터 |
| `data/output/gov24_link_candidates.jsonl` | 검수 전 후보 전체 |
| `data/output/link_resolution_report.json` | 품질 리포트 |

## 디렉터리 구조

```
gov24_link_resolver/
  data/
    raw/          ← 크롤러/검색 원본
    working/      ← 수동 seed 및 중간 처리 결과
    output/       ← 검수 완료 산출물
  schemas/        ← JSON Schema 정의
  scripts/        ← 정규화·매칭·검증 스크립트
  tests/          ← 스키마·포맷 단위 테스트
  docs/           ← 라이선스 검토 등 문서
```

## 실행 순서

```powershell
cd gov24_link_resolver
pip install -r requirements.txt

# 1. 링크 후보 정규화
python scripts/normalize_links.py

# 2. 서비스 메타데이터 매칭
python scripts/match_services.py

# 3. 검증 및 리포트 생성
python scripts/validate_outputs.py

# 4. 단위 테스트
python -m pytest tests/ -v
```

## P1 연동 계약

P1은 `review_status = reviewed`인 링크를 우선 사용한다.
`pending` 링크는 후보로만 취급하며 자동 추천의 강한 근거로 사용하지 않는다.

필수 소비 필드: `link_id`, `title`, `url`, `link_type`, `domain_ids`, `keywords`, `confidence`, `review_status`

## 범위 외

- 정부24 로그인 / 본인인증 자동화
- 신청서 자동 제출
- P1 시나리오 생성 / P2 API 도구 생성 / P3 그래프 생성
