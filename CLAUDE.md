# Nara 개발 지침

data.go.kr API 문서를 수집·검색·조합하는 개인 개발용 모노레포다. 현재 구현과 테스트에
필요한 코드만 유지하며, 이전 경로 호환이나 미래 사이트 구조 대응을 미리 넣지 않는다.

## 현재 구조

최상위는 두 컨테이너로 나뉜다. `apps/`는 완성된 서비스, `modules/`는 그것을 구성하는
부품이다.

```text
data.go.kr -> modules/crawler -> api_storage/ (gitignore)
                                 -> modules/search :8000
                                 -> modules/combiner :8003

apps/prologue  :8020  계획 수립. Hermes Gateway(:8642) + Nara MCP 오케스트레이터
apps/epilogue  :8002  계획 수행. 행정 실행 통제 서비스 (현재 Dummy Adapter 전용)
apps/gazetta          정적 페이지

modules/crawler       크롤링 CLI + 제어 UI :8004
modules/search        검색·상세·관계 API :8000
modules/combiner      서비스 계획 초안 API :8003
modules/refresher     활용신청 연장 CLI + 제어 UI :8005
modules/dashboard     React Flow 편집기 :5173 (dev 서버가 Ollama :11434도 프록시)
libs/nara_common      표준 라이브러리 기반 저장소 공통 유틸리티
```

- 프롤로그가 계획을 만들고 에필로그가 그 계획을 실행한다. 두 앱은 한 세트다.
- `apps/*`는 `modules/*`를 HTTP로 사용한다. 구현을 직접 import하지 않는다.
  `modules/dashboard`도 search·combiner를 HTTP로만 부른다.
- 표준 라이브러리만 사용하는 저장소 공통 유틸리티는 `libs/nara_common/`에서 공유한다.
  각 독립 실행기는 `libs/`를 `sys.path`에 넣어 import한다. 루트에는 컨테이너 디렉터리만 둔다.
  CLI를 실행·관찰·중단하는 공용 실행기는 `nara_common.process_runs`에 있다.
  요청을 argv로 옮기는 규칙만 각 서비스가 갖는다.
- 저장소 루트는 `.nara-root`로 찾고 모든 산출물은 루트 `api_storage/`에 둔다.
- `archive/`와 날짜가 붙은 계획 문서는 현재 구현 판단에 사용하지 않는다.

## 모듈 계약

### crawler

- 현재 data.go.kr 마크업과 catalog 응답만 지원한다.
- 결과 유형은 `openapi_new`, `openapi_old`, `openapi_link`, `fileData`, `standard`다.
  `openapi_old`는 현재도 Swagger JSON이 없는 HTML 문서를 뜻하므로 제거 대상이 아니다.
- 심화 파일 분석은 `--deep`, 전체 파일 수신은 `--full-download`, 외부 기관 수집은
  `--harvest`를 명시해야 실행한다.
- `backend/`는 CLI를 서브프로세스로 실행하고 출력을 SSE로 흘린다. 크롤러 내부
  함수를 직접 호출하지 않으므로 UI와 터미널이 같은 코드 경로를 탄다.
- 실행될 명령은 서버가 만든다(`POST /runs/preview`). UI가 argv를 자체 조립하지 않는다.

### search / combiner

- 입력 데이터는 `api_storage/openapi_new/` 등 crawler 결과다. fresh clone에는 데이터가
  없으므로 crawler 실행 전 검색 결과를 가정하지 않는다.
- search는 검색·상세·관계 API, combiner는 읽기 전용 서비스 계획 초안을 제공한다.

### prologue

- 애플리케이션 run 하나가 Hermes Gateway run 하나에 대응한다.
- Nara MCP는 `search_api_docs`와 `get_api_detail`만 노출하고 최대 6회 호출한다.
  두 도구는 선택에 필요한 요약만 반환한다. 문서 전문은 루프가 끝난 뒤
  Orchestrator가 Nara에서 다시 조회한다.
- LLM은 service_id 선택기다. 요청이 `selected_service_ids`를 지정하면 run을 만들지 않는다.
- 루프 지침은 `HERMES_INSTRUCTIONS_TEMPLATE` 한 곳에만 둔다. 실행 경로가 로드를
  확인할 수 없는 skill 문서로 절차를 나누지 않는다.
- LLM 출력은 형식이 자유다. Orchestrator는 거기서 service_id만 읽고 검색·상세·관계·
  계획은 Nara 원본에서 다시 조회한다.
- 진행 단계와 critic이 루프 동작을 말할 때는 Gateway가 보고한 `tool_calls` 기록만
  근거로 삼는다. 모델 출력의 자기보고를 근거로 쓰지 않는다.
- 문서 최신성 검사의 인덱스 빌드 시각은 search `/health`에서 읽는다.
  `NARA_INDEX_BUILT_AT`는 덮어쓰기용이며 비어 있는 것이 기본이다.
- critic은 로컬 결정형 검증만 수행한다. 결과 재검증을 위한 추가 LLM run을 만들지 않는다.
- 실제 행정 처리나 외부 시스템 변경을 수행했다고 주장하지 않는다. 실행은 epilogue가 맡는다.

### epilogue

- 프롤로그가 만든 `ExecutionPlan`을 받아 검증·승인·실행을 통제한다. 계획을 스스로 만들지 않는다.
- 클라이언트는 대상 URL·HTTP 메서드·코드·승인자 ID를 계획에 넣을 수 없다. 실행 대상은
  서버가 소유한 `operation_id` 카탈로그(`config/operations.json`)에서만 정해진다.
- 승인은 세션 principal·계획 hash·입력 요약 hash·만료 시각에 결속한다. 승인 이후 계획이나
  입력이 바뀌면 승인은 무효다. `approved: true` 같은 자기 선언은 받지 않는다.
- API는 실행을 저장만 하고 외부 요청을 직접 보내지 않는다. 별도 Worker가 lease를 잡고
  실행하며, 프로세스가 죽으면 만료된 lease를 회수한다.
- 상태 변경과 감사 이벤트는 한 트랜잭션이다. 감사 기록은 SQLite 트리거로 append-only다.
- `manual`과 `linkout`은 `succeeded`가 아니라 `awaiting_user`다. 결과 불명은
  `outcome_unknown`이며 자동 재시도하지 않는다.
- **현재 Dummy Adapter만 있다.** 실제 기관 Adapter와 Refresher Adapter는
  `apps/prologue/docs/administrative-service-executor-modernization-plan.md` 16절의
  완료 기준을 만족하기 전까지 등록·활성화하지 않는다.

### refresher

- 현재 확인된 흐름만 지원한다:
  `selectAcountList.do -> fn_detail(...) -> 연장 신청하기 -> confirm/alert`.
- 로그인은 사람이 브라우저에서 수행하고 Playwright storage state를 저장한다.
- `extend`는 dry-run이며 실제 제출에는 `--commit`이 필요하다.
- HTTP 직접 제출, 사이트 자동 탐색, 다른 포털/과거 마크업 폴백은 지원하지 않는다.
- `backend/`도 CLI를 서브프로세스로 실행한다. 목록 표시만 읽기 전용으로
  `fetch_account_rows`를 직접 호출한다(표로 그리려면 구조화된 값이 필요하다).
- UI에서의 실제 제출은 `commit`과 별개로 `confirm_commit`을 함께 받아야 만들어진다.
  dry-run 요청을 그대로 되보내는 것만으로 실제 제출이 되지 않는다.
- 로그인 창은 서버가 도는 컴퓨터에 열린다. 원격 제어용이 아니다.

## 개발 환경

- 기준 환경: Windows PowerShell, 저장소 예시 경로 `C:\chronicle`.
- 각 모듈의 가상환경은 해당 디렉터리 `venv/`에 둔다.
- 서비스 포트: search 8000, epilogue 8002, combiner 8003, crawler UI 8004,
  refresher UI 8005, prologue 8020, Hermes Gateway 8642, dashboard 5173.
- dashboard의 dev 서버는 `/api`→search, `/combiner`→combiner와 함께
  `/ollama`→`localhost:11434`를 프록시한다. Ollama는 저장소 밖 런타임이며
  없으면 그 경로만 실패한다. 나머지 화면은 동작한다.
- 제어 UI(crawler·refresher)는 CORS를 열지 않고 `127.0.0.1`에만 바인딩한다.
  실행을 일으키는 표면이라 다른 출처의 페이지가 요청을 보내게 두면 안 된다.
  한 번에 하나의 실행만 허용한다.
- Python 테스트는 쓰기 가능한 임시 폴더를 사용한다:

```powershell
python -m pytest -q --basetemp C:\tmp\nara-pytest
```

변경 시 관련 모듈 테스트를 실행하고, 현재 동작에 필요하지 않은 호환 분기·중복 문서·
복제 유틸을 추가하지 않는다.
