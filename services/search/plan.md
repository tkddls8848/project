# nara_search MCP 적용 계획

작성일: 2026-06-20
범위: 독립 기능 프로젝트 `nara_search(API문서검색)`

## 1. 목적

`nara_search`의 목표는 공공 API 문서를 빠르게 검색하고, 검색 결과의 `service_id`로 상세 문서를 조회할 수 있게 하는 것이다. MCP 적용의 목적은 검색 엔진을 바꾸는 것이 아니라, 이 검색 기능을 외부 MCP host가 안정적으로 호출할 수 있는 read-only 표면으로 만드는 것이다.

ITWorld 기사에서 언급된 Pinecone, Neo4j, BigQuery, MCP Toolbox의 공통점은 데이터 원천을 자연어 도구로 노출한다는 점이다. 현재 이 프로젝트에는 FAISS 검색과 JSON 문서가 이미 있으므로, 외부 벡터 DB로 교체하지 않고 기존 검색 API를 정돈해 MCP에서 쓰기 쉽게 만든다.

## 2. MCP에서 기대하는 역할

`nara_search`는 직접 MCP 서버가 되지 않는다. `nara_mcp`가 이 프로젝트의 HTTP API를 호출한다.

노출 대상:

| MCP tool | nara_search endpoint | 필요 작업 |
| --- | --- | --- |
| `search_public_services` | `POST /search` | 기존 응답 유지 |
| `get_service_detail` | `GET /services/{service_id}` | TODO/404 상태를 실제 구현으로 전환 |
| `get_index_health` | `GET /health` | 인덱스 상태를 host가 판단할 수 있게 유지 |

## 3. 기능 구현 계획

### 3.1 상세조회 endpoint 구현

현재 README 기준 `GET /services/{service_id:path}`는 TODO다. MCP와 대시보드 모두 이 endpoint가 있어야 검색 결과에서 상세 문서로 넘어갈 수 있다.

구현 원칙:

- `backend/catalog/data_loader.py`와 `document_builder.py`를 재사용한다.
- MCP 전용 파서를 만들지 않는다.
- `openapi_new:{api_id}`와 순수 `api_id` 입력을 어떻게 처리할지 명시한다.
- 응답 필드는 최소 `service_id`, `api_id`, `info`, `endpoints`, `swagger_json`로 한다.

### 3.2 검색 응답 안정화

- `POST /search`의 기존 envelope을 바꾸지 않는다.
- MCP host가 결과를 카드로 만들 수 있도록 각 item에 `service_id`, `title`, `agency`, `summary`, `score`가 있는지 확인한다.
- `top_k`와 query 길이 검증은 기존 FastAPI/Pydantic 레이어에서 처리한다.

### 3.3 health 응답 보강

`GET /health`는 MCP host가 "검색 가능한 상태인지" 판단하는 진단 endpoint다.

권장 필드:

```json
{
  "ok": true,
  "index_loaded": true,
  "document_count": 3526,
  "model_ready": true,
  "data_dir": "apidata"
}
```

## 4. 간단하고 강력하게 만드는 결정

- FAISS를 Pinecone, Chroma, Milvus로 즉시 바꾸지 않는다.
- MCP Toolbox를 붙이기보다 `POST /search`와 `GET /services/{service_id}`를 먼저 안정화한다.
- 상세조회 endpoint 하나를 구현해 MCP와 대시보드가 같이 쓰게 한다.
- 검색 품질 개선과 MCP 노출을 분리한다. MCP는 검색 품질을 높이는 계층이 아니라 검색 기능을 쓰기 쉽게 만드는 계층이다.

## 5. 테스트 계획

- `/search` 결과의 첫 `service_id`로 `/services/{service_id}`가 200을 반환한다.
- 없는 `service_id`는 404와 짧은 message를 반환한다.
- `/health`는 인덱스 미적재와 적재 상태를 구분한다.
- MCP 연동 테스트에서 `search_public_services`와 `get_service_detail`이 같은 ID 체계를 사용한다.
- 기존 대시보드 `/api/search` 프록시 동작이 깨지지 않는다.

## 6. 완료 기준

- MCP 없이도 `nara_search` 단독 기능이 완성된다.
- `nara_mcp`가 검색, 상세조회, health를 HTTP로 호출할 수 있다.
- 대시보드가 같은 상세조회 endpoint를 재사용할 수 있다.

## 7. 참고할 오픈소스 프로젝트

| 프로젝트 | 참고할 부분 | 적용 방식 |
| --- | --- | --- |
| `chroma-core/chroma` | 재생성 가능한 vector collection, metadata filter 구조 | FAISS 이후 이행 후보. Phase 1에는 도입하지 않음 |
| `qdrant/qdrant` | payload 기반 filter, 운영형 vector DB 설계 | 원격/운영 vector DB가 필요할 때 비교 후보 |
| `deepset-ai/haystack` | retriever/ranker/generator pipeline 분리 | 현재 검색 코드를 단계별 pipeline으로 정리할 때 참고 |
| `run-llama/llama_index` | document chunking, metadata node 구성 | `retrieval_chunks.jsonl` 설계 참고 |
| `WooilJeong/PublicDataReader` | 실제 공공 API wrapper와 코드 데이터 | 검색 결과 상세에서 실제 호출 가능성 표시용 보조 정보 후보 |

도입하지 않을 것:

- FAISS를 즉시 Chroma/Qdrant로 교체하지 않는다.
- Haystack/LlamaIndex 전체 framework를 검색 서비스에 넣지 않는다. pipeline 구조와 chunking 관례만 참고한다.
- PublicDataReader로 Nara 검색 인덱스를 대체하지 않는다.

## 8. 참고 자료

- ITWorld MCP 서버 기사: https://www.itworld.co.kr/article/4184249/
- MCP 공식 문서: https://modelcontextprotocol.io/docs/getting-started/intro
- Pinecone MCP 언급점: 벡터 DB 교체가 아니라 현 FAISS 검색을 read-only tool로 노출하는 방향만 채택
- Chroma: https://github.com/chroma-core/chroma
- Qdrant: https://github.com/qdrant/qdrant
- Haystack: https://github.com/deepset-ai/haystack
- LlamaIndex: https://github.com/run-llama/llama_index
- PublicDataReader: https://github.com/WooilJeong/PublicDataReader
