# 프로젝트 전체 지도 (SSoT)

이 저장소는 한국 공공데이터(나라장터/data.go.kr) API 문서를 수집·검색·조합하는
파이프라인형 모듈 모음과, 별개 제품인 korea100으로 구성된다. 새 세션은 이 문서로
모듈 관계와 활성/폐기 상태를 파악한 뒤 각 모듈의 README를 읽는다.

## 모듈 지도

데이터 흐름 (실선 = 파일, HTTP = 런타임 호출):

```
data.go.kr ──크롤링──> nara_crawler ──JSON──> nara_storage/ (레포 루트, gitignore됨)
                                                  │
                                    ┌─────────────┴─────────────┐
                                    ▼                           ▼
                          nara_search (:8000)          nara_combiner (:8003)
                          임베딩+FAISS 검색 백엔드      LLM 조합 제안 (Ollama)
                                    │                           │
                    ┌───── HTTP ────┼───────── HTTP ────────────┤
                    ▼               ▼                           ▼
        nara_dashboard (:5173)   nara_workbench (:8010)   nara_hermes_poc (:8020)
        React Flow 노드 에디터    통합 게이트웨이(한 화면)   MCP/에이전트 검증용 PoC
```

| 모듈 | 역할 | 비고 |
| --- | --- | --- |
| `nara_crawler(API문서크롤러)` | data.go.kr 문서 크롤링 → `nara_storage/`에 JSON 저장 | 파이프라인의 시작점 |
| `nara_search(API문서검색)` | SentenceTransformer(ko-sroberta) + FAISS 벡터 검색 백엔드 | 포트 8000, 데이터는 `../nara_storage/openapi_new/` |
| `nara_combiner(API문서조합기)` | API 조합 제안·행정 서비스 계획 초안 생성 | 포트 8003, 실행/승인/감사로그는 명시적 범위 밖 |
| `nara_dashboard(API관계대시보드)` | React Flow 관계 맵 프론트엔드 | 포트 5173, search/combiner에 프록시 의존 |
| `nara_workbench(API통합워크벤치)` | search+dashboard+combiner를 한 화면·한 진입점으로 통합 | 포트 8010, 기존 코드 복사 없이 HTTP 게이트웨이 방식 |
| `nara_hermes_poc` | Hermes 에이전트/MCP 연동 검증용 독립 PoC | 포트 8020, search·combiner를 HTTP 소비자로만 사용 |
| `korea100` | 대한민국 제도 187개 분석 공개 웹서비스 (별개 제품) | 나라 파이프라인과 무관, GitHub Pages 배포 |
| `docs/superpowers` | 통합·리팩터링 계획/설계 문서 (의사결정 기록) | 날짜 접두 파일명 |

## 활성 / 폐기 구분

- **활성**: 위 표의 모든 모듈. 현재 무게중심은 `nara_workbench`(통합 UI)와
  `nara_hermes_poc`(에이전트 루프 확장)이다.
- **보류(archive/)**: 건드리지 말 것. 부활시키려면 사유 확인 먼저.
  - `nara_gov24_link_resolver(정부24서비스링크매핑)` — 정부24 링크 매핑 시도, 보류.
  - `nara_openclaw(행정서비스실행기)` — 실행기 프로젝트. combiner가 "계획 초안까지만"으로
    범위를 좁히면서 실행 기능 전체가 여기로 보류됨. 실제 행정 API 실행·자동 제출은
    전 모듈에서 의도적으로 제외된 범위다.
- `.gitignore` 머리말에 나오는 `nara_relist`, `nara_agui`는 과거 모듈명이며 현재
  저장소에 존재하지 않는다.

## 코드만으로 알 수 없는 것들

### 데이터 루트가 레포 밖에 있다
- 모든 크롤링 산출물은 레포 루트의 `nara_storage/`에 저장되며 **gitignore 대상**이다.
  각 모듈 README의 `../nara_storage/`는 모듈 디렉터리 기준 상대경로다.
- 따라서 **fresh clone에는 데이터가 없다.** search/combiner를 띄우기 전에
  crawler를 먼저 실행해 `nara_storage/openapi_new/{api_id}.json`을 만들어야 한다.
  스키마: `api_id, info, endpoints, swagger_json` (같은 api_id 재크롤링 시 덮어씀).

### 개발 환경은 Windows
- 원 개발 환경은 Windows PowerShell (`D:\project\`)이다. README의 실행 명령이
  PowerShell 기준인 이유. 리눅스 세션에서는 경로·활성화 스크립트를 치환할 것.
- 전체 기동 스크립트 `start-all.ps1`은 README에서 참조되지만 **git에 추적되지 않는다**
  (로컬 머신에만 존재). 클론 환경에서는 각 서비스를 개별 기동해야 한다.

### 외부 API·모델 특이사항
- **data.go.kr 크롤링**: 공식 API가 아니라 HTML/CSV 스크래핑이다. OpenAPI 문서는
  페이지에 인라인된 `swaggerJson`을 추출하고, fileData는 HTML에 임베드된
  `atchFileId`로 다운로드 URL을 조립한다. 사이트 마크업이 바뀌면 크롤러가 조용히
  깨질 수 있다.
- **serviceKey**: 코드·테스트에 등장하는 `serviceKey`는 수집된 API 문서의
  요청 파라미터 필드명일 뿐이다. **이 저장소는 실제 공공데이터 인증키를 보유하지도,
  실제 API를 호출하지도 않는다** (문서 메타데이터만 다룸).
- **LLM은 로컬 Ollama**: combiner 등은 `OLLAMA_BASE_URL`(기본
  `http://localhost:11434`), `OLLAMA_MODEL`(기본 `qwen3.5:4b`)에 의존한다.
  Ollama 미기동 환경에서는 LLM 경로가 실패하므로 비-LLM 경로로 테스트할 것.
- **임베딩 모델**: `nara_search/models/ko-sroberta-multitask/`가 없으면 최초 실행 시
  자동 다운로드된다(네트워크 필요). 테스트는 fixture 기반이라 모델 없이 돈다.
- **korea100의 법령 인용 원칙**: 원문 확인 못 한 인용은 추정하지 않고 `unverified`로
  표기한다. 콘텐츠 수정 시 이 검증 원칙(README 참조)을 깨지 말 것.
  `korea100/web/`에는 자체 CLAUDE.md(→AGENTS.md)가 있다.

### 포트 계약
8000(search) · 8003(combiner) · 8010(workbench) · 8020(hermes PoC) · 5173(dashboard dev).
workbench 실행기는 8000/8003이 이미 떠 있으면 기존 프로세스를 재사용한다.
