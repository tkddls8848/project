# Hermes PoC vs Workbench 비교 검토 — 자연어 검색·다중 조합 기반 창의적 정보 서비스

**작성일:** 2026-07-29
**대상:** `nara_hermes_poc` (8020) vs `nara_workbench(API통합워크벤치)` (8010)
**질문:** API 문서의 자연어 검색과 여러 조합에 따라, 사용자에게 창의적인 정보를 출력할 수 있는 서비스는 무엇인가?

> 이 문서는 구현 계획이 아니라 **코드 근거 기반 평가·의사결정 기록**이다.
> 모든 인용은 저장소 루트 기준 상대경로 `모듈/파일:라인` 형식이다.

> **경로 주석(2026-07-29 재배치 이후):** 본문의 `nara_search(API문서검색)/…` 등은
> 작성 시점 경로다. 현재 경로는 `services/search/…`, `services/combiner/…`,
> `services/crawler/…`, `apps/workbench/…`, `apps/dashboard/…`, `apps/hermes_poc/…`로
> 읽는다. 결론은 재배치와 무관하므로 본문은 그대로 둔다.
> 재배치 계획: `docs/superpowers/plans/2026-07-29-module-layering.md`

---

## 0. 결론 요약

**오늘 사용자용 서비스로 쓸 수 있는 것은 Workbench다. 그러나 어느 쪽도 "창의적 정보 서비스"에 도달하지 못했고, 병목은 두 앱이 아니라 `nara_combiner`의 조합 계약에 있다.**

- **Workbench** — 비기술 사용자가 API 이름을 모른 채 문장으로 검색하고, 후보를 비교·선택하고, 관계 근거를 보고 조합까지 갈 수 있는 유일한 화면. 사용자 서비스의 **얼굴**.
- **Hermes PoC** — 사용자 서비스가 아니라 **플랫폼**. 타입 있는 run envelope, critic, freshness, MCP 도구, flow export는 Workbench에 전혀 없는 자산.
- 두 앱은 경쟁 관계가 아니라 **한 제품의 앞면과 뒷면**이다.

핵심 병목: **`io-chain` 관계 근거가 조합 프롬프트에 구조적으로 도달할 수 없다.** (§5)

---

## 1. 검증 방법

Orca 오케스트레이션으로 codex 기반 에이전트 2기를 병렬 dispatch하여 각 계열을 독립 감사했다.

| 태스크 | 워커 | 분석 범위 | 결과 |
|---|---|---|---|
| `task_0125fe57c012` | `hermes-poc-analyst` | hermes_poc + search + combiner | completed |
| `task_0de8c07bcf4a` | `workbench-analyst` | workbench + search + combiner + dashboard | completed |

- 두 워커 모두 **읽기 전용**으로 제약했고, 실행 후 `git status` 클린을 확인했다.
- 각 워커에게 "자기 진영을 변호하지 말고 사실만 적으라"고 지시하고, 상대 진영이 우월한 지점을 명시적으로 요구했다.
- 두 리포트의 주요 주장은 코디네이터가 코드로 재검증했다. 상충 없이 수렴했다.

**한계:** 서비스를 실제 기동하지 않은 정적 코드 감사다. 데이터 품질, 모델 출력 품질, 운영 부하는 **미검증**이다.

---

## 2. 전제 정정 — Workbench는 dashboard를 사용하지 않는다

당초 전제는 "workbench가 combiner·dashboard·search를 사용한다"였으나, 코드상 **dashboard는 연결되어 있지 않다.**

- 게이트웨이 upstream은 search·combiner 둘뿐이다 — `nara_workbench(API통합워크벤치)/main.py:18-21`
- 실행기 서비스 목록에도 dashboard가 없다 — `nara_workbench(API통합워크벤치)/run.py:31-49`
- 관계 맵은 바닐라 `<svg>`와 자체 `renderGraph`로 재구현했다 — `nara_workbench(API통합워크벤치)/static/app.js:553-669`
- 실제 dashboard는 `@xyflow/react` 기반 별개 앱이다 — `nara_dashboard(API관계대시보드)/package.json:10-13`, `src/App.jsx:381-413`

따라서 README의 "dashboard 핵심 흐름 통합"은 **개념·UX 차용과 자체 재구현**으로 읽어야 한다.

**역설:** dashboard 계약을 실제로 구현한 쪽은 hermes_poc다. `nara_hermes_poc/app/flow_export.py`가 내보내는 `nara-dashboard-flow` v1은 `nara_dashboard(API관계대시보드)/src/data/flowIO.js:4-5`의 `FLOW_FORMAT`/`FLOW_VERSION`과 정확히 일치한다.

---

## 3. 구조 비교 — 투자 방향이 정반대다

| | Hermes PoC | Workbench |
|---|---|---|
| Python 로직 | **1,433 LOC** (agent, critic, freshness, flow_export, orchestrator) | 445 LOC (게이트웨이 184 + 실행기 261) |
| 프론트엔드 | 얇음 (app.js/index.html/styles.css) | **3,604 LOC** (app.js 1,142 / html 359 / css 2,103) |
| 성격 | 검증·오케스트레이션·에이전트 경계 | 프레젠테이션·사용자 상호작용 |

한쪽은 **검증**에, 한쪽은 **표현**에 투자했다. 이것이 두 계열 차이의 본질이다.

---

## 4. 기능 비교 (7축)

| 축 | Hermes PoC | Workbench |
|---|---|---|
| **1. 자연어 검색** | search에 그대로 위임. 질의 재작성·확장 없음 (`app/nara_client.py:90-98`) | 동일 + 벡터 토글·채널 진단 UI 노출 (`static/index.html:90-102`, `static/app.js:311-325`) |
| **2. 문서 선택** | 자동 top-3, 수동은 service_id 직접 입력 (`app/agent.py:287-294`, `static/index.html:27`) | **체크박스 + 선택 칩 + 상세 모달(요청·응답 필드 24행)** (`static/app.js:227-239, 721-805`) |
| **3. 관계 근거 표시** | JSON `pre` 텍스트 (`static/app.js:132-134`) | **SVG 그래프 + evidence·confidence 카드** (`static/app.js:589-613, 678-718`) |
| **4. 관계 → 조합 투입** | **없음** (`app/agent.py:207-229`) | **없음** (`static/app.js:886-901`) |
| **5. 최종 산출물** | `suggestion` 문자열 + 구조화 envelope (`app/schemas.py:24-32, 72-81`) | `suggestion` 문자열, 후속 동작은 복사뿐 (`static/app.js:1098-1105`) |
| **6. 검증 장치** | critic(`pass`/`evidence_gap`/`contradiction`), freshness (`app/critic.py:43-49`, `app/freshness.py:68-103`) | **없음** |
| **7. 재사용·확장** | run_id, SSE, flow export, MCP 도구 5개 (`app/main.py:86-134`, `mcp_server/server.py:18-56`) | 없음 (탭 메모리만, `static/app.js:4-23`) |

### 공통 상한
조합 문서 수는 **최대 3개**이며, UI·API·테스트가 일치한다 — `nara_combiner(API문서조합기)/app/schemas.py:16-18`, `nara_workbench(API통합워크벤치)/static/app.js:2`, `nara_combiner(API문서조합기)/tests/test_compose_api.py:93-108`.

### 검색 엔진은 동일 (nara_search)
두 앱 모두 같은 백엔드를 소비하므로 **검색 품질 차이는 없다.**
- 벡터: 복합 질의를 "및/또는/하고/와/과"로 분리해 하위 의도까지 임베딩, 임계값 0.42 — `nara_search(API문서검색)/backend/search/faiss_retriever.py:14-27`, `backend/core/config.py:14-22`
- 렉시컬: ASCII 단어 + 한글/CJK bigram, 제목 3배·키워드 2배 BM25F 근사 — `backend/search/lexical_retriever.py:18-56, 131-163`
- 융합: 가중 RRF(k=60, 벡터 0.9 / 렉시컬 1.1) — `backend/search/fusion.py:9-46`
- **FAISS가 없어도 렉시컬로 계속 동작한다** — `backend/main.py:131-150`

---

## 5. 핵심 발견 — 창의성의 병목

두 에이전트가 독립적으로 같은 결론에 도달했고, 스키마로 재확인했다.

### `ComposeRequest`는 `{service_ids, question}`만 받는다
`nara_combiner(API문서조합기)/app/schemas.py:16-18`

이것이 결정적이다. 이 저장소에서 가장 가치 있는 자산은 **`io-chain` 관계** — A의 응답 필드가 B의 요청 파라미터로 흘러들어간다는 **방향성 있는 필드 단위 근거**다.

```
evidence = [f"응답 {src['response_fields'][key]} → 요청 {tgt['request_params'][key]}" ...]
```
— `nara_search(API문서검색)/backend/relations/extractor.py:75-86`

이 정보의 가치:
- 사람이 문서를 눈으로 훑어서는 **찾을 수 없는** 조합 가능성이다.
- LLM이 아니라 **규칙으로 도출**되므로 환각이 없다 (`backend/relations/builder.py:19`).
- 공통 파라미터(`serviceKey`, 페이징)는 제외해 노이즈를 걸렀다 (`backend/relations/extractor.py:10-17`).

### 그런데 이 근거가 프롬프트에 도달하지 못한다

LLM이 실제로 보는 것은 이름·기관·분야·설명 300자·키워드 8개·엔드포인트 경로 3개뿐이다 — `nara_combiner(API문서조합기)/app/prompts.py:22-39`. **요청/응답 필드도, 관계 근거도 포함되지 않는다.**

프롬프트는 이렇게 지시한다:

> "개별 API를 단독으로 열거하지 말고, **조합해야만 가능한 흐름**에 집중하세요."
> "필요한 **사용자 입력값**, 확인 조건, 후속 실행 후보를 구분하세요."
> — `nara_combiner(API문서조합기)/app/prompts.py:14-17`

**즉 조합 가능성을 증명하는 데이터와 입력 필드를 주지 않은 채, 그것을 서술하라고 요구한다.** 이는 환각을 유도하는 구조다.

두 앱 모두 관계를 조회해놓고 화면에만 그린 뒤 버린다. Workbench의 "검색 → 관계 검토 → 조합"은 **UX 순서일 뿐 데이터 계보가 아니다** (`nara_workbench(API통합워크벤치)/static/app.js:489-518` → `886-901`).

---

## 6. 신뢰성 장치의 실제 수준

### Hermes critic이 검증하는 것 / 하지 않는 것

**검증한다** (`nara_hermes_poc/app/critic.py:52-166`):
- 선택 ID마다 detail이 존재하는가
- 선택 ID가 검색 결과 또는 사용자 명시 ID에 있는가
- **주장한 관계를 search에 재조회했을 때 동일 edge가 있는가** (`critic.py:120-148`)
- 3개 상한·중복 없음·단계 순서 계약

**검증하지 않는다:**
- `plan.suggestion` 본문의 사실 주장. 제안문을 파싱하는 코드가 **없다**.

따라서 critic은 **"환각 방지"가 아니라 "구조적 모순 탐지"**다. 관계 edge 위조는 잡지만, LLM이 존재하지 않는 입력 필드나 절차를 서술하는 것은 막지 못한다. 또한 critic 실패는 run을 실패시키지 않는 **fail-soft 사후 진단**이다 (`app/agent.py:252-274`).

### freshness는 기본 설정에서 전부 `unverified`
`NARA_INDEX_BUILT_AT` 기본값이 빈 값이므로, 별도 운영 설정 없이는 모든 문서가 `unverified`로 보고된다 — `nara_hermes_poc/app/config.py:31-35`. 추정하지 않고 `unverified`를 반환하는 설계 자체는 옳다 (`app/freshness.py:77-95`).

### evaluation 골든셋은 아무것도 검증하지 않는다
질의 5개와 `expected_domains`만 있고 **러너가 없다** — `nara_hermes_poc/evaluation/golden_queries.json`. 코드 전체에서 이 파일을 읽는 참조가 없다.

### Workbench에는 등가물이 없다
관계 카드에 승인·기각·수정 컨트롤이 없고 (`static/app.js:696-717`), 조합 버튼은 **문서 1개만 있어도, 관계가 0개여도** 활성화된다 (`static/app.js:485-486, 830-837`). 생성 문장에 출처가 결부되지 않는다.

### dashboard에만 있는 승인 게이트
이 저장소에서 **유일한 human-in-the-loop 근거 승인**은 dashboard에 있다 — `nara_dashboard(API관계대시보드)/src/components/RelationProperties.jsx:38` → `status: 'approved'` (`src/data/relationEdges.js:41`). 기각 기능은 코드상 없다. Workbench는 이 능력을 흡수하지 않았다.

---

## 7. "에이전트"의 실체

Hermes PoC의 에이전트 루프는 **모델 주도 루프가 아니다.**

- Python이 `search → top-3 → detail → relations → compose` 순서를 고정한다 — `nara_hermes_poc/app/agent.py:183-229`
- 각 단계에서 Hermes CLI를 띄워 지정 MCP 도구를 정확히 한 번 호출하게 하지만, **그 반환값을 결과에 쓰지 않는다.** 호출 상태만 `run.hermes.calls`에 기록하고(`app/agent.py:276-281`), 실제 결과는 직후 `NaraClient` 직접 호출로 받는다(`app/agent.py:188-221`).
- 검색어 재작성, 후보 판단·교체, 재검색은 **없다** — `docs/hermes_tool_loop_plan.md:41-54`

즉 현재 구현은 **결정형 오케스트레이터 + 단계별 MCP 호출 증명 프로브**다. compose 단계에서는 Ollama 조합이 두 번 실행될 수 있고 최종 `plan`은 후자다(비용·일관성 문제).

MCP 표면 자체(`mcp_server/server.py:18-56`의 도구 5개)는 향후 확장에 좋은 경계이며, 이것이 Hermes 계열의 실질 자산이다.

---

## 8. 운영 관점

### 기동 요구사항 (공통)
- `nara_storage/openapi_new` 데이터 — **fresh clone에는 없다.** crawler 선행 필요 (`CLAUDE.md`)
- 벡터 경로: FAISS 인덱스 + `ko-sroberta-multitask` (없으면 HuggingFace 자동 다운로드)
- 조합: 로컬 Ollama `qwen3.5:4b`, 기본 timeout 210초 (`nara_combiner(API문서조합기)/app/config.py:10-18`)

### degrade 동작
| 결손 | 결과 |
|---|---|
| FAISS/모델/인덱스 없음 | 렉시컬로 검색 지속 (양쪽 동일) |
| Ollama 없음 | 조합만 503, 검색·관계는 유지 (양쪽 동일) |
| Hermes 없음 | `hermes.status=partial`, 결정형 흐름 지속 (Hermes 계열) |
| detail/relations 실패 | **Hermes는 run 전체 실패** — fail-soft 미구현 |

### 영속성
양쪽 모두 없다. Hermes run은 인메모리 dict에 쌓이고 정리되지 않으며 재시작 시 사라진다(`app/agent.py:113-132`). Workbench 상태는 탭 메모리뿐이다(`static/app.js:4-23`).

---

## 9. 부수 발견 — 실제 결함

**Workbench 상단의 "모든 서비스 연결"은 Ollama가 완전히 죽어 있어도 초록으로 표시된다.**

- combiner `/health`는 Ollama 연결을 시도하지 않고 `"ok": True`를 하드코딩한다 — `nara_combiner(API문서조합기)/app/main.py:51-55`
- workbench `_health_one`은 `response.is_success`(HTTP 2xx)만 보고 payload의 `ok`을 판정에 쓰지 않는다 — `nara_workbench(API통합워크벤치)/main.py:66-86`
- search `/health`는 FAISS가 없으면 `ok:false`지만 HTTP 200이다 — `nara_search(API문서검색)/backend/main.py:101-116`

결과적으로 상단 표시는 **HTTP 프로세스 생존**을 뜻할 뿐, 벡터 검색·LLM 생성 준비 완료를 보장하지 않는다.

**부수 발견 2:** combiner는 4,000자 초과 시 `truncated=true`를 반환하지만, Workbench 메타 렌더러는 이 필드를 표시하지 않는다 — `nara_combiner(API문서조합기)/app/main.py:145-158` vs `nara_workbench(API통합워크벤치)/static/app.js:905-931`. 사용자는 계획이 잘렸다는 사실을 알 수 없다.

---

## 10. 권고 (ROI 순)

### 1순위 — 관계 근거를 조합 프롬프트에 주입
`ComposeRequest`에 relations를 추가하고 프롬프트에 io-chain evidence를 포함한다.

- 변경 지점: `nara_combiner(API문서조합기)/app/schemas.py:16-18`, `app/prompts.py:22-39`
- 규모: 각 수 줄
- 효과: **두 앱이 동시에 이득을 본다.** "조합해야만 가능한 흐름"이라는 프롬프트 지시가 처음으로 근거를 갖게 된다. 창의성 측면에서 다른 모든 작업을 합친 것보다 효과가 크다.

### 2순위 — 요청·응답 필드를 프롬프트에 포함
현재 "필요한 사용자 입력값을 쓰라"고 요구하면서 입력 필드를 주지 않는다. 환각 유도 구조를 제거한다.

### 3순위 — `suggestion` 구조화
계획 단계·입력·조건·근거가 스키마 필드가 아니라 한 덩어리 문자열이라 후속 자동화가 불가능하다 — `nara_combiner(API문서조합기)/app/schemas.py:21-31`.

### 4순위 — health 정확도 수정
§9의 결함. 작고 자체 완결적이다.

### 목표 아키텍처
```
Workbench UI (검색·선택·관계 검토)     ← 사용자 접점
        +
Hermes envelope (run_id·critic·freshness·flow export)  ← 검증·재사용
        +
근거를 받는 combiner (relations + fields → 프롬프트)   ← 창의성
        +
Dashboard 승인 게이트 (status: approved)               ← human-in-the-loop
```
hermes_poc는 이미 dashboard flow 계약을 구현했으므로(§2), 이 루프는 닫을 수 있다.

---

## 11. 미검증 사항 (unverified)

정적 코드 감사의 한계로 다음은 확인하지 않았다.

- 실제 검색 적합도·환각률·p95 지연 (골든셋 러너 부재로 측정 수단 자체가 없음)
- 실제 모델(`qwen3.5:4b`) 출력 품질
- 운영 부하·동시 사용자
- 일반 최종 사용자가 GUI 없이 접근할 대화형 CLI·인증 API 클라이언트의 존재
- Hermes·Ollama·MCP subprocess 통합 장애 시나리오

---

## 부록: 워커 리포트 원본

두 codex 워커의 전체 리포트(라인 단위 근거 포함)는 세션 스크래치패드에 생성되었으며 저장소에는 커밋하지 않았다.

- `report_hermes.md` — Hermes PoC 계열 감사
- `report_workbench.md` — Workbench 계열 감사

두 워커 모두 읽기 전용으로 실행했고, 실행 후 저장소는 변경되지 않았다.
