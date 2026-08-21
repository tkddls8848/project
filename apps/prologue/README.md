# Nara Hermes Orchestrator

Hermes Gateway Runs API와 Nara MCP를 결합해 공공 API 문서를 탐색하고, 근거가 있는 서비스 계획 초안을 만드는 로컬 오케스트레이터입니다. 실제 행정 API 실행이나 민원 제출은 하지 않습니다.

## 구성

```text
UI/API :8020 -> Hermes Gateway :8642 -> Cloudflare 호환 프록시 :8643 -> Workers AI
                                      -> Nara MCP (stdio)
                                           -> Search :8000
                                           -> Combiner :8003
```

호환 프록시는 Cloudflare의 OpenAI 호환 스트림에서 문자열 필드가 숫자나 객체로 오는 경우에만 JSON 문자열로 정규화합니다. Hermes 본체나 전역 Hermes profile은 수정하지 않습니다.

## 설치와 설정

```powershell
cd C:\project\apps\prologue
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

`.env`에 다음 값을 설정합니다.

```dotenv
CLOUDFLARE_ACCOUNT_ID=...
CLOUDFLARE_API_TOKEN=...
NARA_CLOUDFLARE_PROXY_KEY=충분히-긴-로컬-임의값
API_SERVER_KEY=운영용-임의값
```

Cloudflare 토큰에는 Workers AI 읽기 권한이 필요합니다. 토큰과 Account ID는 호환 프록시만 읽으며, Hermes에는 로컬 프록시 키만 전달됩니다.

## 실행

기존 `:8642` Hermes Gateway가 실행 중이라면 먼저 해당 콘솔에서 `Ctrl+C`로 종료합니다. 런처는 어떤 profile로 시작된 프로세스인지 판별할 수 없으므로 기존 Gateway를 임의로 재사용하거나 종료하지 않습니다.

```powershell
.\venv\Scripts\python.exe run.py
```

런처는 다음 파일을 실행 시 자동 생성합니다.

```text
apps/prologue/.runtime/hermes/profiles/nara-cf/config.yaml
```

이 profile은 프로젝트 내부에서만 사용되고 `.gitignore`에 포함됩니다. 설치된 Hermes 폴더와 사용자 전역 profile은 그대로 유지됩니다.

정상 시작 시 콘솔에 다음 두 줄이 모두 보여야 합니다.

```text
[준비] Cloudflare Compatibility Proxy: /health 응답 확인 (:8643)
[설정] 프로젝트 전용 Hermes profile: C:\project\apps\prologue\.runtime\hermes\profiles\nara-cf\config.yaml
```

실행 후에도 `expected str instance, int found`가 보인다면 기존 전역 Gateway가 아직 `:8642`를 점유하고 있는지 확인합니다. 호환 프록시 상태와 실제 전달 건수는 다음 명령으로 볼 수 있습니다.

```powershell
Invoke-RestMethod http://127.0.0.1:8643/health
```

`upstream_requests`가 실행마다 증가해야 Hermes 요청이 호환 프록시를 통과한 것입니다.

이미 별도로 올린 Gateway를 명시적으로 재사용하려면 다음 옵션을 사용합니다. 이 경우 런처는 호환 프록시와 Hermes를 관리하지 않으므로 Gateway 설정 책임은 호출자에게 있습니다.

```powershell
.\venv\Scripts\python.exe run.py --no-hermes
```

브라우저 UI는 `http://127.0.0.1:8020`, OpenAPI 문서는 `/docs`입니다.

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

## 안전 경계

- Nara MCP allowlist 도구만 노출 (`search_api_docs`, `get_api_detail`)
- 도구 결과는 선택에 필요한 요약만 반환하고 문서 전문은 전달하지 않는다
- 전체 도구 시작 이벤트 최대 4회
- 요청이 `selected_service_ids`를 지정하면 Hermes run을 만들지 않는다
- Gateway 승인 요청 자동 거부
- terminal/file/browser/web/messaging/delegation 미노출
- 실제 행정 처리 완료 주장 금지
- Cloudflare 호환 프록시는 `127.0.0.1`에만 바인딩되고 한 개 API 경로만 전달

## 테스트

```powershell
.\venv\Scripts\python.exe -B -m pytest tests -q
```
