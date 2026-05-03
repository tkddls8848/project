/**
 * API Client Configuration
 * Next.js API Routes를 통해 백엔드 호출 (보안 강화)
 * API Key는 서버 측에서만 사용되어 브라우저에 노출되지 않음
 */

import type { Result } from '@/lib/types/result';
import {
  success,
  failureWithCode,
  httpStatusToErrorCode,
  errorToResultError,
} from '@/lib/types/result';

export const BASE_URL = '/api/backend'; // Next.js API Routes

export const HEADERS = {
  'Content-Type': 'application/json',
};

export const TIMEOUT_MS = 60000; // Increased timeout for potentially long LLM responses

/**
 * Common fetch utility with timeout and error handling
 */
export const fetchWithTimeout = async (
  url: string,
  options: RequestInit = {},
  timeoutMs: number = TIMEOUT_MS
): Promise<Response> => {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
    });
    clearTimeout(timeoutId);

    if (!response.ok) {
      let errorMessage = `HTTP error! status: ${response.status}`;
      try {
        const errorData = await response.json();
        errorMessage = errorData.detail || errorMessage;
      } catch {
        // If response is not JSON, use the default error message
      }
      throw new Error(errorMessage);
    }

    return response;
  } catch (error: unknown) {
    if (error instanceof Error && error.name === 'AbortError') {
      throw new Error('Request timed out');
    }
    throw error;
  }
};

/**
 * Result Pattern을 사용하는 fetch 유틸리티
 *
 * Why: 에러를 예외 대신 Result 타입으로 반환하여
 *      타입 안전한 에러 처리를 강제합니다.
 *
 * @param url 요청 URL
 * @param options fetch 옵션
 * @param timeoutMs 타임아웃 시간
 * @returns Result<Response>
 */
export const fetchWithResult = async <T = unknown>(
  url: string,
  options: RequestInit = {},
  timeoutMs: number = TIMEOUT_MS
): Promise<Result<T>> => {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
    });
    clearTimeout(timeoutId);

    if (!response.ok) {
      let errorMessage = `HTTP error! status: ${response.status}`;
      try {
        const errorData = await response.json();
        errorMessage = errorData.detail || errorMessage;
      } catch {
        // If response is not JSON, use the default error message
      }

      return failureWithCode(
        httpStatusToErrorCode(response.status),
        errorMessage,
        { status: response.status }
      );
    }

    const data = await response.json() as T;
    return success(data);
  } catch (error: unknown) {
    clearTimeout(timeoutId);
    return failureWithCode(
      errorToResultError(error).code,
      errorToResultError(error).message,
      error
    );
  }
};
