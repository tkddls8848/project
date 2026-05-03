# NARA Service

공공데이터 조회 및 RAG 기반 질의응답 서비스

## 프로젝트 구조

```
nara_service/
├── backend/          # FastAPI 백엔드 API
├── frontend/         # Next.js 프론트엔드
├── storage/          # 데이터 저장소
└── DEPLOYMENT.md     # 배포 가이드 📦
```

## 빠른 시작

### 로컬 개발 환경

#### Backend 실행
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# .env 파일 수정 (OPENAI_API_KEY 등)
uvicorn app.main:app --reload
```

Backend API: http://localhost:8000

#### Frontend 실행
```bash
cd frontend
npm install
cp .env.example .env.local
# .env.local 파일 수정 (Google OAuth 등)
npm run dev
```

Frontend: http://localhost:3000

## 배포

**🚀 [DEPLOYMENT.md](./DEPLOYMENT.md) 파일을 참조하세요**

- Backend + Storage → Railway
- Frontend → Vercel

상세한 단계별 배포 가이드와 트러블슈팅 정보가 포함되어 있습니다.

## 주요 기능

- 📊 공공데이터 조회 및 필터링
- 🤖 RAG 기반 자연어 질의응답
- 🔐 Google OAuth 인증
- 📁 파일 다운로드 링크 제공
- 💬 사용자 피드백 수집

## 기술 스택

### Backend
- FastAPI
- OpenAI GPT
- FAISS (벡터 검색)
- Sentence Transformers

### Frontend
- Next.js 15
- TypeScript
- NextAuth.js
- Tailwind CSS
- shadcn/ui

### 인프라
- Railway (Backend + Storage)
- Vercel (Frontend)

## API 문서

로컬 개발: http://localhost:8000/docs
프로덕션: https://your-backend.up.railway.app/docs

(Basic Auth 필요: username=admin, password=설정값)

## 환경 변수

### Backend (.env)
- `OPENAI_API_KEY`: OpenAI API 키 (필수)
- `ALLOWED_ORIGINS`: CORS 허용 도메인
- `DEBUG`: 디버그 모드 (True/False)

### Frontend (.env.local)
- `NEXT_PUBLIC_API_URL`: Backend API URL
- `NEXTAUTH_URL`: Frontend 도메인
- `NEXTAUTH_SECRET`: NextAuth 시크릿 키
- `GOOGLE_CLIENT_ID`: Google OAuth 클라이언트 ID
- `GOOGLE_CLIENT_SECRET`: Google OAuth 시크릿

## 라이선스

MIT

## 문의

프로젝트 관련 문의사항은 GitHub Issues를 이용해주세요.
