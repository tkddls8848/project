# nara_crawler MCP 적용 계획

작성일: 2026-06-20
범위: 독립 기능 프로젝트 `nara_crawler(API문서크롤러)`

## 1. 목적

`nara_crawler`는 공공 API 원본을 수집하고 검색 가능한 JSON 산출물을 만드는 데이터 생산 프로젝트다. MCP 적용의 목적은 크롤러를 MCP로 직접 실행하게 하는 것이 아니라, 검색·조합·MCP 어댑터가 쓰기 쉬운 산출물을 만드는 것이다.

ITWorld 기사에서 MCP Toolbox for Databases는 `tools.yaml` 같은 선언형 정의로 여러 데이터 소스를 tool로 노출한다. 이 프로젝트는 그 아이디어를 직접 DB MCP로 도입하지 않고, Nara용 `api_tool_specs.jsonl`, `retrieval_chunks.jsonl`, `catalog_manifest.json` 같은 산출물로 적용한다.

## 2. MCP에서 기대하는 역할

`nara_crawler`는 MCP tool이 아니다. downstream 프로젝트가 사용할 데이터 계약을 만든다.

```text
nara_crawler
  -> apidata/*.json
  -> catalog/index 산출물
  -> nara_search 검색/상세조회
  -> nara_mcp read-only tools
```

## 3. 목표 산출물

우선순위 산출물:

| 파일 | 목적 |
| --- | --- |
| `apidata/*.json` | 기존 검색과 상세조회 원천 |
| `catalog_manifest.json` | crawl_run, schema_version, 파일 수, checksum |
| `api_tool_specs.jsonl` | 향후 MCP tool/resource 생성 후보 |
| `retrieval_chunks.jsonl` | FAISS/Chroma/BM25가 공통으로 사용할 검색 청크 |
| `quality_report.json` | 누락 필드, 깨진 endpoint, HTML 잔존 여부 |

## 4. 간단하고 강력하게 만드는 결정

- 크롤러에서 MCP 서버를 띄우지 않는다.
- data.go.kr이나 정부24 자동 작업은 별도 약관 검토 전에는 read-only 수집으로 제한한다.
- MCP Toolbox의 선언형 tool catalog 발상만 차용하고, Nara 내부 형식은 JSONL로 둔다.
- downstream이 직접 원본 HTML을 해석하지 않도록 crawler가 정제 책임을 가진다.
- 수집 산출물에는 `schema_version`, `crawl_run_id`, checksum을 기록한다.

## 5. 구현 계획

1. 기존 `apidata/*.json` 스키마를 문서화한다.
2. 수집 결과마다 `catalog_manifest.json`을 생성한다.
3. 검색용 텍스트를 `retrieval_chunks.jsonl`로 분리한다.
4. MCP tool 후보를 `api_tool_specs.jsonl`로 만든다.
5. HTML 태그, 엔티티, 깨진 endpoint를 `quality_report.json`에 기록한다.
6. `nara_search`가 상세조회에 필요한 `api_id`, `info`, `endpoints`, `swagger_json`을 안정적으로 찾을 수 있게 보장한다.

## 6. 테스트 계획

- `apidata/*.json` 전체가 JSON parse를 통과한다.
- 필수 필드 누락률이 report에 집계된다.
- 같은 입력에서 manifest checksum이 재현된다.
- `api_tool_specs.jsonl`은 line 단위 JSON으로 읽힌다.
- `retrieval_chunks.jsonl`의 각 chunk가 원 service ID로 역참조된다.

## 7. 완료 기준

- 크롤러 산출물을 `nara_search`가 추가 파서 없이 소비할 수 있다.
- MCP 어댑터가 직접 원본 파일을 읽지 않아도 검색과 상세조회가 가능하다.
- 향후 tool registry 생성에 필요한 `api_tool_specs.jsonl`의 최소 형식이 마련된다.

## 8. 참고할 오픈소스 프로젝트

| 프로젝트 | 참고할 부분 | 적용 방식 |
| --- | --- | --- |
| `scrapy/scrapy` | spider, item pipeline, retry, robots.txt 존중 | 크롤러가 커질 때 구조 참고. 현재 작은 스크립트는 유지 |
| `frictionlessdata/frictionless-py` | tabular data schema, validate, transform | JSONL/CSV 산출물 검증과 report 생성에 참고 |
| `WooilJeong/PublicDataReader` | 국내 공공 API wrapper와 행정 코드 데이터 | 크롤링 대상 보강, API 호출 예시, 코드 정규화 참고 |
| `openapi-generators/openapi-python-client` | OpenAPI 명세에서 client 생성 | `api_tool_specs.jsonl`와 실행 adapter 후보 생성에 참고 |
| `googleapis/mcp-toolbox` | tool catalog를 선언형 파일로 관리 | `api_tool_specs.jsonl` 설계에 참고 |

도입하지 않을 것:

- 단순 수집 단계에서 Scrapy로 전면 재작성하지 않는다.
- Frictionless를 런타임 필수 의존성으로 넣기보다 검증 스크립트 후보로 둔다.
- PublicDataReader를 수집 원천 전체의 대체재로 보지 않는다.

## 9. 참고 자료

- ITWorld MCP 서버 기사: https://www.itworld.co.kr/article/4184249/
- MCP Toolbox for Databases: https://mcp-toolbox.dev/
- MCP 공식 문서: https://modelcontextprotocol.io/docs/getting-started/intro
- Scrapy: https://github.com/scrapy/scrapy
- Frictionless: https://github.com/frictionlessdata/frictionless-py
- PublicDataReader: https://github.com/WooilJeong/PublicDataReader
- openapi-python-client: https://github.com/openapi-generators/openapi-python-client
