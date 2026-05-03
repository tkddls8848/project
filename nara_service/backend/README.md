# NARA Service API

FastAPI 기반 공공데이터 검색 및 RAG(Retrieval-Augmented Generation) 백엔드 API 서버

## 주요 기능

- **RAG 기반 자연어 검색**: FAISS 벡터 데이터베이스를 활용한 의미 기반 검색
- **다중 LLM 지원**: OpenAI GPT-4 / Ollama 로컬 모델
- **실시간 스트리밍**: Ollama를 통한 실시간 응답 스트리밍
- **한국어 임베딩**: `jhgan/ko-sroberta-multitask` 모델 사용
- **공공데이터 인덱싱**: `storage/index.json` 기반 자동 벡터 인덱스 생성
- **피드백 수집**: 사용자 피드백을 JSON 파일로 저장 및 관리
- **데이터 API**: 프론트엔드에 index.json 데이터 제공

## 설치

```bash
# 가상환경 생성 (권장)
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# FAISS 설치 (GPU/CPU 자동 감지)
python scripts/install_faiss.py
```

### FAISS GPU/CPU 설치

FAISS는 벡터 검색 엔진으로, GPU 가속을 지원합니다. 시스템 환경에 따라 적절한 버전을 선택하세요:

#### 옵션 1: 자동 설치 (권장)
```bash
python scripts/install_faiss.py
```
- GPU가 있으면 `faiss-gpu` 자동 설치
- GPU가 없으면 `faiss-cpu` 자동 설치

#### 옵션 2: 수동 설치
```bash
# GPU 환경 (CUDA 11.0 이상 필요)
pip install faiss-gpu==1.13.2

# CPU 환경
pip install faiss-cpu==1.13.2
```

#### GPU 사용 시 성능 향상
- **임베딩 속도**: 2~5배 향상 (배치 처리 최적화)
- **벡터 검색**: 10~100배 향상 (대용량 인덱스 시)
- **메모리**: GPU VRAM 사용 (시스템 RAM 절약)

**참고**: 코드는 GPU/CPU를 자동으로 감지하여 최적 설정을 적용합니다.

## 환경 설정

### 1. .env 파일 생성

```bash
# .env 파일 생성
cp .env.example .env
```

### 2. 환경 변수 설정

`.env` 파일에 다음 변수 설정:

```bash
# OpenAI API 키 (선택사항 - GPT 사용 시 필요)
OPENAI_API_KEY=your-openai-api-key-here

# Ollama 서버 URL (로컬 LLM 사용 시)
OLLAMA_URL=http://localhost:11434

# CORS 설정
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173
```

### 3. Ollama 설치 (로컬 LLM 사용 시)

```bash
# Ollama 설치 (https://ollama.ai)
# 모델 다운로드
ollama pull gemma3:4b
```

### 4. index.json 준비

크롤러에서 생성한 `index.json` 파일을 `../storage/` 디렉토리에 배치:

```bash
# web/ 폴더 기준
cp ../../nara_crawler/data/index.json ../storage/index.json
```

**참고**: 백엔드는 `../storage/index.json` 경로에서 데이터를 읽습니다.

## 실행

```bash
# 개발 서버 실행
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

서버가 실행되면 다음 주소에서 확인할 수 있습니다:
- API: http://localhost:8000
- API 문서 (Swagger): http://localhost:8000/docs
- API 문서 (ReDoc): http://localhost:8000/redoc

## API 엔드포인트

### 기본 엔드포인트
- `GET /` - 서비스 정보
- `GET /health` - 헬스 체크

### 데이터 엔드포인트
- `GET /index` - storage/index.json 파일 반환 (프론트엔드용)

### RAG 엔드포인트
- `POST /query` - 자연어 질의 (일반 응답)
- `POST /query/stream` - 자연어 질의 (스트리밍 응답, Ollama 지원)

#### RAG 요청 예시
```json
{
  "message": "건강검진 관련 데이터를 찾아줘",
  "llm_type": "openai"  // "openai" 또는 "ollama"
}
```

### 피드백 엔드포인트
- `POST /feedback` - 사용자 피드백 저장

#### 피드백 요청 예시
```json
{
  "query": "건강검진 관련 데이터를 찾아줘",
  "response": "LLM 응답 내용",
  "feedback": "like",  // "like" 또는 "dislike"
  "llm_type": "openai",
  "timestamp": "2025-11-25T12:34:56"
}
```

**참고**: 피드백은 `../storage/cookies/feedbacks.json`에 누적 저장됩니다.

## 프로젝트 구조

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI 애플리케이션 진입점
│   │                        # - Pydantic 모델 정의 (QueryRequest, FeedbackRequest 등)
│   │                        # - 모든 API 라우트 정의
│   │                        # - CORS 설정
│   ├── core/                # 핵심 설정
│   │   ├── __init__.py
│   │   └── config.py        # 앱 설정 (환경변수)
│   └── services/            # 비즈니스 로직
│       └── rag_service.py   # RAG 서비스 (FAISS + LLM)
├── .env.example             # 환경 변수 예제
├── .env                     # 환경 변수 (로컬)
└── requirements.txt         # Python 의존성

# 데이터 저장 위치 (backend/ 상위 폴더)
../storage/
├── index.json               # 공공데이터 인덱스 (RAG에서 사용)
└── cookies/
    └── feedbacks.json       # 사용자 피드백 저장
```

## RAG 서비스 아키텍처

1. **데이터 로딩**: `../storage/index.json`에서 공공데이터 로드
2. **임베딩 생성**: 한국어 Sentence-BERT 모델 (`jhgan/ko-sroberta-multitask`)로 벡터화
3. **FAISS 인덱싱**: 벡터 데이터베이스 구축
4. **검색**: 사용자 쿼리와 유사한 문서 검색 (Top-K)
5. **응답 생성**:
   - OpenAI GPT: 일반 응답 반환
   - Ollama: 스트리밍 응답 반환 (실시간)

## 주요 의존성

- **FastAPI** - 웹 프레임워크
- **Pydantic** - 데이터 검증 및 스키마 정의
- **pydantic-settings** - 환경 변수 관리
- **sentence-transformers** - 한국어 임베딩 모델
- **faiss-cpu/faiss-gpu** - 벡터 검색 엔진 (GPU 가속 지원)
- **openai** - OpenAI API 클라이언트
- **httpx** - Ollama API 통신
- **uvicorn** - ASGI 서버

## 데이터 흐름

### 1. 초기화 (앱 시작 시)
```
storage/index.json 로드 → 임베딩 생성 → FAISS 인덱스 구축
```

### 2. RAG 질의 처리
```
사용자 쿼리 → 임베딩 변환 → FAISS 검색 (Top-K) → LLM 응답 생성 → 결과 반환
```

### 3. 피드백 저장
```
프론트엔드 피드백 → /feedback 엔드포인트 → storage/cookies/feedbacks.json 추가
```
