# Nara Search

공공데이터 API 문서를 BM25/CJK bigram과 SentenceTransformer+FAISS로 검색하는 FastAPI
서비스다. 포트는 `8000`이며 데이터는 저장소 루트 `api_storage/`에서 읽는다.

## 실행

```powershell
cd C:\project\modules\search
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

`http://127.0.0.1:8000/`의 단독 UI에서 인덱스를 빌드할 수 있다. 모델이나 FAISS
인덱스가 없어도 lexical 검색은 동작한다.

## API

| 메서드 | 경로 | 설명 |
|---|---|---|
| `GET` | `/health` | 데이터·모델·인덱스 상태 |
| `POST` | `/search` | `{query, top_k, use_vector}` 검색 |
| `POST` | `/build` | 백그라운드 인덱스 빌드 |
| `GET` | `/build/status` | 빌드 진행률 |
| `GET` | `/catalog` | 대시보드용 카탈로그 |
| `GET` | `/services/{service_id}` | 문서 상세 |
| `GET` | `/relations?ids=...` | 문서 관계 |

정식 `service_id`는 `{source}:{api_id}` 형식이다. 예:
`openapi_new:15000827`. 검색 결과의 ID를 상세·관계 API에 그대로 전달한다.

주요 환경 변수는 `NARA_SEARCH_APIDATA_DIR`, `NARA_SEARCH_STORAGE_DIR`,
`NARA_SEARCH_MODEL_DIR`, `NARA_SEARCH_DATA_DIR`이다.

## 테스트

```powershell
python -m pytest tests -q
```
