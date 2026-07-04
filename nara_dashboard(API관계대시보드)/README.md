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

## 데이터 모드 (local)

현재 대시보드는 **로컬 데이터 모드**로 동작한다. `src/data/apiDocs.js`가
`apidata/*.json`을 빌드 타임에 eager glob으로 번들에 포함하며, 검색·필터·조인은
모두 브라우저 안에서 이 로컬 카탈로그를 대상으로 실행된다. `nara_search`
백엔드 연동은 별도 개발 슬라이스이며, 프록시(`/api/*`)는 검색 보강과 Ollama
채팅에만 쓰인다.

- `apidata/`가 비어 있으면 카탈로그가 빈 상태로 기동한다 (앱은 동작, 검색 결과 0건)
- 번들 크기는 `apidata/` 문서 수에 비례한다 — 대형 청크 경고의 주원인
- **저장 노드는 미구현**이다. 실행 시 `persisted:false`와 미구현 안내를 반환하며
  브라우저 밖에 아무것도 저장하지 않는다

## 테스트

```powershell
npm test          # vitest run
```

- `src/data/__tests__/workflowEngine.test.js` — 노드 실행·topo 순서·출력별 부분 실행,
  join/if/merge/export/save 노드의 성공·오류 경로 (카탈로그는 fixture로 대체)
- `src/data/__tests__/exporters.test.js` — CSV 이스케이프·UTF-8 BOM·헤더, Excel HTML
  이스케이프, JSON export 형식

내보내기 직렬화는 `src/data/exporters.js`의 순수 함수로 분리되어 있다.
CSV는 Excel 호환을 위해 UTF-8 BOM으로 시작하고, XLSX 선택 시 실제 산출물은
Excel 호환 HTML 테이블(`.xls`)이다.

## 프록시 (vite.config.js)

| 경로 | 타겟 | 비고 |
| --- | --- | --- |
| `/ollama/*` | `http://localhost:11434` | 로컬 Ollama |
| `/api/*` | `http://127.0.0.1:8000` | `nara_search` 백엔드 (선행 기동 필요) |

프론트에서 `fetch('/api/search', ...)` 호출 시 nara_search의 `POST /search`로 라우팅됩니다.

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

- `d:\project\nara_search\` — FAISS 벡터 검색 백엔드 (이전 `backend/`)
- `d:\project\nara_crawler\` — 원본 데이터 수집기
- `d:\project\nara_openclaw\` — API 조합 분석 PoC (별도 미니 프로젝트)
