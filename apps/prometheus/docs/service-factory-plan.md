# Prometheus 서비스 공장 계획

Prometheus는 멀티에이전트로 공공 API 문서를 조합해 **새 이용 시나리오를 설계하는 공장**이다.
그 산출물인 시나리오 문서를 근거로 **실행 가능한 웹 서비스 번들**을 사람 개입 없이 만들어 낸다.

```text
[A단계] 시나리오 설계 (멀티에이전트)        [B단계] 웹 서비스 생성 (결정형 9노드)
질의 -> 문서 선택 -> 시나리오 초안            ScenarioDoc -> 번들(app.py + static + README)
     -> 결정형 바인딩 -> 결정형 검증 -> ScenarioDoc            -> 사용자가 자기 서비스키로 실행
```

두 단계의 유일한 접점은 2절의 `ScenarioDoc`이다. B단계는 A단계의 대화 내용이나 LLM 원문을
읽지 않는다.

## 1. 목표와 비목표

목표

- 질의 하나 → 근거가 검증된 시나리오 문서 하나 → 실행 가능한 웹 서비스 번들 하나. 중간 질문 없음.
- 시나리오는 "문서 열람"이 아니라 **이용 흐름**이다. 화면은 문서 목록이 아니라 단계로 구성된다.
- 서비스키는 개인이 브라우저에서 직접 입력한다. 서버·생성물·zip·로그 어디에도 남지 않는다.

비목표

- 상용 배포물 생성(도커, 인증, DB, 빌드 툴체인). 생성물은 표준 라이브러리 단일 실행 번들이다.
- 실제 행정 처리 수행. 생성물은 조회 API 호출과 표시만 한다.
- LLM 자유 텍스트를 코드 생성 근거로 직접 사용하는 것. 모든 참조는 Nara 원본으로 재검증한다.

## 2. 접점 계약: ScenarioDoc

A단계의 유일한 산출물이자 B단계의 유일한 입력이다. 모든 참조는 재조회한 상세 문서에 실재해야
한다. 실재하지 않는 참조는 3.4의 바인딩 단계에서 제거되거나 사용자 입력으로 승격된다.

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

## 3. A단계: 멀티에이전트 오케스트레이션

### 3.1 역할

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

### 3.2 run 구조

애플리케이션 run 하나가 Gateway run **최대 2개**(A1, A2)에 대응한다. 순차 실행이며 병렬로
띄우지 않는다. 각 run은 자기 도구 예산을 갖고, 예산은 지금처럼 클라이언트가 강제한다.

- 요청이 `selected_service_ids`를 지정하면 A1은 실행하지 않는다(기존 규칙).
- 요청이 `scenario: false`면 A2도 실행하지 않고 지금과 같은 문서·계획 결과만 만든다.
- A2가 실패하거나 파싱 불가면 3.5의 결정형 폴백으로 내려간다. 실행이 실패하지는 않는다.

### 3.3 A2 프롬프트 계약

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

### 3.4 A3 결정형 바인딩

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
| `auth`/`paging`/`format` 파라미터가 들어 있음 | 제거 후 N3 규칙으로 재주입 |
| `display`가 없는 `fetch` | 마지막에 `display` 단계 자동 추가 |

정정 후에도 `fetch` 단계가 0개면 폴백으로 내려간다.

### 3.5 결정형 폴백

LLM 없이도 공장이 멈추지 않아야 한다. 폴백 시나리오는 선택 문서마다 첫 GET 엔드포인트를
`fetch`하고 그 결과를 `table`로 `display`하는 문서 열람형 흐름이다. 제목은 질의를 그대로 쓰고,
`warnings`에 "시나리오 설계 없이 기본 흐름으로 생성했습니다"를 남긴다.

### 3.6 A4 검증 항목 (기존 critic에 추가)

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

### 3.7 진행 보고와 프롬프트 위치

- `AgentEvent.name`에 `scenario`를 추가하고 A2·A3·A4 진행을 이벤트로 보고한다.
- 단계 메시지가 "에이전트가 무엇을 했다"고 말할 때는 Gateway가 보고한 `tool_calls` 기록만
  근거로 삼는다(기존 규칙 유지).
- 역할별 프롬프트는 `apps/prometheus/app/prompts.py` 한 모듈에 모은다. 실행 경로가 로드를
  확인할 수 없는 skill 문서로 절차를 나누지 않는다는 규칙은 그대로다.

## 4. B단계: 웹 서비스 생성 (고정 9노드)

분기 없는 단일 파이프라인이다. 입력은 `ScenarioDoc` 하나다.

```text
N1 intake -> N2 contract -> N3 capability -> N4 wire -> N5 layout
          -> N6 render -> N7 verify -> N8 package -> N9 publish
```

| 노드 | 하는 일 | 실패 정책 |
|---|---|---|
| N1 intake | run 또는 `scenario_id`로 `ScenarioDoc` 확보, 완료 상태 확인 | 하드 (409/422) |
| N2 contract | 참조 문서 상세 재조회, 문서 자격 판정, `base_url` 확인 | 문서별 소프트, 전멸 시 하드 |
| N3 capability | 엔드포인트·파라미터 정규화, auth/paging/format 주입 | 단계별 소프트 |
| N4 wire | 단계 간 값 전달 확정(`step_field` → 실행 순서와 의존 그래프) | 소프트 |
| N5 layout | 화면 구성 확정(입력 폼, 단계 순서, 표·카드) | 하드 |
| N6 render | 번들 파일 문자열 생성 | 하드 |
| N7 verify | 생성물 자체 검사 | 하드 (번들 폐기) |
| N8 package | 디렉터리·zip 기록 | 하드 |
| N9 publish | 미리보기 등록과 응답 구성 | 하드 |

소프트 실패는 `warnings`와 `excluded[]`에 사유를 남기고 계속한다. 하드 실패는 번들을 남기지
않고 중단한다. 반쯤 만들어진 번들을 사용자에게 주지 않는다.

### N1 intake

- 입력: `{run_id}` 또는 `{scenario}`(문서 직접 전달). `run_id`면 스냅샷이 `completed`이고
  `result.scenario`가 있어야 한다.
- 출력: `Intake{scenario, source_run_id|None}`.
- 실패: 미완료 run 409, 시나리오 없음 422.

### N2 contract

- `scenario.service_ids`의 상세를 **search에서 다시 조회한다**. A단계 결과에 실린 상세를 쓰지
  않는 이유는 두 가지다. run이 오래됐을 수 있고, `base_url` 같은 계약 변경이 반영돼 있지 않다.
- 문서 자격: `base_url`이 비어 있지 않다 / GET 엔드포인트가 1개 이상이다.
- 자격 미달 문서를 참조하는 단계는 제거하고 `excluded[]`에 사유를 남긴다.

### N3 capability

파라미터 4분류(이름 소문자 기준, 공장 전용 규칙. `libs/nara_common`에 넣지 않는다):

| 분류 | 판정 | 처리 |
|---|---|---|
| auth | `servicekey`, `authkey`, `apikey`, `key` | 시나리오에서 제거된 상태. 전역 키 입력으로 주입 |
| paging | `numofrows`, `pageno`, `pagesize` | 기본값 10 / 1 주입, 화면에서 수정 가능 |
| format | `resulttype`, `_type`, `type` | `json` 고정 주입 |
| query | 나머지 | 시나리오 `source`대로 연결 |

인증 파라미터가 없는 문서도 허용한다. 그 경우 키 없이 호출된다고 화면에 표시한다.

### N4 wire

- `step_field` 의존으로 실행 순서를 정한다(위상 정렬). 순환은 A3에서 이미 제거됐고 여기서
  다시 만나면 하드 실패다.
- 앞 단계 결과가 여러 행일 때의 규칙: 기본은 **첫 행의 값**을 쓰고, 화면에서 사용자가 다른
  행을 골라 다시 실행할 수 있게 한다. 전체 행을 자동 순회하지 않는다(대량 호출 금지).

### N5 layout

- 화면 = `inputs` 폼 하나 + 실행 버튼 + 단계 순서대로의 결과 영역.
- `display.columns` 순서와 라벨은 시나리오를 따르고, 라벨은 응답 필드 `description` 우선.
- 결과 컬럼 상한 30.
- 서비스키 입력 1개(전역). 활용신청마다 키가 다른 경우를 위해 "문서별 키" 토글을 함께 둔다.
- 문서 순서·단계 순서는 `ScenarioDoc` 순서 고정. 검색 점수로 재정렬하지 않는다(재현성).

### N6 render

- 출력 파일: `app.py`, `static/index.html`, `static/app.js`, `static/styles.css`, `README.md`,
  `scenario.json`(= 검증된 `ScenarioDoc`).
- 표준 라이브러리 문자열 템플릿만 쓴다. 템플릿 엔진을 새로 들이지 않는다.

### N7 verify

생성물을 그대로 검사하는 하드 게이트다. 실패하면 파일을 남기지 않는다.

- 생성 문자열에 서비스키로 보이는 값이 없다(입력에 없으니 회귀 방지용이다).
- `app.py`의 allowlist 집합 == 시나리오가 호출하는 엔드포인트 URL 집합.
- 필수 파일이 모두 있고 `scenario.json`은 다시 직렬화해도 같다.
- `app.py`가 `127.0.0.1` 외 주소에 바인딩하지 않는다.

### N8 package

`nara_storage/prometheus_factory/{build_id}/`에 파일을 쓰고 같은 이름의 zip을 만든다.
`build_id`는 uuid, 재현성 확인용으로 `ScenarioDoc.content_hash`를 함께 남긴다.

### N9 publish

미리보기 경로를 등록하고 응답을 만든다. 응답에는 `nodes[]`, `warnings[]`, `excluded[]`,
다운로드·미리보기 링크가 들어간다.

### 노드 상태 보고

각 노드는 `FactoryNode{name, status: completed|skipped|failed, message}`를 남긴다. 모양은
기존 `StageRecord`와 같지만 이름 집합이 다르므로 타입을 재사용하지 않고 공장 전용으로 둔다.
B단계는 결정형이라 즉시 끝난다. 진행 SSE를 새로 만들지 않고 응답에 한 번에 싣는다.

## 5. 생성물의 런타임 노드

번들 화면도 고정 구성이다. 시나리오 단계 수만큼 결과 영역이 늘 뿐 구조는 바뀌지 않는다.

| 노드 | 화면 | 규칙 |
|---|---|---|
| R1 키 | 서비스키 입력, 보관 방식 선택, 삭제 | 비어 있으면 실행 버튼 비활성. 디코딩 키 안내 |
| R2 입력 | 시나리오 `inputs` 폼 | 필수 표시, `example`을 placeholder로 |
| R3 실행 | 단계 순서대로 호출 | 단계당 1회. 자동 반복·순회 없음 |
| R4 릴레이 | 로컬 프록시 `POST /call` | 키는 헤더로만, allowlist 고정, 타임아웃 적용 |
| R5 결과 | 단계별 표·카드·요약 + 원본 응답 토글 | 아래 오류 규칙 참고 |
| R6 이어실행 | 결과 행 선택 → 다음 단계 재실행 | `step_field`가 있는 단계에서만 |

오류 표시 규칙: 공공 API는 실패도 HTTP 200 본문으로 오는 경우가 많다. 릴레이는 상태 코드만
보고 성공이라 말하지 않는다. 본문에 `resultCode`/`resultMsg`(XML은 `errMsg`/`returnAuthMsg`)가
있으면 그대로 보여 주고, 없으면 성공·실패를 판정하지 않고 원본을 보여 준다. 문서에 없는
오류 규격을 추측해 만들지 않는다.

응답 파싱: `format` 파라미터가 있으면 JSON을 기본으로 요청한다. JSON이 아니면 브라우저에서
XML로 파싱해 반복 노드(`item`)를 표로 그린다. 둘 다 실패하면 원본 텍스트를 보여 준다.

## 6. 서비스키 취급 규칙

이 확장의 핵심 제약이다. 어긋나는 구현은 받지 않는다.

1. Prometheus는 서비스키를 저장하지 않는다. 설정 파일·환경 변수·시나리오·zip·로그에 없다.
2. 미리보기 릴레이는 키를 요청 헤더(`X-Nara-Service-Key`)로만 받고, 메모리에서 upstream
   요청에만 붙인 뒤 버린다. 응답·에러 메시지·서버 로그에서는 마스킹한다(`****`).
3. 생성 번들도 같다. 브라우저가 키를 보관하고(기본 `sessionStorage`, 사용자가 명시적으로
   "이 브라우저에 저장"을 켜면 `localStorage`), 로컬 프록시는 받은 요청에만 사용한다.
4. 생성 번들의 프록시는 `127.0.0.1`에만 바인딩하고 CORS를 열지 않는다. 실행을 일으키는
   표면이라 다른 출처의 페이지가 요청을 보내게 두지 않는다(crawler·refresher UI와 같은 규칙).
5. 릴레이 대상은 빌드 시점에 고정된 `base_url + endpoint path` 목록만이다. 임의 URL을
   요청 본문으로 받지 않는다. 응답 크기 상한과 타임아웃을 둔다.
6. data.go.kr은 인코딩 키와 디코딩 키를 함께 발급한다. 안내는 **디코딩 키** 입력으로
   통일하고, 릴레이는 쿼리 문자열을 만들 때 한 번만 인코딩한다(이중 인코딩은 인증 실패다).

서버 프록시가 필요한 이유: 공공 API 응답에 CORS 헤더가 없어 브라우저에서 직접 호출할 수 없다.
릴레이는 선택 기능이 아니라 번들의 최소 구성이다.

## 7. 선행 변경: 상세 문서의 호출 기준

현재 search 상세 응답에는 엔드포인트 상대 경로(`/getCtprvnRltmMesureDnsty`)만 있고 호출
기준 URL이 없다. 공장은 이것 없이 동작할 수 없다.

- `services/search`의 상세 계약에 `base_url`을 추가한다. 값은 swagger의
  `schemes[0]://host + basePath`로 파생한다(crawler `NaraParser.extract_base_url`과 같은 규칙).
- 두 상세 경로(`_build_flat_detail`, `DocumentBuilder.build`) 모두 같은 키를 채운다.
  근거가 없으면 빈 문자열이며, 빈 값은 N2에서 "제외 + 경고"로 처리한다.
- search 테스트에 `base_url` 파생과 빈 값 케이스를 추가한다.

이 변경은 apps가 services를 HTTP로만 쓰는 경계를 바꾸지 않는다. 필드 하나가 늘 뿐이다.

## 8. API 계약

| 메서드 | 경로 | 동작 |
|---|---|---|
| `POST` | `/agent/design-runs` | 기존. 요청에 `scenario: bool = true` 추가 |
| `GET` | `/agent/design-runs/{id}` | 기존 응답에 `result.scenario` 추가 |
| `POST` | `/factory/builds` | `{run_id}` 또는 `{scenario}` → 번들 생성. 200 + 노드 상태 |
| `GET` | `/factory/builds/{id}` | 시나리오, 노드 상태, 제외 목록, 경고 |
| `GET` | `/factory/builds/{id}/download` | zip 첨부 응답 |
| `GET` | `/factory/builds/{id}/preview` | 생성 UI(정적) 서빙 |
| `POST` | `/factory/builds/{id}/call` | `{step_id, params}` + 키 헤더 → upstream 릴레이 |

UI에는 완료된 run 결과 패널에 시나리오 요약 카드와 `웹 서비스 만들기` 버튼을 추가한다
(플로우 내보내기 옆).

## 9. CLAUDE.md 개정 항목

이 계획은 현재 문서화된 계약 세 가지를 바꾼다. 구현과 같은 커밋에서 갱신한다.

| 현재 문구 | 갱신 |
|---|---|
| 애플리케이션 run 하나가 Hermes Gateway run 하나에 대응한다 | 역할별 Gateway run 최대 2개(선택기·설계자)에 순차 대응한다 |
| LLM은 service_id 선택기다 | LLM 역할은 선택기와 시나리오 설계자 둘이다. 설계자 출력도 결정형 바인딩과 검증을 거친 뒤에만 결과에 들어간다 |
| 루프 지침은 `HERMES_INSTRUCTIONS_TEMPLATE` 한 곳에만 둔다 | 역할별 지침은 `app/prompts.py` 한 모듈에만 둔다 |

바뀌지 않는 것: 도구는 `search_api_docs`·`get_api_detail`만, 도구 호출 상한 유지, critic은
추가 LLM run을 만들지 않음, 실제 행정 처리 주장 금지, 문서 원본 재조회 원칙.

## 10. 단계

1. search 상세에 `base_url` 추가 + 테스트.
2. `ScenarioDoc` 스키마와 A3 바인더(`app/scenario.py`) — LLM 없이 폴백 시나리오만으로 통과.
3. A2 프롬프트(`app/prompts.py`)와 두 번째 Gateway run 연결, `scenario` 이벤트.
4. A4 시나리오 검사 6종을 critic에 추가.
5. B단계 N1~N5(`factory/spec.py`).
6. B단계 N6~N8(`factory/render.py`, `factory/bundle.py`).
7. N9와 API·UI 버튼, 미리보기 릴레이(`factory/relay.py`).
8. README와 CLAUDE.md 갱신.

각 단계는 그 단계의 테스트까지 포함해야 끝난 것으로 본다. 2단계까지만 끝나도 폴백 시나리오로
번들이 나와야 한다. 그것이 LLM 장애와 무관하게 공장이 도는지 보는 기준이다.

## 11. 테스트

- `test_scenario_bind.py` A3 정정 표의 각 행. 특히 필수 파라미터 자동 승격, 순환 제거,
  auth/paging/format 제거, 폴백 생성.
- `test_scenario_prompt.py` 축약 상세가 프롬프트 예산 안에 들어가는지, 어휘 목록이 스키마와
  일치하는지.
- `test_critic.py` 시나리오 검사 6종의 violation·pass 경로(기존 파일 확장).
- `test_factory_spec.py` 노드별 판정: 문서 자격(N2), 파라미터 4분류(N3), 위상 정렬과 순환 하드
  실패(N4), 같은 입력 → 같은 `content_hash`(N5).
- `test_factory_render.py` 필수 파일 존재, 생성물에 키·절대 경로 없음, allowlist 일치.
- `test_factory_bundle.py` N7 실패 시 파일을 남기지 않음, zip 구성.
- `test_factory_api.py` 미완료 run 409, 시나리오 없음 422, 다운로드 헤더, 응답의 `nodes[]`.
- `test_factory_relay.py` allowlist 밖 경로 차단, 키 마스킹, 상한 초과 응답 처리.

기존 규칙대로 쓰기 가능한 임시 폴더를 쓴다:

```powershell
python -m pytest -q --basetemp C:\tmp\nara-pytest
```

## 12. 미지원 (명시)

- OAuth·서명·POST 본문 인증을 쓰는 API. `serviceKey` 질의 파라미터 방식만 지원한다.
- `fileData`, `standard`, swagger가 없는 `openapi_old` 문서. 호출 기준이 없으면 제외한다.
- 페이지네이션 자동 순회, 결과 저장, 예약·주기 실행. 한 단계 한 요청만 한다.
- 쓰기·신청·제출 시나리오. 설계 단계에서 금지하고 검증 단계에서 다시 막는다.
- 생성 번들의 외부 노출. 로컬 실행 전용이며 그 상태로 배포하지 않는다.
