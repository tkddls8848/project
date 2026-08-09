# Nara Hermes Orchestrator

Hermes Gateway Runs API와 Nara MCP를 결합해 공공 API 문서를 검색·검토하고 근거가
있는 서비스 계획 초안을 만드는 독립 오케스트레이션 서비스다. 서비스는 읽기와 계획
작성만 수행하며 실제 행정 API 실행이나 민원 제출은 하지 않는다.

## 구성

```text
UI/API :8020 -> Hermes Gateway :8642 -> Nara MCP (stdio)
                                      -> Search :8000
                                      -> Combiner :8003
```

한 애플리케이션 run이 한 Hermes Gateway run에 대응한다. Hermes가 단일 세션에서
검색, 상세 검토, 후보 선택, 관계 확인과 조합 도구를 선택한다. 백엔드는 Gateway SSE를
브라우저 이벤트로 변환하고 최종 JSON을 검증한 뒤 로컬 critic과 신선도 검사를
수행한다. critic은 추가 LLM 호출을 만들지 않는다.

## 설치와 설정

```powershell
cd C:\project\apps\prometheus
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

`.env`에서 최소한 다음 값을 설정한다.

```dotenv
CLOUDFLARE_API_TOKEN=...
API_SERVER_KEY=운영용-임의의-긴-키
```

`config/hermes.example.yaml`을 Hermes 프로필의 `config.yaml`로 복사하고
`<ACCOUNT_ID>`를 실제 Cloudflare Account ID로 바꾼다. 프로필 위치는
`%HERMES_HOME%\profiles\nara-cf\config.yaml`이며 `HERMES_HOME`이 없을 때만
`%USERPROFILE%\.hermes\profiles\nara-cf\config.yaml`을 사용한다. MCP 설정의 Python
경로와 `PYTHONPATH`는 현재 checkout 절대 경로에 맞춘다.

`API_SERVER_KEY`는 Hermes Gateway와 이 서비스가 함께 읽는다. 운영에서는 예시
기본값 `change-me-local-dev`를 사용하지 않는다.

## 실행

Search, Combiner, Hermes Gateway와 서비스를 함께 시작한다.

```powershell
.\venv\Scripts\python.exe run.py
```

**인자 없이 실행하면 포트·상류 옵션을 먼저 물어본다.** 전부 Enter로 넘기면 예전과
같은 기본 실행이고, 마지막에 조립된 명령을 보여준 뒤 확인을 받는다. 묻지 않고 바로
띄우려면 인자를 하나라도 주면 된다 (예: `run.py --port 8020`). 파이프·CI처럼 입력이
콘솔이 아닐 때도 묻지 않고 기본값으로 실행한다.

이미 별도로 실행 중인 Gateway를 사용할 때:

```powershell
.\venv\Scripts\python.exe run.py --no-hermes
```

브라우저 UI는 `http://127.0.0.1:8020`, OpenAPI 문서는 `/docs`다.

## 주요 API

| 메서드 | 경로 | 설명 |
|---|---|---|
| `GET` | `/health` | Search·Combiner 상태 |
| `GET` | `/agent/health` | Hermes Gateway 상세 readiness |
| `POST` | `/agent/design-runs` | Hermes 오케스트레이션 생성 |
| `GET` | `/agent/design-runs/{id}` | 상태·결과 조회 |
| `GET` | `/agent/design-runs/{id}/events` | 진행 이벤트 SSE |
| `POST` | `/agent/design-runs/{id}/stop` | 실행 중단 |
| `GET` | `/agent/design-runs/{id}/flow` | Dashboard flow 다운로드 |

## 모델과 비용

기본 프로필은 Cloudflare Workers AI의
`@cf/mistralai/mistral-small-3.1-24b-instruct`를 사용한다. 선택 모델은 function
calling, Hermes가 요구하는 64K 이상의 컨텍스트, 한국어 tool 인자 보존을 만족해야
한다.

Workers AI 무료 할당량 안에서는 외부 결제가 없지만 Runs API 기반 에이전트 루프의
호출 횟수와 토큰은 요청마다 달라지므로 run당 비용을 고정값으로 추정하지 않는다.
`AgentRunResponse.hermes.usage`와 Cloudflare
대시보드의 Neurons를 함께 모니터링한다.

## 안전 경계

- Nara MCP 다섯 도구만 화이트리스트
- 전체 도구 시작 이벤트 최대 12회
- Gateway 승인 요청 자동 거부
- terminal/file/browser/web/messaging/delegation 미노출
- Gateway와 provider 키를 브라우저에 미노출
- 실제 행정 처리 완료 주장 금지

## 테스트

```powershell
.\venv\Scripts\python.exe -B -m pytest tests -q
```

테스트 환경의 기본 임시 폴더 권한이 제한되면 쓰기 가능한 작업공간 경로를
`--basetemp`로 지정한다.
