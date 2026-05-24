# Nara Search

공공데이터 OpenAPI 문서를 SentenceTransformer로 임베딩하고 FAISS로 벡터 검색하는 **독립 백엔드 서비스**.

원래 `nara_crawler/stage99_service`에 있었고, 한 차례 `nara_dashboard/backend/`로 이관됐다가, 검색 서비스만 단독 프로젝트로 다시 분리되었습니다.

## 폴더 구조

```
nara_search/
  backend/
    __init__.py
    main.py              ← FastAPI 엔트리 (GET /, /health, /search, /build, ...)
    config.py            ← BASE_DIR = nara_search/, ensure_local_model()
    faiss_retriever.py   ← SentenceTransformer + FAISS 검색
    index_builder.py     ← 백그라운드 인덱스 빌드 (4단계 진행 보고)
    run_server.ps1
    requirements.txt
    (참고: data_loader/cache_builder/lexical/ollama_retriever/ranker/retriever/schemas/document_builder
           — main.py가 import하지 않는 이전 작업물. 추후 활용 가능)
  frontend/              ← 단독 사용용 vanilla JS UI (index.html, app.js, styles.css)
                          URL 마운트는 /static (변경 없음)
  data/
    apidata/             ← OpenAPI JSON ({api_id}_{date}.json, 평면 3,526건)
  models/
    ko-sroberta-multitask/  ← 임베딩 모델 (없으면 자동 다운로드)
  storage/               ← (런타임 생성) faiss.index, metadata.jsonl
```

## 사전 준비

### 데이터

`data/apidata/*.json`. 스키마: `api_id`, `info`, `endpoints`, `swagger_json` (data.go.kr 크롤러 출력 포맷).

### 모델

자동 다운로드. `config.ensure_local_model()`이 모델 디렉터리가 비어있으면 HuggingFace Hub에서 `jhgan/ko-sroberta-multitask` (~2.5GB) 다운로드 → `models/ko-sroberta-multitask/`에 저장.

수동 다운로드도 가능:

```powershell
python -c "from huggingface_hub import snapshot_download; snapshot_download('jhgan/ko-sroberta-multitask', local_dir='models/ko-sroberta-multitask')"
```

## 실행

```powershell
cd d:\project\nara_search
pip install -r backend\requirements.txt

# 방법 1: PowerShell 스크립트
.\backend\run_server.ps1

# 방법 2: 직접 실행
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

`http://127.0.0.1:8000/` 접속 → 단독 검색 UI. 처음 한 번 우상단 **"인덱스 빌드"** 클릭 (또는 `curl.exe -X POST http://127.0.0.1:8000/build`).

빌드 완료 후 `storage/faiss.index`, `storage/metadata.jsonl` 생성, retriever 자동 reload.

## 엔드포인트

| Method | Path | 설명 |
| --- | --- | --- |
| GET | `/` | `backend/static/index.html` 반환 (단독 UI) |
| GET | `/health` | 인덱스 상태, 데이터 경로, 빌드 상태 |
| POST | `/search` | 자연어 검색. body: `{query, top_k, use_vector}` |
| POST | `/build` | 백그라운드 인덱스 빌드 트리거 |
| GET | `/build/status` | 빌드 진행률 (4단계: 파일탐색→파싱→임베딩→저장) |
| GET | `/static/*` | 정적 파일 |
| GET | `/services/{service_id:path}` | 현재 404 (TODO) |

CORS: 전체 오리진 허용 (`allow_origins=["*"]`, GET/POST만).

## 외부 소비자와의 관계

- **nara_dashboard** (React Flow 대시보드): `vite.config.js`에 `/api/* → http://127.0.0.1:8000` 프록시 설정 → 프론트에서 `fetch('/api/search', ...)` 호출 시 본 서비스로 라우팅
- **nara_crawler**: 직접 의존 없음. apidata는 별도로 채워야 함 (크롤러 출력 복사 또는 재크롤)

## 환경 변수

현재 사용 안 함. 모든 경로는 `backend/config.py`에서 `BASE_DIR` 기준 계산. 다른 위치에 데이터/모델을 두려면 config.py를 직접 수정하거나 환경변수 기반으로 리팩토링 필요.
