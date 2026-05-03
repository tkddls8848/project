# NARA Service Frontend

Next.js + TypeScript + TailwindCSS 기반 공공데이터 검색 및 RAG 서비스 프론트엔드

## 주요 기능

- **데이터 카드 뷰**: `index.json` 기반 공공데이터 카드 형식 표시
- **타입별 필터링**: FileData, OpenAPI_link, swagger, general, Standard 타입별 필터링
- **검색 기능**: 제목 기반 실시간 검색
- **페이지네이션**: 30개씩 데이터 표시 및 페이지 전환
- **상세 페이지**: API 엔드포인트 정보를 포함한 상세 정보 조회
- **다크 모드**: 라이트/다크 테마 전환 지원
- **RAG 기반 자연어 질의**: AI를 활용한 자연어 검색
- **다중 LLM 지원**: OpenAI GPT / Ollama 로컬 모델 선택 가능
- **실시간 스트리밍**: Ollama 사용 시 실시간 응답 스트리밍
- **피드백 시스템**: 응답에 대한 좋아요/싫어요 피드백 수집
- **API 연결 상태**: 실시간 백엔드 연결 상태 표시
- **토글 가능한 UI**: 데이터 목록 표시/숨김 전환

## 시작하기

### 1. 패키지 설치

```bash
npm install
```

### 2. 백엔드 서버 준비

백엔드 서버가 `http://localhost:8000`에서 실행 중이어야 하며, `/index` 엔드포인트를 통해 `index.json` 데이터를 제공합니다.

```bash
# 백엔드 폴더에서
cd ../backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. 개발 서버 실행

```bash
npm run dev
```

브라우저에서 [http://localhost:3000](http://localhost:3000) 열기

## 기술 스택

- **Next.js 15** - React 프레임워크 (App Router)
- **TypeScript** - 타입 안전성
- **TailwindCSS** - 스타일링
- **shadcn/ui** - UI 컴포넌트 라이브러리 (Radix UI 기반)
- **next-themes** - 다크 모드 지원
- **Lucide React** - 아이콘 라이브러리
- **Axios** - HTTP 클라이언트
- **Streaming API** - 실시간 응답 스트리밍

## 프로젝트 구조

```
frontend/
├── src/
│   ├── app/                         # Next.js App Router
│   │   ├── layout.tsx               # 루트 레이아웃 (테마 프로바이더 포함)
│   │   ├── page.tsx                 # 홈페이지 (메인 대시보드)
│   │   ├── detail/[type]/[id]/      # 상세 페이지 (동적 라우팅)
│   │   │   └── page.tsx             # API 상세 정보 페이지
│   │   └── globals.css              # 전역 스타일
│   ├── components/                  # React 컴포넌트
│   │   ├── Header.tsx               # 헤더 (연결 상태 표시, 다크 모드 토글)
│   │   ├── Footer.tsx               # 푸터
│   │   ├── QuerySection.tsx         # RAG 질의 섹션
│   │   ├── theme-toggle.tsx         # 테마 전환 버튼
│   │   ├── theme-provider.tsx       # 테마 컨텍스트 프로바이더
│   │   ├── ui/                      # shadcn/ui 컴포넌트
│   │   │   ├── button.tsx
│   │   │   ├── card.tsx
│   │   │   ├── input.tsx
│   │   │   ├── badge.tsx
│   │   │   ├── tabs.tsx
│   │   │   ├── select.tsx
│   │   │   ├── skeleton.tsx
│   │   │   └── ...
│   │   └── index.ts                 # 컴포넌트 export
│   ├── hooks/                       # Custom React Hooks
│   │   ├── useApiConnection.ts      # API 연결 상태 관리
│   │   ├── useQuery.ts              # RAG 쿼리 처리
│   │   └── index.ts                 # Hooks export
│   ├── types/                       # TypeScript 타입 정의
│   │   └── index.ts                 # 공통 타입
│   └── lib/
│       ├── api.ts                   # Axios 인스턴스 (FastAPI 연결)
│       └── utils.ts                 # 유틸리티 함수 (cn 등)
├── public/
│   └── icons/                       # LLM 아이콘 (chatgpt.png, ollama.svg)
├── .env.local                       # 환경 변수
└── package.json
```

## 데이터 구조

### index.json
```json
{
  "FileData": { "id": { "title": "", "description": "", "URL": "", "update_time": "", ... } },
  "OpenAPI_link": { ... },
  "swagger": { ... },
  "general": { ... },
  "Standard": { ... }
}
```

### API 엔드포인트
- `GET /index` - 전체 데이터 목록 조회
- `GET /detail/{type}/{id}` - 특정 데이터 상세 정보 조회 (endpoints 정보 포함)

## 주요 컴포넌트

### Header (src/components/Header.tsx)
- 애플리케이션 헤더
- 백엔드 연결 상태 실시간 표시 (연결 중/연결됨/연결 실패)
- 색상 인디케이터로 상태 표현
- 다크 모드 토글 버튼 (ThemeToggle 컴포넌트)

### QuerySection (src/components/QuerySection.tsx)
- RAG 기반 자연어 질의 인터페이스
- LLM 선택: OpenAI GPT / Ollama (라디오 버튼, 아이콘 포함)
- 실시간 스트리밍 응답 (Ollama)
- 피드백 시스템 (좋아요/싫어요)
- Enter 키 지원

### DetailPage (src/app/detail/[type]/[id]/page.tsx)
- API 상세 정보 페이지
- 엔드포인트 목록 표시 (HTTP 메서드, 경로, 설명)
- 파라미터 정보 표시 (required 여부)
- 타입별 색상 구분 배지

### Footer (src/components/Footer.tsx)
- 애플리케이션 푸터
- 저작권 및 추가 정보

### ThemeToggle (src/components/theme-toggle.tsx)
- 라이트/다크 모드 전환 버튼
- next-themes를 사용한 테마 관리

### Custom Hooks
- **useApiConnection**: 백엔드 API 연결 상태 관리
- **useQuery**: RAG 쿼리 처리 및 스트리밍 응답 관리

### 데이터 카드
- 타입별 색상 구분:
  - FileData: 파란색
  - OpenAPI_link: 초록색
  - swagger: 보라색
  - general: 노란색
  - Standard: 빨간색
- 제목 및 설명 line-clamp 처리
- 업데이트 시간 표시
- 반응형 그리드 레이아웃 (모바일: 1열, 태블릿: 2열, 데스크톱: 3열)
- 호버 효과 및 애니메이션

### UI 기능
- **검색**: 제목 기반 실시간 검색 (대소문자 구분 없음)
- **필터링**: 타입별 필터링 (각 필터에 개수 표시)
- **페이지네이션**: 30개씩 표시, 페이지 번호 버튼
- **토글**: "데이터 목록 보기" 버튼으로 목록 표시/숨김
- **스켈레톤 로딩**: 데이터 로딩 중 스켈레톤 UI 표시
- **빈 상태**: 필터링 결과가 없을 때 안내 메시지

## 빌드 및 배포

```bash
# 프로덕션 빌드
npm run build

# 프로덕션 서버 실행
npm start
```
