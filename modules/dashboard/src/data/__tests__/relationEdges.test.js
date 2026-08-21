import { describe, expect, it } from 'vitest';
import { approveRelationEdge, APPROVED_EDGE_STYLE, placeSearchResults, SUGGESTED_EDGE_STYLE } from '../relationEdges.js';

const DOCS = [
  { apiId: '15000001', serviceId: 'openapi_new:15000001', name: '대기오염정보' },
  { apiId: '15000003', serviceId: 'openapi_new:15000003', name: '측정소정보' },
];

const RELATIONS = [{
  id: 'rel:io-chain:openapi_new:15000003:openapi_new:15000001',
  source: 'openapi_new:15000003',
  target: 'openapi_new:15000001',
  type: 'io-chain',
  evidence: ['응답 sidoName → 요청 sidoName'],
  confidence: 0.6,
  status: 'derived',
  generatedAt: '2026-07-16',
}];

function makeIdFactory() {
  let n = 0;
  return () => `node-q${++n}`;
}

describe('placeSearchResults', () => {
  it('doc이 내장된 apiDoc 노드와 점선 관계 엣지를 만든다', () => {
    const { nodes, edges } = placeSearchResults(DOCS, RELATIONS, makeIdFactory());
    expect(nodes).toHaveLength(2);
    expect(nodes[0].type).toBe('apiDoc');
    expect(nodes[0].data).toEqual({ apiId: '15000001', doc: DOCS[0] });
    expect(nodes[0].position).not.toEqual(nodes[1].position);

    expect(edges).toHaveLength(1);
    expect(edges[0].source).toBe(nodes[1].id); // 15000003 노드
    expect(edges[0].target).toBe(nodes[0].id);
    expect(edges[0].style).toEqual(SUGGESTED_EDGE_STYLE);
    expect(edges[0].animated).toBe(true);
    expect(edges[0].data.relation.evidence).toEqual(['응답 sidoName → 요청 sidoName']);
  });

  it('캔버스에 없는 ID를 가리키는 관계는 버린다', () => {
    const { edges } = placeSearchResults([DOCS[0]], RELATIONS, makeIdFactory());
    expect(edges).toHaveLength(0);
  });
});

describe('approveRelationEdge', () => {
  it('점선 관계 엣지를 실선 승인 엣지로 바꾼다', () => {
    const { nodes, edges } = placeSearchResults(DOCS, RELATIONS, makeIdFactory());
    const approved = approveRelationEdge(edges, edges[0].id);
    expect(approved[0].animated).toBe(false);
    expect(approved[0].style).toEqual(APPROVED_EDGE_STYLE);
    expect(approved[0].data.relation.status).toBe('approved');
    expect(nodes).toHaveLength(2); // 노드는 건드리지 않는다
  });

  it('relation이 없는 일반 엣지는 그대로 둔다', () => {
    const plain = [{ id: 'e1', source: 'a', target: 'b' }];
    expect(approveRelationEdge(plain, 'e1')).toEqual(plain);
  });
});
