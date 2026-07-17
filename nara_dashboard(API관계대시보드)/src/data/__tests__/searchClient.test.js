import { afterEach, describe, expect, it, vi } from 'vitest';
import { detailToWorkflowDoc, fetchRelations, searchDocsWithDetails } from '../searchClient.js';
import { DETAILS, stubBackend } from './fixtures/backendContracts.js';

afterEach(() => vi.unstubAllGlobals());

describe('searchClient', () => {
  it('검색 결과를 상세조회로 보강한 워크플로우 doc으로 돌려준다', async () => {
    stubBackend();
    const docs = await searchDocsWithDetails('대기오염', 5);
    expect(docs).toHaveLength(2);
    expect(docs[0]).toMatchObject({
      apiId: '15000001',
      serviceId: 'openapi_new:15000001',
      provider: '한국환경공단',
      topCategory: '환경기상',
      fields: [{ key: 'pm10Value', desc: '미세먼지(PM10) 농도' }],
    });
  });

  it('fetchRelations는 relations 배열을 반환한다', async () => {
    stubBackend();
    const relations = await fetchRelations(Object.keys(DETAILS));
    expect(relations).toHaveLength(1);
    expect(relations[0].type).toBe('io-chain');
  });

  it('detailToWorkflowDoc은 endpoints summary를 description으로 매핑한다', () => {
    const doc = detailToWorkflowDoc(DETAILS['openapi_new:15000001']);
    expect(doc.endpoints).toEqual([
      { method: 'GET', path: '/getCtprvnRltmMesureDnsty', description: '시도별 조회' },
    ]);
  });

  it('백엔드 미기동이면 명확한 오류를 던진다', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('ECONNREFUSED')));
    await expect(searchDocsWithDetails('대기오염', 5)).rejects.toThrow(/연결/);
  });
});
