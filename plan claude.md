Here is Claude's plan:
╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌ 나라 프로젝트에 MCP 서버 적용 — nara_mcp (읽기 전용 MVP)
  
 Context (왜 이 작업을 하는가)

 공유된 ITWorld 기사("자연어로 데이터베이스를 조작하는 시대, MCP 서버가 열다")는
 LLM 에이전트가 SQL을 직접 쓰지 않고 자연어로 데이터 소스를 조회/조작하도록
 표준 커넥터(MCP)로 노출하는 흐름을 정리한다. 핵심 사례:

 - MCP Toolbox for Databases (Google) — tools.yaml에 데이터 소스를 정의해
 30여 종 DB를 도구로 노출. → 나라의 api_tool_specs.jsonl(SP3 계획)과 사실상 동형.
 - Pinecone / Chroma / Milvus 등 벡터 DB MCP 서버 — 임베딩 검색을 도구화.
 → 나라의 FAISS 검색과 동일 역할.
 - 보안 권고 — 읽기 전용 기본, 최소 권한, 수동 승인, 프롬프트 인젝션 방어,
 MCP 레지스트리로 섀도우 IT 방지. → 나라 SP7 보안 하드닝 및 openclaw의
 dry-run/승인 게이트/입력 마스킹과 정확히 일치.

 나라는 이미 "자연어 한 줄 → 공공 API 검색·조합·호출" 인프라이고,
 SERVICE_PLAN.md §15.2에 MCP 활용 검토가 오픈 이슈로 적혀 있다.
 따라서 가장 자연스러운 적용은 나라의 검색/카탈로그 기능을 MCP 도구로 노출하여
 Claude Code · Cursor · Gemini CLI · Claude Desktop 같은 임의의 MCP 호스트가
 나라의 공공데이터 검색을 자연어로 쓰게 만드는 것이다.

 사용자 결정: ① 방향 = "나라를 MCP 서버로 노출", ② 범위 = "읽기 전용부터".
 실행(openclaw) 도구화는 본 MVP 범위 밖(Phase 2)으로 미룬다.

 목표 (이번 MVP의 산출물)

 기존 운영 코드(nara_search, nara_dashboard)를 건드리지 않고,
 독립 실행 가능한 신규 서브프로젝트 nara_mcp를 추가한다.
 완료 정의 = Claude Code(또는 Claude Desktop)에 nara_mcp를 등록하면
 자연어로 공공 API를 검색·상세조회할 수 있다.

 SERVICE_PLAN의 단방향 의존 원칙(§3.3)을 따른다 →
 nara_mcp는 nara_search의 HTTP 엔드포인트만 소비하고, 코드를 직접 import 하지 않는다.

 노출할 도구 (Phase 1, 모두 read-only)

 ┌────────────────────────┬─────────────────┬──────────────────────────┬──────────────────────────┐    
 │          도구          │      입력       │          백엔드          │           비고           │    
 ├────────────────────────┼─────────────────┼──────────────────────────┼──────────────────────────┤    
 │ search_public_services │ query: str,     │ POST nara_search:8000    │ 이미 존재 — 그대로 래핑  │    
 │                        │ top_k: int=5    │ /search                  │                          │    
 ├────────────────────────┼─────────────────┼──────────────────────────┼──────────────────────────┤    
 │                        │                 │ GET                      │ nara_search에 신규       │    
 │ get_service_detail     │ service_id: str │ /services/{service_id}   │ 엔드포인트 1개 추가      │    
 │                        │                 │                          │ 필요(아래)               │    
 ├────────────────────────┼─────────────────┼──────────────────────────┼──────────────────────────┤    
 │ get_index_health       │ —               │ GET /health              │ 인덱스 상태/문서 수 확인 │    
 │                        │                 │                          │  (선택)                  │    
 └────────────────────────┴─────────────────┴──────────────────────────┴──────────────────────────┘    

 - query 최소 2자 검증은 nara_search가 이미 수행 → 도구는 그대로 위임.
 - 결과 envelope은 _to_result()(main.py:34) 형식을 그대로 통과 — 재정의 금지.

 변경/추가 대상 파일

 A. 신규 서브프로젝트 nara_mcp(MCP서버)/

 nara_mcp(MCP서버)/
   server.py            # FastMCP 서버 (stdio 트랜스포트 기본)
   client.py            # nara_search HTTP 호출 래퍼 (httpx, 단방향 의존)
   config.py            # NARA_SEARCH_BASE_URL(기본 http://127.0.0.1:8000), 타임아웃
   requirements.txt     # mcp>=1.0, httpx>=0.27
   README.md            # 등록 방법 + 보안 메모 + MCP 레지스트리 항목

 - SDK: 공식 Python mcp 패키지의 FastMCP. 각 도구는 @mcp.tool() 데코레이터로
 정의하고, 내부에서 client.py의 async httpx 호출만 수행.
 - 트랜스포트: 1차는 stdio(로컬 Claude Code/Desktop/Cursor 등록용).
 원격(SSE/HTTP)은 SP7 보안 확정 후 Phase 2에서 추가 — 기사의 "원격 서버 보안" 권고 반영.
 - 기존 httpx 패턴 재사용: combiner/agui가 이미 httpx 비동기 호출을 사용 중이라 동일 스타일 유지.      

 B. nara_search 최소 보강 — 상세조회 엔드포인트 구현

 - 현재 GET /services/{service_id}(main.py:110)는 항상 404 스텁이다.
 get_service_detail 도구가 동작하려면 실제 상세를 반환해야 한다.
 - 기존 카탈로그 로더 재사용: backend/catalog/data_loader.py, document_builder.py가
 apidata/*.json을 파싱하므로, service_id(openapi_new:{api_id})로 해당 JSON을 찾아
 info / endpoints / swagger_json를 반환하도록 구현. 신규 파서 작성 금지, 기존 로더 활용.
 - 이 변경은 대시보드 노드 상세 패널에도 곧바로 이득(현재 빈 endpoints 채움).

 C. 등록 설정 (문서로만 제공, 코드 변경 아님)

 - .mcp.json(프로젝트 루트) 또는 Claude Desktop 설정 예시를 README에 기재:
 { "mcpServers": {
     "nara": { "command": "python",
               "args": ["nara_mcp(MCP서버)/server.py"],
               "env": { "NARA_SEARCH_BASE_URL": "http://127.0.0.1:8000" } } } }

 보안 적용 (기사 권고 → 나라 매핑)

 - 읽기 전용 기본: Phase 1 도구는 GET/검색만. 쓰기·실행(openclaw) 도구는 미포함.
 - 최소 권한: MCP 서버는 nara_search 공개 엔드포인트만 호출, 파일시스템·DB 직접 접근 없음.
 - 수동 승인: 실행 도구는 Phase 2로 분리하고, 그때 openclaw의 기존 dry-run/승인 게이트
 (executor.build_dry_run, approval_required)를 도구 경계에서 강제.
 - 민감정보 보호: openclaw mask_inputs(executor.py:12)의 SENSITIVE_KEYS 마스킹 패턴을
 Phase 2 실행 도구에 그대로 적용. Phase 1은 자격증명을 다루지 않음.
 - MCP 레지스트리: nara_mcp/README.md에 승인된 서버 목록·용도를 문서화(섀도우 IT 방지).

 적용하지 않을 것 (스코프 밖)

 - 내부 검색을 구글 MCP Toolbox(tools.yaml)로 대체하는 리팩터(사용자가 미선택).
 단, 향후 DuckDB/ChromaDB(SP3) 도입 시 query_catalog 도구의 백엔드로 재검토 — README에 메모만.
 - openclaw 실행 도구화 (Phase 2).
 - 원격 SSE/HTTP 트랜스포트 + 인증 (SP7 이후).

 검증 (end-to-end)

 1. nara_search 기동: uvicorn backend.main:app --port 8000 → GET /health로 인덱스 적재 확인.
 2. nara_search에 /services/{service_id} 보강 후, 검색 결과의 service_id로 200 응답 확인
 (예: curl http://127.0.0.1:8000/services/openapi_new:15000827).
 3. MCP 인스펙터로 단독 검증: mcp dev nara_mcp(MCP서버)/server.py →
 search_public_services("여행경보"), get_service_detail(...) 호출 결과 확인.
 4. Claude Code/Desktop에 위 .mcp.json 등록 → "여행경보 관련 공공 API 찾아줘" 자연어 질의 →
 도구 호출 → 결과 카드 반환되는지 확인.
 5. (회귀) nara_dashboard가 기존대로 동작하는지 — /search 응답 형식 불변 확인.

 후속 (Phase 2 예고, 본 MVP 외)

 - execute_plan / dry_run_plan 도구로 openclaw(8002) 래핑 — 승인 게이트·마스킹 강제.
 - DuckDB/ChromaDB 도입 시 query_catalog(자연어/구조화 조회) 도구 추가.
 - 원격 트랜스포트 + 인증(API Key) — SP7과 함께.