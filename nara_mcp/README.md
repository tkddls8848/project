# nara_mcp

`nara_search(API문서검색)`의 read-only 기능만 외부 MCP host(Claude Code,
Claude Desktop, Cursor 등)에 노출하는 **로컬 stdio 어댑터**.

- Search의 Python 코드를 import하지 않고 **HTTP로만** 호출한다
- index build, 파일 쓰기, 조합·실행 기능은 노출하지 않는다
- MCP 등록·해제와 무관하게 Search는 독립 실행 가능하다
- 원격 transport는 인증·감사 설계 전에는 열지 않는다 (stdio 전용)

## 구조

```
nara_mcp/
  server.py                 ← FastMCP stdio 서버 (도구 3개)
  config.py                 ← 환경 변수 (NARA_SEARCH_BASE_URL 등)
  clients/
    search_client.py        ← Search HTTP client + 구조화 오류 변환
  tests/
    test_search_client.py   ← 성공·400/404/503·timeout·연결 실패·비JSON 변환
    test_server_tools.py    ← 도구 등록 범위·검색→상세조회 흐름
  requirements.txt
```

## 사전 조건

1. `nara_search` 백엔드가 기동돼 있어야 한다 (기본 `http://127.0.0.1:8000`)
2. 검색 결과가 필요하면 Search 쪽에서 FAISS 인덱스를 빌드해 둔다
   (인덱스가 없어도 어댑터는 동작하며, `get_index_health`가 원인을 진단한다)

## 실행

```bash
pip install -r requirements.txt
python server.py            # stdio — MCP host가 spawn하는 방식이 일반적
```

## 환경 변수

| 변수 | 기본값 | 용도 |
| --- | --- | --- |
| `NARA_SEARCH_BASE_URL` | `http://127.0.0.1:8000` | Search 서비스 주소 |
| `NARA_MCP_REQUEST_TIMEOUT` | `10` | upstream 호출 timeout (초) |

## MCP host 등록 예시

Claude Code:

```bash
claude mcp add nara-search -- python /path/to/nara_mcp/server.py
```

Claude Desktop / 일반 JSON 설정:

```json
{
  "mcpServers": {
    "nara-search": {
      "command": "python",
      "args": ["/path/to/nara_mcp/server.py"],
      "env": { "NARA_SEARCH_BASE_URL": "http://127.0.0.1:8000" }
    }
  }
}
```

## 도구 계약

| Tool | Upstream | 설명 |
| --- | --- | --- |
| `search_public_services(query, top_k=5, use_vector=true)` | `POST /search` | 자연어 검색. query 2~300자, top_k 1~20 |
| `get_service_detail(service_id)` | `GET /services/{service_id}` | 검색 결과의 정식 ID(`openapi_new:{api_id}`)를 그대로 전달 |
| `get_index_health()` | `GET /health` | 인덱스·데이터 준비 상태 진단 |

성공 응답은 upstream JSON에 `ok: true`, `service: "nara_search"`만 더한
최소 정규화다. 실패는 항상 다음 형식이다.

```json
{
  "ok": false,
  "service": "nara_search",
  "error_code": "NOT_FOUND",
  "message": "service_id not found",
  "retryable": false
}
```

| error_code | 상황 | retryable |
| --- | --- | --- |
| `INVALID_ARGUMENT` | query/top_k/service_id가 계약 위반 (upstream 호출 없음) | false |
| `INVALID_SERVICE_ID` / `UNSUPPORTED_SOURCE` | Search가 400으로 응답 | false |
| `NOT_FOUND` | 미존재 service_id (404) | false |
| `SERVICE_UNAVAILABLE` | Search 데이터 소스 미준비 (503) | true |
| `CONNECTION_FAILED` | Search 미기동·연결 거부 | true |
| `TIMEOUT` | 응답 시간 초과 | true |
| `BAD_UPSTREAM_RESPONSE` | 비JSON 응답 | 상태에 따라 |
| `UPSTREAM_ERROR` | 그 외 upstream 오류 | 5xx면 true |

stack trace, 로컬 절대 경로, 원문 예외 메시지는 반환하지 않는다.

## MCP 없이 같은 흐름 재현 (read-only 안내)

MCP를 등록하지 않은 클라이언트도 같은 HTTP 계약을 그대로 쓸 수 있다.

```bash
# 1) 상태 확인
curl -s http://127.0.0.1:8000/health

# 2) 자연어 검색
curl -s -X POST http://127.0.0.1:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "미세먼지 실시간 조회", "top_k": 5}'

# 3) 결과의 service_id 그대로 상세조회
curl -s http://127.0.0.1:8000/services/openapi_new:15000827
```

안내 범위는 검색·상세조회·health뿐이다. index build(`POST /build`)는 운영
절차이므로 에이전트 안내 대상이 아니다.

## 테스트

```bash
python -m pytest tests -q
```

실제 네트워크 없이 `httpx.MockTransport`로 upstream 성공·오류 변환 계약을
검증한다. 라이브 검증은 Search 기동 후 MCP Inspector 또는
`mcp.client.stdio`로 도구 3개 호출을 확인한다:

```bash
npx @modelcontextprotocol/inspector python server.py
```

## 범위 밖 (보류)

- Combiner·OpenClaw 연결, 실행 tool, 원격 transport, resources/prompts —
  각 원 프로젝트의 계약이 안정된 뒤 필요성을 재평가한다 (루트 계획 문서 참고)
