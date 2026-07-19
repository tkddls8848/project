# Nara Hermes PoC

기존 `nara_workbench(API통합워크벤치)`를 변경하지 않고 Hermes Agent 연동을
검증하기 위한 독립 프로젝트다.

이 프로젝트는 기존 서비스를 HTTP 소비자로만 사용한다.

- Nara Search: `http://127.0.0.1:8000`
- Nara Combiner: `http://127.0.0.1:8003`
- PoC API: `http://127.0.0.1:8020`

## PoC 범위

1. 자연어로 API 문서를 검색한다.
2. 검색 결과 또는 명시적으로 선택한 문서의 상세 정보를 가져온다.
3. 두 개 이상 문서가 선택되면 관계 근거를 조회한다.
4. 최대 세 개 문서로 행정 서비스 계획 초안을 만든다.
5. 위 기능을 Hermes가 사용할 수 있는 MCP 도구로 노출한다.

실제 행정 API 실행, 외부 시스템 변경, 브라우저 자동화, 예약 작업은 포함하지
않는다.

## 구조

```text
nara_hermes_poc/
├─ app/                 PoC HTTP API와 오케스트레이터
├─ mcp_server/          Hermes용 MCP stdio 서버
├─ skills/              Hermes 스킬 초안
├─ evaluation/          평가 질문 골든셋
├─ config/              Hermes 설정 예시
└─ tests/               외부 서비스 없이 실행되는 단위 테스트
```

## 구현 계획

현재의 결정형 흐름을 실제 Hermes MCP 도구 호출 루프로 확장하는 계획은
[`docs/hermes_tool_loop_plan.md`](docs/hermes_tool_loop_plan.md)에 정리되어 있다.

## 설치

PowerShell:

```powershell
cd C:\project\nara_hermes_poc
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 테스트

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## PoC API 실행

먼저 기존 Nara Search와 Combiner를 실행한 다음:

```powershell
python .\app\main.py
```

또는 Uvicorn으로 직접 실행한다.

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8020
```

설계 요청 예시:

```powershell
$body = @{
  query = "청년 주거와 취업 지원 서비스를 설계해줘"
  top_k = 5
  use_vector = $true
  compose = $true
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8020/design `
  -ContentType application/json `
  -Body $body
```

`selected_service_ids`를 전달하지 않으면 검색 결과 상위 세 개를 사용한다. 검토된
문서만 조합하려면 다음처럼 ID를 명시한다.

```json
{
  "query": "선택한 API로 행정 서비스 계획을 작성해줘",
  "selected_service_ids": [
    "openapi_new:15000827",
    "openapi_new:15000863"
  ]
}
```

## MCP 서버 실행

Hermes 설치 후 stdio MCP 서버를 직접 확인할 수 있다.

```powershell
.\.venv\Scripts\python.exe -m mcp_server.server
```

노출되는 도구:

- `search_api_docs`
- `get_api_detail`
- `derive_relations`
- `compose_service_plan`

Hermes 설정 예시는 `config/hermes.example.yaml`에 있다. Python 경로는 실제 PoC
가상환경의 절대 경로로 맞춰야 한다. 초기 검증에서는 Hermes의 터미널·파일 쓰기·
브라우저 도구를 켜지 않는다.

## 환경 변수

| 이름 | 기본값 | 설명 |
|---|---|---|
| `NARA_SEARCH_URL` | `http://127.0.0.1:8000` | 검색 백엔드 |
| `NARA_COMBINER_URL` | `http://127.0.0.1:8003` | 조합 백엔드 |
| `NARA_REQUEST_TIMEOUT` | `30` | HTTP 요청 제한 시간(초) |
| `NARA_COMPOSE_TIMEOUT` | `240` | 로컬 모델 계획 생성 제한 시간(초) |
