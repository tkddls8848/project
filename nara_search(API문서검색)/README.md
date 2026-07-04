# Nara Search

공공데이터 OpenAPI 문서를 SentenceTransformer로 임베딩하고 FAISS로 벡터 검색하는 **백엔드 서비스**.

## 폴더 구조

```
nara_search/
  backend/
    __init__.py
    main.py              ← FastAPI 엔트리 (GET /, /health, /search, /build, ...)
    core/
      config.py          ← BASE_DIR = nara_search/, 경로 계약, ensure_local_model()
      service_id.py      ← service_id 정규화 계약 ({source}:{api_id})
      schemas.py         ← 공통 Pydantic 스키마
    catalog/
      data_loader.py     ← 카탈로그/문서 JSONL 로더
      document_builder.py
      detail_service.py  ← 상세조회 (catalog 우선, 평면 apidata fallback)
    search/
      faiss_retriever.py ← SentenceTransformer + FAISS 검색 (지연 import)
    indexing/
      index_builder.py   ← 백그라운드 인덱스 빌드 (4단계 진행 보고)
    requirements.txt
  tests/                 ← pytest (fixture apidata 기반, 무거운 의존성 불필요)
  frontend/              ← 단독 사용용 vanilla JS UI (index.html, app.js, styles.css)
                          URL 마운트는 /static (변경 없음)
  apidata/               ← OpenAPI JSON ({api_id}_{date}.json, 평면 3,526건)
  models/
    ko-sroberta-multitask/  ← 임베딩 모델 (없으면 자동 다운로드)
  storage/               ← (런타임 생성) faiss.index, metadata.jsonl
```

## 사전 준비

### 데이터

`apidata/*.json`. 스키마: `api_id`, `info`, `endpoints`, `swagger_json` (data.go.kr 크롤러 출력 포맷). React 소스의 `src/data` 같은 폴더와 혼동을 피하기 위해 `data/`가 아닌 `apidata/`로 둠.

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
| GET | `/` | `frontend/index.html` 반환 (단독 UI) |
| GET | `/health` | 인덱스 상태, 데이터 경로, 빌드 상태, `diagnostics` (apidata/index/metadata/model 존재 여부) |
| POST | `/search` | 자연어 검색. body: `{query, top_k, use_vector}` |
| POST | `/build` | 백그라운드 인덱스 빌드 트리거 |
| GET | `/build/status` | 빌드 진행률 (4단계: 파일탐색→파싱→임베딩→저장) |
| GET | `/static/*` | 정적 파일 |
| GET | `/services/{service_id:path}` | 서비스 상세조회 (아래 참고) |

CORS: 전체 오리진 허용 (`allow_origins=["*"]`, GET/POST만).

## service_id 계약

정식 형식은 `{source}:{api_id}` (예: `openapi_new:15000827`)이며 `/search` 결과의
`service_id`를 `/services/{service_id}`에 그대로 전달하면 성공해야 한다.

| 입력 | 동작 |
| --- | --- |
| `openapi_new:15000827` | 정식 형식. 그대로 조회 |
| `15000827` (순수 숫자 api_id) | Search가 `openapi_new:` prefix로 정규화 |
| `filedata:15000827` (미지원 source) | `400` + `error_code: UNSUPPORTED_SOURCE` |
| `abc` 등 형식 위반 | `400` + `error_code: INVALID_SERVICE_ID` |
| 형식은 유효하나 미존재 | `404` + `error_code: NOT_FOUND` |
| 데이터 소스 미준비 (catalog·apidata 모두 없음) | `503` + `error_code: SERVICE_UNAVAILABLE` |

정규화는 Search만 담당한다 (`backend/core/service_id.py`). 다른 프로젝트는 받은
정식 ID를 재해석하지 않고 그대로 전달한다.

오류 응답 형식:

```json
{"ok": false, "error_code": "NOT_FOUND", "message": "service_id not found"}
```

## 상세조회 데이터 소스

`/services/{service_id}`는 두 소스를 순서대로 시도한다 (`detail_source` 필드로 표시).

1. **catalog** — `data/02_catalog/*.jsonl` 등 카탈로그 산출물이 있으면
   `DataRepository` + `DocumentBuilder` 사용 (endpoint/field/mapping 포함 상세)
2. **apidata_flat** — 카탈로그가 없으면 평면 `apidata/{api_id}_{date}.json`을 직접
   파싱해 최소 계약(name, description, provider_agency_name, category, endpoints,
   request_fields, response_fields, source)을 채운다

응답의 `raw_path`/`refined_path`는 로컬 절대 경로 대신 프로젝트 기준 상대 경로다.

## 외부 소비자와의 관계

- **nara_dashboard** (React Flow 대시보드): `vite.config.js`에 `/api/* → http://127.0.0.1:8000` 프록시 설정 → 프론트에서 `fetch('/api/search', ...)` 호출 시 본 서비스로 라우팅
- **nara_crawler**: 직접 의존 없음. apidata는 별도로 채워야 함 (크롤러 출력 복사 또는 재크롤)

## 환경 변수

모든 경로는 기본값이 `BASE_DIR` 기준이며 다음 환경변수로 재지정할 수 있다.

| 변수 | 기본값 | 용도 |
| --- | --- | --- |
| `NARA_SEARCH_APIDATA_DIR` | `apidata/` | 평면 OpenAPI JSON |
| `NARA_SEARCH_STORAGE_DIR` | `storage/` | faiss.index, metadata.jsonl |
| `NARA_SEARCH_MODEL_DIR` | `models/ko-sroberta-multitask/` | 임베딩 모델 |
| `NARA_SEARCH_DATA_DIR` | `data/` | 카탈로그 산출물 루트 (02_catalog/03_semantic/04_output/minimal) |

## 테스트

```bash
pip install pytest httpx
python -m pytest tests -q
```

테스트는 faiss·sentence-transformers·실제 데이터 없이 실행된다.
fixture apidata(`tests/fixtures/apidata/`)로 상세조회 계약을, monkeypatch로
검색 envelope과 오류 계약을 검증한다. 인덱스·모델·카탈로그가 없어도 앱은
기동하며 `/health`의 `diagnostics`로 무엇이 없는지 진단할 수 있다.
