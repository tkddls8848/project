# nara_agui MCP 적용 계획

작성일: 2026-06-20
범위: 독립 기능 프로젝트 `nara_agui(에이전트UI데모)`

## 1. 목적

`nara_agui`는 Agent UI 패턴을 보여주는 독립 데모다. MCP 적용의 목적은 이 데모를 MCP 서버로 바꾸는 것이 아니라, MCP tool 호출 흐름을 사용자가 이해할 수 있는 단계형 UI로 표현하는 것이다.

공식 MCP 문서는 MCP가 AI 애플리케이션을 외부 data, tools, workflows에 연결하는 표준이라고 설명한다. AGUI는 그 연결 과정이 사용자에게 어떻게 보여야 하는지를 검증하는 화면이다.

## 2. MCP와의 관계

`nara_agui`는 MCP host가 아니다. 다만 MCP tool 호출과 유사한 실행 흐름을 NDJSON 이벤트로 표현한다.

대응 관계:

| AGUI 이벤트 | MCP 의미 |
| --- | --- |
| `step query_analysis` | host가 사용자 요청을 tool 호출 후보로 해석 |
| `step vector_search` | `search_public_services` 호출 |
| `layout` | tool 결과를 화면 구조로 변환 |
| `token` | 설명/요약 생성 |
| `done` | tool workflow 종료 |

## 3. 목표 기능

- MCP tool 호출 흐름을 시각화할 수 있는 이벤트 이름을 정리한다.
- 검색, 조합, dry-run 같은 단계가 추가되어도 envelope은 유지한다.
- 실제 서비스 연동 전에는 mock data로 UI 패턴만 빠르게 검증한다.
- 향후 `nara_mcp` tool 결과 fixture를 받아 화면 렌더링을 테스트할 수 있게 한다.

## 4. 간단하고 강력하게 만드는 결정

- AGUI 안에 실제 MCP client를 넣지 않는다.
- mock 흐름과 실제 service 흐름을 같은 NDJSON envelope으로 맞춘다.
- UI는 `single`, `grid`, `flow` 세 레이아웃만 우선 지원한다.
- MCP Apps는 장기 후보로만 둔다. 지금은 브라우저 기반 독립 데모를 유지한다.

## 5. 구현 계획

1. 현재 NDJSON envelope을 유지한다.
2. 이벤트 payload에 `tool_name`, `request_id`, `service_id` 같은 선택 필드를 추가할 수 있게 타입을 정리한다.
3. `search_public_services` fixture를 추가해 검색 tool 결과 화면을 검증한다.
4. `compose_services` fixture를 추가해 flow 레이아웃을 검증한다.
5. OpenClaw 실행 단계는 실제 실행이 아니라 dry-run/approval 표시까지만 mock으로 둔다.

## 6. 테스트 계획

- 시드 쿼리 3개가 `single`, `grid`, `flow`를 각각 렌더한다.
- `tool_name`이 포함된 이벤트도 기존 UI가 깨지지 않는다.
- stream 중 오류 이벤트가 오면 타임라인에 실패 상태가 표시된다.
- mock fixture를 실제 MCP tool 결과 구조로 교체해도 레이아웃이 유지된다.

## 7. 완료 기준

- AGUI는 독립 데모로 유지된다.
- MCP tool workflow를 설명 가능한 UI 이벤트로 표현한다.
- 실제 서비스 연동 없이도 검색/조합/승인 흐름의 화면 구조를 검증할 수 있다.

## 8. 참고할 오픈소스 프로젝트

| 프로젝트 | 참고할 부분 | 적용 방식 |
| --- | --- | --- |
| `ag-ui-protocol/ag-ui` | agent-user interaction event model, streaming, generative UI | 현재 NDJSON envelope을 AG-UI event naming에 맞춰 정리할 때 참고 |
| `copilotkit/copilotkit` | React 기반 agent UI와 frontend tool integration | 데모를 React 앱으로 확장할 때 참고 |
| `xyflow/xyflow` | flow layout과 node interaction | 절차형 layout을 정식 React Flow로 옮길 때 참고 |
| `langchain-ai/langgraph` | workflow state와 human-in-the-loop 개념 | 승인/중단/재개 이벤트 설계 참고 |
| `modelcontextprotocol/servers` | MCP tool 실행 결과를 host가 보여주는 방식 | tool workflow를 UI step으로 표현할 때 참고 |

도입하지 않을 것:

- AGUI 데모가 실제 MCP client를 내장하지 않는다.
- CopilotKit 전체 stack을 현재 vanilla demo에 바로 붙이지 않는다.
- LangGraph를 UI demo의 런타임으로 쓰지 않는다.

## 9. 참고 자료

- MCP 공식 문서: https://modelcontextprotocol.io/docs/getting-started/intro
- MCP reference servers: https://github.com/modelcontextprotocol/servers
- ITWorld MCP 서버 기사: https://www.itworld.co.kr/article/4184249/
- AG-UI protocol: https://github.com/ag-ui-protocol/ag-ui
- CopilotKit: https://github.com/copilotkit/copilotkit
- React Flow/xyflow: https://github.com/xyflow/xyflow
- LangGraph: https://github.com/langchain-ai/langgraph
