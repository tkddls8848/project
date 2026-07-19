# Nara Hermes 실제 도구 호출 루프 구현 계획

- 문서 상태: 구현 승인 전 계획
- 작성 기준일: 2026-07-19
- 적용 프로젝트: `C:\project\nara_hermes_poc`
- 보호 대상: `C:\project\nara_workbench(API통합워크벤치)` 변경 금지

## 1. 결론

현재 PoC의 `/design`은 정해진 Python 순서로 검색 결과 상위 세 개를 선택한다.
Hermes가 검색 결과를 읽고 판단하는 구조가 아니므로 기존 Workbench와 기능적으로
큰 차이가 없다.

다음 구현에서는 기존 `/design`을 비교 기준으로 유지하고 별도의
`/agent/design-runs` 흐름을 추가한다. 이 흐름에서는 Hermes가 Nara MCP 도구를
직접 반복 호출하여 다음을 수행해야 한다.

1. 요구사항을 검색 의도로 분해한다.
2. 하이브리드 검색 결과를 검토한다.
3. 결과가 부적합하면 검색어 또는 검색 방식을 바꿔 재검색한다.
4. 상세 문서에 근거해 API를 선택하거나 제외한다.
5. 관계 근거를 확인하고 부족하면 후보를 다시 탐색한다.
6. 계획 초안을 생성한 뒤 근거와 제약을 검증한다.
7. 선택·제외 이유와 전체 도구 호출 기록을 사용자에게 보여준다.

권장 통합 방식은 **Hermes Gateway API 서버를 별도 프로세스로 실행하고 PoC가
Runs API를 호출하는 sidecar 구조**다. Hermes를 PoC Python 환경에 직접 import하는
방식은 첫 구현에서 사용하지 않는다.

## 2. 현재 기준선

### 2.1 현재 동작

```text
사용자
  → POST /design
  → NaraOrchestrator
  → search(query)
  → 검색 결과 상위 3개 자동 선택
  → detail × 3
  → relations
  → compose
  → 결과 반환
```

현재 구현 파일:

- `app/orchestrator.py`: 고정 순서와 상위 세 개 자동 선택
- `app/nara_client.py`: Nara Search·Combiner HTTP 클라이언트
- `mcp_server/server.py`: Hermes에 노출할 MCP 도구 네 개
- `skills/nara-service-design/SKILL.md`: 도구 사용 절차 초안
- `evaluation/golden_queries.json`: 초기 평가 질문

### 2.2 현재 구조에서 불가능한 것

- 검색 결과에 대한 모델의 의미 판단
- 검색어 재작성과 반복 검색
- 벡터 검색 결과가 동떨어졌을 때 lexical-only 전환
- 후보 선택·제외 이유 생성
- 관계가 부족할 때 후보 교체
- Hermes 세션·도구 호출·토큰·오류 추적
- 실행 중 진행 이벤트, 중단, 승인
- Workbench 수동 결과와 에이전트 결과의 비교

## 3. 목표와 비목표

### 3.1 목표

- 실제 Hermes 모델이 Nara MCP 도구를 선택하고 호출한다.
- 한 요청에서 최대 12회의 Nara 도구 호출만 허용한다.
- 최대 세 개 API를 선택하되 단순 검색 순위를 그대로 사용하지 않는다.
- 모든 선택과 관계 주장에 조회된 문서 근거가 있어야 한다.
- 검색 결과가 부적합하면 최대 두 번까지 재검색한다.
- 도구 진행 상황을 프론트페이지에 실시간 표시한다.
- 실행을 중단하고 실패 후 상태를 복원할 수 있다.
- 기존 결정형 `/design`과 에이전트 결과를 동일 질문으로 비교할 수 있다.

### 3.2 비목표

- 실제 행정 API 실행
- 민원 제출, 데이터 변경, 이메일·메신저 발송
- 터미널·파일 쓰기·브라우저 도구 허용
- 무승인 메모리 또는 스킬 변경
- 처음부터 여러 Hermes Agent를 병렬 운영
- 기존 Workbench 코드 또는 동작 변경

## 4. 목표 아키텍처

```text
브라우저 :8020
    │
    │ POST /agent/design-runs
    │ GET  /agent/design-runs/{id}/events  (SSE)
    │ POST /agent/design-runs/{id}/stop
    ▼
Nara Hermes PoC API :8020
    │
    │ Bearer 인증, 서버 간 요청
    ▼
Hermes Gateway API :8642
    │
    │ Hermes 실제 추론·도구 호출 루프
    ▼
Nara MCP stdio server
    ├─ search_api_docs
    ├─ get_api_detail
    ├─ derive_relations
    └─ compose_service_plan
         │
         ├─ Nara Search :8000
         └─ Nara Combiner :8003 → Ollama :11434
```

Hermes API 서버는 OpenAI 호환 응답 외에 장시간 작업용 Runs API를 제공한다.
Runs API는 실행 생성, 상태 조회, SSE 이벤트, 중단, 승인을 지원하므로 이번 UI
연동에 적합하다.

공식 근거:

- [Hermes API Server와 Runs API](https://hermes-agent.nousresearch.com/docs/user-guide/features/api-server/)
- [Hermes MCP 연결·필터링](https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp)
- [Hermes Skills System](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills/)
- [Hermes Security](https://hermes-agent.nousresearch.com/docs/user-guide/security/)
- [Hermes Sessions와 trace export](https://hermes-agent.nousresearch.com/docs/user-guide/sessions/)

## 5. 통합 방식 결정

### 5.1 선택: Hermes Gateway API + Runs API

PoC 백엔드는 다음 Hermes 공식 API만 소비한다.

- `GET /health`: 생존 확인
- `GET /health/detailed`: 모델·설정 준비 상태 확인
- `GET /v1/capabilities`: Runs·중단·승인 지원 여부 확인
- `POST /v1/runs`: 에이전트 실행 생성
- `GET /v1/runs/{run_id}`: 실행 상태와 최종 결과 조회
- `GET /v1/runs/{run_id}/events`: 도구·토큰·상태 SSE 구독
- `POST /v1/runs/{run_id}/stop`: 실행 중단
- `POST /v1/runs/{run_id}/approval`: 승인 요청 처리

선택 이유:

- Hermes 프로세스와 PoC 의존성을 격리할 수 있다.
- UI가 도구 호출 진행 상황을 실시간으로 받을 수 있다.
- 실행 중단과 재접속이 가능하다.
- API 키를 브라우저에 노출하지 않고 PoC 서버에만 보관할 수 있다.
- Hermes 내부 Python API 변경보다 공식 HTTP 계약에 덜 결합된다.

### 5.2 보류: Hermes Python Library 직접 내장

`AIAgent.run_conversation()`은 전체 메시지와 도구 호출을 받을 수 있지만, Hermes와
PoC가 같은 프로세스·가상환경을 공유하게 된다. 초기 PoC에서는 의존성 충돌,
스레드 안전성, 서버 중단 영향 범위가 커지므로 보류한다.

Python Library는 향후 오프라인 평가 러너에서만 검토한다.

## 6. Hermes 도구 호출 정책

### 6.1 허용 도구

Hermes에는 다음 네 개만 노출한다.

| MCP 도구 | 용도 | 호출 제한 |
|---|---|---|
| `search_api_docs` | 하이브리드 또는 lexical-only 검색 | 최대 3회 |
| `get_api_detail` | 후보 문서 상세 검증 | 최대 8회 |
| `derive_relations` | 선택 후보 관계 검증 | 최대 2회 |
| `compose_service_plan` | 최대 3개 문서로 계획 초안 생성 | 최대 1회 |

Hermes에 등록되는 실제 이름은 `mcp_nara_<tool_name>` 형식이 된다.

### 6.2 비허용 도구

- terminal
- file
- browser
- web
- cronjob
- delegation
- messaging
- memory
- skills 쓰기 도구

초기 프로필은 Nara MCP toolset만 활성화한다. MCP 설정에는 `tools.include`를 사용해
네 도구만 화이트리스트하고 `resources`, `prompts` 유틸리티는 끈다.

### 6.3 반복 루프

```text
요구 분석
  ↓
1차 hybrid 검색
  ↓
상위 후보 상세 조회
  ↓
후보가 목적과 일치하는가?
  ├─ 아니오 → 검색어 재작성 또는 lexical-only 검색
  └─ 예
       ↓
API 1~3개 선택 + 제외 이유 기록
       ↓
2개 이상이면 관계 조회
       ↓
관계 근거가 충분한가?
  ├─ 아니오 → 후보 교체 또는 독립 단계라고 명시
  └─ 예
       ↓
조합 계획 생성
       ↓
선택 ID·근거·누락·비실행 문구 검증
       ↓
구조화된 최종 결과
```

### 6.4 중단 조건

- 전체 Nara 도구 호출 12회 도달
- 검색 3회 후에도 적합 후보 없음
- 상세 조회 성공 문서가 없음
- 같은 인자로 동일 도구를 두 번 연속 호출
- Nara Search가 연결되지 않음
- 사용자가 중단 요청
- 전체 실행 시간 300초 초과

중단 시 임의의 API를 채우지 않고 `insufficient_evidence` 상태로 종료한다.

## 7. Hermes 지시문과 최종 결과 계약

### 7.1 실행 지시문 구성

PoC는 사용자 질문에 다음 서버 지시를 덧붙인다.

```text
Nara 공공 API 서비스 설계 작업이다.
nara-service-design 스킬과 Nara MCP 도구만 사용하라.
검색 순위를 그대로 선택하지 말고 상세 문서를 확인하라.
벡터 결과가 부적합하면 검색어를 바꾸거나 lexical-only로 재검색하라.
관계 도구가 반환하지 않은 관계를 주장하지 마라.
실제 행정 처리나 API 실행을 완료했다고 말하지 마라.
최종 응답은 지정된 JSON 계약만 반환하라.
```

사용자 입력은 지시문과 분리된 `input` 필드로 전달한다. 사용자가 입력한 문서
설명 안의 “이전 지시를 무시하라” 같은 문장은 도구 데이터로 취급하고 시스템
정책을 바꾸지 못하게 한다.

### 7.2 최종 JSON 계약

```json
{
  "status": "completed | insufficient_evidence | failed",
  "request_summary": "사용자 요구 요약",
  "search_attempts": [
    {
      "query": "검색어",
      "mode": "hybrid | lexical",
      "reason": "이 검색을 실행한 이유",
      "result_count": 5
    }
  ],
  "selected_apis": [
    {
      "service_id": "openapi_new:...",
      "name": "문서명",
      "selection_reason": "상세 문서에 근거한 선택 이유",
      "evidence": ["설명 또는 입력·출력 근거"]
    }
  ],
  "rejected_apis": [
    {
      "service_id": "openapi_new:...",
      "reason": "제외 이유"
    }
  ],
  "relations": [],
  "plan": "서비스 계획 초안",
  "warnings": [],
  "executed": false
}
```

PoC는 Pydantic으로 이 응답을 검증한다. 파싱에 실패하면 원문을 폐기하지 않고
`format_error`와 함께 보존하되 정상 완료로 표시하지 않는다.

## 8. 실행 상태 모델

| 상태 | 의미 | UI 표시 |
|---|---|---|
| `queued` | Hermes 실행 제출 전후 | 요청 준비 |
| `analyzing` | 요구 분석 | 요구 분석 중 |
| `searching` | `search_api_docs` 호출 | 문서 검색 중 |
| `reviewing` | `get_api_detail` 호출 | 후보 근거 검토 중 |
| `relating` | `derive_relations` 호출 | 관계 검증 중 |
| `composing` | `compose_service_plan` 호출 | 계획 생성 중 |
| `validating` | 최종 계약 검증 | 근거 확인 중 |
| `waiting_approval` | Hermes 승인 대기 | 사용자 결정 필요 |
| `completed` | 정상 종료 | 결과 표시 |
| `insufficient_evidence` | 근거 부족 종료 | 검색 조건 수정 안내 |
| `failed` | 실행 오류 | 실패 단계·재시도 안내 |
| `stopping` | 중단 처리 중 | 중단 중 |
| `cancelled` | 중단 완료 | 중단됨 |

SSE의 실제 MCP 도구 이름을 위 상태로 매핑한다. UI 단계는 단순 누적 활성화가
아니라 현재 실행 상태와 완료 상태를 각각 표현한다.

## 9. 구현 단계

### 단계 0 — 기준선 고정

작업:

- 기존 `/design`을 `baseline` 모드로 명명한다.
- 현재 테스트 10개를 회귀 기준으로 유지한다.
- 기존 Workbench 파일의 변경 금지를 테스트·문서에 명시한다.
- 골든 질문을 최소 20개로 확장한다.

완료 조건:

- 기존 `/design` 결과가 변경되지 않는다.
- Workbench git diff가 구현 전후 동일하다.

### 단계 1 — Hermes 전용 프로필과 MCP 연결

작업:

- Hermes를 별도 환경에 설치하고 버전을 고정한다.
- 최소 64K 컨텍스트를 가진 도구 호출 모델을 설정한다.
- `nara-poc` 전용 Hermes profile을 만든다.
- Nara MCP stdio 서버를 등록한다.
- 네 도구만 `tools.include`로 노출한다.
- `supports_parallel_tool_calls: false`를 유지한다.
- memory·skills 쓰기 승인을 켠다.
- terminal·file·browser 등 불필요한 toolset을 끈다.
- `/reload-mcp` 후 네 도구가 검색되는지 확인한다.

완료 조건:

- Hermes가 `mcp_nara_search_api_docs`를 실제 호출한다.
- 허용하지 않은 도구가 세션 tool list에 없다.
- API 키나 전체 프로세스 환경이 MCP subprocess로 전달되지 않는다.

### 단계 2 — Hermes API 클라이언트

추가 예정 파일:

```text
app/
├─ hermes_client.py
├─ agent_schemas.py
├─ agent_prompt.py
├─ agent_result_parser.py
└─ agent_routes.py
```

환경 변수:

```text
HERMES_API_URL=http://127.0.0.1:8642
HERMES_API_KEY=<server-only secret>
HERMES_PROFILE=nara-poc
HERMES_RUN_TIMEOUT=300
NARA_AGENT_MODE=shadow
```

작업:

- Hermes liveness·readiness·capabilities 클라이언트 작성
- Runs 생성·조회·SSE·중단·승인 메서드 작성
- API 키가 로그와 브라우저 응답에 나타나지 않도록 마스킹
- 연결, 인증 실패, 모델 미준비, run 실패를 서로 다른 오류로 변환

완료 조건:

- Mock Hermes API 계약 테스트 통과
- Hermes 중단 후 run 상태가 `cancelled`로 수렴
- API 키가 테스트 캡처와 오류 본문에 없음

### 단계 3 — 에이전트 실행 API

추가 예정 엔드포인트:

| 메서드 | 경로 | 역할 |
|---|---|---|
| `POST` | `/agent/design-runs` | Hermes 실행 생성 |
| `GET` | `/agent/design-runs/{id}` | 상태·최종 결과 |
| `GET` | `/agent/design-runs/{id}/events` | SSE 진행 이벤트 |
| `POST` | `/agent/design-runs/{id}/stop` | 실행 중단 |
| `POST` | `/agent/design-runs/{id}/approval` | 승인 처리 |
| `GET` | `/agent/health` | Hermes 포함 전체 준비 상태 |

작업:

- 사용자 질문과 전용 지시문으로 Hermes run 생성
- Hermes run ID와 PoC 요청 ID 매핑
- MCP tool progress를 Nara 단계 이벤트로 정규화
- 최종 JSON을 Pydantic 계약으로 검증
- 5분이 지난 종료 run 메타데이터 정리

완료 조건:

- `/agent/design-runs`가 기존 `/design`을 호출하지 않는다.
- trace에서 실제 MCP function call과 output을 확인할 수 있다.
- 최종 선택 ID가 실제 상세 조회된 ID의 부분집합이다.

### 단계 4 — 프론트페이지 에이전트 모드

작업:

- `기준선 모드`와 `Hermes Agent 모드` 전환 추가
- 실시간 도구 호출 타임라인 표시
- 검색어 변경 이력 표시
- 선택 API와 제외 API를 나눠 표시
- 선택 이유와 근거 표시
- 실행 중단 버튼 추가
- 연결이 끊기면 run 상태를 조회해 재접속
- 승인 요청 UI는 기능 감지 후에만 표시

완료 조건:

- 사용자가 어떤 검색과 검토를 거쳐 선택되었는지 알 수 있다.
- 이전 단계와 현재 단계가 동시에 현재 상태처럼 보이지 않는다.
- 페이지 새로고침 뒤에도 진행 중 run을 다시 연결할 수 있다.

### 단계 5 — 평가와 shadow mode

`NARA_AGENT_MODE=shadow`에서는 한 질문에 대해 다음 두 결과를 저장하되 사용자에게는
기존 결과만 먼저 보여준다.

```text
baseline: 기존 상위 3개 결정형 흐름
agent: Hermes 반복 도구 호출 흐름
```

평가 지표:

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

사람 평가 항목:

- 선택 API가 사용자 목적과 관련 있는가?
- 제외 이유가 납득 가능한가?
- 관계 근거가 실제 문서에 존재하는가?
- 계획이 선택 API의 입력·출력 범위를 벗어나지 않는가?
- 불확실성을 숨기지 않는가?

완료 조건:

- 20개 이상 골든 질문의 baseline/agent 비교 보고서 생성
- Agent가 기준선을 개선하지 못하면 기본 모드로 승격하지 않음

### 단계 6 — 제한적 메모리·스킬 개선

shadow 평가를 통과한 뒤에만 진행한다.

허용 후보:

- 사용자가 승인한 설명 형식
- 검증된 검색어 재작성 패턴
- 반복적으로 실패한 도구 사용상 주의점

금지:

- 개인정보와 민원 원문
- API 키·토큰
- 검색 결과 전체
- 승인되지 않은 API 조합

`memory.write_approval`과 `skills.write_approval`은 계속 `true`로 유지한다.

## 10. 테스트 계획

### 10.1 단위 테스트

- Hermes API 인증 헤더와 URL 생성
- Runs 상태 변환
- MCP tool progress → UI 단계 매핑
- 최종 JSON 파싱과 필드 검증
- 상세 조회하지 않은 API 선택 거부
- 관계 결과에 없는 주장 거부
- 최대 도구 호출·검색 횟수 초과 처리
- timeout·stop·cancelled 처리
- 비밀정보 마스킹

### 10.2 통합 테스트

- Fake Hermes SSE로 전체 UI 진행 상태 검증
- 실제 Hermes + Mock Nara MCP로 도구 호출 검증
- 실제 Hermes + 실제 Nara Search, `compose=false` 성격의 검색 검증
- 실제 Hermes + Combiner로 전체 계획 생성 검증
- Hermes 재시작, MCP subprocess 종료, Ollama timeout 상황 검증

### 10.3 안전성 테스트

- 사용자 입력이 terminal 호출을 요구해도 거부
- 문서 설명 안의 prompt injection 무시
- 존재하지 않는 service_id 생성 방지
- API 키가 SSE·로그·오류 응답에 나타나지 않음
- Workbench 경로에 쓰기 발생 없음

## 11. 관찰성과 로그

PoC 로그에 다음 필드를 구조화해 남긴다.

```text
request_id
hermes_run_id
session_id
model
started_at / ended_at
status
tool_name
tool_call_id
tool_duration_ms
tool_result_count
selected_service_ids
search_attempt_count
input_tokens / output_tokens
error_code
```

도구 결과 원문과 API 문서 전체는 기본 로그에 저장하지 않는다. 필요 시
service_id와 결과 개수만 기록한다. Hermes session trace는 로컬 검토용으로
내보내며 외부 업로드는 하지 않는다.

## 12. 보안 설정

- Hermes API는 `127.0.0.1:8642`에만 바인딩한다.
- `API_SERVER_KEY`를 필수로 설정한다.
- 브라우저는 Hermes에 직접 접근하지 않는다.
- CORS는 켜지 않으며 PoC 백엔드만 Hermes를 호출한다.
- Hermes 전용 profile과 상태 디렉터리를 사용한다.
- MCP subprocess 환경에는 Nara URL과 timeout만 전달한다.
- Hermes terminal·file·browser 도구를 비활성화한다.
- YOLO mode를 사용하지 않는다.
- 승인 timeout은 fail-closed로 둔다.
- Nara MCP 도구는 읽기·계획만 제공한다.

Hermes 공식 문서도 API 서버가 전체 도구 접근 권한을 가질 수 있으므로 API 키를
필수로 하고, MCP subprocess에는 명시한 환경 변수와 안전한 기본값만 전달한다고
설명한다.

## 13. 실패·복구·롤백

기능 플래그:

```text
NARA_AGENT_MODE=disabled | shadow | enabled
```

- `disabled`: 현재 `/design`만 사용
- `shadow`: 기준선 결과를 사용자에게 제공하고 Agent 결과는 평가용
- `enabled`: Agent 모드를 UI에서 선택 가능

롤백은 `NARA_AGENT_MODE=disabled`로 수행한다. 이때 Hermes Gateway와 MCP 서버를
종료해도 기존 PoC `/design`, Nara Workbench, Search, Combiner는 영향을 받지
않아야 한다.

실패별 처리:

| 실패 | 처리 |
|---|---|
| Hermes 미실행 | Agent 모드 비활성화, 기준선 사용 안내 |
| MCP 연결 실패 | 실행 중단, 검색 결과를 꾸며내지 않음 |
| Search 실패 | 전체 run 실패 |
| Detail 일부 실패 | 해당 후보 제외 후 계속 |
| Relations 실패 | 관계 미검증 경고, 조합 강행 금지 |
| Combiner timeout | 검색·선택·관계 결과 유지, 계획 실패 표시 |
| JSON 파싱 실패 | 원문 보존, `format_error` 표시 |
| SSE 연결 끊김 | run 상태 조회 후 재연결 |

## 14. 구현 순서와 예상 산출물

1. Hermes 전용 profile·64K 이상 모델·MCP 네 도구 연결
2. 실제 CLI에서 도구 호출 trace 1건 확보
3. `HermesClient`와 Runs API Mock 테스트
4. Agent run REST/SSE 프록시 구현
5. 구조화 결과 파서·근거 검증 구현
6. 프론트 Agent 모드와 호출 타임라인 구현
7. 골든 질문 20개 shadow 평가
8. 합격 기준 검토 후 `enabled` 여부 결정
9. 이후에만 승인형 memory·skill 개선 실험

최종 PoC 산출물:

- 실제 Hermes MCP 호출 trace
- baseline/agent 비교 평가 보고서
- 선택·제외 이유가 보이는 프론트 화면
- 중단·오류·재접속 가능한 실행 API
- 재현 가능한 Hermes profile 설정 예시
- Workbench 무변경 확인 결과

## 15. 구현 시작 전 확인 사항

- 사용할 Hermes 버전을 고정했는가?
- Hermes용 모델이 실제로 64K 이상 컨텍스트로 실행되는가?
- 해당 모델의 한국어 도구 호출 성공률을 확인했는가?
- Hermes API Server가 Runs·SSE·stop 기능을 광고하는가?
- Nara MCP 네 도구가 Hermes에 등록되었는가?
- `API_SERVER_KEY`가 생성되어 서버에만 저장되었는가?
- terminal·file·browser가 비활성화되었는가?
- 골든 질문과 baseline 결과가 저장되었는가?

이 항목을 모두 충족한 뒤 단계 2 구현을 시작한다.

