# Nara AGUI Demo

**AGUI = Agent UI** 패턴을 한 화면에 보여주는 최소 데모.

LLM·벡터 검색·그래프 DB 없이, **NDJSON 스트리밍 envelope과 동적 레이아웃 라우터**만 따로 분리해 시연합니다.

## AGUI가 무엇인가

두 가지 아이디어의 결합:

### 1. Thinking Steps — 사고 과정 실시간 표시

Claude 채팅의 "thinking" 박스, ChatGPT의 "reasoning" 표시처럼, 에이전트가 단계별로 무엇을 하는지를 좌측 타임라인에 인디케이터로 흘려보낸다.

```
● 쿼리 분석     ✓
● 쿼리 분류     ✓ flow 으로 판단
● 벡터 검색     ⏳ 실행 중…
● 답변 생성     대기
```

### 2. Generative UI — 결과 레이아웃 자동 선택

같은 검색 결과도 쿼리 성격에 따라 다른 UI로 렌더:

| 쿼리 | 레이아웃 | 화면 |
| --- | --- | --- |
| "여행경보 어디서 봐?" | `single` | 단일 큰 카드 |
| "날씨 API 뭐 있어?" | `grid` | 카드 그리드 |
| "외국인 운전면허 따는 절차" | `flow` | 단계 다이어그램 |

분류는 백엔드(여기선 휴리스틱, 실제 프로젝트에선 Ollama)가 판단해 `layout` 이벤트로 통보. 프론트는 `kind` 값에 따라 다른 렌더러 호출.

## 실행

```powershell
cd d:\project\nara_agui
pip install -r requirements.txt
python -m uvicorn main:app --host 127.0.0.1 --port 8001 --reload
```

브라우저:

```
http://127.0.0.1:8001/
```

상단의 시드 버튼 3개를 차례로 눌러보면 같은 검색 흐름이 **세 가지 다른 레이아웃**으로 마운트되는 것을 확인할 수 있습니다.

## 파일 구조

```
nara_agui/
  main.py          ← FastAPI + NDJSON 스트리밍 + Mock 데이터 (~130줄)
  index.html       ← 단일 HTML (CSS + vanilla JS, ~300줄)
  requirements.txt ← fastapi, uvicorn, pydantic
  README.md
```

총 ~450줄. 외부 의존 3개. 무엇이 AGUI인지 한눈에 보이도록 의도적으로 작게 유지.

## NDJSON Envelope 규약

모든 이벤트는 동일 구조:

```json
{ "type": "<event_type>", "ts": <epoch_ms>, "payload": { ... } }
```

### 이벤트 타입

| type | payload | 용도 |
| --- | --- | --- |
| `step` | `{name, status: "running"\|"done", detail?}` | 사고 단계 인디케이터 갱신 |
| `layout` | `{kind: "single"\|"grid"\|"flow", ...데이터}` | 결과 레이아웃 통보 |
| `token` | `{data: string}` | 답변 텍스트 한 글자씩 |
| `done` | `{}` | 스트림 종료 |

### 표준 시퀀스

```
step  query_analysis      running → done
step  query_classify      running → done (detail: "flow 으로 판단")
step  vector_search       running → done (detail: "4건 후보")
layout {kind, ...}
step  answer_generation   running
token (반복)
step  answer_generation   done
done
```

## 무엇이 빠져 있나 (의도)

| 항목 | 실제 프로젝트에선 | 이 데모에선 |
| --- | --- | --- |
| 쿼리 분류 | Ollama gemma4:e4b | 한국어 키워드 휴리스틱 |
| 벡터 검색 | FAISS + ko-sroberta-multitask | Mock 응답 (1·6·4건) |
| 답변 생성 | LLM 스트림 | 미리 작성된 텍스트를 글자씩 |
| Flow 그래프 | Neo4j 시드 쿼리 | 하드코딩된 4 노드 |
| 노드 에디터 | React Flow (@xyflow/react) | 세로 정렬 + 화살표 |

LLM/DB가 빠져도 **AGUI 패턴 자체**(스트림 envelope + 단계 타임라인 + 동적 레이아웃)는 그대로 작동합니다. 이 데모의 목적은 그 패턴을 분리해서 보여주는 것.

## 다음 단계 (실제 프로젝트 통합)

이 데모의 envelope과 레이아웃 라우터를 `nara_search` 백엔드에 흡수하려면:

1. `main.py`의 `classify()`를 Ollama 호출로 교체
2. Mock 데이터를 FAISS 검색 결과 + Neo4j 그래프로 교체
3. 답변 토큰을 LLM 스트림으로 교체
4. envelope·이벤트 타입은 그대로 유지 (프론트는 무수정)

자세한 계획은 `nara_crawler/docs/SERVICE_PLAN.md` §7~8 (SP4, SP5) 참고.

## 관련 프로젝트

- `nara_search/` — FAISS 벡터 검색 백엔드 (이 데모가 흡수될 후보)
- `nara_dashboard/` — React Flow 노드 에디터 (Flow 레이아웃의 정식 구현)
- `nara_crawler/` — 원본 OpenAPI 데이터 수집기
