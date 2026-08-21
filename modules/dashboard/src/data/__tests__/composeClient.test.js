import { afterEach, describe, expect, it, vi } from 'vitest';
import { compose, ComposeError } from '../composeClient.js';

afterEach(() => vi.unstubAllGlobals());

describe('compose', () => {
  it('성공 응답을 그대로 반환한다', async () => {
    const payload = {
      service_ids: ['openapi_new:15000001'], domains: ['환경기상'],
      warning: null, missing: [], suggestion: '조합 제안 본문',
      truncated: false, elapsed_ms: 1200, model: 'gemma4:e4b',
    };
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => payload }));
    const result = await compose(['openapi_new:15000001'], '무엇이 가능한가?');
    expect(result.suggestion).toBe('조합 제안 본문');
    expect(fetch).toHaveBeenCalledWith('/combiner/compose', expect.objectContaining({ method: 'POST' }));
  });

  it('오류 계약(error_code/message)을 ComposeError로 변환한다', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false, status: 503,
      json: async () => ({ ok: false, error_code: 'UPSTREAM_UNAVAILABLE', message: 'Ollama 연결 실패' }),
    }));
    await expect(compose(['1'], 'q')).rejects.toMatchObject({
      errorCode: 'UPSTREAM_UNAVAILABLE', message: 'Ollama 연결 실패',
    });
  });

  it('백엔드 미기동이면 CONNECTION 오류를 던진다', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('ECONNREFUSED')));
    await expect(compose(['1'], 'q')).rejects.toBeInstanceOf(ComposeError);
  });
});
