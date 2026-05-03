# Did You Know Service - Backend

공공데이터 API 기반 "그거 아셨나요?" 콘텐츠 생성 및 제공 서비스

## Features

- LLM 기반 자동 콘텐츠 생성 (Ollama 사용)
- 3가지 카테고리 지원
  - API 소개
  - 제공 기관 소개
  - 활용 팁
- 캐싱 시스템으로 빠른 응답
- RESTful API

## Requirements

- Python 3.12+
- Ollama (gemma3:4b 모델)

## Installation

```bash
# 가상환경 생성
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# 환경 변수 설정
cp .env.example .env
# .env 파일 수정

# 서버 실행
uvicorn app.main:app --reload
```

## API Endpoints

- `GET /didyouknow/facts` - 모든 사실 조회
- `GET /didyouknow/random` - 랜덤 사실 조회
- `POST /didyouknow/generate` - 새 콘텐츠 생성
- `GET /didyouknow/stats` - 통계 조회

## Docker

```bash
docker build -t didyouknow-service .
docker run -p 8000:8000 didyouknow-service
```
