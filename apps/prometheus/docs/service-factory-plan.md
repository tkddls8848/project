# Prometheus 서비스 공장 계획

Prometheus의 design run 결과(선택 문서 + 관계 + 계획 초안)를 입력으로 받아, **바로 실행되는
웹 서비스 번들**을 사람 개입 없이 한 번에 만들어 내는 확장이다. 생성물은 공공 API 서비스키를
포함하지 않으며, 사용하는 사람이 자기 키를 직접 넣어 자기 컴퓨터에서 돌린다.

## 1. 목표와 비목표

목표

- 완료된 design run 하나 → 실행 가능한 웹 서비스 번들 하나. 중간 질문 없음.
- 생성 근거는 Nara 상세 문서(`endpoints`, `request_fields`, `response_fields`, 관계)뿐이다.
- 서비스키는 개인이 브라우저에서 직접 입력한다. 서버·생성물·zip·로그 어디에도 남지 않는다.

비목표

- 상용 배포물 생성(도커, 인증, DB, 빌드 툴체인). 생성물은 표준 라이브러리 단일 실행 번들이다.
- 실제 행정 처리 수행. 생성물은 조회 API 호출과 표시만 한다.
- 계획 초안(LLM 자유 텍스트)을 코드 생성 근거로 사용하는 것.

## 2. "무지성"의 정의

무지성 = **사람 개입 없이 한 번에**이지, 근거 없는 생성이 아니다. 그러려면 실행 시점에
결정할 것이 남아 있으면 안 된다. 그래서 워크플로우는 6절에 노드 단위로 미리 고정하고,
각 노드는 입력·출력·판정 규칙·실패 정책을 갖는다. 노드가 판정하지 못하는 입력은
"제외하고 경고"이지 "적당히 추측"이 아니다.

- 공장은 새 LLM run을 만들지 않는다(critic이 재검증 run을 만들지 않는 것과 같은 규칙).
- LLM 산출물(`plan.suggestion`)의 용도: 생성 서비스의 제목·설명 문구와 README 배경뿐.
  요청 파라미터나 필드 이름을 여기서 읽지 않는다.
- 같은 입력이면 같은 산출물이 나온다. 순서는 모델 순위가 아니라 검증된 문서 순서로 고정한다.

## 3. 선행 변경: 상세 문서의 호출 기준

현재 search 상세 응답에는 엔드포인트 상대 경로(`/getCtprvnRltmMesureDnsty`)만 있고 호출
기준 URL이 없다. 공장은 이것 없이 동작할 수 없다.

- `services/search`의 상세 계약에 `base_url`을 추가한다. 값은 swagger의
  `schemes[0]://host + basePath`로 파생한다(crawler `NaraParser.extract_base_url`과 같은 규칙).
- 두 상세 경로(`_build_flat_detail`, `DocumentBuilder.build`) 모두 같은 키를 채운다.
  근거가 없으면 빈 문자열이며, 빈 값은 공장에서 "제외 + 경고"로 처리한다.
- search 테스트에 `base_url` 파생과 빈 값 케이스를 추가한다.

이 변경은 apps가 services를 HTTP로만 쓰는 경계를 바꾸지 않는다. 필드 하나가 늘 뿐이다.

## 4. 구성

```text
Prometheus :8020
  POST /factory/builds        design run -> 번들 생성 (결정형 9노드)
  GET  /factory/builds/{id}   스펙·노드 상태·경고 조회
  GET  /factory/builds/{id}/download   zip
  GET  /factory/builds/{id}/preview    생성 UI 미리보기
  POST /factory/builds/{id}/call       미리보기 전용 릴레이 (키는 헤더로만)

생성 번들 (사용자 컴퓨터에서 단독 실행)
  app.py        표준 라이브러리 HTTP 서버 + 고정 allowlist 릴레이, 127.0.0.1 바인딩
  static/       index.html, app.js, styles.css
  README.md     실행 방법, 서비스키 발급·입력 안내
  spec.json     생성 근거(service_id, endpoint, 필드, 연결) — 키 없음
```

새 파일은 `apps/prometheus/app/factory/`에 둔다.

- `spec.py` N1~N5 (입력 → 빌드 스펙)
- `render.py` N6 (스펙 → 번들 파일 문자열)
- `bundle.py` N7~N8 (검사, 파일 쓰기, zip)
- `relay.py` 미리보기 릴레이(allowlist 검사, 키 마스킹)

산출물은 저장소 루트 규칙에 따라 `nara_storage/prometheus_factory/{build_id}/`에 둔다.

## 5. 서비스키 취급 규칙

이 확장의 핵심 제약이다. 어긋나는 구현은 받지 않는다.

1. Prometheus는 서비스키를 저장하지 않는다. 설정 파일·환경 변수·빌드 스펙·zip·로그에 없다.
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
그래서 릴레이는 선택 기능이 아니라 번들의 최소 구성이다.

## 6. 생성 워크플로우 (고정 9노드)

분기 없는 단일 파이프라인이다. 앞 노드의 출력이 다음 노드의 유일한 입력이며, 노드를 건너뛰거나
순서를 바꾸는 옵션은 두지 않는다.

```text
N1 intake -> N2 contract -> N3 capability -> N4 link -> N5 layout
          -> N6 render -> N7 verify -> N8 package -> N9 publish
```

| 노드 | 하는 일 | 실패 정책 |
|---|---|---|
| N1 intake | 입력 확보와 자격 확인 | 하드 (409/422) |
| N2 contract | 문서 상세 재조회와 문서 자격 판정 | 문서별 소프트, 전멸 시 하드 |
| N3 capability | 엔드포인트·파라미터 정규화 | 엔드포인트별 소프트, 전멸 시 문서 제외 |
| N4 link | 문서 간 연결 근거 확정 | 소프트 (skipped 가능) |
| N5 layout | 화면 구성 확정 | 하드 (여기서 실패하면 스펙 결함) |
| N6 render | 번들 파일 문자열 생성 | 하드 |
| N7 verify | 생성물 자체 검사 | 하드 (번들 폐기) |
| N8 package | 디렉터리·zip 기록 | 하드 |
| N9 publish | 미리보기 등록과 응답 구성 | 하드 |

소프트 실패는 `warnings`와 `excluded[]`에 사유를 남기고 파이프라인을 계속한다. 하드 실패는
번들을 남기지 않고 중단한다. 반쯤 만들어진 번들을 사용자에게 주지 않는다.

### N1 intake

- 입력: `{run_id}` 또는 `{selected_service_ids, query}`.
- 판정: `run_id`면 스냅샷이 `completed`인지 확인하고 `result`에서 `selected_service_ids`,
  `relations`, `plan`, `query`를 읽는다. 직접 지정이면 run 없이 진행한다(에이전트가
  `selected_service_ids` 요청에 run을 만들지 않는 규칙과 같다).
- 출력: `Intake{query, service_ids(≤3), plan_text|None, relations|None, source_run_id|None}`.
- 실패: 미완료 run은 409, 문서 0건은 422.

### N2 contract

- 입력: `Intake.service_ids`.
- 하는 일: 각 문서 상세를 **search에서 다시 조회한다**. run 결과에 실린 `details`를 쓰지
  않는 이유는 두 가지다. run이 오래됐을 수 있고, `base_url` 같은 계약 변경이 반영돼 있지 않다.
- 문서 자격: `base_url`이 비어 있지 않다 / `endpoints`가 1개 이상이다 / 그중 GET이 1개 이상이다.
- 출력: `DocContract[]{service_id, name, description, agency, base_url, endpoints, request_fields,
  response_fields, source_url}`, `excluded[]{service_id, reason}`.
- 실패: 문서별 제외는 경고. 남은 문서가 0건이면 422.

### N3 capability

- 입력: `DocContract[]`.
- 파라미터 4분류 (이름 소문자 기준, 공장 전용 규칙. `libs/nara_common`에 넣지 않는다):

  | 분류 | 판정 | 처리 |
  |---|---|---|
  | auth | `servicekey`, `authkey`, `apikey`, `key` | 폼에서 제외, 전역 키 입력으로 대체 |
  | paging | `numofrows`, `pageno`, `pagesize` | 기본값 10 / 1 노출, 사용자가 수정 가능 |
  | format | `resulttype`, `_type`, `type` | 기본값 `json` 고정 |
  | query | 나머지 전부 | 폼 입력. `required`면 필수 표시 |

- 엔드포인트 제외: `method != GET`. 본문 규격 근거가 문서에 없으므로 만들지 않는다.
- 인증 파라미터가 없는 문서도 허용한다. 그 경우 키 없이 호출된다고 화면에 표시한다.
- 출력: `EndpointPlan[]{endpoint_id, method, url, auth_param|None, paging, format, inputs[]}`.
- 실패: 한 문서의 엔드포인트가 전부 제외되면 그 문서를 N2의 `excluded[]`로 승격한다.

### N4 link

- 입력: `Intake.relations`, 포함 문서 목록.
- 하는 일: `relations.relations[]` 중 `source`와 `target`이 모두 포함 문서인 항목만 남기고,
  `evidence`에 적힌 공통 필드명을 읽어 `LinkPlan{from, to, field, evidence}`를 만든다.
- 이름이 비슷하다는 이유로 새 연결을 만들지 않는다. 근거는 relations 응답뿐이다.
- 문서가 1개거나 relations가 없으면 `skipped`. 하드 실패가 아니다.

### N5 layout

- 입력: `DocContract[]`, `EndpointPlan[]`, `LinkPlan[]`, `plan_text`.
- 확정 규칙:
  - 문서 순서 = N2를 통과한 순서(검증 순서). 검색 점수로 재정렬하지 않는다 — 재현성 때문이다.
  - 탭 1개 = 문서 1개, 폼 1개 = 엔드포인트 1개.
  - 결과 테이블 컬럼 = `response_fields` 문서 순서, 상한 30. 라벨은 `description`, 없으면 `name`.
  - 전역 서비스키 입력 1개. 활용신청마다 키를 따로 쓰는 경우를 위해 "문서별 키 사용" 토글을
    함께 둔다(기본 꺼짐).
  - 서비스 제목·소개 문구는 `plan_text`에서 가져오되, 없으면 `query`를 그대로 쓴다.
- 출력: `BuildSpec` (spec.json으로 그대로 직렬화되는 최종 구조).

### N6 render

- 입력: `BuildSpec`.
- 출력 파일: `app.py`, `static/index.html`, `static/app.js`, `static/styles.css`, `README.md`,
  `spec.json`.
- 표준 라이브러리 문자열 템플릿만 쓴다. 템플릿 엔진을 새로 들이지 않는다.

### N7 verify

생성물을 그대로 검사하는 하드 게이트다. 실패하면 파일을 남기지 않는다.

- 생성 문자열에 서비스키로 보이는 값이 없다(입력에 없으니 회귀 방지용이다).
- `app.py`의 allowlist 집합 == `BuildSpec`의 엔드포인트 URL 집합.
- 필수 파일이 모두 있고 `spec.json`은 다시 직렬화해도 같다.
- `app.py`가 `127.0.0.1` 외 주소에 바인딩하지 않는다.

### N8 package

- `nara_storage/prometheus_factory/{build_id}/`에 파일을 쓰고 같은 이름의 zip을 만든다.
- `build_id`는 uuid(기존 run 방식). 재현성 확인용으로 `BuildSpec.content_hash`를 함께 남긴다.

### N9 publish

- 미리보기 경로를 등록하고 응답을 만든다. 응답에는 `nodes[]`, `warnings[]`, `excluded[]`,
  다운로드·미리보기 링크가 들어간다.

### 노드 상태 보고

각 노드는 `FactoryNode{name, status: completed|skipped|failed, message}`를 남긴다. 모양은
기존 `StageRecord`와 같지만 이름 집합이 다르므로 타입을 재사용하지 않고 공장 전용으로 둔다.
생성은 결정형이라 즉시 끝나므로 진행 SSE를 새로 만들지 않는다. 노드 상태는 응답에 한 번에 싣는다.

## 7. 생성물의 런타임 노드

번들 화면도 고정 구성이다. 문서 수만큼 탭이 늘 뿐 구조는 바뀌지 않는다.

| 노드 | 화면 | 규칙 |
|---|---|---|
| R1 키 | 서비스키 입력, 보관 방식 선택, 삭제 | 비어 있으면 조회 버튼 비활성. 디코딩 키 안내 |
| R2 탭 | 문서 선택 | 순서는 `BuildSpec` 순서 고정 |
| R3 폼 | 엔드포인트 입력 | 필수 표시, paging·format 기본값 노출 |
| R4 호출 | 로컬 프록시 `POST /call` | 키는 헤더로만, 요청당 1회, 타임아웃 적용 |
| R5 결과 | 표 + 원본 응답 토글 | 아래 오류 규칙 참고 |
| R6 연결 | 결과 행 → 다른 탭 폼으로 값 전달 | `LinkPlan`에 있는 필드만 |

오류 표시 규칙: 공공 API는 실패도 HTTP 200 본문으로 오는 경우가 많다. 릴레이는 상태 코드만
보고 성공이라 말하지 않는다. 본문에 `resultCode`/`resultMsg`(XML은 `errMsg`/`returnAuthMsg`)가
있으면 그대로 보여 주고, 없으면 성공·실패를 판정하지 않고 원본을 보여 준다. 문서에 없는
오류 규격을 추측해 만들지 않는다.

응답 파싱: `format` 파라미터가 있으면 JSON을 기본으로 요청한다. JSON이 아니면 브라우저에서
XML로 파싱해 반복 노드(`item`)를 표로 그린다. 둘 다 실패하면 원본 텍스트를 보여 준다.

## 8. API 계약

| 메서드 | 경로 | 동작 |
|---|---|---|
| `POST` | `/factory/builds` | `{run_id}` 또는 `{selected_service_ids, query}` → 번들 생성. 200 + 스펙·노드 상태 |
| `GET` | `/factory/builds/{id}` | 스펙, 노드 상태, 포함/제외 문서, 경고 |
| `GET` | `/factory/builds/{id}/download` | zip 첨부 응답 |
| `GET` | `/factory/builds/{id}/preview` | 생성 UI(정적) 서빙 |
| `POST` | `/factory/builds/{id}/call` | `{endpoint_id, params}` + 키 헤더 → upstream 릴레이 |

- 미완료 run은 409(플로우 내보내기와 같은 규칙), 포함 문서 0건은 422 + 제외 사유.
- UI에는 완료된 run 결과 패널에 `웹 서비스 만들기` 버튼 하나를 추가한다(플로우 내보내기 옆).
  누르면 번들을 만들고 노드 상태·미리보기 링크·다운로드 링크를 보여 준다.

## 9. 단계

1. search 상세에 `base_url` 추가 + 테스트.
2. N1~N5: `factory/spec.py`. 노드 상태와 `excluded[]`까지 여기서 완성한다.
3. N6: `factory/render.py` 템플릿과 생성물.
4. N7~N8: `factory/bundle.py` 검사·zip.
5. N9와 API·UI 버튼.
6. 미리보기 릴레이 `factory/relay.py`.
7. README 갱신(Prometheus README의 API 표와 안전 경계 절에 공장 항목 추가).

각 단계는 그 단계의 테스트까지 포함해야 끝난 것으로 본다.

## 10. 테스트

- `test_factory_spec.py` 노드별 판정: 문서 자격(N2), 파라미터 4분류와 GET 외 제외(N3),
  relations 밖 연결을 만들지 않음(N4), 문서 순서 고정과 같은 입력 → 같은 `content_hash`(N5).
- `test_factory_render.py` 필수 파일 존재, 생성물에 키·절대 경로 없음, allowlist 일치.
- `test_factory_bundle.py` N7 실패 시 파일을 남기지 않음, zip 구성.
- `test_factory_api.py` 미완료 run 409, 포함 문서 0건 422, 다운로드 헤더, 응답의 `nodes[]`.
- `test_factory_relay.py` allowlist 밖 경로 차단, 키 마스킹, 상한 초과 응답 처리.

기존 규칙대로 쓰기 가능한 임시 폴더를 쓴다:

```powershell
python -m pytest -q --basetemp C:\tmp\nara-pytest
```

## 11. 미지원 (명시)

- OAuth·서명·POST 본문 인증을 쓰는 API. `serviceKey` 질의 파라미터 방식만 지원한다.
- `fileData`, `standard`, swagger가 없는 `openapi_old` 문서. 호출 기준이 없으면 제외한다.
- 페이지네이션 자동 순회, 대량 수집, 결과 저장. 한 화면 한 요청만 한다.
- 생성 번들의 외부 노출. 로컬 실행 전용이며 그 상태로 배포하지 않는다.
