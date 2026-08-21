# Prometheus 계획 공장 구축 계획 (A단계)

Status: proposed · 구현: 없음 · 현재 구현의 정본은 CLAUDE.md와 system-architecture.html

Prometheus는 멀티에이전트로 공공 API 문서를 조합해 **새 이용 시나리오를 설계하는 공장**이다.
이 문서는 그 설계 단계만 다룬다. 산출물인 계획 문서(`ScenarioDoc`)를 실행 가능한 웹 서비스
번들로 바꾸는 단계는 [service_factory-plan.md](service_factory-plan.md)에 있다.

```text
[A단계] 시나리오 설계 (멀티에이전트)          [B단계] 웹 서비스 생성 (결정형 9노드)
질의 -> 문서 선택 -> 시나리오 초안       ->    service_factory-plan.md
     -> 결정형 바인딩 -> 결정형 검증
     -> ScenarioDoc
```

두 단계의 유일한 접점은 2절의 `ScenarioDoc`이다. B단계는 A단계의 대화 내용이나 LLM 원문을
읽지 않는다.

## 1. 목표와 비목표

목표

- 질의 하나 → 근거가 검증된 계획 문서 하나. 중간 질문 없음.
- 시나리오는 "문서 열람"이 아니라 **이용 흐름**이다. 결과는 문서 목록이 아니라 단계로 구성된다.
- LLM이 멈춰도 공장은 멈추지 않는다. 설계가 실패하면 결정형 폴백으로 문서 하나가 반드시 나온다.

비목표

- 실제 행정 처리 시나리오 설계. 조회와 표시 흐름만 만든다.
- LLM 자유 텍스트를 산출물 근거로 직접 사용하는 것. 모든 참조는 Nara 원본으로 재검증한다.
- 번들 생성·서비스키 취급·화면 렌더링. B단계 소관이다.

## 2. 산출물 계약: ScenarioDoc

A단계의 유일한 산출물이자 B단계의 유일한 입력이다. 여기가 이 스키마의 원본 정의이며 B단계
문서는 소비 규칙만 갖는다. 모든 참조는 재조회한 상세 문서에 실재해야 한다. 실재하지 않는
참조는 6절의 바인딩 단계에서 제거되거나 사용자 입력으로 승격된다.

```jsonc
{
  "scenario_id": "sc_9f2c...",
  "title": "동네 대기질 알림 확인",
  "summary": "지역을 고르면 실시간 대기오염 수치와 측정소 위치를 함께 본다.",
  "user_story": "천식 환자 보호자가 외출 전 동네 미세먼지를 확인한다.",
  "service_ids": ["openapi_new:15000001", "openapi_new:15000581"],
  "inputs": [
    {"key": "region", "label": "시도", "type": "string", "required": true, "example": "서울"}
  ],
  "steps": [
    {"id": "s1", "type": "fetch",
     "service_id": "openapi_new:15000001",
     "endpoint_id": "GET /getCtprvnRltmMesureDnsty",
     "params": [
       {"name": "sidoName", "source": {"kind": "input", "key": "region"}},
       {"name": "numOfRows", "source": {"kind": "const", "value": "10"}}
     ],
     "output_fields": ["stationName", "pm10Value", "pm25Value", "dataTime"]},
    {"id": "s2", "type": "fetch",
     "service_id": "openapi_new:15000581",
     "endpoint_id": "GET /getMsrstnList",
     "params": [
       {"name": "stationName", "source": {"kind": "step_field", "step": "s1", "field": "stationName"}}
     ],
     "output_fields": ["addr", "dmX", "dmY"]},
    {"id": "s3", "type": "display", "from": "s1", "layout": "table",
     "columns": ["stationName", "pm10Value", "pm25Value", "dataTime"],
     "caption": "선택한 시도의 실시간 측정값"}
  ],
  "evidence": [
    {"claim": "sidoName으로 시도 단위 조회가 가능하다",
     "service_id": "openapi_new:15000001", "ref": "GET /getCtprvnRltmMesureDnsty:sidoName"}
  ],
  "content_hash": "sha256:...",
  "warnings": []
}
```

어휘를 좁게 고정한다. 늘리려면 계획을 먼저 고친다.

- `steps[].type`: `fetch` | `display` 두 가지뿐이다. 문서 간 연결은 별도 단계가 아니라
  `params[].source.kind = "step_field"`로 표현한다. 노드 종류를 늘리지 않는 편이 검증이 쉽다.
- `params[].source.kind`: `input` | `const` | `step_field`.
- `display.layout`: `table` | `cards` | `summary`.
- `auth`·`paging`·`format` 파라미터는 ScenarioDoc에 **넣지 않는다**. B단계 N3 규칙이 채운다.
  LLM이 `serviceKey` 값을 지어내는 경로를 아예 없앤다.

## 3. 역할

| 역할 | 구현 | 도구 예산 | 산출 |
|---|---|---|---|
| A1 선택기 | Hermes run (기존 프롬프트 유지) | 4회 (검색 1 + 상세 3) | `service_id` 최대 3개 |
| A2 설계자 | Hermes run (신규 프롬프트) | 0회 | 시나리오 초안 JSON |
| A3 바인더 | 결정형 코드 | - | 실행 가능한 `ScenarioDoc` |
| A4 검증자 | 결정형 코드(기존 critic 확장) | - | 판정과 findings |

A2에 도구를 주지 않는 이유: 선택된 문서의 상세는 Orchestrator가 이미 갖고 있다. 프롬프트에
축약해 넣어 주면 도구 왕복이 필요 없고, 호출당 이전 결과를 다시 실어 보내는 토큰 비용도 없다.

A3·A4는 LLM run을 만들지 않는다. 결과 재검증을 위해 추가 run을 만들지 않는다는 기존 규칙을
그대로 지킨다.

## 4. run 구조

애플리케이션 run 하나가 Gateway run **최대 2개**(A1, A2)에 대응한다. 순차 실행이며 병렬로
띄우지 않는다. 각 run은 자기 도구 예산을 갖고, 예산은 지금처럼 클라이언트가 강제한다.

- 요청이 `selected_service_ids`를 지정하면 A1은 실행하지 않는다(기존 규칙).
- 요청이 `scenario: false`면 A2도 실행하지 않고 지금과 같은 문서·계획 결과만 만든다.
- A2가 실패하거나 파싱 불가면 7절의 결정형 폴백으로 내려간다. 실행이 실패하지는 않는다.

## 5. A2 프롬프트 계약

- 입력: 질의, 선택 문서별 축약 상세(이름, 설명, 기관, 엔드포인트 목록, 요청 필드 이름·필수 여부,
  응답 필드 이름 상한 30), 그리고 2절 스키마와 어휘 목록.
- 지시 요지:
  - 주어진 문서·엔드포인트·필드 이름 밖의 것을 쓰지 않는다.
  - `serviceKey`·페이징·포맷 파라미터는 쓰지 않는다(시스템이 채운다).
  - 단계는 최대 6개, `fetch`는 최대 4개.
  - 실제 행정 처리·제출·통보를 하는 시나리오를 쓰지 않는다. 조회와 표시만 설계한다.
  - JSON 객체 하나만 출력한다.
- Orchestrator는 응답에서 첫 JSON 객체를 추출한다. 형식이 어긋나도 실패로 처리하지 않고
  폴백으로 내려간다. 즉 형식은 **선호**이지 의존이 아니다.

## 6. A3 결정형 바인딩

무지성 자동화의 실체가 여기다. LLM이 대충 써도 실행 가능한 문서로 정정한다.

| 상황 | 처리 |
|---|---|
| `service_id`가 선택 목록 밖 | 해당 단계 제거 + 경고 |
| `endpoint_id`가 상세에 없음 | 이름 정규화(`METHOD /path`) 후 재대조, 그래도 없으면 단계 제거 |
| GET이 아닌 엔드포인트 | 단계 제거 + 경고 (본문 규격 근거가 문서에 없다) |
| 파라미터가 상세에 없음 | 제거 |
| 필수 파라미터에 `source`가 없음 | `inputs`에 자동 추가하고 `input`으로 연결 |
| `step_field`가 앞 단계 `output_fields`에 없음 | 그 필드를 앞 단계 출력에 추가, 응답 필드에도 없으면 `input`으로 승격 |
| `step_field`가 뒤 단계·자기 자신 참조 | 제거 (순환 금지) |
| `output_fields`·`columns`가 응답 필드에 없음 | 제거, 남는 것이 없으면 문서 순서 상위 5개로 채움 |
| `auth`/`paging`/`format` 파라미터가 들어 있음 | 제거 후 B단계 N3 규칙으로 재주입 |
| `display`가 없는 `fetch` | 마지막에 `display` 단계 자동 추가 |

정정 후에도 `fetch` 단계가 0개면 폴백으로 내려간다.

## 7. 결정형 폴백

LLM 없이도 공장이 멈추지 않아야 한다. 폴백 시나리오는 선택 문서마다 첫 GET 엔드포인트를
`fetch`하고 그 결과를 `table`로 `display`하는 문서 열람형 흐름이다. 제목은 질의를 그대로 쓰고,
`warnings`에 "시나리오 설계 없이 기본 흐름으로 생성했습니다"를 남긴다.

## 8. A4 검증 항목 (기존 critic에 추가)

기존 검사(`selected-in-search`, `selected-subset-of-details`, `relations-verified` 등)는 그대로
두고 시나리오 검사를 추가한다. 심각도 체계와 판정 규칙은 기존 `compute_verdict`를 따른다.

| check | violation 조건 |
|---|---|
| `scenario-refs-exist` | 단계의 `service_id`/`endpoint_id`/필드가 상세에 없음 |
| `scenario-required-bound` | 필수 파라미터에 `source`가 없음 |
| `scenario-acyclic` | `step_field`가 뒤 단계나 자신을 참조 |
| `scenario-has-output` | `display` 단계가 없거나 컬럼이 비어 있음 |
| `scenario-no-action-claim` | `title`/`summary`/`user_story`에 신청·제출·발급·통보 등 처리 주장 |
| `scenario-agency-grounded` | 문서에 없는 기관명을 본문에서 주장 |

`scenario-refs-exist`와 `scenario-no-action-claim`은 모순(contradiction) 계열로 분류한다.
바인딩을 거쳤으므로 평시에는 통과가 기본이며, 이 검사들은 회귀 감지용이다.

## 9. 진행 보고와 프롬프트 위치

- `AgentEvent.name`에 `scenario`를 추가하고 A2·A3·A4 진행을 이벤트로 보고한다.
- 단계 메시지가 "에이전트가 무엇을 했다"고 말할 때는 Gateway가 보고한 `tool_calls` 기록만
  근거로 삼는다(기존 규칙 유지).
- 역할별 프롬프트는 `apps/prologue/app/prompts.py` 한 모듈에 모은다. 실행 경로가 로드를
  확인할 수 없는 skill 문서로 절차를 나누지 않는다는 규칙은 그대로다.

## 10. API 계약

| 메서드 | 경로 | 동작 |
|---|---|---|
| `POST` | `/agent/design-runs` | 기존. 요청에 `scenario: bool = true` 추가 |
| `GET` | `/agent/design-runs/{id}` | 기존 응답에 `result.scenario` 추가 |

UI에는 완료된 run 결과 패널에 시나리오 요약 카드를 추가한다. 그 카드에서 B단계를 부르는
버튼은 [service_factory-plan.md](service_factory-plan.md) 소관이다.

## 11. CLAUDE.md 개정 항목

이 계획은 현재 문서화된 계약 세 가지를 바꾼다. 구현과 같은 커밋에서 갱신한다.

| 현재 문구 | 갱신 |
|---|---|
| 애플리케이션 run 하나가 Hermes Gateway run 하나에 대응한다 | 역할별 Gateway run 최대 2개(선택기·설계자)에 순차 대응한다 |
| LLM은 service_id 선택기다 | LLM 역할은 선택기와 시나리오 설계자 둘이다. 설계자 출력도 결정형 바인딩과 검증을 거친 뒤에만 결과에 들어간다 |
| 루프 지침은 `HERMES_INSTRUCTIONS_TEMPLATE` 한 곳에만 둔다 | 역할별 지침은 `app/prompts.py` 한 모듈에만 둔다 |

바뀌지 않는 것: 도구는 `search_api_docs`·`get_api_detail`만, 도구 호출 상한 유지, critic은
추가 LLM run을 만들지 않음, 실제 행정 처리 주장 금지, 문서 원본 재조회 원칙.

## 12. 단계

1. `ScenarioDoc` 스키마와 A3 바인더(`app/scenario.py`) — LLM 없이 폴백 시나리오만으로 통과.
2. A2 프롬프트(`app/prompts.py`)와 두 번째 Gateway run 연결, `scenario` 이벤트.
3. A4 시나리오 검사 6종을 critic에 추가.
4. `design-runs` 응답과 UI 시나리오 요약 카드, README와 CLAUDE.md 갱신.

각 단계는 그 단계의 테스트까지 포함해야 끝난 것으로 본다. 1단계만 끝나도 폴백 시나리오로
`ScenarioDoc`이 나와야 한다. 그것이 LLM 장애와 무관하게 공장이 도는지 보는 기준이며,
B단계 착수 조건이기도 하다.

## 13. 테스트

- `test_scenario_bind.py` A3 정정 표의 각 행. 특히 필수 파라미터 자동 승격, 순환 제거,
  auth/paging/format 제거, 폴백 생성.
- `test_scenario_prompt.py` 축약 상세가 프롬프트 예산 안에 들어가는지, 어휘 목록이 스키마와
  일치하는지.
- `test_critic.py` 시나리오 검사 6종의 violation·pass 경로(기존 파일 확장).

기존 규칙대로 쓰기 가능한 임시 폴더를 쓴다:

```powershell
python -m pytest -q --basetemp C:\tmp\nara-pytest
```

## 14. 미지원 (명시)

- 쓰기·신청·제출 시나리오. A2 프롬프트에서 금지하고 A4 검증에서 다시 막는다.
- 두 개를 넘는 Gateway run, 병렬 run, 검증용 추가 run.
- 2절 어휘 밖의 단계 종류·`source.kind`·`layout`. 늘리려면 이 계획을 먼저 고친다.
- 호출 기준이 없는 문서를 A단계에서 걸러내는 일. 그 판정은 B단계 N2가 한다.
