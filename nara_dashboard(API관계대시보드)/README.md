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
