# nara_gov24_link_resolver MCP 적용 계획

작성일: 2026-06-20
범위: 독립 기능 프로젝트 `nara_gov24_link_resolver(정부24서비스링크매핑)`

## 1. 목적

`nara_gov24_link_resolver`는 정부24 및 관련 기관 서비스 링크를 공통 ID 체계로 정리하는 데이터 프로젝트다. MCP 적용의 목적은 정부24 로그인이나 신청을 자동화하는 것이 아니라, 검수된 링크 정보를 OpenClaw와 MCP host가 안전하게 조회할 수 있게 하는 것이다.

ITWorld 기사에서 MCP 보안 주의점으로 최소 권한, 수동 승인, 민감정보 보호가 강조된다. 정부24 링크는 실제 행정 처리로 이어질 수 있으므로 read-only link resolver로 유지한다.

## 2. MCP에서 기대하는 역할

직접 MCP 서버가 되지는 않는다. 다만 `nara_openclaw` 또는 `nara_mcp`가 다음 형태로 조회할 수 있는 산출물을 제공한다.

```text
resolve_gov24_link(service_id 또는 scenario_id)
  -> reviewed link 후보 반환
```

또는 resource 형태:

```text
gov24://link/{link_id}
gov24://service/{service_id}
```

## 3. 목표 산출물

| 파일 | 목적 |
| --- | --- |
| `data/output/gov24_service_metadata.jsonl` | 검수 완료 서비스 링크 |
| `data/output/gov24_link_candidates.jsonl` | 검수 전 후보 |
| `data/output/link_resolution_report.json` | 품질 리포트 |

필수 필드:

- `link_id`
- `title`
- `url`
- `link_type`
- `domain_ids`
- `keywords`
- `confidence`
- `review_status`

## 4. 간단하고 강력하게 만드는 결정

- 자동 로그인, 본인인증, 신청서 제출은 하지 않는다.
- `review_status=reviewed` 링크만 OpenClaw의 강한 근거로 사용한다.
- `pending` 링크는 사용자 확인 후보로만 표시한다.
- MCP tool은 링크 조회만 제공하고 상태 변경을 하지 않는다.
- link resolver는 데이터 프로젝트로 유지하고, 실행 판단은 OpenClaw가 한다.

## 5. 구현 계획

1. link output JSONL 스키마를 고정한다.
2. `service_id` 또는 scenario keyword로 link 후보를 찾는 스크립트를 정리한다.
3. `review_status`, `confidence`, `source` 필드를 필수화한다.
4. OpenClaw `linkout` 모드가 reviewed 링크를 우선 소비하도록 계약을 문서화한다.
5. MCP resource로 노출 가능한 URI 규칙을 README에 추가한다.

## 6. 테스트 계획

- output JSONL이 schema validation을 통과한다.
- `review_status=reviewed` 필터가 정상 동작한다.
- 깨진 URL 또는 빈 URL이 report에 잡힌다.
- OpenClaw fixture plan에서 linkout 후보를 찾을 수 있다.
- MCP 조회 후보에는 개인정보나 인증 토큰이 포함되지 않는다.

## 7. 완료 기준

- OpenClaw가 linkout 실행 모드에서 검수된 링크를 사용할 수 있다.
- MCP host는 링크를 조회할 수 있지만 행정 신청을 자동 제출할 수 없다.
- 링크 품질 리포트가 매번 재생성 가능하다.

## 8. 참고할 오픈소스 프로젝트

| 프로젝트 | 참고할 부분 | 적용 방식 |
| --- | --- | --- |
| `linkchecker/linkchecker` | broken link 검사, robots.txt 존중, 다양한 출력 형식 | output 링크 품질 검증 스크립트 후보 |
| `frictionlessdata/frictionless-py` | JSONL/CSV schema validation과 report | link metadata 산출물 검증에 참고 |
| `WooilJeong/PublicDataReader` | 법정동/행정동 코드와 국내 공공데이터 wrapper | 지역 기반 링크 매칭과 입력 정규화에 참고 |
| `scrapy/scrapy` | 링크 후보 수집 spider 구조 | 후보 수집량이 커질 때 참고 |
| `modelcontextprotocol/servers` | read-only resource/tool 경계 | 링크 조회 tool이 실행으로 오해되지 않게 설명하는 데 참고 |

도입하지 않을 것:

- LinkChecker GPL 코드를 내부 코드로 복사하지 않는다. CLI 또는 별도 검증 단계 후보로만 둔다.
- 링크 resolver가 정부24 로그인이나 신청 제출을 수행하지 않는다.
- PublicDataReader를 링크 resolver의 핵심 저장소로 삼지 않는다. 코드/정규화 참고에 제한한다.

## 9. 참고 자료

- ITWorld MCP 서버 기사: https://www.itworld.co.kr/article/4184249/
- MCP 공식 문서: https://modelcontextprotocol.io/docs/getting-started/intro
- MCP 보안 원칙: 최소 권한, 수동 승인, 내부 registry 문서화
- LinkChecker: https://github.com/linkchecker/linkchecker
- Frictionless: https://github.com/frictionlessdata/frictionless-py
- PublicDataReader: https://github.com/WooilJeong/PublicDataReader
- Scrapy: https://github.com/scrapy/scrapy
