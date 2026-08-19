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
- 계획 초안(LLM 자유 텍스트)을 코드 생성 근거로 사용하는 것. 아래 3절 참고.

## 2. "무지성"의 정의

무지성 = **사람 개입 없이 한 번에**이지, 근거 없는 생성이 아니다. 공장은 새 LLM run을 만들지
않는다(critic이 재검증용 run을 만들지 않는 것과 같은 규칙). 코드·폼·파라미터·엔드포인트는
Nara 상세 문서에서 결정형으로 파생한다.

- 결정형 템플릿의 입력: `base_url`, `endpoints[]`, `request_fields[]`, `response_fields[]`,
  `relations.relations[]`.
- LLM 산출물(`plan.suggestion`)의 용도: 생성 서비스의 제목·설명 문구와 README의 배경 설명뿐.
  요청 파라미터나 필드 이름을 여기서 읽지 않는다.
- 근거가 없으면 만들지 않는다. 문서에 호출 기준(`base_url`)이 없으면 그 문서를 번들에서
  제외하고 `warnings`에 남긴다. 추측한 호스트를 넣지 않는다.

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
  POST /factory/builds        design run -> 번들 생성 (결정형)
  GET  /factory/builds/{id}   스펙·경고 조회
  GET  /factory/builds/{id}/download   zip
  GET  /factory/builds/{id}/preview    생성 UI 미리보기
  POST /factory/builds/{id}/call       미리보기 전용 릴레이 (키는 헤더로만)

생성 번들 (사용자 컴퓨터에서 단독 실행)
  app.py        표준 라이브러리 HTTP 서버 + 고정 allowlist 릴레이, 127.0.0.1 바인딩
  static/       index.html, app.js, styles.css
  README.md     실행 방법, 서비스키 발급·입력 안내
  spec.json     생성 근거(service_id, endpoint, 필드, 관계) — 키 없음
```

새 파일은 `apps/prometheus/app/factory/`에 둔다.

- `spec.py` 상세 문서 → 결정형 빌드 스펙
- `render.py` 스펙 → 번들 파일들(문자열 템플릿)
- `bundle.py` 파일 쓰기 + zip
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

서버 프록시가 필요한 이유: 공공 API 응답에 CORS 헤더가 없어 브라우저에서 직접 호출할 수 없다.
그래서 릴레이는 선택 기능이 아니라 번들의 최소 구성이다.

## 6. 생성 규칙 (결정형)

| 입력 | 생성물 |
|---|---|
| 문서 1개 | 화면 탭 1개 |
| `endpoints[]` 1개 | 조회 폼 1개 (`method` 그대로, GET 외에는 미지원으로 표시) |
| `request_fields[]` | 폼 입력 1개. `required=true`면 필수 표시, `description`은 도움말 |
| 인증 파라미터 | 폼에서 제외하고 전역 서비스키 입력으로 대체 |
| `response_fields[]` | 결과 테이블 컬럼(문서 순서, 상한 30) |
| `relations` 공통 필드 | 문서 간 "연결 필드" 표시와 값 전달 버튼 |

- 인증 파라미터 판정: 이름 소문자화 후 `servicekey`, `authkey`, `apikey`, `key`.
  이 규칙은 공장 전용이며 `libs/nara_common`에 넣지 않는다.
- 응답 파싱: `resultType`/`_type`/`type` 파라미터가 있으면 기본값 `json`. JSON이 아니면
  브라우저에서 XML로 파싱해 `item` 반복 노드를 표로 그린다.
- 연결 필드는 relations 응답의 근거에서만 가져온다. 이름이 비슷하다는 이유로 잇지 않는다.

## 7. API 계약

| 메서드 | 경로 | 동작 |
|---|---|---|
| `POST` | `/factory/builds` | `{run_id}` 또는 `{selected_service_ids, query}` → 번들 생성. 200 + 스펙 |
| `GET` | `/factory/builds/{id}` | 스펙, 포함/제외 문서, 경고 |
| `GET` | `/factory/builds/{id}/download` | zip 첨부 응답 |
| `GET` | `/factory/builds/{id}/preview` | 생성 UI(정적) 서빙 |
| `POST` | `/factory/builds/{id}/call` | `{endpoint_id, params}` + 키 헤더 → upstream 릴레이 |

- `run_id`가 완료 상태가 아니면 409(플로우 내보내기와 같은 규칙).
- 포함 문서가 하나도 없으면 422 + 제외 사유. 빈 번들을 만들지 않는다.
- 생성은 결정형이라 즉시 끝난다. 진행 SSE를 새로 만들지 않는다.

UI에는 완료된 run 결과 패널에 `웹 서비스 만들기` 버튼 하나를 추가한다(플로우 내보내기 옆).
누르면 번들을 만들고 미리보기 링크와 다운로드 링크를 보여 준다.

## 8. 단계

1. search 상세에 `base_url` 추가 + 테스트.
2. `factory/spec.py` — 상세·관계 → 빌드 스펙. 제외 사유와 경고 포함.
3. `factory/render.py` + `bundle.py` — 번들 파일 생성, zip, `spec.json`.
4. `/factory/builds` 계열 API와 UI 버튼.
5. `factory/relay.py` — 미리보기 릴레이(allowlist·마스킹·상한).
6. README 갱신(Prometheus README의 API 표와 안전 경계 절에 공장 항목 추가).

각 단계는 그 단계의 테스트까지 포함해야 끝난 것으로 본다.

## 9. 테스트

- `test_factory_spec.py` 고정 상세 fixture → 스펙 결정성, 인증 필드 제외, `base_url` 없는
  문서 제외와 경고.
- `test_factory_render.py` 생성물 문자열에 서비스키·절대 경로가 없음, 필수 파일 존재.
- `test_factory_api.py` 미완료 run 409, 포함 문서 0건 422, 다운로드 헤더.
- `test_factory_relay.py` allowlist 밖 경로 차단, 키 마스킹, 상한 초과 응답 처리.

기존 규칙대로 쓰기 가능한 임시 폴더를 쓴다:

```powershell
python -m pytest -q --basetemp C:\tmp\nara-pytest
```

## 10. 미지원 (명시)

- OAuth·서명·POST 본문 인증을 쓰는 API. `serviceKey` 질의 파라미터 방식만 지원한다.
- `fileData`, `standard`, swagger가 없는 `openapi_old` 문서. 호출 기준이 없으면 제외한다.
- 페이지네이션 자동 순회, 대량 수집, 결과 저장. 한 화면 한 요청만 한다.
- 생성 번들의 외부 노출. 로컬 실행 전용이며 그 상태로 배포하지 않는다.
