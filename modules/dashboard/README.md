# Nara Dashboard

React Flow 기반 API 워크플로 편집기다. Search(`:8000`)에서 카탈로그·검색·관계를
읽고 Combiner(`:8003`)에서 조합 제안을 받는다.

## 실행

```powershell
cd C:\project\modules\dashboard
npm install
npm run dev
```

Vite 개발 서버는 `http://localhost:5173`에서 실행된다.

- `/api/*` → `http://127.0.0.1:8000`
- `/combiner/*` → `http://127.0.0.1:8003`
- `/ollama/*` → `http://localhost:11434`

검색 결과를 API 노드로 배치하고, 관계를 엣지로 검토하며, 선택한 최대 3개 API의
조합 제안을 볼 수 있다. flow는 `nara-dashboard-flow` v1 JSON으로 가져오고 내보낸다.

## 테스트

```powershell
npm test
```
