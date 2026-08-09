# Nara 개발 지침

data.go.kr API 문서를 수집·검색·조합하는 개인 개발용 모노레포다. 현재 구현과 테스트에
필요한 코드만 유지하며, 이전 경로 호환이나 미래 사이트 구조 대응을 미리 넣지 않는다.

## 현재 구조

```text
data.go.kr -> services/crawler -> nara_storage/ (gitignore)
                                 -> services/search :8000
                                 -> services/combiner :8003

apps/dashboard :5173   React Flow 편집기
apps/workbench :8010   search/combiner 통합 UI
apps/prometheus :8020  Hermes Gateway(:8642) + Nara MCP 오케스트레이터
services/refresher     data.go.kr 활용신청 연장 CLI
```

- `apps/*`는 `services/*`를 HTTP로 사용한다. 서비스 구현을 직접 import하지 않는다.
- 실행기 공통 CLI 코드만 `nara_common/`에서 공유한다.
- 저장소 루트는 `.nara-root`로 찾고 모든 산출물은 루트 `nara_storage/`에 둔다.
- `archive/`와 날짜가 붙은 계획 문서는 현재 구현 판단에 사용하지 않는다.

## 모듈 계약

### crawler

- 현재 data.go.kr 마크업과 catalog 응답만 지원한다.
- 결과 유형은 `openapi_new`, `openapi_old`, `openapi_link`, `fileData`, `standard`다.
  `openapi_old`는 현재도 Swagger JSON이 없는 HTML 문서를 뜻하므로 제거 대상이 아니다.
- 심화 파일 분석은 `--deep`, 전체 파일 수신은 `--full-download`, 외부 기관 수집은
  `--harvest`를 명시해야 실행한다.

### search / combiner

- 입력 데이터는 `nara_storage/openapi_new/` 등 crawler 결과다. fresh clone에는 데이터가
  없으므로 crawler 실행 전 검색 결과를 가정하지 않는다.
- search는 검색·상세·관계 API, combiner는 읽기 전용 서비스 계획 초안을 제공한다.

### prometheus

- 애플리케이션 run 하나가 Hermes Gateway run 하나에 대응한다.
- Nara MCP의 읽기 전용 도구만 허용하고 최대 12회 호출한다.
- 최종 LLM 출력은 코드 펜스 없는 JSON 객체여야 한다.
- critic은 로컬 결정형 검증만 수행한다. 결과 재검증을 위한 추가 LLM run을 만들지 않는다.
- 실제 행정 처리나 외부 시스템 변경을 수행했다고 주장하지 않는다.

### refresher

- 현재 확인된 흐름만 지원한다:
  `selectAcountList.do -> fn_detail(...) -> 연장 신청하기 -> confirm/alert`.
- 로그인은 사람이 브라우저에서 수행하고 Playwright storage state를 저장한다.
- `extend`는 dry-run이며 실제 제출에는 `--commit`이 필요하다.
- HTTP 직접 제출, 사이트 자동 탐색, 다른 포털/과거 마크업 폴백은 지원하지 않는다.

## 개발 환경

- 기준 환경: Windows PowerShell, 저장소 예시 경로 `C:\project`.
- 각 모듈의 가상환경은 해당 디렉터리 `venv/`에 둔다.
- 서비스 포트: search 8000, combiner 8003, workbench 8010, prometheus 8020,
  Hermes Gateway 8642, dashboard 5173.
- Python 테스트는 쓰기 가능한 임시 폴더를 사용한다:

```powershell
python -m pytest -q --basetemp C:\tmp\nara-pytest
```

변경 시 관련 모듈 테스트를 실행하고, 현재 동작에 필요하지 않은 호환 분기·중복 문서·
복제 유틸을 추가하지 않는다.
