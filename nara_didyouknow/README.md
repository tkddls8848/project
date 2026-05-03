# Did You Know Service

공공데이터 포털의 흥미로운 사실들을 AI로 생성하고 표시하는 서비스입니다.

## 프로젝트 구조

```
nara_didyouknow/
├── backend/           # FastAPI 백엔드
│   ├── app/
│   │   ├── core/     # 핵심 설정
│   │   ├── domain/   # 도메인 로직
│   │   ├── prompts/  # AI 프롬프트
│   │   ├── routers/  # API 라우터
│   │   └── services/ # 서비스 로직
│   ├── .env          # 환경 변수
│   └── requirements.txt
└── frontend/          # Next.js 프론트엔드
    ├── src/
    │   ├── app/      # Next.js App Router
    │   ├── components/ # React 컴포넌트
    │   └── lib/      # 유틸리티 및 API
    └── package.json
```

## 시작하기

### 백엔드

1. 환경 설정:
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. 환경 변수 설정:
`.env` 파일을 생성하고 필요한 변수를 설정합니다.

3. 서버 실행:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 프론트엔드

1. 의존성 설치:
```bash
cd frontend
npm install
```

2. 환경 변수 설정:
```bash
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
```

3. 개발 서버 실행:
```bash
npm run dev
```

## 주요 기능

- AI 기반 공공데이터 관련 흥미로운 사실 생성
- 카테고리별 분류 및 필터링
- 슬라이드쇼 형식의 인터랙티브 UI
- 다크 모드 지원
- 관리자용 콘텐츠 생성 기능

## 기술 스택

### 백엔드
- FastAPI
- Python 3.13
- Claude API (Anthropic)

### 프론트엔드
- Next.js 15
- TypeScript
- Tailwind CSS
- Radix UI

## 라이선스

MIT
