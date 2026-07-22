# Nara Hermes 실제 도구 호출 루프 구현 계획

- 문서 상태: **부분 구현 반영됨** — 단계 0~4는 축소된 형태로 구현, 단계 5·6 미착수
- 작성 기준일: 2026-07-19 / 현행화 기준일: 2026-07-22
- 적용 프로젝트: `C:\project\nara_hermes_poc`
- 보호 대상: `C:\project\nara_workbench(API통합워크벤치)` 변경 금지
- 파생 문서
  - [`agent_expansion_exploration.md`](agent_expansion_exploration.md) — 확장 후보 탐구
  - [`plan_critic_agent_plan.md`](plan_critic_agent_plan.md) — 후보 A, 구현 반영됨
  - [`flow_export_plan.md`](flow_export_plan.md) — 후보 D, 구현 반영됨

## 1. 결론

### 1.1 원안

기존 결정형 `/design`을 비교 기준으로 유지하고 별도의 `/agent/design-runs`
흐름을 추가한다. 이 흐름에서 Hermes가 Nara MCP 도구를 직접 반복 호출해
검색 → 검토 → 재검색 → 선택·제외 → 관계 검증 → 계획 생성을 스스로 수행한다.
통합 방식은 Hermes Gateway를 별도 프로세스로 띄우고 PoC가 **Runs API**를
호출하는 sidecar 구조로 한다.

### 1.2 실제 구현에서 바뀐 것

`/agent/design-runs` 계열 API, SSE 진행 이벤트, 중단, 프론트 실행 화면은
구현되었다. 그러나 **통합 방식과 판단 주체가 원안과 다르다.**

- Runs API(`POST /v1/runs`)는 사용하지 않는다. 대신 각 단계마다 Hermes CLI를
  서브프로세스로 띄워 **Nara MCP 도구를 정확히 한 번 호출시키는 프로브**
  (`run_hermes_tool_probe`)를 실행하고, 그 stdout trace로 호출 사실을 확인한다.
- 실제 오케스트레이션 순서(무엇을 검색하고 무엇을 선택할지)는 여전히 Python
  (`AgentRunManager._run_loop`)이 정한다. 선택은 검색 상위 3개 자동 선택이다.
- 따라서 **§4.1 목표 중 "모델이 결과를 읽고 판단·재검색·제외한다"는 아직
  달성되지 않았다.** 현재 구현이 baseline `/design`보다 추가로 증명하는 것은
  "Hermes가 Nara MCP 도구를 실제로 호출할 수 있다"와 "실행 상태를 실시간으로
  보여주고 중단할 수 있다" 두 가지다.

원안의 Runs API 방식은 폐기가 아니라 **보류**다. 재개 조건은 §17에 정리한다.

## 2. 구현 현황 요약 (2026-07-22)

| 항목 | 원안 | 현재 구현 | 상태 |
|---|---|---|---|
| 통합 방식 | Hermes Gateway Runs API sidecar | 단계별 Hermes CLI 프로브 서브프로세스 | 대체 구현 |
| 도구 선택 주체 | Hermes 모델 | Python 고정 순서 | 미달성 |
| API 선택 기준 | 상세 근거 기반 판단 | 검색 상위 3개 자동 | 미달성 |
| 재검색 | 최대 2회 자동 재작성 | 없음 (사용자 `use_vector` 토글만) | 미착수 |
| 실행 API | 생성·조회·SSE·중단·승인 | 생성·조회·SSE·중단 (승인 없음) | 부분 구현 |
| 최종 결과 계약 | §8.2 전용 JSON | 기준선과 동일한 `DesignResponse` | 미도입 |
| 실행 상태 모델 | 13개 상태 | 5개 run 상태 + 단계 이벤트 | 축소 구현 |
| 프론트 진행 표시 | 타임라인·중단·재접속 | 타임라인·중단 구현, 재접속 미구현 | 부분 구현 |
| 계획 검증(critic) | 원안에 없음 | 결정형 + 프로브 2층 구현 | 추가 구현 |
| flow 내보내기 | 원안에 없음 | `GET .../flow` 구현 | 추가 구현 |
| shadow 평가 | 골든 20개 비교 보고서 | 골든 5개, 러너 없음 | 미착수 |
| 구조화 로그 | 13개 필드 | 로깅 없음 (메모리 이벤트만) | 미착수 |

실제 추가된 파일:

```text
app/agent.py          AgentRunManager, run_hermes_tool_probe
app/critic.py         결정형 검증기 + Hermes 검증 프로브
app/flow_export.py    대시보드 flow JSON 변환
app/schemas.py        AgentRunRequest/Response, AgentEvent, CriticReport
static/               에이전트 실행 화면 (index.html, app.js, styles.css)
config/hermes.example.yaml, Modelfile.hermes-64k, Modelfile.hermes-2b-64k
run.py                Search·Combiner·PoC(·Hermes Gateway) 통합 실행기
```

원안 단계 2가 예고한 `hermes_client.py`, `agent_prompt.py`,
`agent_result_parser.py`, `agent_routes.py`는 Runs API를 쓰지 않으므로
생성되지 않았다.

## 3. 현재 동작

### 3.1 기준선 `/design` (변경 없음)

```text
POST /design → run_design() → search → 상위 3개 자동 선택
             → detail × N → relations → compose → DesignResponse
```

### 3.2 에이전트 `/agent/design-runs` (현행)

```text
POST /agent/design-runs (202, run_id 즉시 반환)
  └─ asyncio task
       ├─ [search]    Hermes 프로브: search_api_docs 1회 → NaraClient.search
       ├─ 상위 3개 자동 선택 (요청에 selected_service_ids가 있으면 그것)
       ├─ [detail]    선택 ID마다 Hermes 프로브 get_api_detail → NaraClient.detail 병렬
       ├─ [relations] 2개 이상일 때만 프로브 derive_relations → NaraClient.relations
       ├─ [compose]   compose=true일 때 프로브 compose_service_plan → NaraClient.compose
       ├─ [critic]    결정형 검증(+full 모드면 검증 프로브) → CriticReport
       └─ completed
```

각 단계는 `AgentEvent`로 SSE 스트림에 발행되고, `DesignResponse.stages`에도
누적된다. Hermes 프로브가 실패하면 해당 도구 이름이 결과 `warnings`에 남고
`hermes.status`가 `partial`이 되지만 **run은 계속 진행된다** (fail-soft).

### 3.3 여전히 불가능한 것

- 검색 결과에 대한 모델의 의미 판단과 후보 제외
- 검색어 재작성·반복 검색, 벡터 이탈 시 lexical-only 자동 전환
- 선택·제외 이유 생성 (`rejected_apis`가 계약에 없다)
- 관계 부족 시 후보 교체
- Hermes 세션·토큰·비용 추적 (프로브는 매 호출마다 새 세션이다)
- 승인 대기(`waiting_approval`) 흐름
- baseline과 agent 결과의 자동 비교

## 4. 목표와 비목표

### 4.1 목표와 달성 여부

| 목표 | 상태 |
|---|---|
| 실제 Hermes가 Nara MCP 도구를 호출한다 | 달성 (단, 호출 대상은 PoC가 지정) |
| 모델이 도구를 선택한다 | 미달성 |
| 한 요청에서 Nara 도구 호출 12회 이하 | 달성 (구조상 최대 6회, §7.1) |
| 최대 3개 API 선택 | 달성 (`_select_ids`가 3개로 절단) |
| 검색 순위를 그대로 쓰지 않는다 | 미달성 |
| 모든 선택·관계 주장에 조회된 근거 | 부분 달성 — critic이 사후 검증(§10.1) |
| 부적합 시 최대 2회 재검색 | 미착수 |
| 도구 진행 상황 실시간 표시 | 달성 (SSE + 프론트 타임라인) |
| 실행 중단 | 달성 (`POST .../stop` → task cancel) |
| 실패 후 상태 복원 | 부분 달성 — `GET .../events?after=N`은 있으나 UI 미사용 |
| baseline과 agent 비교 | 미착수 |

### 4.2 비목표 (전부 유지됨)

- 실제 행정 API 실행, 민원 제출, 데이터 변경, 외부 발송
- 터미널·파일 쓰기·브라우저 도구 허용
- 무승인 메모리 또는 스킬 변경
- 여러 Hermes Agent 병렬 운영 — critic도 메인 run 종료 후 순차 1회다
- 기존 Workbench 코드·동작 변경

## 5. 아키텍처

### 5.1 현재 (as-built)

```text
브라우저 :8020
    │  POST /agent/design-runs · GET .../events (SSE) · POST .../stop
    │  GET  .../flow
    ▼
Nara Hermes PoC API :8020  (FastAPI, app/main.py)
    │
    ├─ 단계마다 subprocess: hermes -p <profile> -m <model> chat -q "<한 도구만 호출>"
    │      └─ Hermes ──stdio──> Nara MCP server (mcp_server/server.py)
    │                              └─ Nara Search :8000 / Combiner :8003
    │
    └─ 같은 단계에서 NaraClient가 Search·Combiner를 직접 HTTP 호출
       (실제 결과 데이터는 이쪽에서 온다)
```

프로브와 직접 호출이 **이중으로 나가는 구조**다. 프로브는 "Hermes가 이 도구를
호출할 수 있다"는 증거를 만들고, 결과 데이터는 PoC가 직접 가져온다. 원안
아키텍처로 가면 이 이중 호출이 사라진다.

### 5.2 목표 (보류 중)

```text
브라우저 :8020 → PoC API :8020 → Hermes Gateway :8642 (Runs API)
                                    └─ Nara MCP stdio → Search :8000 / Combiner :8003
```

`run.py --with-hermes`가 이미 `hermes ... gateway`를 띄우므로 게이트웨이
프로세스 자체는 확보되어 있다. 남은 것은 PoC가 Runs API를 소비하는 클라이언트다.

공식 근거:

- [Hermes API Server와 Runs API](https://hermes-agent.nousresearch.com/docs/user-guide/features/api-server/)
- [Hermes MCP 연결·필터링](https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp)
- [Hermes Skills System](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills/)
- [Hermes Security](https://hermes-agent.nousresearch.com/docs/user-guide/security/)
- [Hermes Sessions와 trace export](https://hermes-agent.nousresearch.com/docs/user-guide/sessions/)

## 6. 통합 방식

### 6.1 채택: 단계별 CLI 프로브 (현행)

`app/agent.py: run_hermes_tool_probe(tool, instruction, settings, profile=None)`

- 실행 파일 탐색 순서: `HERMES_EXE` → `%LOCALAPPDATA%\hermes\...\hermes.exe` → `PATH`
- 실행: `hermes -p <profile> -m <model> chat -q <경계 프롬프트>`
- 프롬프트는 "지정한 도구 하나만 정확히 한 번 호출하라"로 고정한다.
- 호출 확인은 stdout에서 `mcp__nara__<tool>` 패턴을 찾는다. OpenAI 계열
  provider는 도구 접미사 없이 `mcp__nara`만 남기므로, 경계 프롬프트가 도구를
  하나로 제한한다는 전제하에 이 축약 trace도 호출로 인정한다
  (`verification: exact-tool-name | bounded-nara-trace`).
- 반환 상태: `called | failed | timeout | disabled | unavailable`

선택 이유: Runs API 클라이언트 없이 "Hermes가 Nara MCP를 실제로 호출한다"를
가장 빨리 증명할 수 있고, Hermes 미설치 환경에서도 `NARA_HERMES_PROBE=0`으로
전체 흐름을 그대로 돌릴 수 있다.

한계: 세션이 매 호출마다 끊기므로 모델이 이전 단계 결과를 볼 수 없다. 판단·
재검색을 모델에게 넘기려면 이 방식으로는 불가능하다.

### 6.2 보류: Hermes Gateway Runs API

PoC 백엔드가 소비할 공식 API (아직 미사용):

```text
GET  /health · /health/detailed · /v1/capabilities
POST /v1/runs · GET /v1/runs/{id} · GET /v1/runs/{id}/events
POST /v1/runs/{id}/stop · POST /v1/runs/{id}/approval
```

장점(프로세스 격리, 세션 연속성, 중단·재접속, 키 비노출)은 원안 그대로
유효하다. §17 조건 충족 시 재개한다.

### 6.3 보류: Hermes Python Library 직접 내장

`AIAgent.run_conversation()` 직접 import는 의존성 충돌·스레드 안전성 때문에
계속 보류한다. 오프라인 평가 러너(§11 단계 5)에서만 재검토한다.

## 7. Hermes 도구 호출 정책

### 7.1 허용 도구와 예산

| MCP 도구 | 용도 | 원안 상한 | 현재 실효 호출 수 |
|---|---|---:|---|
| `search_api_docs` | 하이브리드/lexical 검색 | 3 | 1 (재검색 없음) |
| `get_api_detail` | 후보 문서 상세 검증 | 8 | 선택 문서 수 = 최대 3 |
| `derive_relations` | 관계 검증 | 2 | 0 또는 1 |
| `compose_service_plan` | 계획 초안 생성 | 1 | 0 또는 1 |

현재는 Python이 호출 횟수를 구조적으로 결정하므로 **한 run의 프로브는 최대
6회**이며 별도 카운터가 필요 없다. 모델이 도구를 선택하게 되면 원안 상한과
12회 총량 제한을 실제 카운터로 강제해야 한다.

Hermes에 등록되는 이름은 `mcp__nara__<tool_name>` 형식이다.

### 7.2 비허용 도구

terminal · file · browser · web · cronjob · delegation · messaging · memory ·
skills 쓰기 도구.

`config/hermes.example.yaml`이 Nara MCP만 등록하고 `tools.include`로 네 도구를
화이트리스트하며 `resources`·`prompts`를 끈다. `memory.write_approval`과
`skills.write_approval`은 `true`다.

### 7.3 목표 반복 루프 (미구현)

```text
요구 분석 → 1차 hybrid 검색 → 상위 후보 상세 조회
  → 목적과 일치하는가? ─아니오→ 검색어 재작성 또는 lexical-only 재검색
  → 예 → API 1~3개 선택 + 제외 이유 기록
  → 2개 이상이면 관계 조회 → 근거 충분한가? ─아니오→ 후보 교체 또는 독립 단계 명시
  → 조합 계획 생성 → 선택 ID·근거·누락·비실행 문구 검증 → 구조화된 최종 결과
```

### 7.4 중단 조건

| 조건 | 상태 |
|---|---|
| 사용자 중단 요청 | 구현 (`POST .../stop`) |
| Nara Search 연결 실패 | 구현 (run `failed`) |
| 프로브 단건 시간 초과 | 구현 (`NARA_HERMES_TIMEOUT`, 기본 75초) |
| 검증 단계 시간 초과 | 구현 (`NARA_CRITIC_TIMEOUT`, 기본 60초) |
| 도구 호출 12회 도달 | 불필요 (구조상 최대 6회) |
| 검색 3회 후 적합 후보 없음 | 해당 없음 (재검색 미구현) |
| 동일 인자 연속 호출 | 해당 없음 |
| 전체 실행 300초 초과 | **미구현** — run 전체 timeout이 없다 |
| 상세 조회 성공 문서 없음 | 미구현 — 상세 실패는 예외로 run 실패 |

검색 결과가 비면 상세·관계·계획 단계를 `skipped`로 기록하고 경고를 남긴 채
`completed`로 끝난다. 원안의 `insufficient_evidence` 상태는 아직 없다.

## 8. 지시문과 결과 계약

### 8.1 현재 프롬프트

프로브 프롬프트는 단일 도구 호출만 지시한다.

```text
반드시 nara MCP의 <tool_name> 도구만 정확히 한 번 호출하라. <인자 안내>
다른 도구, 스킬, 파일 접근을 사용하지 마라. 도구 응답 뒤에는 짧게 완료만 답하라.
```

설계 판단을 위한 정책 지시문(검색 순위를 그대로 쓰지 말 것, 근거 없는 관계를
주장하지 말 것 등)은 `skills/nara-service-design/SKILL.md`에만 존재하고 실행
경로에서 사용되지 않는다. 사용자 입력은 프롬프트에 직접 들어가지 않으므로
현재 구조에서는 프롬프트 주입 표면이 작다. 모델에게 판단을 넘기는 순간
아래 서버 지시문과 입력 분리가 필요해진다.

```text
Nara 공공 API 서비스 설계 작업이다.
nara-service-design 스킬과 Nara MCP 도구만 사용하라.
검색 순위를 그대로 선택하지 말고 상세 문서를 확인하라.
벡터 결과가 부적합하면 검색어를 바꾸거나 lexical-only로 재검색하라.
관계 도구가 반환하지 않은 관계를 주장하지 마라.
실제 행정 처리나 API 실행을 완료했다고 말하지 마라.
최종 응답은 지정된 JSON 계약만 반환하라.
```

### 8.2 결과 계약

**현재**: 에이전트 run은 기준선과 동일한 `DesignResponse`를 반환한다.

```text
DesignResponse:   query, selected_service_ids, search, details,
                  relations?, plan?, stages[], warnings[]
AgentRunResponse: run_id, status, query, events[], result?, hermes{}, critic?, error?
```

**목표 계약(미도입)**: `status`, `request_summary`, `search_attempts[]`,
`selected_apis[]`(선택 이유·근거 포함), `rejected_apis[]`, `relations[]`,
`plan`, `warnings[]`, `executed: false`.

목표 계약은 모델 판단이 도입돼야 채울 값이 생긴다(선택 이유, 제외 이유,
검색 시도 이력). 도입 시 Pydantic 검증과 `format_error` 보존 규칙을 함께
넣고, [`plan_critic_agent_plan.md`](plan_critic_agent_plan.md) §2.1의 검사를
새 계약으로 확장한다.

## 9. 실행 상태 모델

### 9.1 현재 구현

`AgentRunResponse.status`: `queued · running · completed · failed · cancelled`

`AgentEvent.name`: `queued · agent · search · detail · relations · compose ·
critic · completed · failed · cancelled`
`AgentEvent.status`: `queued · running · completed · skipped · failed · cancelled`

프론트는 이벤트 `name`을 행 단위로 갱신하고(같은 이름은 같은 행), 상단 워크플로
띠는 `search / detail / compose` 세 칸을 현재 상태로 칠한다. 이전 단계와 현재
단계가 동시에 "진행 중"으로 보이지 않는다.

### 9.2 목표 상태와의 차이

| 목표 상태 | 현재 대응 |
|---|---|
| `analyzing` | 없음 (`agent` 이벤트가 대신) |
| `searching` / `reviewing` / `relating` / `composing` | `search` / `detail` / `relations` / `compose` 이벤트 |
| `validating` | `critic` 이벤트로 구현 |
| `waiting_approval` | 없음 |
| `insufficient_evidence` | 없음 — 경고 + `completed` |
| `stopping` | 없음 — 즉시 `cancelled` |

## 10. 후처리 단계 (원안 이후 추가)

### 10.1 계획 검증 (Plan Critic)

메인 루프 종료 후 순차 1회, 읽기 전용으로 결과를 재검증한다. 결과를 수정하지
않고 `critic.verdict`(`pass`/`evidence_gap`/`contradiction`/`failed`)와
findings만 첨부하며, 검증 실패는 run을 실패시키지 않는다.

- 결정형 검사 6종: `selected-subset-of-details`, `selected-in-search`,
  `relations-verified`(관계 1회 재조회), `relations-not-skipped`,
  `plan-missing-reported`, `contract-limits`
- `NARA_CRITIC_MODE=full`이면 `nara-critic` 프로필로 `get_api_detail`(≤3)·
  `derive_relations`(≤1) 프로브를 추가 실행
- 상세: [`plan_critic_agent_plan.md`](plan_critic_agent_plan.md)

이 verdict는 §11 단계 5의 "근거 없는 관계 주장률 0%" 지표를 자동 측정할 수단이
된다. 평가 연동은 아직 미착수다.

### 10.2 대시보드 flow 내보내기

`GET /agent/design-runs/{run_id}/flow`가 완료된 run의 선택 API·관계를
nara_dashboard 가져오기용 flow JSON으로 변환한다(404: 없는 run, 409: 미완료).
MCP 도구가 아니므로 도구 예산·보안 정책에 영향이 없다.
상세: [`flow_export_plan.md`](flow_export_plan.md)

## 11. 구현 단계 진행 상황

### 단계 0 — 기준선 고정 · 부분 완료

- 완료: `/design`은 원형 그대로 유지되고 별도 경로로 에이전트가 추가됐다.
  테스트는 10개에서 **36개**로 늘었고 전부 통과한다. Workbench 파일 변경 없음.
- 남음: 골든 질문 20개 확장 (현재 `evaluation/golden_queries.json` 5개).

### 단계 1 — Hermes 프로필과 MCP 연결 · 완료

- `config/hermes.example.yaml`: Nara MCP stdio 등록, `tools.include` 4개,
  `supports_parallel_tool_calls: false`, `resources`/`prompts` off,
  memory·skills 쓰기 승인 on.
- 모델: 기본은 OpenAI 프로필(`nara-openai` / `gpt-5.4-mini`). 로컬 대안으로
  `config/Modelfile.hermes-64k`(qwen3.5:4b, num_ctx 65536)와 2b 변형 제공.
- 남음: `nara-critic` 프로필이 예시 파일에 없다(로컬 `~/.hermes`에만 존재).
  재현 가능한 설정 예시에 포함시켜야 한다.

### 단계 2 — Hermes 클라이언트 · 대체 구현

`hermes_client.py` 대신 `run_hermes_tool_probe`로 대체됐다. 환경 변수도
원안(`HERMES_API_URL`, `HERMES_API_KEY`, `HERMES_RUN_TIMEOUT`,
`NARA_AGENT_MODE`)이 아니라 아래를 쓴다.

| 변수 | 기본값 | 의미 |
|---|---|---|
| `NARA_HERMES_PROFILE` | `nara-openai` | 실행 프로필 |
| `NARA_HERMES_MODEL` | `gpt-5.4-mini` | 도구 호출 모델 |
| `NARA_HERMES_TIMEOUT` | `75` | 프로브 1건 제한 시간(초) |
| `NARA_HERMES_PROBE` | `1` | `0`이면 프로브 없이 흐름만 실행 |
| `HERMES_EXE` | (없음) | 실행 파일 경로 직접 지정 |
| `NARA_CRITIC_MODE` | `deterministic` | `disabled`/`deterministic`/`full` |
| `NARA_CRITIC_TIMEOUT` | `60` | 검증 단계 제한 시간(초) |
| `NARA_HERMES_CRITIC_PROFILE` | `nara-critic` | 검증 프로브 프로필 |

Runs API를 도입할 때 `HERMES_API_URL`·`HERMES_API_KEY`를 추가하되, 기존
`NARA_HERMES_*`를 단일 출처로 유지한다(`app/config.py`의 `HERMES_ENV_DEFAULTS`).

### 단계 3 — 에이전트 실행 API · 부분 완료

| 메서드 | 경로 | 상태 |
|---|---|---|
| `POST` | `/agent/design-runs` | 구현 (202) |
| `GET` | `/agent/design-runs/{id}` | 구현 |
| `GET` | `/agent/design-runs/{id}/events` | 구현 (SSE, `after` 재개 지원) |
| `POST` | `/agent/design-runs/{id}/stop` | 구현 |
| `GET` | `/agent/design-runs/{id}/flow` | 구현 (§10.2) |
| `GET` | `/agent/health` | 구현 — 프로필·모델·프로브 여부만 보고 |
| `POST` | `/agent/design-runs/{id}/approval` | 미구현 |

남은 작업:

- `/agent/health`가 Hermes 생존을 실제로 확인하지 않는다(설정값만 반환).
- 종료된 run 메타데이터 정리가 없다 — `AgentRunManager._runs`가 무한히 쌓인다.
- 최종 선택 ID가 상세 조회 ID의 부분집합인지는 critic이 사후 검증한다.

### 단계 4 — 프론트 에이전트 모드 · 부분 완료

- 구현: 실시간 도구 호출 타임라인, 워크플로 단계 표시, 실행 중단 버튼,
  critic 배지와 findings 목록, "대시보드로 내보내기" 버튼, 상단 서비스 상태.
- 남음: 기준선/에이전트 모드 전환, 검색어 변경 이력, 선택/제외 API 분리 표시,
  선택 이유 표시(계약에 필드가 없다), 새로고침 후 진행 중 run 재접속
  (`run_id`가 메모리에만 있다), 승인 UI.

### 단계 5 — 평가와 shadow mode · 미착수

`NARA_AGENT_MODE`(`disabled`/`shadow`/`enabled`) 플래그 자체가 없다.
평가 지표(원안 유지):

| 지표 | 초기 합격 기준 |
|---|---:|
| 실제 MCP 도구 호출 포함률 | 100% |
| 선택 API 상세 조회율 | 100% |
| 근거 없는 관계 주장률 | 0% |
| 허용되지 않은 도구 호출 | 0건 |
| 최종 JSON 파싱 성공률 | 95% 이상 |
| 벡터 이탈 질문의 재검색 수행률 | 80% 이상 |
| 골든셋 선택 적합도 | baseline보다 개선 |
| 정상 요청 완료율 | 90% 이상 |
| 전체 도구 호출 수 | 요청당 12회 이하 |
| p95 완료 시간 | 300초 이하 |

사람 평가 항목: 선택 API의 목적 적합성, 제외 이유의 납득 가능성, 관계 근거의
실재성, 계획이 선택 API의 입력·출력 범위를 벗어나지 않는지, 불확실성을 숨기지
않는지.

주의: 지금 구조에서는 baseline과 agent의 선택 로직이 동일하므로 **비교 평가를
해도 선택 적합도 차이가 나올 수 없다.** 단계 5는 모델 판단(§6.2 또는 다중 턴
세션)이 들어간 뒤에 의미가 생긴다.

### 단계 6 — 제한적 메모리·스킬 개선 · 미착수

shadow 평가 통과 전에는 진행하지 않는다. 허용 후보(승인된 설명 형식, 검증된
검색어 재작성 패턴, 반복 실패한 도구 사용 주의점)와 금지 항목(개인정보·민원
원문, API 키, 검색 결과 전체, 승인되지 않은 조합)은 원안 그대로다.

## 12. 테스트 현황

현재 36개 테스트가 외부 서비스 없이 통과한다.

| 파일 | 개수 | 범위 |
|---|---:|---|
| `test_agent.py` | 4 | 단계 이벤트·프로브 호출 순서, critic 통합, `disabled`, fail-soft |
| `test_critic.py` | 12 | 검사별 위반/통과, 관계 재조회 실패 `unverified`, verdict 계산 |
| `test_flow_export.py` | 7 | 노드·엣지 변환, 고아 엣지 제외, flowIO 계약 미러 검증 |
| `test_app.py` | 6 | 정적 자산, flow 라우트 404/409/200 |
| `test_nara_client.py` | 3 | 업스트림 오류 변환 |
| `test_orchestrator.py` | 4 | 기준선 흐름 회귀 |

미구현 테스트(원안 §10):

- 프로브 stdout 파싱(`exact-tool-name` / `bounded-nara-trace` / `timeout`) 단위 테스트
- SSE 스트림 자체와 `after` 재개 테스트
- 최대 도구 호출·검색 횟수 초과 처리 (해당 로직 부재)
- 비밀정보 마스킹, 프롬프트 주입 무시, 존재하지 않는 service_id 생성 방지
- Hermes 재시작·MCP subprocess 종료·Ollama timeout 상황의 통합 테스트

## 13. 관찰성과 로그

**현재 미구현.** `app/`에 로깅 호출이 없고, 진행 정보는 run 객체의 인메모리
이벤트 목록뿐이라 프로세스 종료와 함께 사라진다.

도입 시 남길 구조화 필드(원안 유지, Runs API 도입 전에는 `hermes_run_id`·
`session_id`·토큰 필드가 비게 된다):

```text
request_id · hermes_run_id · session_id · model · started_at / ended_at · status
tool_name · tool_call_id · tool_duration_ms · tool_result_count
selected_service_ids · search_attempt_count · input_tokens / output_tokens · error_code
```

도구 결과 원문과 API 문서 전체는 로그에 남기지 않는다. Hermes session trace는
로컬 검토용으로만 내보내고 외부 업로드하지 않는다.

## 14. 보안 설정

현행 적용:

- Nara MCP 도구는 읽기·계획만 제공한다.
- `config/hermes.example.yaml`이 MCP subprocess에 넘기는 환경을 Nara URL·
  타임아웃·인코딩으로 제한하고, terminal·file·browser toolset을 켜지 않는다.
- YOLO mode를 쓰지 않는다. memory·skills 쓰기는 승인 필요.
- 브라우저는 Hermes를 직접 호출하지 않는다 (PoC 백엔드만 서브프로세스를 띄운다).
- `.env`는 git 제외이며 `.env.example`에는 빈 키만 둔다.

미해당 / 미검증:

- `API_SERVER_KEY`, Hermes API `127.0.0.1:8642` 바인딩, CORS 설정은 Runs API를
  쓰기 시작할 때 필요하다.
- `run_hermes_tool_probe`는 Hermes CLI에 **`os.environ.copy()` 전체를 넘긴다**
  (`OPENAI_API_KEY` 포함). MCP subprocess까지 전달되는지는 Hermes 설정의 env
  처리에 달려 있고 아직 확인하지 않았다. 원안의 "전체 프로세스 환경을
  MCP subprocess로 전달하지 않는다"를 만족하는지 실측이 필요하다.
- 프로브 stdout은 파싱 후 버려지지만, 실패 메시지(`message`)가 run 응답으로
  나가므로 stdout에 비밀정보가 섞이면 노출될 수 있다. 마스킹 미구현.

## 15. 실패·복구·롤백

현재 롤백 수단:

| 플래그 | 효과 |
|---|---|
| `NARA_HERMES_PROBE=0` | Hermes 호출 없이 결정형 흐름만 실행 (Hermes 미설치 환경 기본) |
| `NARA_CRITIC_MODE=disabled` | 검증 단계 제거, `critic`은 `None` |
| 에이전트 경로 미사용 | `/design`만 호출하면 기존 동작과 동일 |

Hermes Gateway와 MCP 서버를 모두 내려도 `/design`, Nara Workbench, Search,
Combiner는 영향을 받지 않는다. 원안의 `NARA_AGENT_MODE`는 단계 5와 함께
도입한다.

실패별 처리:

| 실패 | 현재 동작 |
|---|---|
| Hermes 미실행·미설치 | 프로브 `unavailable`, `hermes.status=partial`, 흐름 계속 |
| 프로브 시간 초과 | 프로세스 종료 후 `timeout`, 흐름 계속 |
| Search 실패 | run `failed` |
| Detail 실패 | **현재는 예외로 run 실패** (원안: 해당 후보 제외 후 계속) |
| Relations 실패 | 예외 전파 → run 실패. critic 재조회 실패는 `unverified` |
| Combiner timeout | compose 단계 `failed`, 검색·선택·관계 결과 유지 |
| 검증기 예외·시간 초과 | `critic.verdict=failed`, run은 `completed` |
| SSE 연결 끊김 | 프론트가 run 상태를 재조회해 최종 결과 표시 |

`Detail 실패`와 `Relations 실패`의 fail-soft 처리는 남은 작업이다.

## 16. 다음 작업 순서

1. 골든 질문 20개 확장 (단계 0 잔여, 다른 작업의 전제).
2. `Detail`·`Relations` 부분 실패 fail-soft 처리와 run 전체 timeout 추가.
3. 종료 run 정리와 `/agent/health`의 Hermes 실제 생존 확인.
4. 프로브 stdout 파싱·SSE 재개 단위 테스트 보강, 비밀정보 마스킹.
5. `nara-critic` 프로필을 `config/hermes.example.yaml`에 반영 (재현성).
6. **판단 이관 결정** — §6.2 Runs API 클라이언트를 구현할지, 아니면 프로브를
   다중 턴 세션으로 확장할지 정한다. 이 결정 없이는 §8.2 목표 계약과
   단계 5 평가가 진행 의미를 갖지 못한다.
7. 판단 이관 후: 목표 JSON 계약 도입 → critic 검사 확장 → shadow 평가 →
   `enabled` 승격 여부 결정 → 그 다음에만 승인형 memory·skill 실험.

확장 후보(법령 근거·문서 신선도 등)의 우선순위는
[`agent_expansion_exploration.md`](agent_expansion_exploration.md) §9를 따른다.

## 17. Runs API 재개 전 확인 사항

- 사용할 Hermes 버전을 고정했는가?
- Hermes API Server가 Runs·SSE·stop 기능을 실제로 광고하는가 (`/v1/capabilities`)?
- 사용할 모델이 64K 이상 컨텍스트로 실행되며 한국어 도구 호출 성공률이 충분한가?
- `API_SERVER_KEY`를 생성해 서버에만 저장했는가?
- Nara MCP 네 도구가 Hermes 세션 tool list에 등록되고, 그 외 도구가 없는가?
- MCP subprocess로 전달되는 환경 변수를 실측했는가 (§14)?
- 골든 질문과 baseline 결과가 저장되었는가?

이 항목을 충족한 뒤 §6.2 클라이언트 구현을 시작한다.
