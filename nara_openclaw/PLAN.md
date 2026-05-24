# Nara OpenClaw — 미니 프로젝트 계획서

작성일: 2026-05-24
모체 프로젝트: `d:\project\nara_crawler\` (특히 `docs/SERVICE_PLAN.md` SP6 / `docs/06_workflow_api_discovery.md`)
한 줄 정의: **사용자가 직접 띄워 쓰는** 작은 로컬 서비스로, 공공 API 두세 개를 묶어 "이 조합으로 어떤 서비스가 가능한가"를 LLM이 답해주는 PoC.

---

## 1. 왜 만드는가

`nara_crawler` 본 계획서(SERVICE_PLAN.md)는 9개 서브프로젝트로 쪼개진 큰 그림이다. 그중 **SP6 (Workflow API Discovery)** 의 핵심 아이디어 — "개별 API 문서를 검색하는 것을 넘어, 여러 API를 논리 노드로 연결해 단일 문서로는 알 수 없는 새로운 활용 방안을 도출한다" — 만 떼어내, 노드 에디터·DAG 엔진 같은 무거운 인프라 없이 **단일 LLM 호출**로 가치 검증을 한다.

핵심 가설:
- 가치의 70%는 노드 구조가 아니라 LLM에 넘기는 컨텍스트 품질에 있다 (`06_workflow_api_discovery.md` §"가치의 원천")
- 그 가설을 가장 작은 코드로 빠르게 검증한다

성공 시: SP6 본격 구현(노드 에디터 + DAG 엔진)으로 자연스럽게 흡수
실패 시: 노드 에디터를 만들기 전에 방향을 바꿀 수 있음

---

## 2. nara_crawler와의 관계

```
nara_crawler/        (모체: 데이터 수집·저장·검색)
  data/
    raw_data/ 또는 02_catalog/services.jsonl
              ↓ 읽기 전용
nara_openclaw/       (이 프로젝트: 조합 분석 PoC)
```

규칙:
- **단방향 의존**: `nara_openclaw → nara_crawler/data` 만. 반대 방향 금지.
- `nara_crawler` 코드를 import 하지 않는다. **파일만 읽는다.**
- 데이터 경로는 환경변수(`NARA_DATA_DIR`)로 주입한다.

---

## 3. 기술 스택 (의도적 최소화)

| 구성 | 선택 | 이유 |
| --- | --- | --- |
| 런타임 | Python 3.11+ | nara_crawler와 동일 |
| 웹 프레임워크 | FastAPI | 단일 엔드포인트로 충분 |
| LLM | **Ollama** (로컬, 모델은 `gemma4:e4b` 또는 `qwen2.5:7b` 등) | 외부 API 키 불필요, "직접 실행 서비스" 컨셉 일치 |
| UI | 단일 HTML 페이지 또는 CLI (둘 다 선택 가능) | 노드 에디터 없음 |
| 저장소 | 없음 | 결과 캐시만 파일 1개로 |
| 의존성 | `fastapi`, `httpx`, `uvicorn`, `jinja2` 정도 | requirements.txt 한 화면 이내 |

**의도적으로 빼는 것**:
- 데이터베이스 (PostgreSQL/SQLite 모두 X)
- ChromaDB, FAISS, BM25, DuckDB
- Neo4j
- React Flow, Next.js
- 인증/Rate Limit
- 다중 사용자

---

## 4. 단일 핵심 기능

### 4.1 입력

```
POST /compose
Content-Type: application/json
{
  "service_ids": ["15000001", "15012890", "15000345"],
  "question": "이 API들을 조합하면 어떤 새로운 서비스가 가능한가?"
}
```

또는 CLI:
```
openclaw compose 15000001 15012890 15000345
```

### 4.2 처리

1. `services.jsonl`에서 해당 ID들의 메타데이터(이름·기관·도메인·필드 목록·설명) 로드
2. 도메인 라벨이 모두 동일하면 경고 ("자명한 조합일 수 있음")
3. 프롬프트 구성: 각 API의 스키마와 도메인 레이블을 정제된 형태로 합침
4. Ollama 호출 (`/api/generate` 또는 `/api/chat`, 스트리밍)
5. 결과를 텍스트로 반환

### 4.3 출력

```json
{
  "service_ids": ["15000001", "15012890", "15000345"],
  "domains": ["welfare", "transport", "health"],
  "warning": null,
  "suggestion": "거동 불편 노인 맞춤 병원 이동 지원 서비스가 가능합니다. ...",
  "elapsed_ms": 8421,
  "model": "gemma4:e4b"
}
```

스트리밍 응답도 함께 지원 (`Accept: text/event-stream`) — SERVICE_PLAN.md NDJSON envelope 규약과 호환되게 토큰만 흘려보냄.

---

## 5. 폴더 구조

```
nara_openclaw/
  PLAN.md                     ← 본 문서
  README.md                   ← 사용 방법, 환경변수, 예시
  .env.example                ← NARA_DATA_DIR, OLLAMA_BASE_URL, OLLAMA_MODEL
  requirements.txt
  app/
    __init__.py
    main.py                   ← FastAPI 엔트리, /compose 라우트
    config.py                 ← 환경변수 로드
    loader.py                 ← services.jsonl 로더 (지연 로드 + 메모리 캐시)
    llm.py                    ← Ollama 호출 (스트리밍/논스트리밍)
    prompts.py                ← 프롬프트 템플릿 1~2종
    schemas.py                ← Pydantic 입출력 모델
  cli/
    compose.py                ← 동일 기능 CLI 진입점
  templates/
    index.html                ← 입력창 + 결과 스트림 표시 (선택)
  static/
    style.css
  tests/
    test_loader.py
    test_prompt.py            ← 프롬프트 결정성 검증
    fixtures/
      services_sample.jsonl
```

총 코드량 목표: **800줄 이하** (테스트 제외).

---

## 6. 구현 단계 (5 step, 각 0.5~1일)

각 step은 독립 PR/커밋 단위. step 완료 = "체크리스트 통과 + 다음 step의 입력 준비됨".

### Step 1 — 골격 & 환경
- `requirements.txt`, `.env.example`, `app/config.py`, `app/main.py`(헬스체크만)
- `uvicorn app.main:app` 으로 기동 확인
- README에 "Ollama 사전 설치 + 모델 pull" 명시
- **완료 기준**: `GET /health` 200 응답, `OLLAMA_BASE_URL` 도달 확인

### Step 2 — Loader
- `app/loader.py`: `services.jsonl` (없으면 `raw_data` 폴백) 읽어 dict 캐시
- `get_services(ids: list[str]) -> list[Service]`
- 누락 ID는 에러가 아닌 경고로 처리
- **완료 기준**: 픽스처 3건으로 단위 테스트 통과

### Step 3 — Ollama 클라이언트
- `app/llm.py`: `generate(prompt, stream=True) -> AsyncGenerator[str]`
- 타임아웃, 모델 미존재 시 부팅 차단(SERVICE_PLAN.md SP4 규약과 동일)
- **완료 기준**: `curl`로 토큰 스트림 확인

### Step 4 — 프롬프트 & 라우트
- `app/prompts.py`: 컨텍스트 합치기 1종 ("도메인+필드 정제" 패턴)
- `POST /compose` 라우트 완성 (논스트리밍 우선)
- 도메인 동일 경고 로직
- **완료 기준**: 시드 입력 3종에 대해 "그럴듯한" 응답 텍스트 확보

### Step 5 — UI 또는 CLI
- 단일 HTML 입력창 + EventSource 토큰 스트림 (또는 CLI 선택)
- 시드 입력 버튼 3개 (예: 관광+교통+날씨, 복지+의료+교통, 사업자+자금+업종)
- **완료 기준**: 브라우저에서 한 번 클릭으로 결과 표시

---

## 7. 시드 입력 (검증용)

`README.md`에 동봉:

| # | 조합 | 의도 |
| --- | --- | --- |
| A | 관광지 + 대중교통 + 기상 | 이종 도메인, 좋은 예 |
| B | 복지 수급자 + 의료기관 + 교통 노선 | 이종 도메인, 사회적 가치 |
| C | 관광지 + 관광 코스 | **나쁜 예(자명한 조합)** — 경고가 떠야 함 |

이 3종이 모두 "예상한 종류의 응답"을 내면 PoC 성공.

---

## 8. 데이터 의존 상세

- 1순위: `d:\project\nara_crawler\data\02_catalog\services.jsonl` (SP1 결과물)
- 2순위(fallback): `d:\project\nara_crawler\data\raw_data\*_summary.json`
- 환경변수 `NARA_DATA_DIR`로 루트만 받고 내부에서 자동 탐색
- **읽기 전용 마운트 가정** — openclaw가 nara_crawler 데이터를 절대 쓰지 않음

services.jsonl이 아직 없는 시점(SP1 미완료)에도 동작해야 한다 → loader는 두 경로를 모두 시도.

---

## 9. 비포함 범위 (Out of Scope)

명확히 안 한다:
- 노드 기반 UI (`@xyflow/react` 등)
- DAG 위상 정렬 실행 엔진
- 워크플로우 저장/재실행
- 다중 LLM 라우팅, OpenRouter, Perplexity
- 데이터베이스, 사용자 계정
- 실제 공공 API 호출 (도구화는 본 프로젝트 SP 별도 책임)
- 결제, Rate Limit, 인증

이 모든 것은 SP6 본격 구현 시점으로 미룬다. **openclaw가 검증하는 단 한 가지**: "LLM이 API 메타데이터 조합만 보고 의미 있는 활용 방안을 도출할 수 있는가."

---

## 10. 성공 / 실패 판정

### 성공 (다음 단계로)
- 시드 3종 중 A, B는 그럴듯한 활용 방안 텍스트 응답
- C는 도메인 동일 경고가 표시되거나 응답이 자명함을 사용자가 인지 가능
- 응답 시간 30초 이내 (gemma4:e4b 기준)
- nara_crawler 코드/DB 변경 0건

### 실패 (방향 전환)
- LLM 응답이 어느 조합에서도 자명한 수준에 머무름 → 프롬프트 재설계 1회 시도 후에도 실패 시, "메타데이터 품질 부족"으로 결론 짓고 SP2(Semantic Layer) 선행 필요로 회수

---

## 11. nara_crawler와의 통합 시점

- openclaw가 안정화되고 시드 3종에서 유의미한 결과가 나오면
- SP6의 "PoC (1~2일)" 단계 결과물로 인정
- 노드 에디터·DAG 엔진은 그 다음 단계에서 별도로 추가
- openclaw 자체는 그대로 두고 SP6에 "LLM 분석 노드"로 흡수 (호출 인터페이스만 일치시키면 됨)

---

## 12. 즉시 다음 액션 (체크리스트)

- [ ] `nara_crawler/data/` 안에 services.jsonl 또는 raw_data 존재 확인
- [ ] Ollama 설치 + `ollama pull gemma4:e4b` (또는 다른 로컬 모델 선택)
- [ ] `requirements.txt` 작성 (fastapi, uvicorn, httpx, jinja2, pydantic, python-dotenv)
- [ ] `.env.example` 작성
- [ ] Step 1 착수

---

## 부록 A — 프롬프트 초안

```
당신은 한국 공공 API 활용 컨설턴트입니다.

다음은 사용자가 조합하려는 공공 API들의 메타데이터입니다:

[API 1]
이름: {name}
기관: {agency}
도메인: {domain}
설명: {description}
주요 필드: {fields}

[API 2]
...

질문: 이 API들을 결합하면 어떤 새로운 서비스나 가치를 만들 수 있습니까?

답변 규칙:
- 각 API에 단독으로 적힌 활용은 제외하고, 조합으로만 가능한 것에 집중
- 같은 도메인의 자명한 조합이면 그 사실을 먼저 지적
- 구체적인 사용자 시나리오 1~2개 제시
- 5문장 이내
```

본 프롬프트는 Step 4 진입 시 1회 튜닝.
