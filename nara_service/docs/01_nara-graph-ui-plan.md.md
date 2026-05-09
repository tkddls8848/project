# nara-graph-ui 실행 계획

> 한국 공공데이터 OpenAPI 정보를 부처/카테고리별로 취합하고, 자연어로 목적에 맞는
> API를 추천하되, "정보 간 관계성"을 1차 화면으로 끌어올려 데이터포털과 차별화하는
> 그래프 인터페이스 프로젝트의 실행 계획.

---

## 1. 프로젝트 개요

### 상위 목표
1. 공공데이터 OpenAPI 사이트에서 부처/카테고리별 API URL과 메타데이터를 취합
2. 자연어 질의를 받아 목적에 맞는 API를 출력
3. 정보 간 관계성을 특별하게 연출하여 새로운 사용자 경험 제공 (차별화 핵심)

### 데이터 백엔드
별도 리포지토리 `tkddls8848/project`의 `nara_crawler`가 데이터 수집·정리 담당.
산출물 위치(예정):
- `02_catalog/services.jsonl`, `agencies.jsonl`, `endpoints.jsonl`, `fields.jsonl`
- `03_semantic/concepts.jsonl`, `aliases.jsonl`, `field_mappings.jsonl`, `service_tags.jsonl`
- `04_output/cross_ref/service_relations.jsonl` (관계 데이터)

### 프런트엔드 (본 프로젝트)
별도 리포지토리 `nara-graph-ui`로 분리. 모의 데이터로 시작하고 실제 JSONL은 추후 연결.

---

## 2. 핵심 차별화 가설

> "공공데이터의 진짜 가치는 단건 API가 아니라 API들 사이의 관계에 있다.
> 데이터포털은 그 관계를 사용자가 직접 발견하게 하지만,
> 이 서비스는 관계를 보여주며 검색을 시작한다."

이 가설이 흔들리면 프로젝트 가치 명제 전체가 흔들린다. 모든 설계 결정은
이 가설을 강화하는 방향으로 정렬한다.

---

## 3. 이전 시도 분석과 교훈

### 시도 내용
API 검색 결과를 노드 블록으로 만들고 다대다 관계(긍정/부정/상위/하위)로 연결한
모달 그래프 + 프롬프트 기반 문장 생성.

### 실패 원인 진단
1. **다대다 구현이 막힘.** UI 프레임워크의 본질적 한계가 아니라 거의 확실히
   데이터 모델 안티패턴(노드 안에 관계 박기, 분리된 useState로 노드/엣지 관리,
   라이브러리 없이 SVG 직접 그리기) 중 하나였을 가능성이 높음.

2. **관계 유형이 너무 추상적.** 긍정/부정/상위/하위는 어떤 도메인에도 들어맞아서
   사용자가 라벨에서 새로운 정보를 얻지 못함. 공공데이터 맥락의 구체 라벨
   (`prerequisite`, `same_concept`, `complementary`, `alternative`)이 필요.

3. **그래프가 모달의 부가 기능이었음.** 검색 → 카드 목록 → 클릭하면 모달 그래프
   라는 흐름은 그래프를 부수물로 만든다. 차별화 핵심이 그래프라면 그래프가
   메인 캔버스여야 한다.

### 본 프로젝트의 대응
- 데이터 모델: 엣지를 별도 컬렉션으로, 단일 상태 저장소(Zustand)로 관리
- 관계 라벨: 도메인 구체 라벨 6종 사용 (`same_concept`, `alternative`,
  `complementary`, `prerequisite`, `broader`, `tagged_as`)
- 인터페이스 위치: 그래프가 메인 캔버스, 카드 목록은 사이드 패널 보조

---

## 4. 타겟 사용자

| 우선순위 | 페르소나 | MVP 포함 |
|---------|---------|---------|
| 1차 | 개발자/데이터 분석가 (자연어 → 호출 가능 API 명세) | O |
| 2차 | 정책/기획 실무자 (도메인 지도, 부처 횡단 비교) | △ (β 단계) |
| 3차 | 일반 시민 (자격/혜택 중심 추천) | X (이후) |

---

## 5. 핵심 UX 모먼트

### 채택 (MVP)
- **M1. 개념 지도 우선 응답.** 질의 → 개념 칩과 도메인 노드 우선, 카드 목록은 보조.
- **M2. 부처 횡단 비교 뷰.** 같은 개념이 부처마다 어떻게 다른 용어로 노출되는지
  한 화면에서 표시. 사일로 해소를 가시 가치로 변환.

### 후속 단계 검토
- **M3. 여정 조립.** `prerequisite`/`complementary` 관계로 단계 다이어그램 자동 생성.
- **M4. 필드 중심 탐색.** 식별자(예: 사업자등록번호) 하나로 부처를 가로질러
  관련 API를 묶음 탐색.
- **M5. 의미 충돌 표시.** 같은 용어를 부처마다 다르게 쓰는 경우 명시적 경고.

### 화면 패턴
- **P1. 3단 응답.** 개념 칩 → API 카드 → 인접 관계 패널 시간차 노출.
- **P2. 카드 내부 메타데이터 노출.** 표준 개념 칩, 부처 원어 칩, 동등 서비스 수.
- **P3. 의도 보드 사이드바.** 사용자의 칩 추가/제거 흐름이 영속적으로 보임.

### 다대다 화면 운영 원칙 (이전 실패 재발 방지)
1. 한 번에 보여줄 부분 그래프를 명시적으로 정의 (초점 노드 + N-hop)
2. 관계 유형별로 시각적 채널 다르게 (선 스타일 우선, 색상은 부처에 양보)
3. 엣지 라벨은 호버에서만
4. 관계 유형 필터 토글을 그래프 위에 영구 배치
5. 부처-도메인-서비스 3단계 줌 레벨 정의

---

## 6. 데이터 모델 결정

### 노드 종류 (3)
- `service` — API 서비스 단위
- `concept` — 표준 개념 (대상/혜택/자격/식별자/도메인)
- `agency` — 부처/기관

### 관계 유형 (6)
| 유형 | 의미 | 출처 |
|------|------|------|
| `same_concept` | 부처는 다르지만 같은 개념의 서비스 | service_relations |
| `alternative` | 대체 가능한 서비스 | service_relations |
| `complementary` | 함께 쓰면 좋은 서비스 | service_relations |
| `prerequisite` | 선행 조건 또는 선행 서비스 | service_relations |
| `broader` | 상위 개념 | concept_relations |
| `tagged_as` | 서비스 → 개념/부처 태그 | service_tags |

### 엣지 ID 정책
결정론적 ID: ``${from_id}__${relation_type}__${to_id}``
- 같은 (from, relation, to) 조합은 항상 같은 ID → 중복이 자연스럽게 막힘
- 멱등 추가 가능

### 인덱스
- `indexByFrom: Map<nodeId, Set<edgeId>>`
- `indexByTo: Map<nodeId, Set<edgeId>>`
양방향 인접 탐색을 O(1)에 가능하게 함. 인덱스는 store 액션 안에서만 갱신됨.

---

## 7. 기술 스택

| 항목 | 선택 | 비고 |
|------|------|------|
| 프레임워크 | React 18 + TypeScript + Vite | SSR 불필요, 헤드리스 검증에 유리 |
| 상태 관리 | Zustand (vanilla + 훅) | Node 검증 스크립트 호환 |
| 그래프 시각화 | React Flow v11+ | 노드 안 풍부한 UI 표현, 다대다 표준 지원 |
| 그래프 분석 | (필요 시) graphology | MVP는 자체 BFS로 충분 |
| 스타일링 | Tailwind CSS | |
| 검증 실행 | tsx | TypeScript 직접 실행 |

### 의도적 제외
- **Next.js**: 1단위 헤드리스 검증에 SSR 이점 없음
- **Cytoscape.js**: 분석 강점이 있으나 React 통합이 어색, 노드 내부 UI 표현이 React Flow 대비 약함
- **Neo4j**: MVP 이후 검토. ID 중심 관계 모델은 이미 Neo4j 전환을 염두에 둠
- **graphology + 의존**: 자체 BFS로 충분

---

## 8. 단계별 구현 계획

### 1단위: 헤드리스 골격 [완료]
**범위:** 데이터 모델, Zustand 단일 저장소, 시나리오 A 모의 데이터, N-hop 부분
그래프 추출, 그래프 불변식 검증.

**파일 구조:**
nara-graph-ui/
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.ts
├── postcss.config.js
├── index.html
├── README.md
└── src/
├── index.css
├── main.tsx                placeholder (2단위에서 교체)
├── types/graph.ts          도메인 타입, 결정론적 엣지 ID
├── store/graphStore.ts     Zustand 단일 저장소 + React 훅
├── data/mockData.ts        시나리오 A: 22 nodes, 43 edges
├── graph/
│   ├── subgraph.ts         N-hop 부분 그래프 추출
│   └── invariants.ts       4가지 불변식 검증
└── scripts/verifyGraph.ts  100회 무작위 변경 검증

**시나리오 A 데이터 (22 nodes, 43 edges):**
- 6 concept (창업 지원, 자금 지원, 사업자 등록, 인허가, 세무 지원, 컨설팅)
- 5 agency (중기부, 신용보증기금, 지자체, 국세청, 행안부)
- 11 service
- 관계 분포: broader 5, tagged_as 22, same_concept 5, prerequisite 6,
  complementary 4, alternative 1

**불변식 (4):**
1. `no_dangling_edges` — 모든 엣지가 존재하는 노드를 참조
2. `index_consistency` — edges Map과 두 인덱스가 정확히 일치
3. `no_self_loops` — from_id ≠ to_id
4. `no_duplicate_edges` — 같은 (from, relation, to) 조합 1개

**합격 기준:**
- `npm run verify`에서 100회 무작위 변경 후 불변식 위반 0건
- `npm run typecheck` 통과
- `extractSubgraph(state, 'concept.startup_support', { hops: 2 })`가 합리적
  크기(노드 12~18) 부분 그래프 반환

### 2단위: React Flow 캔버스 [예정]
**범위:** 화면. 1단위 store 위에 시각화 얹기.

**추가 파일:**
src/
├── components/
│   ├── GraphCanvas.tsx         React Flow 메인 캔버스
│   ├── ControlPanel.tsx        관계 유형 필터, hop 슬라이더, 초점 선택
│   ├── nodes/
│   │   ├── ServiceNode.tsx
│   │   ├── ConceptNode.tsx
│   │   └── AgencyNode.tsx
│   └── edges/
│       ├── SameConceptEdge.tsx 점선
│       ├── PrerequisiteEdge.tsx 화살표 실선
│       ├── ComplementaryEdge.tsx 굵은 실선
│       └── AlternativeEdge.tsx 양방향 화살표
└── App.tsx                     캔버스 + 컨트롤 패널 레이아웃

**추가 의존성:** `reactflow` (또는 v12+의 `@xyflow/react`)

**구현 원칙 (이전 실패 재발 방지):**
- 캔버스가 화면 메인 영역, 모달 아님
- 부분 그래프만 렌더 (초점 노드 + N-hop)
- 관계 유형별 시각적 채널 분리 (선 스타일을 1차 채널로)
- 엣지 라벨은 호버 노출
- 관계 필터 토글 영구 배치

**합격 기준:**
- 시나리오 A 모의 데이터로 캔버스가 노드/엣지 정상 렌더
- hop 슬라이더와 관계 필터 토글이 그래프를 즉시 갱신
- 노드 클릭으로 초점 변경 시 부분 그래프 재계산 정상 작동
- 다대다 관계가 시각적으로 혼잡 없이 구분됨

### 3단위 이후 (개략)
- **3단위.** JSONL 로더 (실제 nara_crawler 산출물 연결), 카드 사이드 패널
- **4단위.** 부처 횡단 비교 뷰 (M2)
- **5단위.** 자연어 질의 → 개념 추출 (LLM 또는 자체 NER)
- **6단위.** 여정 조립 뷰 (M3)
- **7단위.** 필드 중심 탐색 (M4), 의미 충돌 표시 (M5)
- **8단위 이후.** 평가 셋과 정량 지표 (top-k recall, MRR), 사용자 피드백 루프

---

## 9. 단위별 합격 기준 정리

| 단위 | 핵심 합격 기준 |
|------|---------------|
| 1 | 100회 무작위 변경 후 불변식 위반 0건, typecheck 통과 |
| 2 | 시나리오 A 캔버스 정상 렌더, 다대다 관계 시각 구분 |
| 3 | 실제 JSONL 로드 후 1단위 합격 기준 동일하게 통과 |
| 4 | 같은 개념 클러스터의 부처별 용어 차이가 표 1행에 정렬 |
| 5 | 예시 질의 20건에 대해 top-3 정확도 60% 이상 |
| 6 | 창업/의료비 등 시나리오 질의가 단계 다이어그램으로 응답 |

---

## 10. 데이터 백엔드 보강 권고

본 프런트엔드 작업과 별도로, `nara_crawler` 측에서 다음을 확정해야 후속 단위가
작동한다.

1. **`03_semantic/` 자동/반자동 생성 파이프라인의 단계별 계획**
   현재 Stage 4 청킹 계획만 명세되어 있고 의미 매핑 파이프라인 단계가 비어 있음.
   semantic 데이터가 빈약하면 자연어 추천 품질 핵심이 흔들림.

2. **카테고리 분류 체계 결정**
   `taxonomy.json`을 공공데이터포털 분류를 따를지 자체 정의할지 명시 필요.

3. **추천 품질 평가 루프**
   `query_examples.jsonl` 위에 평가 셋과 정량 지표(top-k recall, MRR) 운영
   계획이 빠져 있음.

4. **데이터 신선도 정책**
   `crawl_history.jsonl` 변경 감지 후 다운스트림 재빌드 트리거가 정의되지 않음.

---

## 11. 열린 질문

다음 결정들이 후속 단위에서 필요하다.

1. 자연어 → 개념 추출을 LLM API 의존으로 갈지 자체 NER을 둘지
2. 그래프 시각화를 인터랙티브 탐색까지 가져갈지 정적 다이어그램으로 충분한지
3. 부처 횡단 비교 뷰의 행/열 단위 (서비스 단위 vs 필드 단위)
4. 1차 타겟을 개발자로 좁힌 채로 갈지, 2차 타겟까지 동시에 만족시킬지
5. 사용자 검색 로그/피드백 수집을 언제부터 도입할지

---

## 12. 진행 상태

- [x] 프로젝트 목표 정의
- [x] 차별화 가설 수립
- [x] 이전 실패 진단 및 대응 설계
- [x] UX 모먼트 정의
- [x] 데이터 모델 결정
- [x] 1단위 코드 작성
- [ ] 1단위 합격 기준 검증 (사용자 측 `npm run verify` 실행)
- [ ] 2단위 React Flow 캔버스 작성
- [ ] 3단위 실제 JSONL 연결
- [ ] 그 이후 단위들