# Nara MCP 독립 기능 연결 계획

작성일: 2026-06-20
상호 보완 대상: `plan claude.md`, `plan codex.md`
목표: 두 계획의 장점을 합쳐, `D:\project` 아래의 독립 기능 프로젝트들이 자기 책임을 유지한 채 MCP로 필요한 기능만 선택적으로 노출하도록 정리한다.

## 1. 기본 전제

`D:\project`는 여러 하부 업무를 하나로 합친 단일 프로젝트가 아니다. 각 폴더는 검색, 조합, 실행, 대시보드, 크롤링처럼 서로 다른 목적을 가진 독립 기능 프로젝트다.

따라서 이 계획의 목적은 코드베이스나 제품을 하나로 합치는 것이 아니다. 목적은 독립 기능 프로젝트의 경계를 유지하면서, MCP가 필요한 기능을 호출할 수 있는 얇은 연결 표면을 만드는 것이다.

원칙:

- 각 독립 기능 프로젝트는 단독 실행, 단독 테스트, 단독 배포 가능성을 유지한다.
- `nara_mcp`는 중앙 통합 시스템이 아니라 선택적 MCP 어댑터다.
- 기능 구현은 원 소유 프로젝트에서 하고, MCP는 HTTP로 호출만 한다.
- 한 프로젝트의 내부 모듈을 다른 프로젝트에서 직접 import하지 않는다.
- 공통화는 스키마, URL, tool 이름, 에러 envelope처럼 경계에 필요한 부분으로 제한한다.

## 2. 정리 결론

Nara에 MCP를 적용하는 1차 목표는 외부 DB MCP 서버를 도입하는 것이 아니라, 이미 존재하는 Nara의 검색·상세조회·조합·실행감사 기능을 MCP 도구로 안전하게 노출하는 것이다.

다만 한 번에 모든 기능을 MCP로 열면 구현 범위와 보안 검증이 커진다. 따라서 다음 순서로 진행한다.

1. `nara_mcp` 신규 독립 기능 프로젝트를 만든다.
2. Phase 1은 `nara_search`만 래핑하는 read-only MVP로 제한한다.
3. Phase 1.5에서 `nara_combiner`와 `nara_openclaw`의 read-only 조회 기능만 추가한다.
4. Phase 2에서 dry-run과 승인 기반 실행 도구를 별도 플래그로 연다.
5. 원격 MCP, 인증, 실행 자동화는 별도 보안 하드닝 계획이 확정된 뒤 진행한다.

핵심 원칙은 기존 운영 코드의 직접 import 금지다. `nara_mcp`는 각 서비스의 HTTP 엔드포인트만 호출한다.

## 3. 두 계획의 상호 보완 포인트

| 항목 | Claude 계획의 강점 | Codex 계획의 강점 | 정리 결정 |
| --- | --- | --- | --- |
| MVP 범위 | 검색·상세조회·헬스체크로 작게 시작 | 조합·실행감사까지 전체 흐름 제시 | Phase 1은 Claude 범위, Phase 1.5에 Codex 범위 흡수 |
| 보안 | read-only, 최소 권한, 승인 게이트 명확 | write/execute 비활성화와 마스킹 테스트 포함 | 실행 계열은 기본 비활성, 승인·마스킹 통과 후 별도 활성 |
| 구현 방식 | `nara_search` HTTP 의존만 허용 | 기존 Nara 기능을 MCP tools/resources로 노출 | HTTP 어댑터 계층을 공통 패턴으로 고정 |
| 복잡도 관리 | 신규 파서 작성 금지, 기존 로더 재사용 | 프로젝트별 책임 분리 | 엔드포인트 보강은 원 소유 프로젝트에서만 수행 |
| 검증 | MCP 인스펙터와 Claude Desktop E2E | 단위·연동·보안 테스트 체계 | Phase별 완료 기준에 모두 반영 |

## 4. 목표 구조

```
MCP Host
  Claude Code / Claude Desktop / Cursor / Codex
        |
        v
nara_mcp
  server.py      FastMCP 도구 정의
  clients/       각 Nara 서비스 HTTP 클라이언트
  schemas/       MCP 응답 envelope 정규화
  config.py      서비스 URL, timeout, feature flag
        |
        +--> nara_search    : 검색, 상세조회, 헬스체크
        +--> nara_combiner  : API 조합 제안
        +--> nara_openclaw  : 실행감사 조회, dry-run, 승인 실행
```

의존 규칙:

- `nara_mcp`는 어떤 Nara 독립 기능 프로젝트의 Python 모듈도 import 하지 않는다.
- 각 기능의 원천 데이터 접근은 해당 소유 서비스가 담당한다.
- MCP 응답은 원 서비스 응답을 최대한 보존하고, 호스트 사용성에 필요한 얇은 요약만 추가한다.
- Phase 1의 도구는 파일 쓰기, 인덱스 빌드, 실행 제출을 하지 않는다.

## 5. Phase별 구현 계획

### Phase 0: 인터페이스 고정

목표: 구현 전에 서비스 경계와 tool 이름을 고정해 이후 변경 비용을 줄인다.

작업:

- `nara_mcp` 디렉터리명 확정: `nara_mcp`
- MCP tool 이름 확정:
  - `search_public_services`
  - `get_service_detail`
  - `get_index_health`
  - `compose_services`
  - `get_run_record`
  - `dry_run_plan`
  - `execute_with_approval`
- 환경 변수 확정:
  - `NARA_SEARCH_BASE_URL=http://127.0.0.1:8000`
  - `NARA_COMBINER_BASE_URL=http://127.0.0.1:8003`
  - `NARA_OPENCLAW_BASE_URL=http://127.0.0.1:8002`
  - `NARA_MCP_ENABLE_EXECUTE=false`
- 공통 timeout 기본값: 10초
- 공통 에러 envelope 정의:

```json
{
  "ok": false,
  "service": "nara_search",
  "error_code": "NOT_FOUND",
  "message": "service_id not found",
  "detail": {}
}
```

완료 기준:

- README에 tool 목록, 입력, 출력, feature flag가 표로 정리된다.
- 각 원 서비스의 담당 엔드포인트가 명확히 매핑된다.

### Phase 1: 검색 MCP MVP

목표: Claude Code 또는 Claude Desktop에서 자연어로 공공 API를 검색하고 상세조회할 수 있게 한다.

신규 프로젝트:

```
nara_mcp/
  server.py
  config.py
  clients/
    search_client.py
  schemas/
    common.py
  requirements.txt
  README.md
  tests/
    test_search_tools.py
```

MCP tools:

| Tool | 입력 | 호출 대상 | 정책 |
| --- | --- | --- | --- |
| `search_public_services` | `query`, `top_k=5`, `use_vector=true` | `POST /search` | read-only |
| `get_service_detail` | `service_id` | `GET /services/{service_id}` | read-only |
| `get_index_health` | 없음 | `GET /health` | read-only |

`nara_search` 보강:

- 현재 README 기준 `GET /services/{service_id:path}`는 TODO/404 상태다.
- 이 엔드포인트를 실제 상세조회로 구현한다.
- 기존 `backend/catalog/data_loader.py`, `document_builder.py`를 우선 재사용한다.
- 신규 JSON 파서나 별도 카탈로그 규격은 만들지 않는다.
- 반환 필드는 최소 `service_id`, `api_id`, `info`, `endpoints`, `swagger_json`로 둔다.

복잡도 완화:

- MCP 서버에서 apidata를 직접 읽지 않는다.
- 검색 결과 envelope은 `nara_search`의 기존 응답 형식을 유지한다.
- 상세조회 실패는 404를 MCP 에러 envelope으로만 변환한다.

완료 기준:

- `nara_search` 실행 후 `/health`가 정상 응답한다.
- `/search` 결과의 `service_id`로 `/services/{service_id}`가 200을 반환한다.
- `mcp dev nara_mcp/server.py`에서 세 도구가 호출된다.
- Claude Code 또는 Claude Desktop에 등록 후 자연어 질의로 검색 결과가 나온다.

### Phase 1.5: 조합·감사 조회 확장

목표: 검색된 API들을 조합 제안으로 넘기고, 실행 결과는 조회만 가능하게 한다.

추가 clients:

```
nara_mcp/clients/
  combiner_client.py
  openclaw_client.py
```

MCP tools:

| Tool | 입력 | 호출 대상 | 정책 |
| --- | --- | --- | --- |
| `compose_services` | `service_ids`, `question` | `POST /compose` | read-only 성격의 제안 생성 |
| `get_run_record` | `run_id` | `GET /runs/{run_id}` | read-only, 민감정보 마스킹 |

`nara_combiner` 목표 기능:

- service ID 배열과 사용자 질문을 받아 조합 제안과 실행 계획 초안을 생성한다.
- 실제 실행, 승인, 감사 저장은 하지 않는다.
- MCP 호출용으로 응답 길이를 너무 길게 만들지 않도록 `summary`, `plan`, `warnings`를 분리한다.

`nara_openclaw` 목표 기능:

- `GET /runs/{run_id}`만 MCP에 노출한다.
- run payload에 민감정보가 있으면 기존 마스킹 규칙을 적용한 필드만 반환한다.
- 존재하지 않는 run ID는 명확한 not found를 반환한다.

복잡도 완화:

- `compose_services`는 `nara_combiner`의 기존 API를 그대로 래핑한다.
- MCP에서 LLM 프롬프트를 새로 만들지 않는다.
- `get_run_record`는 실행을 시작하지 않고 감사 로그 조회만 수행한다.

완료 기준:

- 검색 결과 service ID 2~3개를 `compose_services`에 넘겨 조합 제안을 받을 수 있다.
- 존재하지 않는 run ID에 대한 에러가 일관된 envelope으로 반환된다.
- 마스킹 테스트가 통과한다.

### Phase 2: dry-run 및 승인 실행

목표: 실행 기능을 열되, dry-run과 명시적 승인 없이는 실제 실행 도구가 호출되지 않게 한다.

MCP tools:

| Tool | 입력 | 호출 대상 | 기본 상태 |
| --- | --- | --- | --- |
| `dry_run_plan` | `plan`, `user_inputs` | `POST /execute/dry-run` | 활성 가능 |
| `execute_with_approval` | `plan`, `user_inputs`, `approval` | `POST /execute` | 기본 비활성 |

활성 조건:

- `NARA_MCP_ENABLE_EXECUTE=true`
- `approval.approved=true`
- `approval.approver`가 비어 있지 않음
- `approval.approval_token`이 필요한 모드에서는 존재해야 함
- 실행 전 dry-run 결과가 성공이어야 함

보안 규칙:

- MCP tool 설명에 "실제 제출 가능성"을 명시한다.
- 민감 키는 `nara_openclaw`의 `SENSITIVE_KEYS` 패턴으로 마스킹한다.
- 실행 결과에는 receipt ID, run ID, masked payload만 반환한다.
- 원격 MCP transport에서는 Phase 2 실행 도구를 열지 않는다. 인증·감사 정책 확정 후 별도 검토한다.

완료 기준:

- 기본 설정에서는 `execute_with_approval`이 비활성화된다.
- 승인 없는 실행 요청은 거부된다.
- dry-run 성공 후 승인 실행 시 `runs/`에 감사 JSON이 생성된다.
- 테스트에서 민감정보 원문이 응답에 노출되지 않는다.

### Phase 3: 원격 MCP와 보안 하드닝

목표: 로컬 stdio MCP가 안정화된 뒤에만 원격 transport를 검토한다.

작업:

- SSE/HTTP transport 도입 여부 결정
- API key 또는 OAuth 계층 검토
- rate limit 적용
- CORS와 allowed host 제한
- MCP 서버 레지스트리 문서화
- 실행 도구는 원격에서 별도 allowlist 필요

완료 기준:

- 인증 없는 원격 호출이 차단된다.
- tool별 권한 정책이 README에 명시된다.
- 감사 로그에 MCP caller, tool name, request ID가 남는다.

## 6. 독립 기능 프로젝트별 목표와 책임

### `nara_mcp`

책임:

- MCP server 진입점
- tool 정의와 설명
- 각 Nara 서비스 HTTP client
- 공통 timeout, 에러 envelope, feature flag
- MCP host 등록 문서

하지 않는 일:

- apidata 직접 파싱
- FAISS/Chroma 인덱스 직접 접근
- LLM 조합 프롬프트 직접 작성
- 승인 없는 실행

목표 기능:

- 자연어 검색용 read-only MCP tools
- 조합 제안 조회
- 실행감사 조회
- feature flag 기반 실행 도구 통제

### `nara_search(API문서검색)`

책임:

- 공공 API 문서 검색
- 인덱스 상태 확인
- service ID 기반 상세조회

필수 보강:

- `GET /services/{service_id:path}` 실제 구현
- 검색 결과의 `service_id`와 상세조회 ID 규칙 일치
- 없는 service ID에 대한 404 응답 정리

복잡도 완화:

- 기존 카탈로그 로더를 재사용한다.
- 검색 응답 envelope을 변경하지 않는다.
- 상세조회 구현은 대시보드에도 재사용 가능하게 FastAPI 엔드포인트로만 제공한다.

### `nara_combiner(API문서조합기)`

책임:

- 여러 API 문서의 조합 가능성 설명
- 행정 서비스 계획 초안 생성
- 실행 가능한 계획 후보를 `nara_openclaw`로 넘길 수 있는 형태로 정리

MCP 연계:

- `compose_services`가 `POST /compose`를 호출한다.
- MCP 서버는 조합 결과를 요약해 반환하되 원문 plan도 보존한다.

복잡도 완화:

- MCP 전용 조합 로직을 만들지 않는다.
- service ID 정규화는 `nara_combiner` 또는 공통 규칙 문서에서 처리한다.

### `nara_openclaw(행정서비스실행기)`

책임:

- dry-run 검증
- 명시적 승인 후 실행
- 실행 감사 JSON 저장
- 민감정보 마스킹

MCP 연계:

- Phase 1.5: `get_run_record`만 노출
- Phase 2: `dry_run_plan`, `execute_with_approval` 노출

복잡도 완화:

- 기본 executor는 계속 dummy로 둔다.
- 실제 Government24 또는 기관 제출 어댑터는 MCP와 독립적으로 교체한다.
- 승인 계약은 기존 OpenClaw 스키마를 따른다.

### `nara_dashboard(API관계대시보드)`

책임:

- 검색 결과와 관계 시각화
- service detail 패널 표시

MCP 적용 효과:

- `nara_search`의 상세조회 엔드포인트가 구현되면 대시보드의 빈 endpoint/detail 패널도 개선된다.

복잡도 완화:

- Phase 1에서는 대시보드 코드를 직접 수정하지 않는다.
- 상세조회 API 안정화 후 필요할 때만 프론트 연동을 보강한다.

### `nara_crawler(API문서크롤러)`

책임:

- 공공 API 원본 수집
- apidata JSON 생성
- 장기적으로 catalog foundation과 품질 리포트 생성

MCP 적용 효과:

- 직접 MCP에 노출하지 않는다.
- 수집 산출물이 `nara_search` 상세조회와 검색 품질의 기반이 된다.

복잡도 완화:

- Phase 1에서는 크롤러 변경 없음.
- 데이터 정제·스키마 정리는 크롤러 또는 별도 데이터 정리 기능에서 처리한다.

### `nara_agui(에이전트UI데모)`

책임:

- 에이전트 사고 과정, 검색 결과, 조합 흐름을 시각적으로 보여주는 데모

MCP 적용 효과:

- MCP는 외부 호스트용 도구 표면이고, AGUI는 사용자-facing 데모 표면이다.
- 두 표면은 같은 원 서비스 API를 소비하되 서로 직접 의존하지 않는다.

복잡도 완화:

- MCP 구현 중 AGUI를 수정하지 않는다.
- MCP 안정화 후 tool 호출 결과를 AGUI 흐름에 붙일지 별도 결정한다.

## 7. 구현 순서

1. `nara_search`의 `/services/{service_id}` 구현
2. `nara_mcp` 기본 골격 생성
3. `search_public_services`, `get_service_detail`, `get_index_health` 구현
4. MCP README와 `.mcp.json` 예시 작성
5. Phase 1 단위 테스트와 MCP 인스펙터 검증
6. `compose_services` 추가
7. `get_run_record` 추가와 마스킹 검증
8. `dry_run_plan` 추가
9. `execute_with_approval`는 feature flag와 승인 검증 후 추가
10. 원격 transport는 보안 하드닝 이후 별도 계획으로 분리

## 8. 테스트 전략

### 단위 테스트

- `search_public_services`가 `top_k`, `query`를 올바르게 전달한다.
- `get_service_detail`이 200과 404를 구분한다.
- `compose_services`가 service ID 배열을 그대로 전달한다.
- `get_run_record`가 민감 필드를 마스킹한다.
- 실행 feature flag가 꺼져 있으면 실행 tool이 거부된다.

### 연동 테스트

- `nara_search` 기동 후 MCP tool로 검색한다.
- 검색 결과의 service ID로 상세조회한다.
- service ID 2~3개를 조합 도구에 넘긴다.
- OpenClaw demo run 또는 fixture run을 조회한다.

### 보안 테스트

- 기본 설정에서 파일 쓰기, 인덱스 빌드, 실행 제출이 불가능하다.
- 승인 없는 `execute_with_approval` 요청은 실패한다.
- 민감정보 원문이 MCP 응답에 포함되지 않는다.
- timeout과 upstream 오류가 내부 stack trace 없이 반환된다.

### 회귀 테스트

- `nara_dashboard`가 기존 `/search` 응답 형식 변경 없이 동작한다.
- `nara_combiner`와 `nara_openclaw`의 기존 pytest가 통과한다.

## 9. MCP 등록 문서 예시

`nara_mcp/README.md`에 다음 형식으로 제공한다.

```json
{
  "mcpServers": {
    "nara": {
      "command": "python",
      "args": ["D:/project/nara_mcp/server.py"],
      "env": {
        "NARA_SEARCH_BASE_URL": "http://127.0.0.1:8000",
        "NARA_COMBINER_BASE_URL": "http://127.0.0.1:8003",
        "NARA_OPENCLAW_BASE_URL": "http://127.0.0.1:8002",
        "NARA_MCP_ENABLE_EXECUTE": "false"
      }
    }
  }
}
```

## 10. 스코프에서 제외할 것

현재 하지 않는다:

- Postgres, Supabase, MongoDB, Redis, BigQuery MCP 서버 도입
- FAISS를 Pinecone, Chroma, Milvus로 즉시 교체
- Neo4j를 실제 운영 그래프 DB로 승격
- MCP 서버에서 직접 apidata 파일 읽기
- 승인 없는 행정서비스 실행
- 원격 MCP transport 즉시 도입
- 크롤러와 대시보드의 대규모 리팩터

나중에 검토한다:

- `retrieval_chunks.jsonl` 기반 ChromaDB 이행
- `api_tool_specs.jsonl`를 MCP tool registry로 자동 변환
- AGUI와 MCP 결과 표면 연동
- 원격 MCP 인증과 감사 정책

## 11. 리스크와 대응

| 리스크 | 영향 | 대응 |
| --- | --- | --- |
| `/services/{service_id}` 구현이 불안정함 | MCP 상세조회 실패 | `nara_search` 로더 재사용, fixture 기반 테스트 추가 |
| service ID 형식 불일치 | 검색 후 상세조회 실패 | `openapi_new:{api_id}`와 순수 `api_id` 허용 여부를 명시 |
| MCP tool 범위 과확장 | 보안·테스트 부담 증가 | Phase 1을 read-only 검색으로 제한 |
| 실행 도구 오용 | 실제 제출 위험 | feature flag, dry-run, approval 필수화 |
| 민감정보 노출 | 개인정보 사고 | OpenClaw 마스킹 규칙 재사용 |
| 원 서비스 미기동 | MCP 도구 실패 | health tool과 명확한 upstream unavailable 오류 제공 |
| 응답이 너무 길어짐 | MCP host 사용성 저하 | 요약 필드와 원문 필드를 분리하고 필요 시 limit 도입 |

## 12. 최종 완료 정의

Phase 1 완료:

- `nara_mcp`가 로컬 stdio MCP 서버로 실행된다.
- Claude Code 또는 Claude Desktop에서 공공 API 검색과 상세조회가 가능하다.
- 기존 `nara_search` 검색 응답 형식은 깨지지 않는다.
- 대시보드와 검색 서비스의 기존 동작이 유지된다.

Phase 1.5 완료:

- 검색된 service ID를 조합 도구로 넘겨 행정 서비스 계획 초안을 받을 수 있다.
- 실행 감사 로그를 마스킹된 형태로 조회할 수 있다.

Phase 2 완료:

- dry-run과 승인 실행이 MCP에서 가능하다.
- 기본 설정에서는 실행이 비활성화된다.
- 승인, 마스킹, 감사 로그 테스트가 모두 통과한다.

## 13. 요약

정리 전략은 "작은 MCP 어댑터를 먼저 만들고, 기능은 원 소유 프로젝트에 남긴다"이다. Claude 계획의 작은 read-only MVP를 Phase 1의 기준으로 삼고, Codex 계획의 조합·감사·실행 흐름은 Phase 1.5와 Phase 2로 분리해 흡수한다.

이 방식은 목표 기능을 줄이지 않으면서도 구현 복잡도를 낮춘다. 각 독립 기능 프로젝트는 자기 책임만 구현하고, `nara_mcp`는 필요한 기능을 안전한 도구 표면으로 선택 연결한다.
