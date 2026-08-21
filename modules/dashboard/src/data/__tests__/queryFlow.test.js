import { afterEach, describe, expect, it, vi } from 'vitest';
import { fetchRelations, searchDocsWithDetails } from '../searchClient.js';
import { placeSearchResults, SUGGESTED_EDGE_STYLE } from '../relationEdges.js';
import { stubBackend } from './fixtures/backendContracts.js';

afterEach(() => vi.unstubAllGlobals());

it('E2E: 자연어 질의 → 노드 배치 → 근거 점선 엣지까지 fixture로 재현된다', async () => {
  stubBackend();
  const docs = await searchDocsWithDetails('대기오염 실시간 측정', 6);
  const relations = await fetchRelations(docs.map(doc => doc.serviceId));
  let n = 0;
  const { nodes, edges } = placeSearchResults(docs, relations, () => `node-e2e-${++n}`);

  expect(nodes).toHaveLength(2);
  expect(nodes.every(node => node.type === 'apiDoc' && node.data.doc)).toBe(true);
  expect(edges).toHaveLength(1);
  expect(edges[0].style).toEqual(SUGGESTED_EDGE_STYLE);
  expect(edges[0].data.relation.type).toBe('io-chain');
  expect(edges[0].data.relation.status).toBe('derived');
  expect(edges[0].data.relation.evidence).toEqual(['응답 sidoName → 요청 sidoName']);
});
