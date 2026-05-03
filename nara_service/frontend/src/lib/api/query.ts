/**
 * Query API - RAG query and feedback
 *
 * Why: Result Pattern을 적용하여 타입 안전한 에러 처리를 제공합니다.
 */
import { LLMType, APIDocData } from '@/types';
import { BASE_URL, HEADERS, TIMEOUT_MS, fetchWithResult } from './client';
import type { Result } from '@/lib/types/result';

export const submitQuery = async (
  query: string,
  llmType: LLMType,
  onToken?: (token: string) => void
) => {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), TIMEOUT_MS);

  try {
    const response = await fetch(`${BASE_URL}/query/stream`, {
      method: 'POST',
      headers: HEADERS,
      body: JSON.stringify({
        message: query,
        llm_type: llmType,
      }),
      signal: controller.signal,
    });
    clearTimeout(timeoutId);

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    if (!response.body) {
      throw new Error('No response body');
    }

    // Read streaming response
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let finalMessage = '';
    let relevantDocuments: APIDocData[] = [];
    let totalDocuments = 0;
    let relatedDocuments: any[] = [];
    let contextInsights: string[] = [];

    while (true) {
      const { done, value } = await reader.read();

      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');

      // Keep the last incomplete line in the buffer
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (!line.trim()) continue;

        try {
          const data = JSON.parse(line);

          if (data.type === 'documents') {
            relevantDocuments = data.data || [];
            totalDocuments = data.total || 0;
          } else if (data.type === 'related_documents') {
            // Neo4j related documents
            relatedDocuments = data.data || [];
            contextInsights = data.insights || [];
          } else if (data.type === 'token') {
            // Accumulate tokens for streaming response (Ollama)
            const token = data.data;
            finalMessage += token;
            // Call onToken callback for real-time updates
            if (onToken) {
              onToken(token);
            }
          } else if (data.type === 'complete') {
            // Complete response (OpenAI)
            finalMessage = data.data;
            // Call onToken callback with complete message
            if (onToken) {
              onToken(data.data);
            }
          } else if (data.type === 'error') {
            throw new Error(data.data);
          } else if (data.type === 'done') {
            // Stream completed
            break;
          }
        } catch (parseError) {
          console.error('Failed to parse line:', line, parseError);
        }
      }
    }

    return {
      message: finalMessage,
      relevant_documents: relevantDocuments,
      total_documents: totalDocuments,
      related_documents: relatedDocuments,
      context_insights: contextInsights,
    };
  } catch (error: unknown) {
    if (error instanceof Error && error.name === 'AbortError') {
      throw new Error('Request timed out');
    }
    throw error;
  }
};

/**
 * 피드백 저장
 *
 * Why: Result Pattern을 사용하여 타입 안전한 에러 처리를 제공합니다.
 *
 * @param query 사용자 질의
 * @param answer LLM 응답
 * @param feedback 피드백 (like | dislike)
 * @param llmType LLM 타입
 * @param user 사용자 ID (선택)
 * @returns Result<피드백 저장 결과>
 */
export const saveFeedback = async <T = any>(
  query: string,
  answer: string,
  feedback: "like" | "dislike",
  llmType: LLMType,
  user?: string
): Promise<Result<T>> => {
  return await fetchWithResult<T>(`${BASE_URL}/feedback`, {
    method: 'POST',
    headers: HEADERS,
    body: JSON.stringify({
      query,
      response: answer,
      feedback,
      llm_type: llmType,
      timestamp: new Date().toISOString(),
      user: user || "",
    }),
  });
};
