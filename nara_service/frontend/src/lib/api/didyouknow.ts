/**
 * Did You Know API - 흥미로운 공공데이터 사실
 *
 * Why: Result Pattern을 적용하여 타입 안전한 에러 처리를 제공합니다.
 */
import { BASE_URL, HEADERS, fetchWithResult } from './client';
import type { Result } from '@/lib/types/result';

/**
 * 사실 인터페이스
 */
export interface Fact {
  id: string;
  category: string;
  content: string;
  source_doc_id?: string;
  created_at: string;
  metadata?: Record<string, any>;
}

/**
 * 사실 목록 응답
 */
export interface FactsListResponse {
  total: number;
  facts: Fact[];
}

/**
 * 통계 응답
 */
export interface StatsResponse {
  total: number;
  by_category: Record<string, number>;
}

/**
 * 모든 사실 조회
 *
 * Why: Result Pattern을 사용하여 타입 안전한 에러 처리를 제공합니다.
 *
 * @param category 카테고리 필터 (선택)
 * @returns Result<사실 목록>
 */
export const getAllFacts = async (
  category?: string
): Promise<Result<FactsListResponse>> => {
  const url = category
    ? `${BASE_URL}/didyouknow/facts?category=${category}`
    : `${BASE_URL}/didyouknow/facts`;

  return await fetchWithResult<FactsListResponse>(url, {
    method: 'GET',
    headers: HEADERS,
  });
};

/**
 * 랜덤 사실 1개 조회
 *
 * Why: Result Pattern을 사용하여 타입 안전한 에러 처리를 제공합니다.
 *
 * @param category 카테고리 필터 (선택)
 * @returns Result<단일 사실>
 */
export const getRandomFact = async (
  category?: string
): Promise<Result<Fact>> => {
  const url = category
    ? `${BASE_URL}/didyouknow/random?category=${category}`
    : `${BASE_URL}/didyouknow/random`;

  return await fetchWithResult<Fact>(url, {
    method: 'GET',
    headers: HEADERS,
  });
};

/**
 * 통계 조회
 *
 * Why: Result Pattern을 사용하여 타입 안전한 에러 처리를 제공합니다.
 *
 * @returns Result<통계 정보>
 */
export const getStats = async (): Promise<Result<StatsResponse>> => {
  return await fetchWithResult<StatsResponse>(`${BASE_URL}/didyouknow/stats`, {
    method: 'GET',
    headers: HEADERS,
  });
};

/**
 * 생성 결과 응답
 */
export interface GenerateResponse {
  status: string;
  generated_count: number;
  total_count: number;
}

/**
 * 생성 설정 인터페이스
 */
export interface GenerateConfig {
  counts: {
    api_introduction: number;
    provider_introduction: number;
    usage_tip: number;
  };
  llm_params: {
    temperature: number;
    top_p: number;
    max_tokens: number;
  };
}

/**
 * 신문기사 정보 인터페이스
 */
export interface ArticleInfo {
  index: number;
  title: string;
  url: string;
  count: number;
  article_preview: string;
}

/**
 * 관련 API 응답 인터페이스
 */
export interface RelatedAPI {
  id: string;
  title: string;
  description: string;
  provider: string;
  keywords: string[];
  url: string;
  type: string;
  score: number;
  rank_method?: string; // 하이브리드 RAG용 (llm_reranked, keyword_fallback)
}

/**
 * 신문기사와 관련 API 인터페이스
 */
export interface ArticleWithAPIs {
  index: number;
  title: string;
  url: string;
  count: number;
  article_preview: string;
  related_apis: RelatedAPI[];
  match_method?: string; // hybrid_rag, keyword_only
}

/**
 * 새 콘텐츠 생성 (관리자용)
 *
 * Why: Result Pattern을 사용하여 타입 안전한 에러 처리를 제공합니다.
 *      생성에 5-10분이 걸릴 수 있으므로 timeout을 15분으로 설정합니다.
 *
 * @param config 생성 설정 (카테고리별 개수, LLM 파라미터)
 * @returns Result<생성 결과>
 */
export const generateFacts = async (
  config: GenerateConfig
): Promise<Result<GenerateResponse>> => {
  // 15분 timeout (생성 시간이 길 수 있음)
  const LONG_TIMEOUT = 15 * 60 * 1000; // 900000ms

  return await fetchWithResult<GenerateResponse>(
    `/api/backend/didyouknow/generate`,
    {
      method: 'POST',
      headers: HEADERS,
      body: JSON.stringify(config),
    },
    LONG_TIMEOUT
  );
};

/**
 * 모든 신문기사 목록 조회
 *
 * @returns Result<신문기사 목록>
 */
export const getArticles = async (): Promise<Result<ArticleInfo[]>> => {
  return await fetchWithResult<ArticleInfo[]>(`${BASE_URL}/didyouknow/articles`, {
    method: 'GET',
    headers: HEADERS,
  });
};

/**
 * 신문기사 내용 기반으로 관련 API 문서 찾기
 *
 * @param articleIndex 기사 인덱스 (1부터 시작)
 * @param articleText 직접 제공된 기사 텍스트 (선택)
 * @param topK 반환할 문서 개수 (기본값: 20)
 * @returns Result<관련 API 목록>
 */
export const getRelatedAPIs = async (
  articleIndex?: number,
  articleText?: string,
  topK: number = 20
): Promise<Result<RelatedAPI[]>> => {
  const params = new URLSearchParams();
  if (articleIndex) params.append('article_index', articleIndex.toString());
  if (articleText) params.append('article_text', articleText);
  params.append('top_k', topK.toString());

  const url = `${BASE_URL}/didyouknow/related-apis?${params.toString()}`;

  return await fetchWithResult<RelatedAPI[]>(url, {
    method: 'GET',
    headers: HEADERS,
  });
};

/**
 * 모든 신문기사와 관련 API 목록 조회 (키워드 기반, 미리 계산됨)
 *
 * @param topK 각 기사당 반환할 API 개수 (기본값: 20)
 * @param minScore 최소 유사도 점수 (기본값: 25.0, 키워드 유사도 0–100 스케일)
 * @returns Result<신문기사와 관련 API 목록>
 */
export const getArticlesWithAPIs = async (
  topK: number = 20,
  minScore: number = 25.0
): Promise<Result<ArticleWithAPIs[]>> => {
  const params = new URLSearchParams();
  params.append('top_k', topK.toString());
  params.append('min_score', minScore.toString());

  const url = `${BASE_URL}/didyouknow/articles-with-apis?${params.toString()}`;

  return await fetchWithResult<ArticleWithAPIs[]>(url, {
    method: 'GET',
    headers: HEADERS,
  });
};

/**
 * 하이브리드 RAG로 매칭된 신문기사와 관련 API 목록 조회
 *
 * 2단계 접근 방식:
 * 1. 키워드 필터링 (빠름, 100k → 30 후보)
 * 2. LLM 의미적 재랭킹 (gemma3:4b, 30 → 5 최종)
 *
 * @param useCache 캐시된 결과 사용 여부 (기본값: true)
 * @param forceRegenerate 캐시 무시하고 강제 재생성 (기본값: false)
 * @returns Result<신문기사와 관련 API 목록>
 */
export const getArticlesWithAPIsHybrid = async (
  useCache: boolean = true,
  forceRegenerate: boolean = false
): Promise<Result<ArticleWithAPIs[]>> => {
  const params = new URLSearchParams();
  params.append('use_cache', useCache.toString());
  params.append('force_regenerate', forceRegenerate.toString());

  const url = `${BASE_URL}/didyouknow/articles-with-apis-hybrid?${params.toString()}`;

  // 재생성 시 최대 2분 대기 (20기사 × 4초)
  const timeout = forceRegenerate ? 120000 : 30000;

  return await fetchWithResult<ArticleWithAPIs[]>(url, {
    method: 'GET',
    headers: HEADERS,
  }, timeout);
};

/**
 * 재생성 응답 인터페이스
 */
export interface RegenerateResponse {
  status: string;
  generated_at: string;
  total_articles: number;
  total_matches: number;
  avg_matches_per_article: number;
  method: string;
  message: string;
}

/**
 * 신문기사-API 매칭 수동 재생성
 *
 * 사용 사례:
 * - 새 media_links_*.json 파일 업로드
 * - index.json 업데이트 (새 API 추가)
 * - 매칭 알고리즘 파라미터 변경 후 테스트
 *
 * @returns Result<재생성 결과>
 */
export const regenerateArticleMatches = async (): Promise<Result<RegenerateResponse>> => {
  // 재생성에 최대 2분 소요
  const REGENERATE_TIMEOUT = 120000;

  return await fetchWithResult<RegenerateResponse>(
    `${BASE_URL}/didyouknow/regenerate-article-matches`,
    {
      method: 'POST',
      headers: HEADERS,
    },
    REGENERATE_TIMEOUT
  );
};
