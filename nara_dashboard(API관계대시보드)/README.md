# Nara Dashboard

React Flow 기반 노드 에디터 프론트엔드. **검색 기능은 별도 프로젝트 `nara_search`로 분리되었습니다.**

## 폴더 구조

```
nara_dashboard/
  src/                  ← Vite + React + React Flow
  doc/                  ← 설계 문서
  index.html
  vite.config.js        ← /ollama, /api 프록시
  package.json
```

검색 백엔드, 데이터(apidata), 임베딩 모델은 더이상 이 디렉터리에 없습니다. `d:\project\nara_search\` 참고.

## 실행

```powershell
cd d:\project\nara_dashboard
npm install
npm run dev
```

Vite dev 서버: `http://localhost:5173`

## 데이터 모드 (backend)

카탈로그는 `nara_search` 백엔드에서 런타임 로딩한다 (`GET /api/catalog`,
vite 프록시 → 127.0.0.1:8000). 빌드 타임 eager 번들은 제거되었다.

- 백엔드 미기동: 상단에 연결 오류 배너 + 빈 카탈로그로 동작 (앱은 죽지 않음)
- **자연어 질의 바**: `/api/search`(FAISS+BM25) → 결과를 apiDoc 노드로 자동 배치,
  `/api/relations` → 노드 간 근거 점선 엣지 표시. 엣지 클릭 → 근거 확인·승인(실선 확정)
- **⚡ 조합 제안**: apiDoc 노드를 선택하고 툴바 버튼 → `nara_combiner /compose`
  제안을 우측 패널에 표시 (프록시 `/combiner` → 127.0.0.1:8003)
- 전체 기동: 저장소 루트의 `..\start-all.ps1`

알려진 한계: flow JSON 내보내기는 엣지의 관계 메타데이터(label/근거)를 직렬화하지
않으므로, 가져온 관계 엣지는 일반 엣지가 된다.

## 워크플로우 저장·공유 (flow JSON)

Node-RED의 flow export/import 패턴을 따라 워크플로우 정의를 JSON 파일로
내보내고 다시 가져올 수 있다.

- 툴바 **⬇ 내보내기** / 저장 노드 실행 → `{이름}.flow.json` 다운로드
- 툴바 **⬆ 가져오기** → 파일 선택으로 캔버스 교체
- 형식: `{format: "nara-dashboard-flow", version: 1, name, exported_at, nodes[], edges[]}`
- 실행 결과(status/results/output 등 런타임 필드)는 저장하지 않고 노드
  설정과 연결만 직렬화한다 (`src/data/flowIO.js`)
- 가져오기 시 format/version/노드 타입을 검증하고, 없는 노드를 가리키는
  연결은 버린다. 실패하면 원인을 알림으로 표시한다

## 테스트

```powershell
npm test          # vitest run
```

- `src/data/__tests__/workflowEngine.test.js` — 노드 실행·topo 순서·출력별 부분 실행,
  join/if/merge/export/save 노드의 성공·오류 경로 (카탈로그는 fixture로 대체)
- `src/data/__tests__/exporters.test.js` — CSV 이스케이프·UTF-8 BOM·헤더, Excel HTML
  이스케이프, JSON export 형식
- `src/data/__tests__/flowIO.test.js` — flow JSON 직렬화/역직렬화 왕복, 런타임 필드
  제거, format/version/타입 검증, dangling 엣지 제거

내보내기 직렬화는 `src/data/exporters.js`의 순수 함수로 분리되어 있다.
CSV는 Excel 호환을 위해 UTF-8 BOM으로 시작하고, XLSX 선택 시 실제 산출물은
Excel 호환 HTML 테이블(`.xls`)이다.

## 프록시 (vite.config.js)

| 경로 | 타겟 | 비고 |
| --- | --- | --- |
| `/ollama/*` | `http://localhost:11434` | 로컬 Ollama |
| `/api/*` | `http://127.0.0.1:8000` | `nara_search` 백엔드 (선행 기동 필요) |
| `/combiner/*` | `http://127.0.0.1:8003` | `nara_combiner` 조합 제안 API (prefix 제거 rewrite) |

프론트에서 `fetch('/api/search', ...)` 호출 시 nara_search의 `POST /search`로 라우팅됩니다.
마찬가지로 `fetch('/combiner/compose', ...)` 호출은 nara_combiner의 `POST /compose`로 라우팅됩니다.

## 의존 서비스 기동 순서

1. (필요 시) Ollama 기동 — 채팅 모달용
2. (필요 시) `nara_search` 백엔드 기동 — 문서 검색용
   ```powershell
   cd d:\project\nara_search
   .\backend\run_server.ps1
   ```
3. 본 프론트엔드 기동 (`npm run dev`)

대시보드 단독으로도 동작 가능 (검색·Ollama 호출만 실패). 프록시 타겟이 없으면 해당 fetch가 502/connection refused로 끝납니다.

## 관련 프로젝트

- `d:\project\nara_search(API문서검색)\` — 검색·카탈로그·관계 API (FAISS+BM25, `:8000`)
- `d:\project\nara_combiner(API문서조합기)\` — 조합 제안 API (`:8003`)
- `d:\project\nara_crawler\` — 원본 데이터 수집기
- `d:\project\archive\` — 더 이상 유지되지 않는 서브프로젝트 보관 (`nara_openclaw`, `nara_gov24_link_resolver` 등)
