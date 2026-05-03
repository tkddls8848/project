/**
 * Result Pattern Implementation
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

export type Result<T, E = ResultError> =
  | { success: true; data: T }
  | { success: false; error: E };

export const success = <T>(data: T): Result<T, never> => ({
  success: true,
  data,
});

export const failure = <E = ResultError>(error: E): Result<never, E> => ({
  success: false,
  error,
});

export const failureWithCode = (
  code: ErrorCode,
  message: string,
  details?: unknown
): Result<never, ResultError> => ({
  success: false,
  error: { code, message, details },
});

export const httpStatusToErrorCode = (status: number): ErrorCode => {
  if (status === 401) return 'UNAUTHORIZED';
  if (status === 403) return 'FORBIDDEN';
  if (status === 404) return 'NOT_FOUND';
  if (status === 400) return 'VALIDATION_ERROR';
  if (status >= 500) return 'SERVER_ERROR';
  return 'UNKNOWN_ERROR';
};

export const errorToResultError = (error: unknown): ResultError => {
  if (error instanceof Error) {
    if (error.name === 'AbortError') {
      return {
        code: 'TIMEOUT_ERROR',
        message: 'Request timed out',
        details: error,
      };
    }

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
