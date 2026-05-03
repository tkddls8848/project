네이버 일일 토픽 기사 기반 공공데이터 API 추천 기능 구현 계획

 📋 개요

 네이버 일일 토픽 기사 5개를 기반으로 연관된 공공데이터 API를 RAG 시맨틱 검색으로 찾아 "그거 아셨나요?" 형식으로 추천하는 기능을 구현합니다.

 사용자 요구사항:
 - 네이버 크롤링: 사용자가 나중에 직접 통합 예정
 - 실행 방식: 수동 트리거 (관리자 버튼 클릭)
 - 뉴스 개수: 일일 5개
 - 구현 범위: MVP + 관리자 대시보드 + 자동 스케줄링 + 유사도 필터링

 🎯 핵심 설계 결정

 1. 새로운 FactCategory 추가

 FactCategory.NEWS_RECOMMENDATION = "news_recommendation"을 추가하여 기존 시스템과 명확히 분리합니다.

 2. 뉴스 데이터 형식 정의

 사용자가 제공할 뉴스 데이터 JSON 형식:
 {
   "crawled_date": "2026-01-21",
   "articles": [
     {
       "article_id": "unique_id",
       "title": "기사 제목",
       "summary": "기사 요약 (200자 이내)",
       "url": "기사 URL",
       "published_at": "2026-01-21T09:00:00",
       "category": "정치|경제|사회|문화 등",
       "source": "연합뉴스 등"
     }
   ]
 }

 저장 위치: nara_service/backend/storage/naver_news/YYYYMMDD.json

 3. 뉴스-API 매칭 전략

 RAG 시맨틱 검색 사용:
 - SearchRAGService의 search_chunks() 메서드 활용
 - 기사 제목 + 요약을 쿼리로 사용
 - 코사인 유사도 기반으로 상위 3개 API 추출
 - 유사도 임계값 0.6 이상만 선택

 📂 구현할 파일 및 수정 사항

 Phase 1: 백엔드 - DidYouKnowService 확장

 파일 1: nara_service/backend/app/services/didyouknow_service.py

 수정 사항:
 1. FactCategory Enum에 NEWS_RECOMMENDATION 추가
 2. _select_source_documents() 메서드에 뉴스 기반 로직 추가:
   - 최신 뉴스 파일 로드 (_load_latest_news() 메서드 구현)
   - 각 뉴스마다 RAG 검색으로 관련 API 찾기
   - 유사도 임계값 필터링 (0.6 이상)
 3. _get_prompt_for_category() 메서드에 분기 추가

 핵심 로직:
 elif category == FactCategory.NEWS_RECOMMENDATION:
     news_data = self._load_latest_news()
     if not news_data:
         return []

     recommendations = []
     for article in news_data['articles'][:5]:
         query = f"{article['title']} {article.get('summary', '')}"
         related_apis = self.search_rag_service.search_chunks(query, top_k=3)

         if related_apis and related_apis[0].get('score', 0) >= 0.6:
             recommendations.append({
                 'news_article': article,
                 'related_api': related_apis[0]['metadata'],
                 'similarity_score': related_apis[0]['score']
             })

     return recommendations

 파일 2: nara_service/backend/app/prompts/didyouknow.py

 추가 함수: get_news_recommendation_prompt()

 def get_news_recommendation_prompt(news_article: Dict[str, Any], api_doc: Dict[str, Any], similarity_score: float = 0.0) -> str:
     """
     뉴스 기반 API 추천 프롬프트

     Args:
         news_article: 뉴스 기사 정보
         api_doc: API 문서 정보
         similarity_score: 유사도 점수

     Returns:
         LLM 프롬프트 문자열
     """
     title = news_article.get('title', '')
     summary = news_article.get('summary', '')[:200]

     api_title = api_doc.get('title', '')
     provider = api_doc.get('provider', '')
     description = api_doc.get('description', '')[:200]

     return f"""당신은 시의성 있는 뉴스와 공공데이터를 연결하는 AI입니다.

 아래 뉴스 기사와 연관된 공공데이터 API를 "그거 아셨나요?" 형식으로 소개하세요.

 [뉴스 기사]
 제목: {title}
 요약: {summary}

 [연관 API]
 제목: {api_title}
 제공기관: {provider}
 설명: {description}
 연관도: {similarity_score:.2f}

 [작성 지침]
 1. "그거 아셨나요? 최근 '[뉴스 주제]' 뉴스와 관련하여 [기관]에서 [API 기능] API를 제공해요!" 형식
 2. 뉴스와 API의 연관성을 자연스럽게 설명
 3. 시의성 강조 ("최근", "요즘", "화제가 된")
 4. 80자 이내로 간결하게
 5. URL은 생성하지 마세요 (시스템에서 자동 추가됨)

 예시:
 "그거 아셨나요? 최근 'AI 규제법' 논의와 관련하여 과학기술정보통신부에서 AI 윤리 가이드라인 데이터를 제공해요!"

 한 문장만 생성하세요:"""

 Phase 2: 백엔드 - API 라우터 및 스키마 업데이트

 파일 3: nara_service/backend/app/routers/didyouknow.py

 수정 사항:
 1. CategoryCounts 모델에 news_recommendation 필드 추가:
 class CategoryCounts(BaseModel):
     api_introduction: int = Field(34, ge=0, le=100)
     provider_introduction: int = Field(34, ge=0, le=100)
     usage_tip: int = Field(34, ge=0, le=100)
     news_recommendation: int = Field(5, ge=0, le=20)  # 새로 추가

 2. /didyouknow/generate 엔드포인트는 기존 로직 그대로 사용 (자동으로 매핑됨)

 파일 4: nara_service/backend/storage/naver_news/ 디렉토리 생성

 뉴스 데이터를 저장할 디렉토리를 생성합니다. 사용자가 여기에 YYYYMMDD.json 형식으로 파일을 저장하면 시스템이 자동으로 읽습니다.

 Phase 3: 프론트엔드 - UI 업데이트

 파일 5: nara_service/frontend/src/app/didyouknow/page.tsx

 수정 사항:
 1. CATEGORY_LABELS에 추가:
 const CATEGORY_LABELS: Record<string, string> = {
   api_introduction: "API 소개",
   provider_introduction: "제공 기관",
   usage_tip: "활용 팁",
   news_recommendation: "뉴스 추천",  // 새로 추가
 };

 2. CATEGORY_COLORS에 추가:
 const CATEGORY_COLORS: Record<string, string> = {
   api_introduction: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
   provider_introduction: "bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300",
   usage_tip: "bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300",
   news_recommendation: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",  // 새로 추가
 };

 파일 6: nara_service/frontend/src/components/GenerateFactsModal.tsx

 수정 사항:
 뉴스 추천 카테고리 입력 필드 추가:
 <div>
   <label className="block text-sm font-medium mb-2">
     뉴스 추천 (5개 권장)
   </label>
   <input
     type="number"
     min="0"
     max="20"
     value={counts.news_recommendation}
     onChange={(e) => setCounts({...counts, news_recommendation: parseInt(e.target.value)})}
     className="w-full px-3 py-2 border rounded-lg"
   />
 </div>

 Phase 4: 관리자 대시보드 (선택적 구현)

 파일 7: nara_service/frontend/src/app/admin/news/page.tsx (신규)

 기능:
 - 뉴스 파일 업로드 UI
 - 크롤링된 뉴스 목록 표시
 - 각 뉴스별 매칭된 API 표시
 - 유사도 점수 표시
 - 생성 이력 확인

 파일 8: nara_service/backend/app/routers/admin_news.py (신규)

 엔드포인트:
 - GET /admin/news/list - 뉴스 파일 목록
 - GET /admin/news/{date} - 특정 날짜 뉴스 상세
 - POST /admin/news/upload - 뉴스 파일 업로드
 - GET /admin/news/stats - 통계 (총 뉴스 수, 평균 유사도 등)

 Phase 5: 자동 스케줄링 (선택적 구현)

 파일 9: nara_service/backend/app/services/scheduler_service.py (신규)

 기능:
 - APScheduler를 사용한 스케줄링
 - 매일 오전 9시 자동 실행 (설정 가능)
 - 뉴스 파일 확인 후 자동 생성
 - 에러 로깅 및 알림

 from apscheduler.schedulers.asyncio import AsyncIOScheduler
 from apscheduler.triggers.cron import CronTrigger

 class SchedulerService:
     def __init__(self, didyouknow_service):
         self.scheduler = AsyncIOScheduler()
         self.didyouknow_service = didyouknow_service

     def start(self):
         # 매일 오전 9시 실행
         self.scheduler.add_job(
             self._daily_news_generation,
             CronTrigger(hour=9, minute=0),
             id='daily_news_generation'
         )
         self.scheduler.start()

     async def _daily_news_generation(self):
         try:
             # 오늘 뉴스 파일이 있는지 확인
             news_data = self.didyouknow_service._load_latest_news()
             if news_data:
                 # 자동 생성
                 facts = self.didyouknow_service.generate_batch({
                     FactCategory.NEWS_RECOMMENDATION: 5
                 })
                 # 기존 facts 로드 후 병합
                 existing_facts = self.didyouknow_service.load_facts()
                 all_facts = existing_facts + facts
                 self.didyouknow_service.save_facts(all_facts)
                 print(f"[Scheduler] Generated {len(facts)} news recommendations")
         except Exception as e:
             print(f"[Scheduler] Error: {e}")

 파일 10: nara_service/backend/app/main.py

 수정 사항:
 스케줄러 초기화 추가:
 if settings.ENABLE_SCHEDULER:
     from app.services.scheduler_service import SchedulerService
     scheduler_service = SchedulerService(didyouknow_service)
     scheduler_service.start()
     print("[Main] Scheduler started")

 Phase 6: 유사도 필터링 UI (선택적 구현)

 파일 11: nara_service/backend/app/core/config.py

 추가 설정:
 # DidYouKnow 설정
 DIDYOUKNOW_SIMILARITY_THRESHOLD: float = 0.6  # 유사도 임계값

 파일 12: nara_service/frontend/src/components/GenerateFactsModal.tsx

 추가 UI:
 유사도 임계값 슬라이더:
 <div>
   <label className="block text-sm font-medium mb-2">
     유사도 임계값: {similarityThreshold.toFixed(2)}
   </label>
   <input
     type="range"
     min="0.3"
     max="0.9"
     step="0.05"
     value={similarityThreshold}
     onChange={(e) => setSimilarityThreshold(parseFloat(e.target.value))}
     className="w-full"
   />
   <p className="text-xs text-gray-500 mt-1">
     낮을수록 더 많은 API가 매칭되지만 정확도가 낮아집니다.
   </p>
 </div>

 🔄 데이터 흐름

 1. 사용자가 뉴스 파일 업로드 (storage/naver_news/YYYYMMDD.json)
    ↓
 2. 관리자가 프론트엔드에서 "콘텐츠 생성" 버튼 클릭
    ↓
 3. POST /didyouknow/generate (news_recommendation: 5)
    ↓
 4. DidYouKnowService._select_source_documents()
    ├─ 뉴스 파일 로드
    ├─ 각 뉴스마다 RAG 시맨틱 검색
    ├─ 유사도 0.6 이상 필터링
    └─ 추천 목록 반환
    ↓
 5. 각 추천마다 LLM 프롬프트 생성 및 실행
    ├─ get_news_recommendation_prompt() 호출
    ├─ Ollama gemma3:4b로 "그거 아셨나요?" 생성
    └─ fact 객체 생성 (metadata에 뉴스 정보 포함)
    ↓
 6. facts.json에 저장 (기존 facts와 병합)
    ↓
 7. 프론트엔드 슬라이드쇼에 표시

 📊 Facts.json 메타데이터 구조

 {
   "id": "uuid",
   "category": "news_recommendation",
   "content": "그거 아셨나요? 최근 'AI 데이터센터 구축' 뉴스와 관련하여...",
   "source_doc_id": "15012345",
   "created_at": "2026-01-21T10:00:00",
   "metadata": {
     "provider": "과학기술정보통신부",
     "title": "AI 학습용 데이터셋 API",
     "category": "openapi_new",
     "doc_url": "https://www.data.go.kr/data/15012345/openapi.do",
     "news_article_id": "001_0014867283",
     "news_title": "정부, AI 데이터센터 구축 예산 1조원 투입",
     "news_url": "https://...",
     "news_date": "2026-01-21",
     "similarity_score": 0.87
   }
 }

 ✅ 검증 계획

 1. 백엔드 테스트

 1. 샘플 뉴스 파일 생성 (storage/naver_news/20260121.json)
 2. Python 스크립트로 _load_latest_news() 테스트
 3. RAG 검색 결과 확인 (유사도 점수 체크)
 4. LLM 생성 결과 확인 (프롬프트 품질 평가)
 5. facts.json 저장 확인

 2. API 테스트

 # 생성 요청
 curl -X POST http://localhost:8000/didyouknow/generate \
   -H "Content-Type: application/json" \
   -d '{
     "counts": {
       "api_introduction": 0,
       "provider_introduction": 0,
       "usage_tip": 0,
       "news_recommendation": 5
     }
   }'

 # 결과 조회
 curl http://localhost:8000/didyouknow/facts?category=news_recommendation

 3. 프론트엔드 테스트

 1. 브라우저에서 http://localhost:3000/didyouknow 접속
 2. "뉴스 추천" 필터 선택
 3. 슬라이드쇼 작동 확인
 4. "API 문서 보러가기" 버튼 클릭 테스트
 5. "콘텐츠 생성" 모달에서 뉴스 추천 개수 조정

 4. 통합 테스트

 1. 뉴스 파일 업로드 → 생성 → 조회 → 표시 전체 플로우
 2. 여러 날짜 뉴스 파일 테스트
 3. 유사도 낮은 경우 필터링 확인
 4. 에러 케이스 테스트 (뉴스 파일 없음, RAG 검색 실패 등)

 🚨 주의사항

 1. 법적 고려사항

 - 뉴스 데이터는 사용자가 직접 수집하므로 법적 책임은 사용자에게 있음
 - 뉴스 제목/요약만 저장하고 본문 전체는 저장하지 않음
 - 출처 명시 필수 (metadata에 news_url, source 포함)

 2. 성능 고려사항

 - RAG 검색은 청크 임베딩이 완료된 상태에서 빠름 (< 1초)
 - LLM 생성은 5개 기사 * 3-5초 = 15-25초 소요
 - 백그라운드 태스크로 처리하거나 프론트엔드에 로딩 표시 필요

 3. 품질 관리

 - 유사도 임계값 0.6은 초기값이며, 결과를 보고 조정 필요
 - 뉴스와 API 연관성이 낮으면 생성하지 않도록 필터링
 - LLM 프롬프트는 몇 번의 테스트를 거쳐 튜닝 필요

 📦 의존성 추가

 requirements.txt (선택적)

 apscheduler>=3.10.0  # 자동 스케줄링용 (Phase 5)

 🎯 구현 우선순위

 필수 (MVP):

 1. ✅ FactCategory.NEWS_RECOMMENDATION 추가
 2. ✅ 뉴스 데이터 로드 로직
 3. ✅ RAG 시맨틱 검색 통합
 4. ✅ 프롬프트 작성 및 LLM 생성
 5. ✅ API 라우터 업데이트
 6. ✅ 프론트엔드 UI 업데이트

 권장 (Enhancement):

 7. ✅ 관리자 대시보드 (뉴스 관리)
 8. ✅ 자동 스케줄링
 9. ✅ 유사도 필터링 UI

 📝 핵심 파일 요약
 ┌─────────────────────────┬───────────────────────────────────────┬──────────┐
 │          파일           │                 작업                  │ 우선순위 │
 ├─────────────────────────┼───────────────────────────────────────┼──────────┤
 │ didyouknow_service.py   │ FactCategory 추가, 뉴스-API 매칭 로직 │ 필수     │
 ├─────────────────────────┼───────────────────────────────────────┼──────────┤
 │ didyouknow.py (prompts) │ 뉴스 추천 프롬프트 작성               │ 필수     │
 ├─────────────────────────┼───────────────────────────────────────┼──────────┤
 │ didyouknow.py (routers) │ CategoryCounts 업데이트               │ 필수     │
 ├─────────────────────────┼───────────────────────────────────────┼──────────┤
 │ page.tsx (didyouknow)   │ UI 레이블 및 색상 추가                │ 필수     │
 ├─────────────────────────┼───────────────────────────────────────┼──────────┤
 │ GenerateFactsModal.tsx  │ 뉴스 추천 입력 필드 추가              │ 필수     │
 ├─────────────────────────┼───────────────────────────────────────┼──────────┤
 │ admin/news/page.tsx     │ 관리자 대시보드 (신규)                │ 권장     │
 ├─────────────────────────┼───────────────────────────────────────┼──────────┤
 │ admin_news.py (routers) │ 관리자 API (신규)                     │ 권장     │
 ├─────────────────────────┼───────────────────────────────────────┼──────────┤
 │ scheduler_service.py    │ 자동 스케줄링 (신규)                  │ 권장     │
 ├─────────────────────────┼───────────────────────────────────────┼──────────┤
 │ config.py               │ 유사도 임계값 설정                    │ 권장     │
 └─────────────────────────┴───────────────────────────────────────┴──────────┘
 🔧 환경 설정

 1. 뉴스 디렉토리 생성

 mkdir -p nara_service/backend/storage/naver_news

 2. 샘플 뉴스 파일 생성 (테스트용)

 cat > nara_service/backend/storage/naver_news/20260121.json << 'EOF'
 {
   "crawled_date": "2026-01-21",
   "articles": [
     {
       "article_id": "test_001",
       "title": "정부, AI 데이터센터 구축에 1조원 투입",
       "summary": "과학기술정보통신부가 AI 기술 발전을 위해 대규모 데이터센터를 구축한다고 발표했다.",
       "url": "https://example.com/news/001",
       "published_at": "2026-01-21T09:00:00",
       "category": "과학/IT",
       "source": "연합뉴스"
     }
   ]
 }
 EOF

 3. 백엔드 서비스 재시작

 수정 후 백엔드를 재시작해야 RAG 서비스 업데이트가 반영됩니다.

 🚀 실행 순서

 1. 백엔드 수정 (Phase 1-2)
 2. 프론트엔드 수정 (Phase 3)
 3. 샘플 뉴스 파일 생성
 4. 백엔드 재시작
 5. 프론트엔드에서 생성 테스트
 6. 관리자 대시보드 구현 (Phase 4)
 7. 자동 스케줄링 구현 (Phase 5)
 8. 유사도 필터링 UI (Phase 6)