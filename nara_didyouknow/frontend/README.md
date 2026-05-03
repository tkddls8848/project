# Did You Know - Frontend

공공데이터 포털의 흥미로운 사실들을 보여주는 프론트엔드 애플리케이션입니다.

## 기술 스택

- **Framework**: Next.js 15
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **UI Components**: Radix UI
- **Icons**: Lucide React
- **Theme**: next-themes

## 시작하기

### 설치

```bash
npm install
```

### 환경 변수 설정

`.env` 파일을 생성하고 백엔드 URL을 설정합니다:

```bash
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
```

### 개발 서버 실행

```bash
npm run dev
```

개발 서버가 [http://localhost:3000](http://localhost:3000)에서 실행됩니다.

### 프로덕션 빌드

```bash
npm run build
npm start
```

## 주요 기능

- 공공데이터 관련 흥미로운 사실들을 슬라이드쇼 형식으로 표시
- 카테고리별 필터링 (API 소개, 제공 기관, 활용 팁)
- 자동 재생/일시정지 기능
- 다크 모드 지원
- 콘텐츠 생성 기능 (관리자)

## 프로젝트 구조

```
src/
├── app/                    # Next.js App Router
│   ├── globals.css        # 전역 스타일
│   ├── layout.tsx         # 루트 레이아웃
│   └── page.tsx           # 메인 페이지
├── components/            # React 컴포넌트
│   ├── ui/               # UI 컴포넌트
│   ├── Header.tsx        # 헤더
│   ├── Footer.tsx        # 푸터
│   └── GenerateFactsModal.tsx  # 콘텐츠 생성 모달
├── lib/                   # 유틸리티 및 API
│   ├── api/              # API 클라이언트
│   └── types/            # TypeScript 타입
└── ...
```

## 라이선스

MIT
