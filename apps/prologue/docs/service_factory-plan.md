# Prometheus 서비스 공장 계획 (B단계)

Status: proposed · 구현: 없음 · 현재 구현의 정본은 CLAUDE.md와 system-architecture.html

Prometheus가 생산한 계획 문서(`ScenarioDoc`) 하나를 받아 **실행 가능한 웹 서비스 번들**을
사람 개입 없이 만들어 내는 단계다. 그 입력 문서를 설계하는 단계는
[scenario_factory-plan.md](scenario_factory-plan.md)에 있다.

```text
[A단계] 시나리오 설계 (멀티에이전트)          [B단계] 웹 서비스 생성 (결정형 9노드)
scenario_factory-plan.md                 ->   ScenarioDoc -> 번들(app.py + static + README)
                                                          -> 사용자가 자기 서비스키로 실행
```

두 단계의 유일한 접점은 `ScenarioDoc`이다. B단계는 A단계의 대화 내용이나 LLM 원문을 읽지
않으며, LLM run을 하나도 만들지 않는다.

## 1. 목표와 비목표

목표

- 계획 문서 하나 → 실행 가능한 웹 서비스 번들 하나. 중간 질문 없음.
- 같은 입력이면 같은 번들이 나온다. 전 구간 결정형이며 검색 점수 같은 가변 값으로 재정렬하지
  않는다.
- 서비스키는 개인이 브라우저에서 직접 입력한다. 서버·생성물·zip·로그 어디에도 남지 않는다.

비목표

- 상용 배포물 생성(도커, 인증, DB, 빌드 툴체인). 생성물은 표준 라이브러리 단일 실행 번들이다.
- 실제 행정 처리 수행. 생성물은 조회 API 호출과 표시만 한다.
- 시나리오 설계·보정·재작성. 들어온 계획 문서를 그대로 실행 형태로 옮길 뿐이다.

## 2. 입력 계약: ScenarioDoc 소비 규칙

스키마 원본 정의는 [scenario_factory-plan.md](scenario_factory-plan.md)의 산출물 계약 절에 있다.
여기서는 소비 쪽 규칙만 고정한다.

- 입력은 `ScenarioDoc` 하나다. A단계 run 스냅샷의 다른 필드나 LLM 원문은 읽지 않는다.
- 처리하는 어휘는 `steps[].type` = `fetch` | `display`, `params[].source.kind` =
  `input` | `const` | `step_field`, `display.layout` = `table` | `cards` | `summary`뿐이다.
  그 밖의 값은 오류가 아니라 제거 대상이며 `excluded[]`에 사유를 남긴다.
- 참조 문서 상세는 A단계 결과에 실린 것을 쓰지 않고 search에서 다시 조회한다(N2).
- `auth`·`paging`·`format` 파라미터는 문서에 없다는 전제로 읽는다. 들어 있으면 N3가 제거한
  뒤 자기 규칙으로 재주입한다.
- 문서 순서·단계 순서는 `ScenarioDoc` 순서 고정이다.

## 3. 선행 변경: 상세 문서의 호출 기준

현재 search 상세 응답에는 엔드포인트 상대 경로(`/getCtprvnRltmMesureDnsty`)만 있고 호출
기준 URL이 없다. 공장은 이것 없이 동작할 수 없다.

- `modules/search`의 상세 계약에 `base_url`을 추가한다. 값은 swagger의
  `schemes[0]://host + basePath`로 파생한다(crawler `NaraParser.extract_base_url`과 같은 규칙).
- 두 상세 경로(`_build_flat_detail`, `DocumentBuilder.build`) 모두 같은 키를 채운다.
  근거가 없으면 빈 문자열이며, 빈 값은 N2에서 "제외 + 경고"로 처리한다.
- search 테스트에 `base_url` 파생과 빈 값 케이스를 추가한다.

이 변경은 apps가 services를 HTTP로만 쓰는 경계를 바꾸지 않는다. 필드 하나가 늘 뿐이다.

## 4. 생성 파이프라인 (고정 9노드)

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

- `step_field` 의존으로 실행 순서를 정한다(위상 정렬). 순환은 A단계 바인딩에서 이미 제거됐고
  여기서 다시 만나면 하드 실패다.
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

`api_storage/prometheus_factory/{build_id}/`에 파일을 쓰고 같은 이름의 zip을 만든다.
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

1. **생성 경로에는** 서비스키가 없다. Prometheus는 계획 문서를 만들 때 공공 API를 호출하지
   않으므로 키가 필요 없고, 미리보기 릴레이도 요청 헤더로 받은 키만 쓴다. 설정 파일·환경
   변수·시나리오·zip·로그 어디에도 남기지 않는다. 이 규칙의 목적은 **생성물에 제작자의 키가
   박힌 채 배포되는 것을 막는 것**이다. 번들 사용자는 각자 자기 키를 브라우저에서 입력한다.
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

## 7. API 계약

| 메서드 | 경로 | 동작 |
|---|---|---|
| `POST` | `/factory/builds` | `{run_id}` 또는 `{scenario}` → 번들 생성. 200 + 노드 상태 |
| `GET` | `/factory/builds/{id}` | 시나리오, 노드 상태, 제외 목록, 경고 |
| `GET` | `/factory/builds/{id}/download` | zip 첨부 응답 |
| `GET` | `/factory/builds/{id}/preview` | 생성 UI(정적) 서빙 |
| `POST` | `/factory/builds/{id}/call` | `{step_id, params}` + 키 헤더 → upstream 릴레이 |

UI에는 완료된 run 결과 패널의 시나리오 요약 카드 옆에 `웹 서비스 만들기` 버튼을 추가한다
(플로우 내보내기 옆). 카드 자체는 A단계 소관이다.

## 8. CLAUDE.md 개정 항목

구현과 같은 커밋에서 갱신한다. A단계가 바꾸는 항목은
[scenario_factory-plan.md](scenario_factory-plan.md)에 따로 있다.

| 모듈 | 추가할 문구 |
|---|---|
| search | 상세 응답은 엔드포인트 상대 경로와 함께 호출 기준 `base_url`을 제공한다. 근거가 없으면 빈 문자열이다 |
| prometheus | 번들 생성은 결정형 9노드다. LLM run을 만들지 않고 `ScenarioDoc` 하나만 입력으로 읽는다 |
| prometheus | 생성 번들과 미리보기 릴레이는 서비스키를 저장하지 않고 `127.0.0.1`에만 바인딩한다. 릴레이 대상은 빌드 시점 allowlist뿐이다 |

## 9. 단계

1. search 상세에 `base_url` 추가 + 테스트.
2. N1~N5(`factory/spec.py`).
3. N6~N8(`factory/render.py`, `factory/bundle.py`).
4. N9와 API·UI 버튼, 미리보기 릴레이(`factory/relay.py`).
5. README와 CLAUDE.md 갱신.

각 단계는 그 단계의 테스트까지 포함해야 끝난 것으로 본다. 착수 조건은 A단계 바인더와 폴백이
끝나 `ScenarioDoc`이 나오는 상태다. 폴백 시나리오만으로도 번들이 나와야 하며, 그것이 LLM
장애와 무관하게 공장이 도는지 보는 기준이다.

## 10. 테스트

- search 상세의 `base_url` 파생과 빈 값 케이스(1단계와 같은 커밋).
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

## 11. 미지원 (명시)

- OAuth·서명·POST 본문 인증을 쓰는 API. `serviceKey` 질의 파라미터 방식만 지원한다.
- `fileData`, `standard`, swagger가 없는 `openapi_old` 문서. 호출 기준이 없으면 N2에서 제외한다.
- 페이지네이션 자동 순회, 결과 저장, 예약·주기 실행. 한 단계 한 요청만 한다.
- 시나리오 보정을 위한 LLM 호출. 입력이 실행 불가면 제외·경고로 남기고 만들 수 있는 만큼만
  만든다.
- 생성 번들의 외부 노출. 로컬 실행 전용이며 그 상태로 배포하지 않는다.
