# 워크플로우 내보내기 (Flow Export) 구현 계획

- 문서 상태: 구현 반영됨 (2026-07-20) — §4.2 기준선 지원과 §7 후속 논의는 범위 밖 유지
- 작성 기준일: 2026-07-20
- 선행 문서: [`agent_expansion_exploration.md`](agent_expansion_exploration.md) 후보 D
- 소비처 계약: `nara_dashboard(API관계대시보드)/src/data/flowIO.js`
- 보호 대상: `nara_workbench(API통합워크벤치)` 변경 금지, 대시보드 코드는 1차
  범위에서 변경하지 않음

## 1. 결론

에이전트 run의 최종 결과(선택 API + 검증된 관계)를 nara_dashboard가
가져올 수 있는 flow JSON 파일로 변환하는 **PoC 백엔드 후처리 엔드포인트**를
추가한다. Hermes에 노출하는 MCP 도구가 아니므로 도구 예산과 보안 정책에
영향이 없다. 사람이 React Flow 캔버스에서 에이전트 결과를 이어서
검토·편집하는 흐름이 완성된다.

```text
에이전트 run 완료
  ↓
GET /agent/design-runs/{run_id}/flow
  ↓
{query}.flow.json 다운로드
  ↓
nara_dashboard 툴바 "⬆ 가져오기"
  ↓
apiDoc 노드 + 관계 엣지가 캔버스에 배치됨
```

## 2. 소비처 계약 확인 (변경 불가 전제)

`flowIO.js`에서 확인한 사실. 1차 구현은 이 계약을 그대로 따른다.

- 형식: `{format: "nara-dashboard-flow", version: 1, name, exported_at, nodes[], edges[]}`
- `deserializeFlow` 검증: `format`·`version` 일치, `nodes` 배열 존재, 노드
  `id` 필수·중복 금지, `type`은 `KNOWN_NODE_TYPES` 안에 있어야 함
- `apiDoc` 노드 데이터: `{apiId}` — 대시보드 카탈로그(`apiDocMap`)가
  **순수 api_id** (`"15000827"`)로 키를 잡는다. `doc` 내장도 허용되지만
  카탈로그 스키마(`toWorkflowDoc`)와 맞춰야 하므로 1차에서는 `apiId`만 쓴다.
- `sanitizeNodeData`는 런타임 키(`status`, `results`, `output` 등)만
  제거하고 **알 수 없는 키는 보존**한다.
- 엣지는 `id`·`source`·`target`(·핸들)만 직렬화된다. `label`·`style`·`data`는
  버려진다. 대시보드 README도 "가져온 관계 엣지는 일반 엣지가 된다"고
  명시한 알려진 한계다.

### 근거 텍스트 우회

엣지가 관계 근거를 실어 나를 수 없으므로, 관계 근거와 선택 이유는
**apiDoc 노드의 추가 데이터 키**에 넣는다 (`sanitizeNodeData`가 보존).
대시보드 UI가 렌더링하지는 않지만 JSON 원문과 재내보내기에서 유실되지
않는다. 렌더링까지 원하면 대시보드 `flowIO.js`에 엣지 `label`/`data`
보존을 추가하는 후속 변경(§7)이 필요하다.

## 3. 변환 규칙

순수 함수 `app/flow_export.py: design_to_flow(result: DesignResponse, *, name: str) -> dict`.

### 3.1 노드

`result.selected_service_ids` 순서대로 apiDoc 노드를 만든다.

| flow 필드 | 값 | 근거 |
|---|---|---|
| `id` | canonical service_id (`"openapi_new:15000827"`) | 중복 없음, 관계 매핑에 그대로 사용 |
| `type` | `"apiDoc"` | `KNOWN_NODE_TYPES` 포함 |
| `position` | `x = 80 + (i % 3) * 280`, `y = 120 + floor(i / 3) * 240` | 대시보드 `placeSearchResults`와 동일한 격자 |
| `data.apiId` | service_id에서 source 접두어 제거 (`"15000827"`) | `apiDocMap` 키 형식 |
| `data.naraTitle` | `details`에서 찾은 문서명 | 카탈로그 미보유 시 사람이 식별할 근거 |
| `data.naraSelectionNote` | 선택 이유·경고 요약 (에이전트 결과에서 발췌) | §2 근거 텍스트 우회 |
| `data.naraRelationNotes` | 이 노드가 참여한 관계의 `type`+`evidence` 목록 | 엣지 메타데이터 유실 보완 |

`nara*` 접두어는 대시보드 기존 키(`apiId`, `doc`)와의 충돌을 피하기 위한
네임스페이스다.

### 3.2 엣지

`result.relations.relations`의 각 항목에서 만든다. 검색 백엔드
`relations/extractor.py`의 엣지 스키마는 다음과 같다.

```json
{
  "id": "rel:io-chain:openapi_new:A:openapi_new:B",
  "source": "openapi_new:A", "target": "openapi_new:B",
  "type": "same-agency | same-domain | param-overlap | io-chain",
  "evidence": ["응답 addr → 요청 addr"],
  "confidence": 0.6, "status": "derived", "generatedAt": "..."
}
```

| flow 필드 | 값 |
|---|---|
| `id` | 관계의 `id` 그대로 (관계 유형이 id 안에 남는다) |
| `source` / `target` | 관계의 service_id — 노드 `id`와 동일 체계라 매핑 불필요 |

`source`·`target`이 선택 노드 집합에 없는 관계는 제외한다 (`serializeFlow`의
고아 엣지 필터와 같은 규칙). `evidence`·`confidence`는 §3.1의
`naraRelationNotes`로 이동한다.

### 3.3 메타

- `format`: `"nara-dashboard-flow"`, `version`: `1`
- `name`: 질문 앞 60자 (`meta.name` 기본값 규칙과 유사하게 비면 `"나라 에이전트 결과"`)
- `exported_at`: 변환 시각 ISO 8601

관계·계획이 없는 결과(문서 1개, relations skipped)도 노드만으로 유효한
flow가 된다. 계획 본문(`plan`)은 캔버스 노드로 만들지 않는다 —
대시보드 `summaryNode`는 런타임 분석 노드(`maxLength` 설정만 가짐)라
정적 텍스트 운반용이 아니기 때문이다.

## 4. 엔드포인트

### 4.1 `GET /agent/design-runs/{run_id}/flow` (핵심)

- `AgentRunManager.snapshot`으로 run 조회
- 404: run 없음 / 409: `status != "completed"` 또는 `result` 없음
- 200: flow JSON 본문,
  `Content-Disposition: attachment; filename="nara-agent-{run_id 앞 8자}.flow.json"`

### 4.2 `POST /flow/export` (선택, 2차)

`DesignResponse` 본문을 받아 같은 변환을 돌려준다. 기준선 `/design` 결과는
서버에 저장되지 않으므로, 기준선 UI가 자기 결과를 내보낼 때 사용한다.
1차 범위에서는 구현하지 않고 자리만 확보한다.

### 4.3 UI

에이전트 모드 결과 영역에 "대시보드로 내보내기" 버튼 하나. `completed`
상태에서만 활성화하며 §4.1을 링크로 연다. 새 화면·상태 관리는 없다.

## 5. 구현 단계

### 단계 1 — 변환기

- `app/flow_export.py` 순수 함수 구현 (I/O 없음, 단위 테스트 대상)
- `tests/test_flow_export.py`

완료 조건: 아래 테스트(§6) 중 변환기 항목 전부 통과.

### 단계 2 — 엔드포인트와 버튼

- `app/main.py`에 §4.1 라우트 추가
- `static/` 버튼 추가

완료 조건: 실제 에이전트 run → 다운로드 → 대시보드 가져오기에서
`FlowImportError` 없이 노드·엣지가 배치된다 (수동 확인 1회 기록).

## 6. 테스트 계획

- 문서 3개 + 관계 2개 결과 → 노드 3·엣지 2, id·apiId·position 검증
- 문서 1개(관계 skipped) → 노드 1·엣지 0
- 관계의 source가 선택 집합 밖 → 해당 엣지 제외
- service_id 접두어 제거 (`openapi_new:15000827` → apiId `15000827`)
- `naraRelationNotes`에 evidence 문자열이 들어가는지
- 산출 JSON을 flowIO 계약으로 재검증: `format`·`version`·노드 타입·id 중복
  (계약 검증 로직을 테스트 안에 미러링해 대시보드 없이 검사)
- 라우트: 404 / 409(진행 중 run) / 200 헤더·파일명
- 산출물에 검색 결과 원문 전체·API 키가 포함되지 않는지

## 7. 후속 논의 (범위 밖)

- 대시보드 `flowIO.js`에 엣지 `label`·`data.relation` 보존을 추가하면
  가져온 관계 엣지가 점선 근거 엣지로 복원될 수 있다. 대시보드 프로젝트
  변경이므로 별도 결정으로 분리한다 (버전 2 계약 또는 하위 호환 확장).
- `POST /flow/export` 기준선 지원 (§4.2)
- korea100 제도 맥락(후보 E) 도입 시 제도 캔버스 링크를 `naraSelectionNote`에
  포함하는 확장

## 8. 비목표

- Hermes MCP 도구로 노출 (도구 예산·보안 정책 무변경)
- 대시보드·워크벤치 코드 변경
- flow 가져오기(역방향 변환)
- 실행 결과·런타임 필드 직렬화 (flowIO의 `RUNTIME_DATA_KEYS` 원칙 준수)
