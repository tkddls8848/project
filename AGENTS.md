# Nara 탐색 지도

이 문서는 기능 수정의 **첫 읽기 위치와 검증 범위**만 정한다. 구조, 서비스 경계,
안전 규약, 개발 환경은 [CLAUDE.md](CLAUDE.md)를 먼저 따른다.

## 작업별 시작점

| 작업 | 먼저 읽을 파일 | 이어서 확인할 계약 | 대응 테스트 |
| --- | --- | --- | --- |
| crawler의 일반 타입·저장 변경 | `modules/crawler/crawl_types.py`(유형 레지스트리) → 해당 crawler → `modules/crawler/managers/file_storage.py` | UI 요청은 `modules/crawler/backend/run_service.py`의 `CrawlRequest.to_argv()`를 거쳐 CLI로 간다. 새 결과 유형을 Search/Combiner가 소비할지 함께 확인한다. | `modules/crawler/tests/test_crawl_control_api.py`, 해당 crawler 테스트 |
| crawler의 심화 단계 변경 | `modules/crawler/depth_pipeline.py` → `modules/crawler/profiling/`, `modules/crawler/link_docs/`, `modules/crawler/portals/` | `--deep`/`--harvest`는 현재 요청 범위가 아니라 저장된 corpus를 읽는다. | `modules/crawler/tests/test_depth_stage_wiring.py` |
| crawler 제어 UI·CLI 인자 변경 | `modules/crawler/backend/run_service.py` → `modules/crawler/backend/main.py` → `modules/crawler/main.py` | 요청→argv 변환과 CLI 검증을 함께 맞춘다. 공용 실행 상태는 `libs/nara_common/process_runs.py`가 소유한다. | `modules/crawler/tests/test_crawl_control_api.py` |
| Search 색인·상세 데이터 변경 | `modules/search/backend/core/config.py` → `modules/search/backend/indexing/index_builder.py` → `modules/search/backend/catalog/detail_service.py` | crawler JSON은 색인 경로와 상세 fallback이 각각 읽는다. 입력 형식 변경은 crawler와 함께 결정한다. | `modules/search/tests/test_search_api.py`, `modules/search/tests/test_detail_api.py`, `modules/search/tests/test_build_lifecycle.py` |
| Search 랭킹 변경 | `modules/search/backend/search/ranking.py`(단일 진입점) → `fusion.py`/`coverage.py`와 두 retriever | 후보 생성, 융합, coverage, 상세 가능 여부 필터가 함께 결과 순서를 만든다. | `modules/search/tests/test_lexical_and_fusion.py`, `modules/search/tests/test_coverage_prior.py`, `modules/search/tests/test_search_api.py` |
| Combiner 조합·SSE 변경 | `modules/combiner/app/main.py` → `modules/combiner/app/llm.py` → `modules/combiner/app/prompts.py`/`schemas.py` | 문서 캐시와 raw ID 변환은 `modules/combiner/app/loader.py`에 있다. Search가 준 정식 ID를 받는 경계도 이 파일에서 확인한다. | `modules/combiner/tests/test_compose_api.py` |
| Refresher 실행·제출 UI 변경 | `modules/refresher/main.py` → `modules/refresher/backend/run_service.py` → `modules/refresher/frontend/app.js` | UI 요청→argv와 CLI 실행을 함께 추적한다. 실행 상태·SSE는 공용 `process_runs.py`를 사용한다. | `modules/refresher/tests/test_refresher_control_api.py`, `modules/refresher/tests/test_refresher.py` |
| Prologue design run 변경 | `apps/prologue/app/agent.py` → `apps/prologue/app/hermes_client.py` → `apps/prologue/app/nara_client.py`/`schemas.py` | run 상태는 `AgentRunManager`가, Gateway 관찰은 Hermes client가 맡는다. Search·Combiner 응답 형태 변경은 해당 서비스와 함께 검토한다. | `apps/prologue/tests/test_agent.py`, `apps/prologue/tests/test_hermes_client.py`, `apps/prologue/tests/test_critic.py` |
| Prologue 기동·profile 변경 | `apps/prologue/run.py` → `apps/prologue/config/hermes.example.yaml` | 런처와 생성 profile을 함께 본다. Dashboard flow 형식은 다음 행의 Dashboard 계약과 같이 바꾼다. | `apps/prologue/tests/test_run.py` |
| Dashboard 워크플로 노드·실행 변경 | `modules/dashboard/src/data/workflowNodeDefinitions.js`(노드 레지스트리) → `workflowEngine.js`(dispatch) → `workflowGraph.js`/`workflowOperators.js` | 팔레트·기본값·import 허용 타입·미니맵은 레지스트리에서 파생된다. 렌더러(`src/nodes/nodeTypes.jsx`)와 executor만 별도로 등록한다. | `modules/dashboard/src/data/__tests__/workflowEngine.test.js`, `modules/dashboard/src/data/__tests__/flowIO.test.js` |
| Dashboard 카탈로그·Search 연동 변경 | `modules/dashboard/src/data/apiDocs.js` → `modules/dashboard/src/data/searchClient.js` | `/api` 응답을 workflow 문서로 바꾸며 canonical `service_id`에서 `apiId`를 분리한다. Search 응답 형식과 함께 검토한다. | `modules/dashboard/src/data/__tests__/apiDocs.test.js`, `modules/dashboard/src/data/__tests__/searchClient.test.js` |
| Epilogue 실행 계약·상태 변경 | `apps/epilogue/domain/plans.py`/`operations.py`/`state_machine.py` → `apps/epilogue/api/main.py` | 실행 대상은 `config/operations.json` 카탈로그에서만 정해진다. 승인 결속과 감사 트리거는 `domain/approvals.py`와 `infra/database.py`에 있다. | `apps/epilogue/tests/test_contracts.py` |
| Epilogue Adapter·Worker 변경 | `apps/epilogue/adapters/registry.py` → `apps/epilogue/adapters/dummy.py` → `apps/epilogue/worker/runner.py` | 현재 Dummy Adapter 전용이다. 실제 Adapter 추가는 CLAUDE.md의 epilogue 계약과 계획 16절 완료 기준을 먼저 확인한다. | `apps/epilogue/tests/test_contracts.py` |
| 공용 경로·CLI·실행 상태 변경 | `libs/nara_common/paths.py`, `cli.py`, `process.py`, `process_runs.py` | 서비스별 request→argv 규칙은 각 `backend/run_service.py`에 남고, 공용층은 실행·관찰만 맡는다. | `tests/test_paths.py`, `tests/test_cli.py`, `tests/test_process.py`, `tests/test_process_runs.py` |

## 검증 명령

README의 테스트 대상(`tests` 또는 `npm test`)을 기준으로, Python 모듈은 각자 venv와
분리된 basetemp를 사용한다. `crawler` README에는 테스트 명령이 없으므로 아래 명령은
현재 테스트 트리와 검토 시 실행 형태를 기준으로 한다. Combiner와 Refresher는 최상위
`app` 패키지명이 같으므로 저장소 루트에서 함께 수집하지 않는다.

| 모듈 | cwd | 실행 명령 |
| --- | --- | --- |
| crawler | `C:\chronicle\modules\crawler` | `.\venv\Scripts\python.exe -m pytest -q tests --basetemp C:\tmp\nara-pytest-crawler -p no:cacheprovider` |
| search | `C:\chronicle\modules\search` | `.\venv\Scripts\python.exe -m pytest tests -q --basetemp C:\tmp\nara-pytest-search` |
| combiner | `C:\chronicle\modules\combiner` | `.\venv\Scripts\python.exe -m pytest tests -v --basetemp C:\tmp\nara-pytest-combiner` |
| refresher | `C:\chronicle\modules\refresher` | `.\venv\Scripts\python.exe -m pytest -q --basetemp C:\tmp\nara-pytest-refresher` |
| prologue | `C:\chronicle\apps\prologue` | `.\venv\Scripts\python.exe -B -m pytest tests -q --basetemp C:\tmp\nara-pytest-prologue` |
| epilogue | `C:\chronicle\apps\epilogue` | `.\venv\Scripts\python.exe -m pytest -q tests --basetemp C:\tmp\nara-pytest-epilogue -p no:cacheprovider` |
| dashboard | `C:\chronicle\modules\dashboard` | `npm test` |
| 공용 라이브러리 | `C:\chronicle` | `python -m pytest -q tests --basetemp C:\tmp\nara-pytest-root` |

`apps/gazetta`는 정적 페이지(`index.html`/`app.js`/`styles.css`)라 테스트 대상이 없다.

## 읽지 않을 경로

기능 경로를 찾을 때 아래는 기본적으로 제외한다. 오류나 생성 절차 자체를 조사해야 할 때만
필요한 파일 하나를 제한적으로 연다.

| 경로 | 제외 이유 |
| --- | --- |
| `api_storage/` | crawler가 만든 대용량·가변 corpus와 실행 산출물이다. 소스 계약은 생산·소비 코드와 테스트 fixture에서 확인한다. |
| `archive/` | 보관된 과거 작업이다. 현재 구현 판단에 쓰지 않는다. |
| `apps/prologue/.runtime/` | 런처가 생성하는 Hermes runtime profile이다. 원본은 `run.py`와 `config/hermes.example.yaml`이다. |
| `**/venv/` | 생성된 인터프리터와 설치 의존성이다. 코드 탐색 대상이 아니다. |
| `modules/dashboard/node_modules/` | 패키지 설치 산출물이다. 의존성 정보는 `modules/dashboard/package.json`에서 확인한다. |

## 식별자 용어

| 이름 | 형식·소유자 | 변환 경계 |
| --- | --- | --- |
| `api_id` | data.go.kr의 원시 문서 키인 숫자 문자열(예: `15000827`). crawler의 `CrawlData`와 저장 문서가 소유한다. | crawler가 JSON에 기록한 값을 Search가 정식 ID로 감싼다. Combiner는 원시 값을 내부 캐시 키로 쓴다. |
| `service_id` | Search가 소유하는 canonical `{source}:{api_id}` (현재 예: `openapi_new:15000827`). 허용 source와 정규화는 `modules/search/backend/core/service_id.py`에서 정의한다. | Search API는 이 값을 상세·관계 조회에 그대로 사용한다. Dashboard는 보존용 `serviceId`로 들고, workflow map용으로만 raw 부분을 꺼낸다. |
| `apiId` | Dashboard workflow 문서와 `apiDocMap`의 raw-ID 키. `searchClient.js`가 마지막 `:` 뒤를 잘라 만든다. | `service_id` → `apiId` 변환은 source 정보를 버린다. 서로 다른 source가 같은 raw ID를 가질 수 있는 변경은 map 키와 round-trip 테스트를 먼저 검토한다. |
| `doc_key` | 이제 코드에 없다. 예전 `IndexManager`가 `index.json`의 `목록키`를 부르던 이름이고, 그 모듈은 삭제됐다. | 다시 만들지 마라. 문서 식별에는 `api_id`를 쓴다. `archive/`나 옛 산출물에서 이 이름을 보면 `api_id`의 별칭으로 읽는다. |
