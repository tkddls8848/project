# Nara Combiner MCP 적용 계획

작성일: 2026-06-20
범위: 독립 기능 프로젝트 `nara_combiner(API문서조합기)`

## 1. 목적

`nara_combiner`는 여러 공공 API 문서를 조합해 단일 API로는 만들 수 없는 행정 서비스 계획 초안을 생성한다. MCP 적용의 목적은 조합 로직을 다른 프로젝트로 옮기는 것이 아니라, MCP host가 검색된 service ID를 넘겨 조합 제안을 받을 수 있게 하는 것이다.

ITWorld 기사에서 Elastic Agent Builder가 원시 DB 인터페이스보다 상위 agent workflow를 노출하는 사례가 언급된다. `nara_combiner`도 같은 방향이다. 데이터베이스 tool이 아니라 "API 조합 제안"이라는 상위 기능을 MCP tool로 노출한다.

## 2. MCP에서 기대하는 역할

`nara_combiner`는 실행하지 않는다. `nara_mcp`는 이 프로젝트의 `POST /compose`를 다음 tool로 래핑한다.

```text
compose_services(service_ids, question)
  -> POST /compose
  -> 조합 제안 + 실행 계획 초안 반환
```

MCP host가 보기 좋은 응답 구조:

```json
{
  "summary": "이 API들은 교통 지원과 복지 신청 안내를 조합할 수 있습니다.",
  "candidate_services": ["15080662", "15051043"],
  "required_inputs": ["region", "birth_date", "income_type"],
  "handoff_target": "nara_openclaw",
  "plan": {},
  "warnings": ["실제 제출은 OpenClaw 승인 흐름에서만 처리"]
}
```

## 3. 책임

- API 문서 메타데이터 로딩
- service ID 기반 API 선택
- API 간 조합 가능성 분석
- 필요한 사용자 입력값과 조건 추정
- `nara_openclaw`로 넘길 수 있는 계획 초안 작성

하지 않는 일:

- 정부24 또는 기관 시스템 호출
- 신청서 제출
- 사용자 승인 처리
- dry-run 실행
- 실행 이력 또는 감사 로그 저장

## 4. 간단하고 강력하게 만드는 결정

- MCP 전용 프롬프트를 새로 만들지 않고 기존 `/compose` 로직을 정돈한다.
- tool 입력은 `service_ids`와 `question`으로 제한한다.
- service 상세조회가 필요하면 `nara_mcp`가 `nara_search`를 먼저 호출하고, combiner는 받은 ID만 처리한다.
- 긴 LLM 결과는 `summary`, `plan`, `warnings`로 나눠 MCP host가 필요한 부분만 표시하게 한다.
- stream endpoint는 유지하되 MCP 1차 연동은 non-stream `POST /compose`로 시작한다.

## 5. OpenClaw와의 경계

```text
nara_combiner
  API 문서 -> 조합 후보 -> 계획 초안

nara_openclaw
  계획 초안 -> dry-run -> 사용자 승인 -> 실행 어댑터 -> 감사 로그
```

경계 규칙:

- combiner 응답은 실행 가능성을 설명할 수 있지만 실행하지 않는다.
- `handoff_target`은 문자열로만 표시하고, 실제 호출은 사용자 또는 MCP host의 다음 tool 호출에 맡긴다.
- 승인과 민감정보는 combiner 입력에 받지 않는다.

## 6. 테스트 계획

- `POST /compose`가 service ID 2개 이상에서 구조화된 응답을 반환한다.
- 없는 service ID가 포함되면 명확한 warning을 반환한다.
- 조합 결과에 실행/수동/linkout 후보가 구분된다.
- MCP 연동 테스트에서 `compose_services`가 기존 endpoint를 그대로 호출한다.

## 7. 완료 기준

- `compose_services` MCP tool이 `/compose`를 안정적으로 호출한다.
- 결과에 `summary`, `candidate_services`, `required_inputs`, `plan`, `warnings`가 포함된다.
- OpenClaw 실행은 여전히 combiner 밖에 있다.

## 8. 참고할 오픈소스 프로젝트

| 프로젝트 | 참고할 부분 | 적용 방식 |
| --- | --- | --- |
| `langchain-ai/langgraph` | long-running stateful workflow, human-in-the-loop 설계 | 조합 결과를 plan graph로 구조화할 때 참고. 즉시 의존성 추가는 보류 |
| `pydantic/pydantic-ai` | Pydantic schema 중심 agent output 검증 | `/compose` 응답을 typed plan으로 고정할 때 참고 |
| `deepset-ai/haystack` | pipeline node 설계와 routing | 검색 후보 -> 조합 -> 요약 단계를 명확히 나눌 때 참고 |
| `WooilJeong/PublicDataReader` | 공공 API 호출 wrapper와 행정구역 코드 | 조합 결과의 "실제 호출 가능성" 판단 보조 자료로 사용 |
| `openapi-generators/openapi-python-client` | OpenAPI 명세 기반 client 생성 | 실행 가능한 API 후보의 typed adapter 생성 가능성 검토 |

도입하지 않을 것:

- LangGraph를 조합기 1차 구현에 넣지 않는다. 현재는 단일 `/compose`가 더 단순하다.
- LLM agent framework가 OpenClaw 승인 경계를 대신하게 하지 않는다.
- PublicDataReader 호출을 combiner 내부에서 직접 실행하지 않는다. 가능성 표시와 입력 스키마 참고에 제한한다.

## 9. 참고 자료

- ITWorld MCP 서버 기사: https://www.itworld.co.kr/article/4184249/
- MCP 공식 문서: https://modelcontextprotocol.io/docs/getting-started/intro
- MCP reference servers: https://github.com/modelcontextprotocol/servers
- LangGraph: https://github.com/langchain-ai/langgraph
- Pydantic AI: https://github.com/pydantic/pydantic-ai
- Haystack: https://github.com/deepset-ai/haystack
- PublicDataReader: https://github.com/WooilJeong/PublicDataReader
- openapi-python-client: https://github.com/openapi-generators/openapi-python-client
