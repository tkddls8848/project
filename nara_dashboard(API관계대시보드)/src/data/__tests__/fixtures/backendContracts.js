import { vi } from 'vitest';

export const SEARCH_PAYLOAD = {
  query: '대기오염',
  results: [
    { service_id: 'openapi_new:15000001', name: '대기오염정보' },
    { service_id: 'openapi_new:15000003', name: '측정소정보' },
  ],
};

export const DETAILS = {
  'openapi_new:15000001': {
    service_id: 'openapi_new:15000001',
    name: '한국환경공단_에어코리아_대기오염정보',
    provider_agency_name: '한국환경공단',
    category: '환경기상 - 대기',
    keywords: ['대기오염'],
    description: '시도별 실시간 대기오염 측정정보',
    endpoints: [{ method: 'GET', path: '/getCtprvnRltmMesureDnsty', summary: '시도별 조회' }],
    request_fields: [{ name: 'sidoName', description: '시도 이름' }],
    response_fields: [{ name: 'pm10Value', description: '미세먼지(PM10) 농도' }],
  },
  'openapi_new:15000003': {
    service_id: 'openapi_new:15000003',
    name: '한국환경공단_에어코리아_측정소정보',
    provider_agency_name: '한국환경공단',
    category: '환경기상 - 대기',
    keywords: ['측정소'],
    description: '측정소 위치와 정보',
    endpoints: [{ method: 'GET', path: '/getMsrstnList', summary: '측정소 목록' }],
    request_fields: [{ name: 'sidoName', description: '시도 이름' }],
    response_fields: [{ name: 'sidoName', description: '시도 이름' }],
  },
};

export const RELATIONS_PAYLOAD = {
  ids: Object.keys(DETAILS),
  missing: [],
  relations: [{
    id: 'rel:io-chain:openapi_new:15000003:openapi_new:15000001',
    source: 'openapi_new:15000003',
    target: 'openapi_new:15000001',
    type: 'io-chain',
    evidence: ['응답 sidoName → 요청 sidoName'],
    confidence: 0.6,
    status: 'derived',
    generatedAt: '2026-07-16',
  }],
};

export function stubBackend() {
  vi.stubGlobal('fetch', vi.fn(async (url) => {
    const path = String(url);
    if (path === '/api/search' || path.startsWith('/api/search')) {
      return { ok: true, json: async () => SEARCH_PAYLOAD };
    }
    if (path.startsWith('/api/relations')) {
      return { ok: true, json: async () => RELATIONS_PAYLOAD };
    }
    const detail = DETAILS[decodeURIComponent(path.replace('/api/services/', ''))];
    return detail
      ? { ok: true, json: async () => detail }
      : { ok: false, status: 404, json: async () => ({ ok: false }) };
  }));
}
