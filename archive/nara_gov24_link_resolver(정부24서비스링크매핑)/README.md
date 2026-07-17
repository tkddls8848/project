# Gov24 Link Resolver

정부24 및 관련 기관 서비스 링크를 사람이 직접 큐레이션하고, 공통 ID 체계로 정리·검증하는 독립 데이터 프로젝트.

## 이 앱은 무엇인가

**"어떤 상황(생활 사건)에서 어느 정부 사이트/URL로 가야 하는지"를 사람이 직접 지정하면, 그것을 표준 링크 데이터셋으로 만들어 주는 큐레이션·검증 도구**입니다.

- 사용자는 후보 링크(제목 + URL + 매핑 근거/이동 경로 메모)를 **직접 입력**한다. (웹 UI 또는 CLI)
- 파이프라인이 각 링크를 자동 태깅한다: 상황 분류(`domain_ids`), 링크 유형(`link_type`), 관련 기관(`related_agency_ids`) — 키워드 매칭 기반.
- 검증 후 재사용 가능한 신뢰 링크 데이터셋(JSONL)과 품질 리포트를 산출한다.

즉, **"유스케이스(시나리오) 생성기"는 아니다.** 시나리오 자체를 생성하는 일(P1)은 범위 밖이고, 이 앱은 그 시나리오가 참조할 **상황↔사이트 매핑 링크**를 사람이 지정·검토하여 만든다. "어느 상황에 어느 사이트"를 직접 지정한다는 점은 맞지만, 결과물은 유스케이스가 아니라 **링크 매핑 데이터셋**이다.

## 목적

- 생활 사건(창업, 신고, 납세 등) 수행 시 이동해야 할 정부 서비스 링크를 안정적으로 제공
- P1(Civic Scenario Catalog), P2(GovAPI MCP), P5(Integration Layer)가 재사용할 수 있는 링크 데이터셋 생성

## 동작 개요

```
[사람이 지정]                [자동 처리 파이프라인]                [산출물]
후보 링크 입력  ──►  normalize(URL 정규화·중복제거)  ──►  gov24_service_metadata.jsonl
(웹 UI / CLI)        match(domain/link_type/agency 태깅)      link_resolution_report.json
                     validate(스키마·URL·중복 검증)
```

- 입력: `data/working/link_candidates.jsonl` (검수 전 후보, 사람이 관리)
- `rejected` 후보는 매칭 단계에서 제외된다.

## 실행 방법

### 웹 UI (권장)

브라우저에서 후보를 추가/검색하고, 검토 상태를 바꾸고, 파이프라인을 실행한다.

```powershell
cd "C:\project\nara_gov24_link_resolver(정부24서비스링크매핑)"
python web_app.py --port 8765
# → http://127.0.0.1:8765/
```

자세한 기능은 [`WEB_UI.md`](WEB_UI.md) 참고.

### CLI 파이프라인

```powershell
cd "C:\project\nara_gov24_link_resolver(정부24서비스링크매핑)"
pip install -r requirements.txt

# 0. (선택) 후보를 대화형으로 추가
python scripts/collect_manual_seed.py

# 1. 링크 후보 정규화 (URL 정규화·중복 제거, 후보 파일 덮어쓰기)
python scripts/normalize_links.py

# 2. 서비스 메타데이터 매칭 (domain/link_type/agency 자동 태깅)
python scripts/match_services.py

# 3. 검증 및 리포트 생성
python scripts/validate_outputs.py

# 4. 단위 테스트
python -m pytest tests/ -v
```

## 출력 산출물

| 파일 | 용도 |
|---|---|
| `data/working/link_candidates.jsonl` | 사람이 관리하는 검수 전 후보 (파이프라인 입력) |
| `data/output/gov24_service_metadata.jsonl` | P1/P5가 소비하는 최종 메타데이터 |
| `data/output/link_resolution_report.json` | 품질 리포트 (검증 결과·도메인 분포) |

현재 상태(리포트 기준): 후보 20건, `reviewed` 16 / `pending` 4 / `rejected` 0, URL 유효율 1.0.

## 디렉터리 구조

```
./
  web_app.py        ← 로컬 웹 UI 서버 (후보 추가·검토·파이프라인 실행)
  static/           ← 웹 UI 프런트엔드 (index.html, app.js, styles.css)
  scripts/          ← 정규화·매칭·검증·시드수집 스크립트
  schemas/          ← JSON Schema 정의 (candidate / metadata)
  tests/            ← 스키마·포맷 단위 테스트
  docs/             ← 라이선스 검토 등 문서
  data/
    working/        ← 후보(link_candidates.jsonl) 및 중간 처리 결과
    output/         ← 최종 메타데이터 + 검증 리포트
  WEB_UI.md         ← 웹 UI 사용 안내
  plan.md, GOV24_LINK_RESOLVER_IMPLEMENTATION_PLAN.md  ← 설계/구현 계획
```

## 스키마 / 주요 필드

- 후보(candidate): `candidate_id`, `title`, `url`, `source`(manual/search/crawler/api), `confidence`, `review_status`(pending/reviewed/rejected), + 선택 필드(`matched_query`, `matched_service_name`, `match_reason`, `notes`)
- 메타데이터(metadata): `link_id`, `source`, `external_id`, `title`, `url`, `link_type`(application/guide/info/agency), `domain_ids`, `related_agency_ids`, `keywords`, `confidence`, `review_status`, `collected_at`, `source_url`, `notes`

정의는 [`schemas/`](schemas/) 참고.

## P1 연동 계약

P1은 `review_status = reviewed`인 링크를 우선 사용한다.
`pending` 링크는 후보로만 취급하며 자동 추천의 강한 근거로 사용하지 않는다.

필수 소비 필드: `link_id`, `title`, `url`, `link_type`, `domain_ids`, `keywords`, `confidence`, `review_status`

## 범위 외

- 정부24 로그인 / 본인인증 자동화
- 신청서 자동 제출
- P1 시나리오 생성 / P2 API 도구 생성 / P3 그래프 생성

## 인코딩

모든 소스, 문서, JSON/JSONL 파일은 UTF-8로 저장한다. Windows PowerShell 5에서 한글이 깨져 보이면 파일이 깨진 것이 아니라 기본 ANSI 디코딩 문제이므로 다음처럼 확인한다.

```powershell
Get-Content -Encoding UTF8 README.md
Get-Content -Encoding UTF8 data\working\link_candidates.jsonl -TotalCount 3
```
