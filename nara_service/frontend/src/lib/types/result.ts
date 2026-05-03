/**
 * Result Pattern Implementation
 *
 * Why: 에러를 예외 대신 명시적 타입으로 표현하여
 *      호출자가 에러 처리를 강제하고 타입 안전성을 보장합니다.
 *
 * CODING_RULES 준수:
 *    - Type Safety: 완전한 타입 힌트
 *    - FP First: 함수형 프로그래밍 패턴
 *    - Error Handling: 예외 대신 Result 타입 사용
 */

export type ErrorCode =
  | 'NETWORK_ERROR'
  | 'TIMEOUT_ERROR'
  | 'VALIDATION_ERROR'
  | 'NOT_FOUND'
  | 'UNAUTHORIZED'
  | 'FORBIDDEN'
  | 'SERVER_ERROR'
  | 'UNKNOWN_ERROR';

export interface ResultError {
  code: ErrorCode;
  message: string;
  details?: unknown;
}

/**
 * Result 타입 - 성공 또는 실패를 표현
 *
 * Why: 타입 시스템을 통해 에러 처리를 강제하여
 *      런타임 에러를 줄이고 안전성을 높입니다.
 */
export type Result<T, E = ResultError> =
  | { success: true; data: T }
  | { success: false; error: E };

/**
 * 성공 Result 생성
 *
 * @param data 성공 데이터
 * @returns 성공 Result
 */
export const success = <T>(data: T): Result<T, never> => ({
  success: true,
  data,
});

/**
 * 실패 Result 생성
 *
 * @param error 에러 정보
 * @returns 실패 Result
 */
export const failure = <E = ResultError>(error: E): Result<never, E> => ({
  success: false,
  error,
});

/**
 * 에러 코드로 실패 Result 생성
 *
 * @param code 에러 코드
 * @param message 에러 메시지
 * @param details 추가 상세 정보
 * @returns 실패 Result
 */
export const failureWithCode = (
  code: ErrorCode,
  message: string,
  details?: unknown
): Result<never, ResultError> => ({
  success: false,
  error: { code, message, details },
});

/**
 * Result를 매핑하여 성공 시 변환 적용
 *
 * Why: 함수형 프로그래밍 패턴으로 Result를 안전하게 변환합니다.
 *
 * @param result 원본 Result
 * @param fn 변환 함수
 * @returns 변환된 Result
 */
export const mapResult = <T, U, E>(
  result: Result<T, E>,
  fn: (data: T) => U
): Result<U, E> => {
  if (result.success) {
    return success(fn(result.data));
  }
  return result;
};

/**
 * Result를 비동기 매핑하여 성공 시 변환 적용
 *
 * @param result 원본 Result
 * @param fn 비동기 변환 함수
 * @returns 변환된 Result Promise
 */
export const mapResultAsync = async <T, U, E>(
  result: Result<T, E>,
  fn: (data: T) => Promise<U>
): Promise<Result<U, E>> => {
  if (result.success) {
    return success(await fn(result.data));
  }
  return result;
};

/**
 * HTTP 상태 코드를 ErrorCode로 매핑
 *
 * Why: HTTP 응답 코드를 애플리케이션 에러 코드로 변환하여
 *      일관된 에러 처리를 제공합니다.
 *
 * @param status HTTP 상태 코드
 * @returns ErrorCode
 */
export const httpStatusToErrorCode = (status: number): ErrorCode => {
  if (status === 401) return 'UNAUTHORIZED';
  if (status === 403) return 'FORBIDDEN';
  if (status === 404) return 'NOT_FOUND';
  if (status === 400) return 'VALIDATION_ERROR';
  if (status >= 500) return 'SERVER_ERROR';
  return 'UNKNOWN_ERROR';
};

/**
 * Error를 ResultError로 변환
 *
 * @param error Error 객체
 * @returns ResultError
 */
export const errorToResultError = (error: unknown): ResultError => {
  if (error instanceof Error) {
    if (error.name === 'AbortError') {
      return {
        code: 'TIMEOUT_ERROR',
        message: 'Request timed out',
        details: error,
      };
    }

    // Check for network error
    if (error.message.includes('fetch') || error.message.includes('network')) {
      return {
        code: 'NETWORK_ERROR',
        message: error.message,
        details: error,
      };
    }

    return {
      code: 'UNKNOWN_ERROR',
      message: error.message,
      details: error,
    };
  }

  return {
    code: 'UNKNOWN_ERROR',
    message: 'An unknown error occurred',
    details: error,
  };
};
