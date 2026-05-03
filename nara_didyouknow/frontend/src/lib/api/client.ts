/**
 * API Client Configuration
 */

import type { Result } from '@/lib/types/result';
import {
  success,
  failureWithCode,
  httpStatusToErrorCode,
  errorToResultError,
} from '@/lib/types/result';

// 백엔드 URL (환경 변수로 설정 가능)
export const BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

export const HEADERS = {
  'Content-Type': 'application/json',
};

export const TIMEOUT_MS = 60000;

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
