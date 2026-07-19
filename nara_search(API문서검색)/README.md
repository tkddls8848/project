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
  models/
    ko-sroberta-multitask/  ← 임베딩 모델 (없으면 자동 다운로드)
  storage/               ← (런타임 생성) faiss.index, metadata.jsonl
```

데이터는 저장소 공통 루트 ../nara_storage/openapi_new/{api_id}.json 에서 읽는다 (NARA_SEARCH_APIDATA_DIR로 오버라이드).

## 사전 준비

### 데이터

`../nara_storage/openapi_new/*.json` ({api_id}.json 평면 — nara_crawler 산출물). 스키마: api_id, info, endpoints, swagger_json.

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

# (선택) GPU 빌드: NVIDIA GPU + 드라이버가 있는 환경에서만.
#   CUDA 지원 torch를 추가 설치한다. requirements-gpu.txt 안의 cu124를 드라이버에 맞게 조정.
# pip install -r backend\requirements-gpu.txt

# 방법 1: PowerShell 스크립트
.\backend\run_server.ps1

# 방법 2: 직접 실행
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

`http://127.0.0.1:8000/` 접속 → 단독 검색 UI. 처음 한 번 우상단 **"빌드(CPU)"** 또는 **"빌드(GPU)"** 클릭
(또는 `curl.exe -X POST http://127.0.0.1:8000/build -H "Content-Type: application/json" -d "{\"device\":\"gpu\"}"`).
GPU 빌드는 CUDA 지원 torch가 설치돼 있어야 하며, 없으면 안내 메시지가 뜨고 빌드가 시작되지 않는다.

빌드 완료 후 `storage/faiss.index`, `storage/metadata.jsonl` 생성, retriever 자동 reload.

### WSL2에서 GPU 빌드 실행

Windows에서 GPU 빌드를 쓰는 가장 깔끔한 경로는 WSL2다. **Linux에서는 기본 PyPI `torch` 휠이 이미 CUDA 빌드**라, 별도 `requirements-gpu.txt` 없이 기본 requirements만으로 GPU torch가 설치된다.

전제 조건:
- NVIDIA GPU + **Windows 호스트**에 최신 NVIDIA 드라이버(WSL 지원 포함). WSL 안에는 드라이버를 따로 설치하지 않는다 — 호스트 드라이버가 `libcuda`를 제공한다.
- WSL2(WSL1 아님) + 배포판(Ubuntu 등).

```bash
# WSL(Ubuntu) 안에서
nvidia-smi                          # GPU가 보이는지 먼저 확인

cd /mnt/c/project/nara_search       # 또는 WSL 홈으로 프로젝트 복사(권장, I/O 빠름)
python3 -m venv venv                # Windows venv/ 재사용 불가 — Linux venv 새로 생성
source venv/bin/activate
pip install -r backend/requirements.txt   # torch가 CUDA 빌드로 설치됨

python -c "import torch; print(torch.cuda.is_available())"   # True 여야 함

uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

`torch.cuda.is_available()`가 `True`면 브라우저에서 **빌드(GPU)** 버튼이 그대로 동작한다(백엔드 `resolve_device()`는 OS와 무관하게 CUDA 가용성만 확인). `faiss-cpu`는 그대로 두면 되며, GPU 가속되는 부분은 임베딩 단계다.

## 관계·카탈로그 API

- `GET /catalog` — 대시보드용 경량 카탈로그 (문서별 name/provider/category/fields/endpoints)
- `GET /relations?ids=15000001,15000003` — 요청 ID 간 derived 관계
  (same-agency / same-domain / param-overlap / io-chain, evidence·confidence 포함)
- `python -m backend.relations.builder` — apidata 전량의 param-overlap·io-chain을
  `storage/relations.jsonl`로 프리컴퓨트 (배치, 수 분 소요 가능)

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

## 하이브리드 검색

`POST /search`는 두 채널을 함께 사용한다.

| 채널 | 구현 | 필요 조건 |
| --- | --- | --- |
| vector | SentenceTransformer + FAISS | 인덱스·모델 (POST /build) |
| lexical | BM25 + CJK 문자 bigram | 없음 (metadata.jsonl 또는 apidata 스캔) |

- 두 채널 모두 결과가 있으면 **가중 RRF**(Reciprocal Rank Fusion, k=60)로
  순위를 융합한다. 기본 가중치는 lexical 1.1, vector 0.9로 정확한 키워드
  일치를 우선한다. 이때 `score`는 가중 RRF 점수다.
- vector 채널은 기본 코사인 유사도 0.42 미만을 제외한다. 복합 질의는 원문과
  `와/과/및/또는`으로 나눈 하위 의도를 함께 검색한 뒤 서비스별 최고 점수로
  합친다.
- 문서는 개요·엔드포인트·응답필드 청크로 나눠 임베딩하고 모든 청크에
  제목·기관·분류·키워드를 반복한다. 모델 입력 한도는 질의와 문서 모두
  256토큰이다.
- 한 채널만 가용하면 그 채널의 원 점수를 그대로 반환한다.
- **인덱스·모델이 없어도 lexical 채널로 검색이 동작한다.** 한국어는
  Elasticsearch `cjk` analyzer와 같은 문자 bigram 방식으로 형태소 분석기
  없이 매칭한다.
- `use_vector: false`로 lexical 전용 검색이 가능하다.
- 결과의 `match_reasons`에 어떤 채널이 문서를 찾았는지 표시된다.
- `diagnostics`에 `lexical_candidates`, `lexical_source`, `fusion` 필드가
  추가됐다 (기존 필드는 유지).

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

모든 경로는 기본값이 `BASE_DIR` 기준이며(단, 데이터는 저장소 공통 루트) 다음 환경변수로 재지정할 수 있다.

| 변수 | 기본값 | 용도 |
| --- | --- | --- |
| `NARA_SEARCH_APIDATA_DIR` | `../nara_storage/openapi_new/` | 평면 OpenAPI JSON ({api_id}.json) |
| `NARA_SEARCH_STORAGE_DIR` | `storage/` | faiss.index, metadata.jsonl, vector_metadata.jsonl |
| `NARA_SEARCH_MODEL_DIR` | `models/ko-sroberta-multitask/` | 임베딩 모델 |
| `NARA_SEARCH_DATA_DIR` | `data/` | 카탈로그 산출물 루트 (02_catalog/03_semantic/04_output/minimal) |
| `NARA_SEARCH_MODEL_MAX_SEQ_LENGTH` | `256` | 질의·문서 임베딩 최대 토큰 |
| `NARA_SEARCH_VECTOR_MIN_SCORE` | `0.42` | 벡터 후보 최소 코사인 유사도 |
| `NARA_SEARCH_VECTOR_RRF_WEIGHT` | `0.9` | 벡터 RRF 가중치 |
| `NARA_SEARCH_LEXICAL_RRF_WEIGHT` | `1.1` | lexical RRF 가중치 |
| `NARA_SEARCH_VECTOR_OVERSAMPLE` | `12` | 청크 검색 후 서비스 집계를 위한 후보 배수 |
| `NARA_SEARCH_VECTOR_CHUNK_MAX_CHARS` | `650` | 원시 청크 묶음의 목표 문자 수 |
| `NARA_SEARCH_VECTOR_MAX_CHUNKS_PER_DOCUMENT` | `12` | 서비스당 최대 벡터 청크 |

## 테스트

```bash
pip install pytest httpx
python -m pytest tests -q
```

테스트는 faiss·sentence-transformers·실제 데이터 없이 실행된다.
fixture apidata(`tests/fixtures/apidata/`)로 상세조회 계약을, monkeypatch로
검색 envelope과 오류 계약을 검증한다. 인덱스·모델·카탈로그가 없어도 앱은
기동하며 `/health`의 `diagnostics`로 무엇이 없는지 진단할 수 있다.
