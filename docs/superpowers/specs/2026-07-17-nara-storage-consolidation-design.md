# nara_storage 중앙 데이터 저장소 설계

- 작성일: 2026-07-17
- 상태: 사용자 승인됨 (대화 중 설계 승인 완료)
- 선행 스펙: docs/superpowers/specs/2026-07-16-subproject-consolidation-design.md (통합 제품 설계 — 본 스펙은 그 위에 데이터 경로 규칙만 통일한다)

## 1. 배경과 목표

crawler·search·combiner가 API 문서 데이터를 각자 폴더(`{앱}/apidata`)에 개별 관리하고
경로 규칙도 조금씩 다르다(타임스탬프 run 폴더 vs 평면, `{api_id}_{수정일}.json` vs 무규칙).
이를 저장소 루트의 단일 디렉터리 `D:\project\nara_storage`로 모으고, 모든 앱이 같은
규칙으로 저장·조회하게 한다.

별도 규칙 문서는 만들지 않는다 — 규칙은 각 앱 config의 기본값으로만 표현한다.

현재 모든 `apidata/` 폴더가 비어 있으므로 데이터 마이그레이션은 없다.

## 2. 저장 규칙 (전 앱 공통)

```
D:\project\nara_storage\
  openapi_new\{api_id}.json     ┐
  openapi_link\{api_id}.json    │ 전 타입 공통: 재크롤링 시 {api_id}.json 덮어쓰기
  fileData\{api_id}.json        │ (최신 1파일만 유지, 수정일은 파일 내용 info.수정일에 있음)
  standard\{api_id}.json        ┘
  manifests\{run_id}.json       ← 크롤 실행 기록 (run_id = %Y-%m-%dT%H-%M-%S, KST)
```

- **타임스탬프 run 폴더 제거**: 데이터 경로에 크롤링 요청 시각 계층을 두지 않는다.
- **덮어쓰기**: 같은 api_id를 다시 크롤링하면 해당 타입 폴더의 `{api_id}.json`을 덮어쓴다.
  이 규칙은 openapi_new만이 아니라 **모든 데이터 타입에 동일하게** 적용된다
  (파일명은 공용 `file_storage.py` 한 곳에서 결정되므로 자동으로 전 타입 공통).
- **manifests**: run별 수집 파일 목록·체크섬 기록은 `manifests/{run_id}.json`으로 보존한다.
- **경로 계산**: 각 앱은 자기 위치 기준 `BASE_DIR.parent / "nara_storage"`를 기본값으로
  계산한다 (모든 앱이 D:\project 바로 아래 있으므로 동일 지점을 가리킴; 절대경로 하드코딩 금지).
- **env 오버라이드 유지**: 기존 `NARA_SEARCH_APIDATA_DIR`, `NARA_DATA_DIR`는 그대로
  동작한다 (테스트가 fixture 경로 주입에 사용 중). 새 env 변수는 추가하지 않는다.

## 3. 앱별 변경

### nara_crawler (저장 측)

- `managers/crawl_run_manager.py`
  - 저장 루트: `{crawler BASE_DIR}/apidata` → `{BASE_DIR.parent}/nara_storage`
  - 데이터 경로에서 `{run_id}` 계층 제거: `get_raw_output_dir(run_id, data_type)` →
    `nara_storage/{data_type}` (run_id는 경로에 쓰지 않음)
  - manifest 저장: `{run_dir}/manifest.json` → `nara_storage/manifests/{run_id}.json`
  - run_id 생성 방식(%Y-%m-%dT%H-%M-%S)은 manifest 파일명·기록용으로 유지
- `managers/file_storage.py`
  - 파일명 `{api_id}_{수정일}.json` → `{api_id}.json` (전 타입 공통, 덮어쓰기)
  - openapi 타입의 api_type 하위 폴더 분기(openapi_new/openapi_link)는 유지
- `main.py`의 `get_default_output_dir`: 변경된 CrawlRunManager 경로를 그대로 사용

### nara_search (조회 측)

- `backend/core/config.py`: `APIDATA_DIR` 기본값 `BASE_DIR / "apidata"` →
  `BASE_DIR.parent / "nara_storage" / "openapi_new"`
- search는 **openapi_new 폴더만** 소비한다 (canonical prefix `openapi_new:`와 일치;
  fileData·standard는 search 파서 대상이 아님)
- 기존 소비 코드는 수정 불필요 확인만 한다: `latest_apidata_files()`의
  `stem.split("_")[0]`와 `detail_service._find_flat_file`의 `{api_id}.json` 패턴은
  새 파일명을 이미 처리한다

### nara_combiner (조회 측)

- `app/config.py`: `NARA_DATA_DIR` 기본값 `BASE_DIR / "apidata"` →
  `BASE_DIR.parent / "nara_storage" / "openapi_new"`
- loader의 `*.json` 평면 glob은 새 구조와 그대로 호환

### nara_dashboard

- 변경 없음 (search `/catalog` API 경유로 이미 파일 직접 접근이 없음)

### 루트

- `start-all.ps1`: `-ApidataDir` 기본값 → `$PSScriptRoot\nara_storage\openapi_new`
- `.gitignore`: `nara_storage/` 추가
- 각 앱의 빈 `apidata/` 폴더 제거 (tests/fixtures/apidata는 유지 — git 추적 중인 fixture)

## 4. 오류 처리

- `nara_storage`(또는 `openapi_new` 하위)가 없을 때의 동작은 현행 유지:
  search는 빈 카탈로그 + 진단 메시지, combiner는 경고 로그 + 빈 캐시,
  crawler는 저장 시 디렉터리를 자동 생성(`os.makedirs(exist_ok=True)`)
- 경로 계산에 절대경로·로컬 사용자 경로를 하드코딩하지 않는다

## 5. 테스트·완성 기준

- crawler: 경로 계산 단위 테스트 추가 — run 폴더 없이 `nara_storage/{타입}/{api_id}.json`,
  manifest가 `manifests/{run_id}.json`에 저장되는지
- search: config 기본값 검증 + 기존 62개 테스트 통과 (fixture env 주입이라 영향 없음)
- combiner: config 기본값 검증 + 기존 22개 테스트 통과
- dashboard: 기존 47개 테스트 통과 (변경 없음 확인)
- README 경로 서술 현행화: crawler·search·combiner README와 dashboard README의
  start-all 안내 (신규 문서는 만들지 않음)

## 6. 범위 밖

- 데이터 마이그레이션 (현재 데이터 없음)
- 새 env 변수·공유 파이썬 패키지 도입
- crawler scanner의 metadata CSV(`metadata_results`) 위치 변경 — API 문서 데이터가 아님
- search의 fileData·standard 소비 (파서·ID 체계 확장은 별도 과제)
- relations.jsonl·faiss index 등 search 산출물 위치 변경 (`{search}/storage` 유지)
