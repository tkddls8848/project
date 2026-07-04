# Nara OpenClaw MCP 적용 계획

작성일: 2026-06-20
범위: 독립 기능 프로젝트 `nara_openclaw(행정서비스실행기)`

## 1. 목적

`nara_openclaw`는 조합기가 만든 실행 계획을 검증하고, 사용자 승인 후 실행 어댑터를 호출하며, 감사 로그를 남기는 독립 기능이다. MCP 적용의 목적은 실행을 쉽게 자동화하는 것이 아니라, dry-run과 승인 경계를 더 명확하게 노출하는 것이다.

ITWorld 기사에서 MCP 보안 주의점으로 프롬프트 인젝션, 최소 권한, 수동 승인, 민감정보 보호, 내부 MCP 서버 catalog가 언급된다. OpenClaw는 실제 행정 실행과 가까운 기능이므로 이 원칙을 가장 강하게 적용한다.

## 2. MCP에서 기대하는 역할

Phase 1.5에서는 조회만 노출한다.

```text
get_run_record(run_id)
  -> GET /runs/{run_id}
```

Phase 2에서만 실행 계열을 노출한다.

```text
dry_run_plan(plan, user_inputs)
  -> POST /execute/dry-run

execute_with_approval(plan, user_inputs, approval)
  -> POST /execute
```

기본 설정:

```text
NARA_MCP_ENABLE_EXECUTE=false
```

## 3. 현재 endpoint

- `GET /demo/plan`: 테스트용 행정 실행 계획 반환
- `POST /execute/dry-run`: 누락 입력값, 승인 필요 여부, 전송 예정 payload 확인
- `POST /execute`: 승인된 계획만 더미 정부 실행 어댑터로 실행
- `GET /runs/{run_id}`: 실행 결과와 감사 로그 조회

## 4. 승인 원칙

- `dry-run`은 외부 실행을 하지 않는다.
- `execute`는 승인 정보가 없으면 403으로 차단한다.
- MCP에서 호출하더라도 기존 승인 계약을 우회하지 않는다.
- 민감 입력값은 응답과 로그에서 마스킹한다.
- 모든 실행은 `runs/{run_id}.json`으로 저장한다.

## 5. 간단하고 강력하게 만드는 결정

- MCP 전용 executor를 만들지 않는다.
- `DummyGovernmentExecutor`는 유지하고, 실제 연동은 같은 adapter 인터페이스를 따른다.
- `get_run_record`부터 안정화해 감사 조회를 먼저 완성한다.
- `execute_with_approval`은 feature flag, 승인값, dry-run 성공 조건을 모두 확인한 뒤에만 허용한다.
- 원격 MCP transport에서는 실행 tool을 열지 않는다. 인증과 감사 정책 확정 후 별도 검토한다.

## 6. 민감정보 정책

마스킹 대상 예:

- `identity_token`
- `approval_token`
- `password`
- `resident_registration_number`
- `phone`
- `email`
- 기타 `SENSITIVE_KEYS`에 포함된 키

MCP 응답에는 masked payload만 포함한다. 원문 사용자 입력을 반환하지 않는다.

## 7. Gov24 Link Resolver 연계

`linkout` 실행 모드는 `nara_gov24_link_resolver`의 검수된 링크 산출물을 사용할 수 있다.

우선순위:

1. `review_status=reviewed`
2. `confidence` 높은 링크
3. `pending` 링크는 자동 실행 근거로 사용하지 않고 사용자 확인용 후보로만 표시

## 8. 테스트 계획

- 승인 없는 `POST /execute`는 실패한다.
- MCP feature flag가 꺼져 있으면 `execute_with_approval`이 실패한다.
- dry-run은 외부 제출을 하지 않는다.
- `GET /runs/{run_id}`는 민감정보를 마스킹한다.
- 없는 run ID는 일관된 not found를 반환한다.

## 9. 완료 기준

- MCP 조회 tool은 감사 로그를 안전하게 반환한다.
- MCP 실행 tool은 기본 비활성이다.
- 승인, dry-run, 마스킹 테스트가 모두 통과한다.
- 실제 정부24 또는 기관 연동은 adapter 경계 안에서만 추가된다.

## 10. 참고할 오픈소스 프로젝트

| 프로젝트 | 참고할 부분 | 적용 방식 |
| --- | --- | --- |
| `WooilJeong/PublicDataReader` | 실제 공공데이터 조회 wrapper, 행정구역 코드 유틸 | read-only 실행 adapter와 입력 정규화 후보 |
| `openapi-generators/openapi-python-client` | OpenAPI에서 Python client 생성 | 기관별 API adapter 자동 생성 후보 |
| `langchain-ai/langgraph` | human-in-the-loop, durable execution 개념 | 장기 실행 workflow와 승인 중단/재개 설계 참고 |
| `modelcontextprotocol/servers` | filesystem/postgres reference의 접근 제한 방식 | MCP 실행 tool 권한 설명과 보안 경계 참고 |
| `linkchecker/linkchecker` | 링크 유효성 확인, robots.txt 존중 | linkout 실행 모드의 링크 검증 보조 도구 후보 |

도입하지 않을 것:

- PublicDataReader를 통해 write/submit 성격의 행정 처리를 자동화하지 않는다.
- LangGraph가 승인 정책을 대체하지 않는다. OpenClaw의 승인 스키마가 우선이다.
- 생성된 OpenAPI client를 검증 없이 실행 adapter로 등록하지 않는다.

## 11. 참고 자료

- ITWorld MCP 서버 기사: https://www.itworld.co.kr/article/4184249/
- MCP 공식 문서: https://modelcontextprotocol.io/docs/getting-started/intro
- MCP reference servers 보안 경고: https://github.com/modelcontextprotocol/servers
- PublicDataReader: https://github.com/WooilJeong/PublicDataReader
- openapi-python-client: https://github.com/openapi-generators/openapi-python-client
- LangGraph: https://github.com/langchain-ai/langgraph
- LinkChecker: https://github.com/linkchecker/linkchecker
