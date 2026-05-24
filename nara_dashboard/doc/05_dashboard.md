# AlphaForge 벤치마킹 프로젝트 스펙

> 참고 영상: [Claude made the financial n8n](https://www.youtube.com/watch?v=Imxj_T3bilM) (Hodu's AI Analysis Lab, 2026.05.04)

---

## 1. 프로젝트 개요

### 1.1 목표
n8n 스타일의 시각적 노드 연결 방식을 **금융 데이터 분석**에 적용한 자동화 도구를 개발한다. 코딩 없이 노드를 드래그/연결하는 것만으로 종목 필터링부터 AI 분석, 결과 전송까지의 파이프라인을 구성할 수 있어야 한다.

### 1.2 벤치마킹 핵심 포인트
- **시각적 파이프라인 빌더**: 노드 기반 UI로 비개발자도 사용 가능
- **금융 도메인 특화 노드**: KOSPI/KOSDAQ 종목 필터링 로직 내장
- **외부 AI 통합**: 뉴스 검색(Perplexity) + LLM 분석(OpenRouter/DeepSeek)
- **다채널 결과 전송**: Excel, Telegram 자동 출력
- **스무스한 UX**: n8n급의 부드러운 인터랙션

### 1.3 차별화 포인트 (확장 아이디어)
- 백테스팅 노드 추가
- 미국 주식(NYSE/NASDAQ) 지원
- 알림 채널 확장 (Discord, Slack, KakaoTalk)
- 실시간 스케줄링 (cron 노드)

---

## 2. 기술 스택

### 2.1 프론트엔드
| 영역 | 선택 | 비고 |
|------|------|------|
| 프레임워크 | React 18+ / Next.js 14+ | App Router |
| 노드 에디터 | **@xyflow/react (React Flow)** | n8n도 동일 계열 사용 |
| 스타일링 | TailwindCSS + shadcn/ui | 빠른 UI 구축 |
| 상태관리 | Zustand | React Flow와 궁합 좋음 |
| 아이콘 | Lucide React | |
| 차트 | Recharts / TradingView Lightweight Charts | 주가 시각화 |

### 2.2 백엔드
| 영역 | 선택 | 비고 |
|------|------|------|
| 런타임 | Node.js (Fastify) 또는 Python (FastAPI) | 워크플로우 실행 엔진 |
| 워크플로우 실행 | 자체 구현 (DAG 기반 토폴로지 실행) | n8n 코드 참고 가능 |
| DB | PostgreSQL + Prisma | 워크플로우/실행 이력 저장 |
| 캐시/큐 | Redis + BullMQ | 비동기 작업 처리 |

### 2.3 외부 API
- **주가 데이터**: 키움 OpenAPI / 한국투자증권 KIS Developers / pykrx
- **뉴스 검색**: Perplexity API
- **LLM 분석**: OpenRouter (DeepSeek, Claude, GPT 등 모델 선택)
- **결과 전송**: Telegram Bot API, SMTP, Webhook

---

## 3. 노드 카탈로그

### 3.1 데이터 소스 노드 (Trigger / Source)
- `Stock Universe`: KOSPI / KOSDAQ / KOSPI200 / 전체 종목 로드
- `Manual Input`: 종목 코드 직접 입력
- `Schedule`: Cron 기반 자동 실행 트리거
- `Webhook`: 외부 호출로 실행

### 3.2 필터링 노드 (영상 기반)
- `Breakout from Box Range` — 박스권 돌파 종목 필터
- `MA Upward Alignment` — 이동평균선 정배열 (5/20/60/120일)
- `Foreign Buying` — 외국인 순매수
- `Institutional Buying` — 기관 순매수
- `Volume Surge` — 거래량 급증 (확장)
- `RSI Filter` — RSI 구간 필터 (확장)
- `Market Cap Filter` — 시가총액 범위 필터 (확장)

### 3.3 분석 노드
- `Perplexity Search` — 종목 관련 최신 뉴스 검색
- `OpenRouter LLM` — DeepSeek/Claude/GPT 등으로 분석
- `Sentiment Score` — 뉴스 감성 점수 산출
- `Technical Score` — 기술적 지표 종합 점수

### 3.4 처리 노드
- `Merge` — 여러 노드 결과 병합
- `Filter` — 조건식 기반 결과 필터
- `Sort` — 점수/조건 기준 정렬
- `Top N` — 상위 N개 선택
- `Code` — 커스텀 JS/Python 로직 실행

### 3.5 출력 노드
- `Excel Export` — XLSX 파일 다운로드
- `Telegram Send` — 텔레그램 봇 메시지 전송
- `Email Send` — 이메일 발송 (확장)
- `Database Write` — DB 저장 (확장)
- `Webhook Out` — 외부 시스템 호출 (확장)

---

## 4. UI/UX 디자인 가이드

### 4.1 "스무스함"을 만드는 요소
1. **베지어 곡선 연결선**: 직선 X, 곡선 O (React Flow 기본)
2. **GPU 가속 팬/줌**: `transform: translate/scale` 기반
3. **requestAnimationFrame 드래그**: 끊김 없는 노드 이동
4. **CSS transition 0.15~0.2s**: 호버/선택 상태 변화
5. **Snap-to-grid**: 격자 정렬 (8px 또는 16px 단위)
6. **닷 그리드 배경**: 시각적 노이즈 최소화
7. **포트 호버 확대**: 마이크로 인터랙션

### 4.2 디자인 시스템
- **다크 모드 우선** (n8n, AlphaForge 모두 다크 톤)
- 노드 카테고리별 색상 구분:
  - 데이터 소스: Blue
  - 필터: Purple
  - 분석/AI: Green
  - 출력: Orange
- 노드 너비 고정 (240~280px), 높이 가변
- 아이콘 + 노드명 + 상태 인디케이터 구조

### 4.3 주요 인터랙션
- 노드 추가: 좌측 사이드바에서 드래그 또는 캔버스 우클릭 메뉴
- 연결: 포트 클릭 → 드래그 → 다른 포트에 드롭
- 실행: 우상단 "Run" 버튼 또는 개별 노드 단독 실행
- 실시간 실행 상태 표시: 노드 테두리 애니메이션 (실행중/성공/실패)

---

## 5. 단계별 개발 계획

### Phase 1: MVP (2~3주)
- [ ] React Flow 기반 캔버스 구축
- [ ] 기본 노드 5종 (Stock Universe, MA Alignment, Foreign Buying, Excel Export, Manual Input)
- [ ] 단순 순차 실행 엔진
- [ ] 로컬 스토리지 워크플로우 저장
- [ ] pykrx 또는 KIS API 1종 연동

### Phase 2: 기능 확장 (3~4주)
- [ ] 노드 10종 추가 (전체 필터링 노드 + Merge/Filter/Sort)
- [ ] Perplexity API 노드
- [ ] OpenRouter LLM 노드
- [ ] Telegram Send 노드
- [ ] 워크플로우 DB 저장 (PostgreSQL)
- [ ] 실행 이력 조회

### Phase 3: 베타 (4주)
- [ ] 스케줄링 (Cron 노드 + BullMQ)
- [ ] 사용자 인증 (NextAuth)
- [ ] 워크플로우 공유/템플릿
- [ ] 실시간 실행 모니터링
- [ ] 에러 처리 & 재시도 로직

### Phase 4: 정식 출시
- [ ] 결제/구독 시스템 (Stripe / 토스페이먼츠)
- [ ] 미국 주식 지원
- [ ] 모바일 반응형
- [ ] 문서/튜토리얼 사이트

---

## 6. 외부 연동 상세

### 6.1 Perplexity API
- 엔드포인트: `https://api.perplexity.ai/chat/completions`
- 용도: 종목 관련 최신 뉴스/이슈 검색
- 노드 입력: 종목명/코드
- 노드 출력: 뉴스 요약 텍스트 + 소스 URL

### 6.2 OpenRouter
- 엔드포인트: `https://openrouter.ai/api/v1/chat/completions`
- 모델 옵션: `deepseek/deepseek-chat`, `anthropic/claude-*`, `openai/gpt-*` 등
- 용도: 수집된 데이터 기반 종목 평가/점수화
- 프롬프트 템플릿 관리 필요

### 6.3 Telegram Bot
- BotFather로 봇 생성 → Token 발급
- 채널/그룹 ID 또는 사용자 chat_id 필요
- 메시지 포맷: Markdown 또는 HTML 지원
- 파일 첨부: Excel 결과 함께 전송 가능

### 6.4 한국 주식 데이터
- **무료 옵션**: pykrx (Python 라이브러리, 일봉 데이터)
- **유료/실시간**: 키움 OpenAPI, KIS Developers
- **글로벌**: yfinance, Alpha Vantage

---

## 7. 참고 라이브러리 및 리소스

### 7.1 노드 에디터 라이브러리
- [React Flow / @xyflow/react](https://reactflow.dev) — 1순위
- [Vue Flow](https://vueflow.dev) — n8n 사용
- [Rete.js](https://retejs.org) — 고도 커스터마이징
- [LiteGraph.js](https://github.com/jagenjo/litegraph.js) — Canvas 기반

### 7.2 참고 오픈소스
- [n8n](https://github.com/n8n-io/n8n) — 워크플로우 엔진 구조 참고
- [Flowise](https://github.com/FlowiseAI/Flowise) — LLM 노드 에디터
- [Langflow](https://github.com/langflow-ai/langflow) — LangChain 시각화

### 7.3 디자인 레퍼런스
- n8n 공식 UI
- Make.com (구 Integromat)
- Zapier Visual Editor
- ComfyUI (스테이블 디퓨전 노드 에디터)

---

## 8. 리스크 및 고려사항

- **데이터 비용**: 실시간 주가 API는 유료. 무료 데이터는 일봉/지연 데이터 위주
- **법적 이슈**: 투자 자문/추천으로 해석될 수 있어 면책 고지 필수
- **LLM 비용**: OpenRouter 사용량 모니터링 및 사용자별 한도 필요
- **성능**: 대량 종목(2,500여개) 필터링 시 백엔드 최적화 필수
- **AlphaForge IP**: 영상 프로젝트는 별도 권리. UI/UX 컨셉만 참고, 직접 코드/에셋 복제 금지

---

## 9. 다음 액션

1. React Flow 학습 + 미니 데모 (드래그/연결만 되는 수준) 구축
2. pykrx로 주가 데이터 1종 가져오는 백엔드 PoC
3. 노드 1개(MA Alignment)로 단일 노드 실행 흐름 완성
4. 위 3가지 완료 후 Phase 1 본격 진행