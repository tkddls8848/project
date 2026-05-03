/**
 * General API - Health check, Index
 *
 * Why: Result Pattern을 적용하여 타입 안전한 에러 처리를 제공합니다.
 */
import { BASE_URL, HEADERS, fetchWithResult } from './client';
import type { Result } from '@/lib/types/result';

/**
 * 백엔드 헬스 체크
 *
 * Why: Result Pattern을 사용하여 타입 안전한 에러 처리를 제공합니다.
 *
 * @returns Result<헬스 체크 응답>
 */
export const checkHealth = async <T = any>(): Promise<Result<T>> => {
  return await fetchWithResult<T>(`${BASE_URL}/`, {
    method: 'GET',
    headers: HEADERS,
  });
};

/**
 * 인덱스 정보 조회
 *
 * Why: Result Pattern을 사용하여 타입 안전한 에러 처리를 제공합니다.
 *
 * @returns Result<인덱스 정보>
 */
export const getIndex = async <T = any>(): Promise<Result<T>> => {
  return await fetchWithResult<T>(`${BASE_URL}/index`, {
    method: 'GET',
    headers: HEADERS,
  });
};
