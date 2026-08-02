# 크롤러 심화 + LINK형 하베스팅 계획 (2026-08-01)

조정자(coordinator)가 소유하는 공유 설계 문서다. 워커는 착수 전에 이 문서를 읽고,
자기 **파일 소유 범위 밖은 절대 수정하지 않는다**. 공유 파일(`requirements.txt`,
`README.md`, `CLAUDE.md`)은 조정자만 고친다.

## 측정된 현재 상태 (추측 아님)

| 항목 | 값 | 출처 |
| --- | --- | --- |
| `nara_storage/openapi_new/` | 4,171건 | 로컬 실측 |
| `nara_storage/openapi_link/` | **7,643건** | 로컬 실측 |
| 마스터 CSV API 행 | 35,186 | `scanner/database/metadata_api.csv` |
| 마스터 CSV 파일 행 | 83,589 | `scanner/database/metadata_file.csv` |

저장된 한글은 정상이다(모지바케 아님 — `repr()`로 확인). 인코딩 이슈는 없다.

### 확인된 결함 3가지

1. **LINK형이 스텁이다.** `openapi_crawler.py:66-70`에서 `data_payload`는
   `api_type == 'openapi_new'`일 때만 채워진다. LINK형 7,643건에는
   `swagger_json`도 `endpoints`도 없다. `info` + `operation_ids`만 있다.
2. **외부 포털 URL이 캡처되지 않는다.** 저장된 LINK 레코드의 `목록 URL`은
   `https://www.data.go.kr/data/{id}/openapi.do` — 자기 자신이다. 실제 기관
   엔드포인트(예: `http://openapi.tour.go.kr/openapi/service/...`)는 상세
   페이지에 있지만 파싱되지 않는다.
3. **분류 오염.** `openapi_crawler.py:91-93` — swagger 추출 실패도 무조건
   `openapi_link`로 떨어진다. 7,643건에 진짜 LINK형과 파싱 실패분이 섞여 있다.

### 결정적 관찰 — LINK형 문서는 이미 data.go.kr에 있다

LINK형 상세 페이지(`/data/{id}/openapi.do`)를 직접 확인한 결과, **상세기능 섹션에
요청/응답 파라미터 표와 샘플 코드가 그대로 렌더링돼 있다.** openapi_new가
인라인 `swaggerJson`으로 주는 정보를, LINK형은 **HTML 표로** 준다.

따라서 LINK형 크롤링은 두 단계로 나뉘고, **1단계만으로 대부분의 가치가 나온다**:

- **Phase A (내부, 외부 요청 0회)** — data.go.kr 상세기능 표를 파싱해
  `endpoints[]`를 openapi_new와 **동일한 스키마로** 합성한다. 7,643건이
  검색 가능해진다. 외부 기관 포털을 건드리지 않으므로 부하·차단 위험이 없다.
- **Phase B (외부, 산개 포털)** — 추출한 외부 엔드포인트 호스트를 클러스터링해
  기관 포털 인벤토리를 만들고, 프로토콜 감지 기반으로 추가 수집한다.

Phase B가 사용자가 말한 "수백~수천 개 산개 포털"이다. 핵심은 **어댑터를 수백 개
쓰지 않는다**는 것이다. 호스트별로 프로토콜을 감지해 5종 어댑터로 커버한다:

| 감지 순서 | 프로브 | 어댑터 |
| --- | --- | --- |
| 1 | `/api/3/action/package_list` | CKAN |
| 2 | `/v2/api-docs`, `/swagger.json`, `/openapi.json`, `/v3/api-docs` | OpenAPI 직수집 |
| 3 | `/robots.txt` → `sitemap.xml` | 사이트맵 기반 |
| 4 | schema.org `Dataset` JSON-LD | DCAT/JSON-LD |
| 5 | 위 전부 실패 | generic(제목·표만) + `unverified` 표기 |

호스트는 롱테일이다. 상위 수십 개 호스트가 대부분의 건수를 차지하므로,
프로토콜 감지 + 상위 호스트 우선 처리로 커버리지 대부분을 확보한다.

## 스코프 조정 (조정자 판단, 명시적으로 남김)

사용자 요청은 Gimi9 수준(50+ 포털 · 실제 파일 수신 · 컬럼 스키마 · 품질 리포트 ·
지도 · 주소 품질)이다. 두 가지는 그대로 만들되 기본값을 바꾼다:

- **파일 전량 다운로드는 기본값이 아니다.** 83,589건 전량 수신은 포털 부하와
  저장 용량(수 TB 추정) 문제가 있다. 기본은 **헤더+선두 N바이트 스트리밍
  샘플링**(스키마 추론에 충분)으로 하고, 전량 수신은 `--full-download`
  명시 플래그 뒤에 둔다. 동시성 상한과 호스트별 딜레이를 강제한다.
- **"50+ 포털"은 어댑터 50개가 아니다.** 위 프로토콜 감지 레지스트리로
  구현하고, 커버된 호스트 수를 실측해 보고한다. 손으로 쓴 어댑터 수를
  성과 지표로 쓰지 않는다.

## 작업 분해와 파일 소유권

**같은 워크트리(`C:/project`)에서 병렬 작업한다. 아래 소유 파일 외 수정 금지.**

| ID | 작업 | 소유 파일 | 의존 |
| --- | --- | --- | --- |
| T1 | LINK 분류 정정 + 외부 URL 추출 + JSON-LD 전체 파싱 | `crawler/openapi_crawler.py`, `crawler/file_data_crawler.py`, `domain/schemas.py` | — |
| T2 | LINK 상세기능 표 → `endpoints[]` 합성 (Phase A) | `crawler/link_spec_builder.py`(신규), `infrastructure/nara_parser.py` | T1 |
| T3 | 파일 수신 + 컬럼 스키마 추론 | `profiling/schema_infer.py`(신규), `profiling/fetcher.py`(신규) | T1 |
| T4 | 품질 프로파일 리포트 | `profiling/quality.py`(신규) | T3 |
| T5 | 주소 품질 검사 + 지도용 좌표 산출 | `profiling/address.py`(신규), `profiling/geo.py`(신규) | T3 |
| T6 | 산개 포털 하베스터 (Phase B) | `portals/`(신규 패키지 전체) | T1 |

조정자 소유(워커 수정 금지): `requirements.txt`, `main.py`, `README.md`,
`CLAUDE.md`, 본 문서.

> `main.py`가 조정자 소유인 이유: 6개 작업이 전부 CLI 플래그를 추가하려 하므로
> 충돌 지점이다. 워커는 자기 모듈에 **함수만** 만들고, 배선은 조정자가 한다.

## 모든 워커 공통 규약

1. **`.nara-root` 규약 유지.** `find_project_root()` 복제본을 새로 만들지 말고,
   `managers/crawl_run_manager.py`의 기존 함수를 재사용한다. 새 복제본을
   만들면 CLAUDE.md에 기록된 4곳 동기화 제약이 5곳으로 늘어난다.
2. **모듈 간 import 금지 규약**은 `services/*` ↔ `apps/*` 사이에만 적용된다.
   `services/crawler` 내부 패키지끼리는 자유롭게 import한다.
3. **네트워크 호출 시 반드시**: 호스트별 동시성 상한, 요청 간 딜레이,
   `robots.txt` 존중, 타임아웃. 정부·기관 사이트를 두드리는 코드다.
4. **테스트는 fixture 기반.** `tests/`에 실제 네트워크 없이 도는 테스트를 남긴다.
   기존 `tests/conftest.py` 패턴을 따른다.
5. **검증 못 한 것은 `unverified`로 표기한다.** 추정값을 사실처럼 쓰지 않는다.
6. 새 런타임 의존성이 필요하면 **직접 `requirements.txt`를 고치지 말고**
   `worker_done` 본문에 "필요 패키지: X>=Y" 로 보고한다. 조정자가 반영한다.
