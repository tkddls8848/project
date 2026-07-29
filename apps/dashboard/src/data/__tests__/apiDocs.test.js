import { afterEach, describe, expect, it, vi } from 'vitest';
import { apiDocs, apiDocMap, loadCatalog, searchApiDocs } from '../apiDocs.js';

const CATALOG_PAYLOAD = {
  total: 1,
  docs: [{
    service_id: 'openapi_new:15000001',
    api_id: '15000001',
    name: '한국환경공단_에어코리아_대기오염정보',
    provider: '한국환경공단',
    category: '환경기상 - 대기',
    keywords: ['대기오염', '미세먼지'],
    description: '시도별 실시간 대기오염 측정정보를 조회하는 서비스',
    fields: [{ key: 'pm10Value', desc: '미세먼지(PM10) 농도' }],
    endpoints: [{ method: 'GET', path: '/getCtprvnRltmMesureDnsty', description: '시도별 실시간 측정정보 조회' }],
  }],
};

afterEach(() => vi.unstubAllGlobals());

describe('loadCatalog', () => {
  it('백엔드 카탈로그로 apiDocs/apiDocMap을 채운다', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => CATALOG_PAYLOAD }));
    const result = await loadCatalog({ force: true });

    expect(result.state).toBe('ready');
    expect(fetch).toHaveBeenCalledWith('/api/catalog');
    expect(apiDocs).toHaveLength(1);
    expect(apiDocMap['15000001'].topCategory).toBe('환경기상');
    expect(apiDocMap['15000001'].serviceId).toBe('openapi_new:15000001');
    expect(searchApiDocs('미세먼지')).toHaveLength(1);
  });

  it('백엔드 미기동이면 error 상태를 반환하고 기존 문서를 지우지 않는다', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('ECONNREFUSED')));
    const before = apiDocs.length;
    const result = await loadCatalog({ force: true });

    expect(result.state).toBe('error');
    expect(result.error).toBeTruthy();
    expect(apiDocs).toHaveLength(before);
  });
});
