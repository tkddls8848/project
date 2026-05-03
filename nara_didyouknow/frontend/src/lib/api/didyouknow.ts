/**
 * Did You Know API Client
 */
import { BASE_URL, HEADERS, fetchWithResult } from './client';
import type { Result } from '@/lib/types/result';

export interface Fact {
  id: string;
  category: string;
  content: string;
  source_doc_id?: string;
  created_at: string;
  metadata?: Record<string, any>;
}

export interface FactsListResponse {
  total: number;
  facts: Fact[];
}

export interface StatsResponse {
  total: number;
  by_category: Record<string, number>;
}

export interface GenerateResponse {
  status: string;
  generated_count: number;
  total_count: number;
}

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

export const getStats = async (): Promise<Result<StatsResponse>> => {
  return await fetchWithResult<StatsResponse>(`${BASE_URL}/didyouknow/stats`, {
    method: 'GET',
    headers: HEADERS,
  });
};

export const generateFacts = async (
  config: GenerateConfig
): Promise<Result<GenerateResponse>> => {
  const LONG_TIMEOUT = 15 * 60 * 1000; // 15분

  return await fetchWithResult<GenerateResponse>(
    `${BASE_URL}/didyouknow/generate`,
    {
      method: 'POST',
      headers: HEADERS,
      body: JSON.stringify(config),
    },
    LONG_TIMEOUT
  );
};
