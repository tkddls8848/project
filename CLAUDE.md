# 프로젝트 전체 지도 (SSoT)

이 저장소는 한국 공공데이터(나라장터/data.go.kr) API 문서를 수집·검색·조합하는
파이프라인형 모듈 모음이다. 새 세션은 이 문서로 모듈 관계와 활성/폐기 상태를
파악한 뒤 각 모듈의 README를 읽는다.

## 모듈 지도

데이터 흐름 (실선 = 파일, HTTP = 런타임 호출):

디렉터리는 **생산층 `services/`** 와 **소비층 `apps/`** 로 나뉜다.
`apps/*`는 `services/*`를 HTTP로만 소비한다 (모듈 간 직접 import 금지).

```
data.go.kr ──크롤링──> services/crawler ──JSON──> nara_storage/ (레포 루트, gitignore됨)
                                                       │
                                         ┌─────────────┴─────────────┐
                                         ▼                           ▼
                             services/search (:8000)     services/combiner (:8003)
                             임베딩+FAISS 검색 백엔드      LLM 조합 제안 (Ollama)
                                         │                           │
                         ┌───── HTTP ────┼───────── HTTP ────────────┤
                         ▼               ▼                           ▼
            apps/dashboard (:5173)  apps/workbench (:8010)   apps/hermes_poc (:8020)
            React Flow 노드 에디터   통합 게이트웨이(한 화면)   MCP/에이전트 검증용 PoC
```

| 모듈 | 역할 | 비고 |
| --- | --- | --- |
| `services/crawler` (API문서크롤러) | data.go.kr 문서 크롤링 → `nara_storage/`에 JSON 저장 | 파이프라인의 시작점 |
| `services/search` (API문서검색) | SentenceTransformer(ko-sroberta) + FAISS 벡터 검색 백엔드 | 포트 8000, 데이터는 `../../nara_storage/openapi_new/` |
| `services/combiner` (API문서조합기) | API 조합 제안·행정 서비스 계획 초안 생성 | 포트 8003, 실행/승인/감사로그는 명시적 범위 밖 |
| `apps/dashboard` (API관계대시보드) | React Flow 관계 맵 프론트엔드 | 포트 5173, search/combiner에 프록시 의존 |
| `apps/workbench` (API통합워크벤치) | search+dashboard+combiner를 한 화면·한 진입점으로 통합 | 포트 8010, 기존 코드 복사 없이 HTTP 게이트웨이 방식 |
| `apps/hermes_poc` | Hermes 에이전트/MCP 연동 검증용 독립 PoC | 포트 8020, search·combiner를 HTTP 소비자로만 사용 |
| `apps/gazetta` | 관보 정적 리더 프로토타입 | 나라 파이프라인 비의존, 빌드·서버 없는 정적 HTML |
| `docs/superpowers` | 통합·리팩터링 계획/설계 문서 (의사결정 기록) | 날짜 접두 파일명 |

> 2026-07-29 이전 문서·커밋에는 `nara_search(API문서검색)`처럼 `nara_` 접두사와 한글
> 괄호가 붙은 옛 디렉터리명이 나온다. 위 표가 현재 경로다.
> 재배치 계획: `docs/superpowers/plans/2026-07-29-module-layering.md`

## 활성 / 폐기 구분

- **활성**: 위 표의 모든 모듈. 현재 무게중심은 `apps/workbench`(통합 UI)와
  `apps/hermes_poc`(에이전트 루프 확장)이다.
- **보류(archive/)**: 건드리지 말 것. 부활시키려면 사유 확인 먼저.
  - `korea100` — 대한민국 제도 187개 분석 공개 웹서비스(별개 제품, GitHub Pages 배포).
    나라 파이프라인과 무관하며 2026-07-29 보류로 전환됐다. 법령 인용 검증 원칙은
    아래 "코드만으로 알 수 없는 것들"에 남겨둔다 — 재개 시 반드시 읽을 것.
  - `nara_gov24_link_resolver(정부24서비스링크매핑)` — 정부24 링크 매핑 시도, 보류.
  - `nara_openclaw(행정서비스실행기)` — 실행기 프로젝트. combiner가 "계획 초안까지만"으로
    범위를 좁히면서 실행 기능 전체가 여기로 보류됨. 실제 행정 API 실행·자동 제출은
    전 모듈에서 의도적으로 제외된 범위다.
- `.gitignore` 머리말에 나오는 `nara_relist`, `nara_agui`는 과거 모듈명이며 현재
  저장소에 존재하지 않는다.

## 코드만으로 알 수 없는 것들

### 저장소 루트는 `.nara-root` 마커로 결정된다
- 레포 루트에 `.nara-root` 파일이 있고, 각 모듈은 `find_project_root()`로 위로 훑어
  이 마커를 찾는다. **디렉터리 깊이에 의존하지 않으므로** 모듈을 다른 계층으로 옮겨도
  `nara_storage` 해석이 유지된다. 마커를 못 찾으면 옛 규약(모듈이 루트의 직계 자식)으로
  폴백한다 — 임시 디렉터리 기준으로 도는 테스트가 이 폴백에 의존한다.
- **모듈 간 import 금지 제약 때문에 이 함수는 4곳에 복제되어 있다.** 한 곳을 고치면
  나머지도 같이 고친다: `services/search/backend/core/config.py`,
  `services/combiner/app/config.py`, `services/crawler/managers/crawl_run_manager.py`,
  `apps/hermes_poc/app/config.py`. (`apps/workbench/run.py`에도 실행기용 사본이 있다.)
- `.nara-root`를 지우면 모듈들이 자기 부모를 루트로 착각해 조용히 엉뚱한 곳을 본다.

### 데이터 루트가 레포 밖에 있다
- 모든 크롤링 산출물은 레포 루트의 `nara_storage/`에 저장되며 **gitignore 대상**이다.
  각 모듈 README의 `../../nara_storage/`는 모듈 디렉터리(2단계 깊이) 기준 상대경로다.
- 따라서 **fresh clone에는 데이터가 없다.** search/combiner를 띄우기 전에
  crawler를 먼저 실행해 `nara_storage/openapi_new/{api_id}.json`을 만들어야 한다.
  스키마: `api_id, info, endpoints, swagger_json` (같은 api_id 재크롤링 시 덮어씀).

### 개발 환경은 Windows
- 원 개발 환경은 Windows PowerShell이다 (현재 `C:\project\`, 과거 문서에는 `D:\project\`).
  README의 실행 명령이 PowerShell 기준인 이유. 리눅스 세션에서는 경로·활성화 스크립트를 치환할 것.
- 전체 기동 스크립트 `start-all.ps1`은 옛 문서에서 참조되지만 **git에도 로컬에도 없다.**
  통합 기동은 `apps/workbench/run.py`(search·combiner를 함께 띄움) 또는
  `apps/hermes_poc/run.py`를 쓴다. 둘 다 `python -m uvicorn`으로 자식을 띄운다.
- 각 모듈의 `venv/`는 옮겨도 `python -m` 경로로는 동작한다(`pyvenv.cfg`의 `home`이
  기본 파이썬을 가리키고 prefix는 exe 위치에서 파생되기 때문). 다만
  `Scripts/*.exe` 콘솔 셔뱅은 절대경로를 내장해 이동 시 깨진다 —
  `python -m pip install --force-reinstall --no-deps <pkg>`로 개별 복구한다.

### 크롤러 심화 파이프라인은 전부 옵트인이다 (2026-08-01)
- `services/crawler`에 `profiling/`(파일 수신·스키마·품질·주소/좌표)과
  `portals/`(산개 기관 포털 하베스터)가 추가됐다. **평범한 크롤에서는 하나도
  실행되지 않는다** — `--deep`(스키마·품질·주소 리포트) 또는 `--harvest`(산개
  포털 수집)로 명시적으로 켜야 한다. 파일 전량 다운로드(`--full-download`)는 그 안에서 또 한 겹 옵트인이다.
  기본은 Range 샘플링이며, 83,589건 전량 수신은 포털 부하·용량 때문에 기본값이 아니다.
- openapi 하위 타입은 `openapi_new` / `openapi_old` / `openapi_link` 셋이다.
  CSV가 LINK를 명시하면 `openapi_link`, 비-LINK 중 인라인 `swaggerJson` 파싱에
  성공하면 `openapi_new`, 나머지는 HTML 표 기반 구형 문서인 `openapi_old`다.
  특정 DOM 태그는 진단 정보일 뿐 판별자로 쓰지 않으며, 상세 근거는 각 문서의
  `api_type_evidence.reason`에 남는다.
- LINK형도 이제 `endpoints[]`를 갖는다. data.go.kr 상세 페이지의 요청/응답 표를
  openapi_new와 같은 스키마로 합성한 것이다. **기관 포털을 실제로 도는 것은
  `--harvest`(Phase B)뿐이다** — LINK 제공처 URL 조회는 data.go.kr 내부 요청이며
  아래 리뉴얼 절에 있다.
- **`external_endpoint_urls`는 신규 필드라 기존 저장분에 없다.** 재크롤링 전에는
  `--harvest`가 0호스트를 보고한다. 설계·근거는
  `docs/superpowers/plans/2026-08-01-crawler-depth-and-link-harvest.md`.

### data.go.kr이 2026-08에 리뉴얼됐다 (2026-08-05)

포털이 상세 페이지 마크업과 catalog JSON 스키마를 동시에 갈아엎었다. 크롤러·스캐너가
여기 맞춰 고쳐졌고, **리뉴얼 전 저장분과 캡처도 계속 파싱되도록 옛 경로를 폴백으로
남겼다.** 회귀 검증은 실제 캡처 fixture(`services/crawler/tests/fixtures/renewed/*.html`
5종, 네트워크 불필요)와 `tests/test_*_renewed.py`·`test_link_url_resolution.py`가 맡는다.
마크업이 또 바뀌면 fixture를 새로 뜬다.

- **상세 페이지 메타데이터가 표에서 키/값 블록으로 바뀌었다**: `<table><th>/<td>` →
  `<li><strong class="key">/<div class="value">`. 세 크롤러가 각자 갖고 있던 표
  스캐너는 `infrastructure/detail_page_parser.py`의 `extract_detail_info()` 하나로
  합쳤다(키 블록이 없으면 옛 표 스캔으로 폴백).
- **SoupStrainer로 태그를 좁히면 조용히 깨진다.** `make_soup(html, ['table','input'])`은
  리뉴얼된 `<li>` 키 블록을 통째로 버린다 — 실제로 이렇게 한 번 깨졌다. openapi는
  `DETAIL_TAGS=['table','input','li']`, fileData/standard는 전체 파싱을 쓴다.
  **`utils/metadata_updater.py:201`은 아직 `['table','input']`을 넘기는 미수정 호출부다.**
- **전화번호는 DOM에 없다.** 인라인 스크립트의 `apiTelNo`/`telNo` 변수에서만 읽히므로
  파서에 원본 HTML을 함께 넘겨야 한다.
- **catalog JSON이 schema.org Dataset으로 바뀌었다**: `/catalog/{num}/{type}.json`은
  여전히 200이지만 `title`→`name`, `organization`→`creator.name`,
  `updateDate`→`dateModified`다. Content-Type은 `text/html`인데 본문은 JSON이다.
- **리뉴얼 응답으로는 알 수 없는 값은 추정하지 않는다.** openapi의 REST/LINK 구분
  (`apiType`)과 standard의 `standardType`이 사라졌다. 공란 + `*_type_source='unverified'`로
  남긴다. 실제 REST/LINK 구분은 `scanner/database/metadata_api.csv`의 "API 유형"
  컬럼(main.py 경로)이나 상세 HTML에서 얻는다. `encodingFormat`은 데이터 포맷(XML/JSON)이지
  REST/LINK 구분이 아니다.
- **standard 그리드 표는 리뉴얼 페이지에 아예 없다.** 서버가 주는 HTML에 `<table>`이
  하나도 없다(15072622·15012892 실측). 메타데이터만으로 문서는 성공 처리하되 렌더된 섹션
  목록과 함께 `errors`에 남기고 실행 끝에 건수를 출력한다 — 안 그러면 빈 크롤이 정상
  성공처럼 보인다.
- **LINK 제공처 URL은 페이지에 더 이상 렌더되지 않는다.** 바로가기 버튼이 쓰는
  `/tcs/dss/selectApiLinkUrl.do?publicDataPk={api_id}`를 LINK 문서당 1회 조회해 복구하며,
  결과는 `api_type_evidence.link_url_lookup`, 집계는 `crawler.link_url_lookups`에 남는다.
  실패해도 문서를 실패시키지 않는다.
- **상세기능(detail function)은 한 번에 하나만 서버 렌더된다.** `select#open_api_detail_select`가
  여덟 개를 제시해도 HTML에는 하나뿐이라, 예전에는 문서 하나가 오퍼레이션 하나만 갖고
  저장됐다. **옵션마다 요청주소·요청변수·출력결과가 다르다** (15061362는 `/GongsiReg`,
  `/GongsiRenew`, `/GongsiTrans` … 8개). 이제 크롤러가 옵션마다
  `/tcs/dss/selectApiDetailFunction.do`에 POST해 전부 수집한다.
  - 필드 3개(`oprtinSeqNo`·`publicDataDetailPk`·`publicDataPk`)가 **모두 필수**다.
    `publicDataPk`를 빼면 404다. 페이지에는 이 필드를 빠뜨린 옛 전역 함수
    `fn_selectApiDetailFunction`이 死코드로 남아 있으니 계약으로 삼지 말 것 —
    버튼이 실제로 부르는 것은 `apiObj.fn_selectApiDetailFunction`이다.
  - 응답은 컨테이너 없는 HTML 조각이다(`#apiDetailFunctionDiv`도 `.open-api-detail-result`도
    없다. 그 이름은 조각에 딸려오는 `<script>` 본문에만 나오므로 **문자열 검색 말고
    선택자로** 판별할 것). `build_detail_function_endpoints()`가 조각을 엔드포인트로 만든다.
  - 옵션별 결과는 문서의 신규 필드 `detail_functions[]`에, 집계는
    `crawler.detail_function_fetches`에 남는다. 한 옵션이 실패해도 나머지는 수집되고,
    전부 실패하면 페이지가 렌더한 하나가 남는다.
  - 인라인 swagger가 있는 `openapi_new`는 스펙이 이미 전체를 담으므로 조회하지 않는다.
- **`swaggerJson` 선언이 `var`→`const`로 바뀌었다.** 빈 리터럴은 "인라인 스펙 없음"으로
  취급한다 — openapi_new/old 판별이 이 구분에 달렸다.
- **fileData 기관자체 다운로드형**(제공형태 "기관자체에서 다운로드")은 JSON-LD도
  `atchFileId`도 없어 항상 폴백을 탄다. 폴백은 페이지의 `publicDataDetailPk`를 먼저 쓴다 —
  infuser는 다른 형태의 id를 주고 시도한 모든 네임스페이스에서 404였다(2026-08-03).

### 외부 API·모델 특이사항
- **data.go.kr 크롤링**: 공식 API가 아니라 HTML/CSV 스크래핑이다. OpenAPI 문서는
  페이지에 인라인된 `swaggerJson`을 추출하고, fileData는 HTML에 임베드된
  `atchFileId`로 다운로드 URL을 조립한다. 사이트 마크업이 바뀌면 크롤러가 조용히
  깨진다 — 2026-08에 실제로 겪었다(위 "data.go.kr이 2026-08에 리뉴얼됐다" 참고).
- **serviceKey**: 코드·테스트에 등장하는 `serviceKey`는 수집된 API 문서의
  요청 파라미터 필드명일 뿐이다. **이 저장소는 실제 공공데이터 인증키를 보유하지도,
  실제 API를 호출하지도 않는다** (문서 메타데이터만 다룸).
- **LLM은 로컬 Ollama**: combiner 등은 `OLLAMA_BASE_URL`(기본
  `http://localhost:11434`), `OLLAMA_MODEL`(기본 `qwen3.5:4b`)에 의존한다.
  Ollama 미기동 환경에서는 LLM 경로가 실패하므로 비-LLM 경로로 테스트할 것.
- **임베딩 모델**: `services/search/models/ko-sroberta-multitask/`가 없으면 최초 실행 시
  자동 다운로드된다(네트워크 필요). 테스트는 fixture 기반이라 모델 없이 돈다.
- **korea100의 법령 인용 원칙** (보류 중, 재개 시 필수): 원문 확인 못 한 인용은
  추정하지 않고 `unverified`로 표기한다. 콘텐츠 수정 시 이 검증 원칙(README 참조)을
  깨지 말 것. `archive/korea100/web/`에는 자체 CLAUDE.md(→AGENTS.md)가 있다.

### 포트 계약
8000(search) · 8003(combiner) · 8010(workbench) · 8020(hermes PoC) · 5173(dashboard dev).
workbench 실행기는 8000/8003이 이미 떠 있으면 기존 프로세스를 재사용한다.
