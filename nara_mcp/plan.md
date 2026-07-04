# nara_mcp MCP 어댑터 계획

작성일: 2026-06-20
범위: 독립 기능 프로젝트 `nara_mcp`

## 1. 목적

`nara_mcp`는 `D:\project` 아래의 독립 기능들을 하나의 제품으로 합치는 프로젝트가 아니다. Claude Code, Claude Desktop, Cursor, Codex 같은 MCP host가 필요한 Nara 기능을 자연어로 호출할 수 있게 하는 얇은 어댑터다.

ITWorld 기사에서 정리한 MCP의 핵심은 데이터베이스나 검색 시스템을 자연어 도구로 노출해 LLM이 스키마, 검색, 조회, 운영 작업을 안전하게 다룰 수 있게 하는 것이다. Nara에는 이미 검색, 조합, 실행감사 기능이 있으므로 외부 DB MCP 서버를 억지로 붙이지 않고 기존 HTTP API를 MCP tools/resources로 노출한다.

## 2. 적용할 MCP 패턴

| 참고 프로젝트/문서 | 가져올 점 | Nara 적용 |
| --- | --- | --- |
| MCP 공식 문서 | tools, resources, prompts를 구분 | 실행은 tools, 문서/상태는 resources, 예시 질의는 prompts |
| MCP Python SDK/FastMCP | 작은 Python 서버를 데코레이터 기반으로 작성 | `server.py`에 tool 정의, 실제 호출은 clients로 분리 |
| modelcontextprotocol/servers | reference server는 학습용이며 보안은 사용자가 설계해야 함 | production-ready로 가정하지 않고 최소 권한 정책 명시 |
| MCP Toolbox for Databases | 선언형 tool catalog와 여러 backend 연결 | `tools.yaml` 대신 `config.py` + tool registry 표로 시작 |
| MongoDB/Supabase류 MCP | read-only 기본, write/execute는 명시적 활성화 | `NARA_MCP_ENABLE_EXECUTE=false` 기본값 |

## 3. 목표 기능

Phase 1은 검색만 다룬다.

- `search_public_services(query, top_k=5, use_vector=true)`
- `get_service_detail(service_id)`
- `get_index_health()`

Phase 1.5는 제안과 조회만 추가한다.

- `compose_services(service_ids, question)`
- `get_run_record(run_id)`

Phase 2는 실행을 다루되 기본 비활성이다.

- `dry_run_plan(plan, user_inputs)`
- `execute_with_approval(plan, user_inputs, approval)`

## 4. 구현 구조

```text
nara_mcp/
  server.py
  config.py
  clients/
    search_client.py
    combiner_client.py
    openclaw_client.py
  schemas/
    common.py
  tests/
    test_search_tools.py
    test_security_gates.py
  README.md
  plan.md
```

원칙:

- `nara_search`, `nara_combiner`, `nara_openclaw`의 Python 코드를 import하지 않는다.
- 모든 호출은 HTTP endpoint를 통해 수행한다.
- upstream 오류는 MCP host가 이해할 수 있는 짧은 structured error로 변환한다.
- tool 설명에는 read-only 여부와 실제 실행 가능성을 명시한다.

## 5. 간결하게 만드는 결정

- 로컬 stdio transport부터 시작한다. 원격 Streamable HTTP는 보안 계획 이후로 미룬다.
- MCP Toolbox 같은 범용 DB MCP를 도입하지 않는다. 현재 Nara의 주 저장소는 DB 제품이 아니라 JSON, FAISS, HTTP 서비스다.
- FastMCP 기반 단일 `server.py`로 시작하고, 기능별 HTTP client만 분리한다.
- 응답을 새로 설계하지 않고 원 서비스 응답을 가능한 한 보존한다.
- 실행 tool은 feature flag와 승인 검증이 통과할 때만 노출한다.

## 6. 보안 정책

- 기본은 read-only다.
- write/execute 성격 tool은 `NARA_MCP_ENABLE_EXECUTE=true` 없이는 실패한다.
- 실행은 dry-run 성공 후 명시적 승인 정보를 요구한다.
- 민감정보는 `nara_openclaw`의 마스킹 규칙을 재사용한다.
- README에 승인된 MCP 서버 이름, 목적, 노출 tool 목록을 기록해 내부 registry 역할을 하게 한다.

## 7. 완료 기준

- `mcp dev nara_mcp/server.py`로 tool 목록이 확인된다.
- `nara_search` 기동 상태에서 검색, 상세조회, health tool이 동작한다.
- `nara_combiner` 기동 상태에서 compose tool이 기존 `/compose` 결과를 반환한다.
- `nara_openclaw` 기동 상태에서 run 조회가 마스킹된 결과만 반환한다.
- 기본 설정에서 `execute_with_approval`은 실행되지 않는다.

## 8. 참고할 오픈소스 프로젝트

| 프로젝트 | 참고할 부분 | 적용 방식 |
| --- | --- | --- |
| `modelcontextprotocol/python-sdk` | FastMCP 기반 tool/resource/prompt 정의 | 1차 구현의 직접 SDK로 사용 |
| `modelcontextprotocol/servers` | reference server의 폴더 구조, `.mcp.json` 예시, 보안 경고 | 구현 패턴만 참고, production-ready로 간주하지 않음 |
| `googleapis/mcp-toolbox` | 선언형 tool catalog, 여러 backend를 하나의 MCP 표면으로 묶는 방식 | `tools.yaml` 도입은 보류하고 tool registry 표만 차용 |
| `WooilJeong/PublicDataReader` | 공공데이터 Python wrapper, 행정구역 코드 유틸 | 선택형 read-only tool 후보로 검토 |
| `openapi-generators/openapi-python-client` | OpenAPI 명세에서 typed client 생성 | data.go.kr 명세 품질이 충분한 API에 한해 adapter 생성 후보 |

도입하지 않을 것:

- MCP 서버를 자동 생성하는 프레임워크를 바로 쓰지 않는다. 현재는 `server.py + clients/` 구조가 더 단순하다.
- DB MCP 서버를 붙여 Nara 내부 구조를 우회하지 않는다.
- PublicDataReader를 핵심 의존성으로 넣지 않는다. 특정 공공 API adapter 후보로만 둔다.

## 9. 참고 자료

- ITWorld, "LLM과 데이터베이스를 연결하는 MCP 서버 10종 총정리": https://www.itworld.co.kr/article/4184249/
- MCP 공식 문서: https://modelcontextprotocol.io/docs/getting-started/intro
- MCP reference servers: https://github.com/modelcontextprotocol/servers
- MCP Python SDK: https://github.com/modelcontextprotocol/python-sdk
- MCP Toolbox for Databases: https://mcp-toolbox.dev/
- PublicDataReader: https://github.com/WooilJeong/PublicDataReader
- openapi-python-client: https://github.com/openapi-generators/openapi-python-client
