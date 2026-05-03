/**
 * Graph Exploration API Client
 *
 * Why: Result Pattern을 적용하여 타입 안전한 에러 처리를 제공합니다.
 */

import { BASE_URL, fetchWithTimeout, fetchWithResult, HEADERS } from './client';
import type { Result } from '@/lib/types/result';

// ==========================================
// Types (Phase 3)
// ==========================================

export interface RelationshipCreate {
  source_id: string;
  target_id: string;
  custom_type: string;
  description: string;
  strength?: number;
}

export interface RelationshipUpdate {
  custom_type?: string;
  description?: string;
  strength?: number;
}

export interface Relationship {
  id: string;
  source_id: string;
  source_title: string;
  target_id: string;
  target_title: string;
  custom_type: string;
  description: string;
  strength?: number;
  created_by: string;
  created_at: string;
}

export interface RelationshipListResponse {
  relationships: Relationship[];
  total: number;
}

export interface RelationshipSuggestion {
  target_doc: {
    id: string;
    title: string;
    description: string;
    category: string;
  };
  suggested_type: string;
  reason: string;
  confidence: number;
  common_keywords: string[];
  common_category?: string;
  common_provider?: string;
}

export interface RelationshipSuggestionsResponse {
  doc_id: string;
  suggestions: RelationshipSuggestion[];
  total: number;
}

/**
 * 특정 문서 주변의 그래프 데이터 탐색
 *
 * Why: Result Pattern을 사용하여 타입 안전한 에러 처리를 제공합니다.
 *
 * @param docId 문서 ID
 * @param depth 탐색 깊이 (1-3, 기본값 2)
 * @returns Result<노드와 엣지 데이터>
 */
export const exploreGraph = async <T = any>(docId: string, depth: number = 2): Promise<Result<T>> => {
  return await fetchWithResult<T>(
    `${BASE_URL}/graph/explore/${encodeURIComponent(docId)}?depth=${depth}`,
    {
      method: 'GET',
      headers: HEADERS,
    },
    10000
  );
};

/**
 * 전체 그래프 통계 및 상위 엔티티 조회
 *
 * Why: Result Pattern을 사용하여 타입 안전한 에러 처리를 제공합니다.
 *
 * @returns Result<통계 및 상위 키워드/제공기관/카테고리>
 */
export const getGraphSummary = async <T = any>(): Promise<Result<T>> => {
  return await fetchWithResult<T>(
    `${BASE_URL}/graph/summary`,
    {
      method: 'GET',
      headers: HEADERS,
    },
    10000
  );
};

/**
 * 두 문서 간 최단 경로 탐색
 *
 * Why: Result Pattern을 사용하여 타입 안전한 에러 처리를 제공합니다.
 *
 * @param sourceId 시작 문서 ID
 * @param targetId 목표 문서 ID
 * @returns Result<경로 노드, 관계, insights>
 */
export const findPath = async <T = any>(sourceId: string, targetId: string): Promise<Result<T>> => {
  return await fetchWithResult<T>(
    `${BASE_URL}/graph/path`,
    {
      method: 'POST',
      headers: HEADERS,
      body: JSON.stringify({
        source_id: sourceId,
        target_id: targetId,
      }),
    },
    10000
  );
};

// ==========================================
// Custom Relationship API (Phase 3)
// ==========================================

/**
 * 사용자 정의 관계 생성
 *
 * Why: Result Pattern을 사용하여 타입 안전한 에러 처리를 제공합니다.
 *
 * @param data 관계 생성 데이터
 * @returns Result<생성된 관계 정보>
 */
export const createRelationship = async (data: RelationshipCreate): Promise<Result<Relationship>> => {
  return await fetchWithResult<Relationship>(
    `${BASE_URL}/graph/relationship`,
    {
      method: 'POST',
      headers: HEADERS,
      body: JSON.stringify(data),
    },
    10000
  );
};

/**
 * 사용자 정의 관계 조회
 *
 * Why: Result Pattern을 사용하여 타입 안전한 에러 처리를 제공합니다.
 *
 * @param relId 관계 ID
 * @returns Result<관계 정보>
 */
export const getRelationship = async (relId: string): Promise<Result<Relationship>> => {
  return await fetchWithResult<Relationship>(
    `${BASE_URL}/graph/relationship/${encodeURIComponent(relId)}`,
    {
      method: 'GET',
      headers: HEADERS,
    },
    10000
  );
};

/**
 * 사용자 정의 관계 수정
 *
 * Why: Result Pattern을 사용하여 타입 안전한 에러 처리를 제공합니다.
 *
 * @param relId 관계 ID
 * @param data 수정 데이터
 * @returns Result<수정된 관계 정보>
 */
export const updateRelationship = async (
  relId: string,
  data: RelationshipUpdate
): Promise<Result<Relationship>> => {
  return await fetchWithResult<Relationship>(
    `${BASE_URL}/graph/relationship/${encodeURIComponent(relId)}`,
    {
      method: 'PUT',
      headers: HEADERS,
      body: JSON.stringify(data),
    },
    10000
  );
};

/**
 * 사용자 정의 관계 삭제
 *
 * Why: Result Pattern을 사용하여 타입 안전한 에러 처리를 제공합니다.
 *
 * @param relId 관계 ID
 * @returns Result<void>
 */
export const deleteRelationship = async (relId: string): Promise<Result<void>> => {
  return await fetchWithResult<void>(
    `${BASE_URL}/graph/relationship/${encodeURIComponent(relId)}`,
    {
      method: 'DELETE',
      headers: HEADERS,
    },
    10000
  );
};

/**
 * 사용자 정의 관계 목록 조회
 *
 * Why: Result Pattern을 사용하여 타입 안전한 에러 처리를 제공합니다.
 *
 * @param limit 최대 조회 개수 (기본값 100)
 * @returns Result<관계 목록 및 총 개수>
 */
export const listUserRelationships = async (limit: number = 100): Promise<Result<RelationshipListResponse>> => {
  return await fetchWithResult<RelationshipListResponse>(
    `${BASE_URL}/graph/relationship?limit=${limit}`,
    {
      method: 'GET',
      headers: HEADERS,
    },
    10000
  );
};

// ==========================================
// AI Relationship Suggestions (Phase 3 Priority 3)
// ==========================================

/**
 * AI 관계 추천: 특정 문서와 관계를 맺으면 유용할 다른 문서들을 추천
 *
 * Why: Result Pattern을 사용하여 타입 안전한 에러 처리를 제공합니다.
 *
 * @param docId 기준 문서 ID
 * @param limit 최대 추천 개수 (기본값 5, 최대 10)
 * @returns Result<AI 추천 목록>
 */
export const getSuggestedRelationships = async (
  docId: string,
  limit: number = 5
): Promise<Result<RelationshipSuggestionsResponse>> => {
  return await fetchWithResult<RelationshipSuggestionsResponse>(
    `${BASE_URL}/graph/relationships/suggestions/${encodeURIComponent(docId)}?limit=${limit}`,
    {
      method: 'GET',
      headers: HEADERS,
    },
    10000
  );
};

// ==========================================
// Advanced Insights API (Phase 4)
// ==========================================

// Relationship Chains
export interface RelationshipChain {
  chain_id: string;
  nodes: Array<{
    id: string;
    title: string;
    category: string;
    description: string;
  }>;
  relationships: Array<{
    type: string;
    description: string;
    strength?: number;
  }>;
  length: number;
  chain_types: string[];
  insight: string;
}

export interface RelationshipChainsResponse {
  doc_id: string;
  chains: RelationshipChain[];
  total: number;
}

// Hidden Connections
export interface HiddenConnection {
  source_doc: {
    id: string;
    title: string;
    category: string;
    description: string;
  };
  target_doc: {
    id: string;
    title: string;
    category: string;
    description: string;
  };
  intermediate_nodes: Array<{
    type: string;
    name: string;
  }>;
  connection_strength: number;
  common_attributes: {
    keywords: string[];
    category?: string;
    provider?: string;
  };
  suggested_relationship: string;
  reason: string;
}

export interface HiddenConnectionsResponse {
  doc_id: string;
  connections: HiddenConnection[];
  total: number;
}

// Communities
export interface Community {
  community_id: number;
  nodes: Array<{
    id: string;
    title: string;
    category: string;
    provider: string;
  }>;
  size: number;
  dominant_category?: string;
  dominant_provider?: string;
  common_keywords: string[];
  description: string;
}

export interface CommunitiesResponse {
  communities: Community[];
  total_communities: number;
  modularity: number;
}

// Centrality Analysis
export interface NodeCentrality {
  node_id: string;
  node_title: string;
  node_type: string;
  degree_centrality: number;
  betweenness_centrality: number;
  pagerank: number;
  importance_score: number;
}

export interface CentralityAnalysisResponse {
  top_nodes: NodeCentrality[];
  total_analyzed: number;
  insights: string;
}

// Complementary Data
export interface ComplementaryData {
  doc_id: string;
  title: string;
  category: string;
  relevance_score: number;
  gap_filled: string;
  reason: string;
}

export interface ComplementaryDataResponse {
  doc_id: string;
  recommendations: ComplementaryData[];
  total: number;
  coverage_analysis: {
    current_keywords: string[];
    current_categories: string[];
    current_providers: string[];
    connected_count: number;
  };
}

/**
 * 관계 체인 발견
 *
 * Why: Result Pattern을 사용하여 타입 안전한 에러 처리를 제공합니다.
 *
 * @param docId 기준 문서 ID
 * @param minLength 최소 체인 길이 (기본값 2)
 * @param maxLength 최대 체인 길이 (기본값 4)
 * @param limit 최대 반환 개수 (기본값 10)
 * @returns Result<관계 체인 목록>
 */
export const getRelationshipChains = async (
  docId: string,
  minLength: number = 2,
  maxLength: number = 4,
  limit: number = 10
): Promise<Result<RelationshipChainsResponse>> => {
  return await fetchWithResult<RelationshipChainsResponse>(
    `${BASE_URL}/insights/chains/${encodeURIComponent(docId)}?min_length=${minLength}&max_length=${maxLength}&limit=${limit}`,
    {
      method: 'GET',
      headers: HEADERS,
    },
    15000
  );
};

/**
 * 숨겨진 연결 발견
 *
 * Why: Result Pattern을 사용하여 타입 안전한 에러 처리를 제공합니다.
 *
 * @param docId 기준 문서 ID
 * @param limit 최대 반환 개수 (기본값 10)
 * @returns Result<숨겨진 연결 목록>
 */
export const getHiddenConnections = async (
  docId: string,
  limit: number = 10
): Promise<Result<HiddenConnectionsResponse>> => {
  return await fetchWithResult<HiddenConnectionsResponse>(
    `${BASE_URL}/insights/hidden-connections/${encodeURIComponent(docId)}?limit=${limit}`,
    {
      method: 'GET',
      headers: HEADERS,
    },
    15000
  );
};

/**
 * 커뮤니티 탐지
 *
 * Why: Result Pattern을 사용하여 타입 안전한 에러 처리를 제공합니다.
 *
 * @param minSize 최소 커뮤니티 크기 (기본값 3)
 * @returns Result<커뮤니티 목록>
 */
export const getCommunities = async (
  minSize: number = 3
): Promise<Result<CommunitiesResponse>> => {
  return await fetchWithResult<CommunitiesResponse>(
    `${BASE_URL}/insights/communities?min_size=${minSize}`,
    {
      method: 'GET',
      headers: HEADERS,
    },
    20000
  );
};

/**
 * 중심성 분석
 *
 * Why: Result Pattern을 사용하여 타입 안전한 에러 처리를 제공합니다.
 *
 * @param limit 최대 반환 노드 개수 (기본값 20)
 * @returns Result<중심성 분석 결과>
 */
export const getCentralityAnalysis = async (
  limit: number = 20
): Promise<Result<CentralityAnalysisResponse>> => {
  return await fetchWithResult<CentralityAnalysisResponse>(
    `${BASE_URL}/insights/centrality?limit=${limit}`,
    {
      method: 'GET',
      headers: HEADERS,
    },
    20000
  );
};

/**
 * 보완 데이터 추천
 *
 * Why: Result Pattern을 사용하여 타입 안전한 에러 처리를 제공합니다.
 *
 * @param docId 기준 문서 ID
 * @param limit 최대 추천 개수 (기본값 10)
 * @returns Result<보완 데이터 추천 목록>
 */
export const getComplementaryData = async (
  docId: string,
  limit: number = 10
): Promise<Result<ComplementaryDataResponse>> => {
  return await fetchWithResult<ComplementaryDataResponse>(
    `${BASE_URL}/insights/complementary/${encodeURIComponent(docId)}?limit=${limit}`,
    {
      method: 'GET',
      headers: HEADERS,
    },
    15000
  );
};
