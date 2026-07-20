# 계획 검증 에이전트 (Plan Critic) 구현 계획

- 문서 상태: 구현 승인 전 계획
- 작성 기준일: 2026-07-20
- 선행 문서: [`agent_expansion_exploration.md`](agent_expansion_exploration.md) 후보 A,
  [`hermes_tool_loop_plan.md`](hermes_tool_loop_plan.md)
- 보호 대상: 기존 `/design` 기준선과 `nara_workbench(API통합워크벤치)` 변경 금지

## 1. 결론

에이전트 설계 run이 완료된 뒤, 최종 결과를 **읽기 전용으로 재검증하는 검증
단계(critic)** 를 추가한다. 검증은 두 층으로 나눈다.

1. **결정형 검증기 (항상 실행)** — Python 코드가 결과 계약을 기계적으로
   재검사한다. 외부 모델 없이 동작하며 여기서 잡히는 위반이 가장 치명적이다.
2. **Hermes 검증 프로브 (선택 실행)** — 별도 프로필 `nara-critic`이
   조회 도구만으로 의미적 검증(제외 이유의 모순, 계획 본문의 필드 지어내기)을
   수행한다. 기존 `run_hermes_tool_probe` 패턴을 재사용한다.

검증기는 결과를 **수정하지 않는다**. verdict와 findings만 첨부하고, 문제가
있어도 run 상태는 `completed`로 유지한 채 UI 경고 배지로 표시한다. 비목표인
"여러 Agent 병렬 운영"과 충돌하지 않도록 메인 run 종료 후 **순차 1회**만
실행한다.

## 2. 검증 항목

### 2.1 결정형 검증기 (`app/critic.py`)

현재 `DesignResponse` 계약(`app/schemas.py`) 기준. 향후
`hermes_tool_loop_plan.md` §7.2 계약이 도입되면 같은 검사를 그 계약으로
확장한다.

| 검사 ID | 내용 | 위반 시 verdict 기여 |
|---|---|---|
| `selected-subset-of-details` | `selected_service_ids`의 모든 ID가 `details`에서 성공 조회된 문서와 1:1 대응하는가 | `evidence_gap` |
| `selected-in-search` | 선택 ID가 `search.results` 또는 요청의 `selected_service_ids`에 실제 존재하는가 (임의 ID 생성 금지) | `contradiction` |
| `relations-verified` | `relations.relations`의 각 항목이 `GET /relations` 재호출 결과의 부분집합인가 (`id` 단위 비교) | `contradiction` |
| `relations-not-skipped` | 문서 2개 이상인데 relations 단계가 `skipped`이면 경고 | `evidence_gap` |
| `plan-missing-reported` | 조합기 `plan.missing`이 있으면 `warnings`에 반영되어 있는가 | `evidence_gap` |
| `contract-limits` | 선택 3개 이하·중복 없음·`stages` 순서(search→detail→relations→compose) 유지 | `contradiction` |

`relations-verified`는 기존 `NaraClient.relations()`를 1회 재호출한다.
재호출이 실패하면 위반이 아니라 `unverified` finding으로 남긴다 (지어내지
않기 원칙: 검증 불가와 위반을 구분한다).

### 2.2 Hermes 검증 프로브 (선택)

프로필 `nara-critic`으로 다음만 노출한다.

| MCP 도구 | 용도 | 호출 제한 |
|---|---|---|
| `get_api_detail` | 선택 문서 재확인 | 최대 3회 |
| `derive_relations` | 관계 근거 재확인 | 최대 1회 |

`search_api_docs`와 `compose_service_plan`은 노출하지 않는다. 검증자는
새 후보를 찾거나 계획을 다시 만들면 안 되기 때문이다.

의미 검증 항목:

- 계획 본문이 상세 문서에 없는 입력·출력 필드를 언급하는가
- 계획 본문이 실제 실행·제출을 완료했다고 주장하는가
- (§7.2 계약 도입 후) `rejected_apis`의 제외 이유가 상세 문서와 모순되는가

프로브 출력은 아래 `CriticReport` JSON으로 강제하고, 파싱 실패 시 원문을
보존하되 `format_error` finding으로 기록한다 (tool loop plan §7.2와 동일한
fail-soft 규칙).

## 3. 결과 계약

`app/schemas.py`에 추가한다.

```python
class CriticFinding(BaseModel):
    check: str                      # 검사 ID (2.1/2.2 표의 값)
    severity: Literal["info", "unverified", "violation"]
    target: str                     # service_id, relation id 등 대상 식별자
    message: str
    evidence: list[str] = []        # 판단 근거 (도구 응답에서 발췌)

class CriticReport(BaseModel):
    verdict: Literal["pass", "evidence_gap", "contradiction", "skipped", "failed"]
    findings: list[CriticFinding] = []
    deterministic: bool             # 결정형 검증 수행 여부
    hermes: dict[str, Any] = {}     # 프로브 상태 (기존 probe 반환 형식)
```

verdict 계산 규칙:

- `violation` finding 중 모순 계열이 있으면 `contradiction`
- 아니고 `violation`·`unverified`가 있으면 `evidence_gap`
- finding이 `info`뿐이면 `pass`
- 검증 자체가 꺼져 있으면 `skipped`, 검증기 예외면 `failed`

`AgentRunResponse`에 `critic: CriticReport | None = None`을 추가하고,
`StageRecord.name`·`AgentEvent.name` Literal에 `"critic"`을 추가한다.
`DesignResponse`와 기준선 `/design`은 변경하지 않는다.

## 4. 실행 흐름 통합

`AgentRunManager._execute`(`app/agent.py`)에서 `_run_loop` 성공 후:

```text
run.result 확보
  ↓
critic 단계 시작 이벤트 (name="critic", status="running")
  ↓
결정형 검증기 실행 (NaraClient 재사용, relations 재호출 1회)
  ↓
NARA_CRITIC_MODE=full 이면 Hermes 프로브 실행
  ↓
CriticReport 산출 → run.critic 저장
  ↓
critic 완료 이벤트 (verdict를 message에 포함)
  ↓
run.status = completed  (verdict와 무관)
```

실패 처리 (fail-soft):

| 실패 | 처리 |
|---|---|
| 검증기 내부 예외 | `verdict=failed`, run은 `completed` 유지, warning 추가 |
| relations 재호출 실패 | 해당 검사만 `unverified`, 나머지 검사 계속 |
| Hermes 프로브 timeout·미설치 | 결정형 결과만으로 report 확정, `hermes.status` 기록 |
| 검증 소요 초과 (`NARA_CRITIC_TIMEOUT`) | 진행된 finding까지로 `failed` 확정 |

검증 단계는 사용자 중단(`stop`)의 취소 범위에 포함된다.

## 5. 설정

`app/config.py`의 `HERMES_ENV_DEFAULTS` 패턴을 따른다.

| 환경 변수 | 기본값 | 의미 |
|---|---|---|
| `NARA_CRITIC_MODE` | `deterministic` | `disabled` \| `deterministic` \| `full` |
| `NARA_CRITIC_TIMEOUT` | `60` | 검증 단계 전체 제한 시간(초) |
| `NARA_HERMES_CRITIC_PROFILE` | `nara-critic` | 프로브용 Hermes 프로필 |

롤백은 `NARA_CRITIC_MODE=disabled`로 수행한다. 이때 run 응답의 `critic`은
`verdict=skipped`가 아니라 `None`으로 두어 기존 소비자와 호환을 유지한다.

## 6. UI 반영

`static/` 에이전트 모드 결과 영역에 배지 하나만 추가한다.

- `pass`: 초록 "근거 검증 통과"
- `evidence_gap`: 노랑 "근거 부족 N건" — findings 목록 펼침
- `contradiction`: 빨강 "근거 모순 N건" — findings 목록 펼침
- `failed`: 회색 "검증 실패 (결과는 유효)"

배지 클릭 시 finding의 `check`·`target`·`message`·`evidence`를 그대로
보여준다. 결과 본문을 숨기거나 바꾸지 않는다.

## 7. 구현 단계

### 단계 1 — 결정형 검증기

- `app/critic.py`: `run_deterministic_checks(result, client) -> list[CriticFinding]`
- `app/schemas.py`: `CriticFinding`, `CriticReport`, Literal 확장
- `AgentRunManager` 통합과 critic 이벤트 발행

완료 조건: 골든 질문 실행 시 `critic.verdict`가 응답에 포함되고, 기존
테스트가 모두 통과하며 `/design` 응답은 바이트 단위로 동일하다.

### 단계 2 — Hermes 프로브 층

- `nara-critic` 프로필 생성, `tools.include`로 두 도구만 화이트리스트
- `run_hermes_tool_probe` 재사용 또는 검증 전용 프롬프트 변형 추가
- `NARA_CRITIC_MODE=full` 경로와 report 병합

완료 조건: 프로브 trace에서 `get_api_detail`·`derive_relations` 외 도구
호출이 0건이다.

### 단계 3 — UI 배지와 평가 연동

- 배지·finding 목록 렌더링
- shadow 평가(tool loop plan 단계 5) 보고서에 verdict 분포 컬럼 추가

완료 조건: 골든셋 실행 보고서에 `pass / evidence_gap / contradiction` 비율이
집계된다. 이 지표가 "근거 없는 관계 주장률 0%" 합격 기준의 자동 측정값이
된다.

## 8. 테스트 계획

- 각 검사 ID별 위반 fixture와 통과 fixture 단위 테스트
- relations 재호출 실패 시 `unverified` 처리 테스트
- 검증기 예외 시 run이 `completed`로 유지되는 fail-soft 테스트
- SSE 스트림에 critic 이벤트가 순서대로 나타나는지 테스트
- `NARA_CRITIC_MODE=disabled`에서 `critic=None`과 이벤트 미발행 테스트
- 프로브 출력 JSON 파싱 실패 시 `format_error` finding 테스트
- 검증 결과에 API 키·전체 문서 원문이 포함되지 않는지 테스트

## 9. 비목표

- 결과 자동 수정, 재실행, 재검색
- 메인 run과의 병렬 실행
- 기준선 `/design`에 검증 단계 추가
- 검증 결과의 메모리·스킬 자동 반영 (단계 6 승인형 절차를 따른다)
