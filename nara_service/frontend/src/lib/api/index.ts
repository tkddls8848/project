/**
 * API Module - Main entry point
 * Re-exports all API functions from split modules
 */

// Client configuration
export { BASE_URL, HEADERS, TIMEOUT_MS, fetchWithTimeout } from './client';

// Query API
export { submitQuery, saveFeedback } from './query';

// General API
export { checkHealth, getIndex } from './general';

// Detail API
export { getDetail } from './detail';

// Did You Know API
export { getAllFacts, getRandomFact, getStats, generateFacts, getArticles, getRelatedAPIs, getArticlesWithAPIs, getArticlesWithAPIsHybrid } from './didyouknow';
export type { Fact, FactsListResponse, StatsResponse, ArticleInfo, RelatedAPI, ArticleWithAPIs } from './didyouknow';
