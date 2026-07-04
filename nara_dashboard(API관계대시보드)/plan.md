# nara_dashboard MCP 적용 계획

작성일: 2026-06-20
범위: 독립 기능 프로젝트 `nara_dashboard(API관계대시보드)`

## 1. 목적

`nara_dashboard`는 React Flow 기반으로 검색 결과와 API 관계를 시각화하는 프론트엔드다. MCP 적용의 목적은 대시보드를 MCP 서버로 바꾸는 것이 아니라, MCP를 통해 안정화되는 검색·상세조회·조합 결과를 화면에서 더 단순하게 소비하는 것이다.

ITWorld 기사에서 Neo4j MCP는 그래프 스키마와 관계 조회를 LLM에게 노출하는 예로 소개된다. 이 프로젝트는 실제 Neo4j 서버를 도입하기보다, 현재 React Flow 화면이 소비할 수 있는 service detail과 relation payload를 먼저 안정화한다.

## 2. MCP와의 관계

`nara_dashboard`는 직접 MCP host나 server가 아니다.

사용 흐름:

```text
nara_dashboard
  -> /api/search 프록시
  -> nara_search POST /search
  -> nara_search GET /services/{service_id}
  -> 화면 detail panel 표시
```

MCP 흐름과 공유하는 부분:

- service ID 규칙
- 상세조회 endpoint
- 조합 결과의 plan/relations 구조
- read-only 조회 우선 정책

## 3. 목표 기능

- 검색 결과 노드 클릭 시 `GET /services/{service_id}`로 상세 패널을 채운다.
- node와 edge payload를 MCP tool 결과와 같은 필드명으로 맞춘다.
- 조합 결과가 있을 때 plan step을 React Flow 노드로 표시할 수 있게 준비한다.
- 대시보드 내부에서 실행을 직접 호출하지 않는다. 실행은 OpenClaw 승인 흐름으로 넘긴다.

## 4. 간단하고 강력하게 만드는 결정

- 대시보드 안에 검색 로직을 다시 넣지 않는다.
- `nara_search`의 상세조회 endpoint를 재사용한다.
- MCP 결과를 화면 전용 타입으로 과도하게 변환하지 않는다.
- Graph DB 도입은 보류한다. 우선 JSON relation payload와 React Flow 렌더링으로 충분한지 검증한다.
- MCP Apps 또는 interactive UI 제공은 장기 후보로 두고, 현재는 웹 프론트엔드 독립성을 유지한다.

## 5. 구현 계획

1. `nara_search` 상세조회 endpoint가 준비되면 detail drawer에서 호출한다.
2. node 데이터 타입에 `service_id`, `title`, `agency`, `endpoints`, `source`를 명시한다.
3. 조합 결과를 받는 경우 `plan.steps[]`를 flow node로 변환하는 pure function을 둔다.
4. 실행 버튼은 직접 실행하지 않고 OpenClaw dry-run 화면 또는 JSON handoff로 연결한다.
5. 검색 API 실패, 상세조회 404, 백엔드 미기동 상태를 UI에서 구분 표시한다.

## 6. 테스트 계획

- `/api/search` 프록시가 기존처럼 동작한다.
- 검색 결과 node 클릭 시 상세조회가 호출된다.
- 상세조회 404가 화면 오류로만 표시되고 앱 전체가 깨지지 않는다.
- 조합 plan fixture가 React Flow 노드로 변환된다.
- OpenClaw 실행 API를 대시보드가 직접 호출하지 않는다.

## 7. 완료 기준

- 대시보드는 독립 프론트엔드로 유지된다.
- 검색과 상세조회는 `nara_search` endpoint만 소비한다.
- MCP tool 결과와 화면 payload가 같은 service ID 체계를 사용한다.

## 8. 참고할 오픈소스 프로젝트

| 프로젝트 | 참고할 부분 | 적용 방식 |
| --- | --- | --- |
| `xyflow/xyflow` | React Flow node/edge 모델, layout, interaction pattern | 현재 대시보드의 핵심 UI 패턴으로 계속 사용 |
| `ag-ui-protocol/ag-ui` | agent 실행 이벤트와 generative UI 이벤트 구분 | MCP tool 결과를 UI 이벤트로 표현할 때 참고 |
| `copilotkit/copilotkit` | frontend agent UX, generative UI 사례 | 대시보드 안에 agent panel을 붙일 때 참고 |
| `neo4j-labs/mcp-neo4j` 또는 Neo4j MCP 사례 | graph schema/query를 tool로 노출하는 방식 | 실제 graph DB 도입 전에는 아이디어만 참고 |
| `modelcontextprotocol/servers` | MCP client 설정 예시 | dashboard에서 MCP를 직접 쓰지 않는다는 경계 문서화에 참고 |

도입하지 않을 것:

- 대시보드가 직접 MCP server가 되지 않는다.
- CopilotKit을 즉시 붙이지 않는다. 현재 목표는 detail panel과 flow payload 안정화다.
- Neo4j를 관계 UI 때문에 바로 도입하지 않는다. JSON relation payload를 먼저 검증한다.

## 9. 참고 자료

- ITWorld MCP 서버 기사: https://www.itworld.co.kr/article/4184249/
- Neo4j MCP 사례: 그래프 관계를 tool로 노출하는 발상만 참고
- MCP 공식 문서: https://modelcontextprotocol.io/docs/getting-started/intro
- React Flow/xyflow: https://github.com/xyflow/xyflow
- AG-UI protocol: https://github.com/ag-ui-protocol/ag-ui
- CopilotKit: https://github.com/copilotkit/copilotkit
