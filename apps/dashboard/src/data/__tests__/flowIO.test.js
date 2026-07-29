import { describe, expect, it } from 'vitest';

import {
  FLOW_FORMAT,
  FLOW_VERSION,
  FlowImportError,
  deserializeFlow,
  flowToJson,
  maxNodeIdSuffix,
  sanitizeNodeData,
  serializeFlow,
} from '../flowIO.js';

const NODES = [
  {
    id: 'node-1',
    type: 'apiSearch',
    position: { x: 100, y: 50 },
    data: {
      query: '미세먼지',
      maxResults: 10,
      status: 'success',
      results: [{ apiId: 'x' }],
      output: { kind: 'apiDocs', docs: [] },
      error: '',
      onRunOutput: () => {},
    },
  },
  {
    id: 'node-2',
    type: 'exportNode',
    position: { x: 400, y: 50 },
    data: { format: 'CSV', filename: 'result' },
  },
];

const EDGES = [
  { id: 'e1', source: 'node-1', target: 'node-2', sourceHandle: 'out' },
  { id: 'dangling', source: 'node-1', target: 'ghost' },
];

describe('sanitizeNodeData', () => {
  it('런타임 필드와 함수를 제거하고 설정만 남긴다', () => {
    const clean = sanitizeNodeData(NODES[0].data);
    expect(clean).toEqual({ query: '미세먼지', maxResults: 10 });
  });
});

describe('serializeFlow', () => {
  it('format·version·이름·노드·엣지를 담고 dangling 엣지를 제외한다', () => {
    const at = new Date('2026-07-04T00:00:00Z');
    const flow = serializeFlow(NODES, EDGES, { name: '테스트 플로우', exportedAt: at });
    expect(flow.format).toBe(FLOW_FORMAT);
    expect(flow.version).toBe(FLOW_VERSION);
    expect(flow.name).toBe('테스트 플로우');
    expect(flow.exported_at).toBe('2026-07-04T00:00:00.000Z');
    expect(flow.nodes).toHaveLength(2);
    expect(flow.nodes[0].data.status).toBeUndefined();
    expect(flow.edges).toHaveLength(1);
    expect(flow.edges[0]).toMatchObject({ source: 'node-1', target: 'node-2', sourceHandle: 'out' });
  });
});

describe('round-trip', () => {
  it('내보낸 JSON을 다시 가져오면 설정·연결이 보존된다', () => {
    const json = flowToJson(NODES, EDGES, { name: '왕복' });
    const flow = deserializeFlow(json);

    expect(flow.name).toBe('왕복');
    expect(flow.nodes.map(n => n.id)).toEqual(['node-1', 'node-2']);
    const search = flow.nodes[0];
    expect(search.type).toBe('apiSearch');
    expect(search.position).toEqual({ x: 100, y: 50 });
    expect(search.data.query).toBe('미세먼지');
    // 가져온 노드는 idle 상태로 시작한다
    expect(search.data.status).toBe('idle');
    expect(search.data.results).toBeUndefined();
    expect(flow.edges).toHaveLength(1);
  });
});

describe('deserializeFlow 검증', () => {
  const valid = () => serializeFlow(NODES, EDGES, { name: 'v' });

  it('JSON 문자열이 아니면 FlowImportError', () => {
    expect(() => deserializeFlow('{broken')).toThrow(FlowImportError);
    expect(() => deserializeFlow(null)).toThrow(FlowImportError);
  });

  it('format 불일치를 거부한다', () => {
    expect(() => deserializeFlow({ ...valid(), format: 'other' })).toThrow(/알 수 없는 형식/);
  });

  it('version 불일치를 거부한다', () => {
    expect(() => deserializeFlow({ ...valid(), version: 999 })).toThrow(/지원하지 않는 버전/);
  });

  it('알 수 없는 노드 타입을 거부한다', () => {
    const doc = valid();
    doc.nodes[0].type = 'evalNode';
    expect(() => deserializeFlow(doc)).toThrow(/지원하지 않는 노드 타입/);
  });

  it('중복 노드 id를 거부한다', () => {
    const doc = valid();
    doc.nodes[1].id = doc.nodes[0].id;
    expect(() => deserializeFlow(doc)).toThrow(/중복 노드 id/);
  });

  it('없는 노드를 가리키는 엣지는 버린다', () => {
    const doc = valid();
    doc.edges.push({ id: 'bad', source: 'node-1', target: 'nope' });
    const flow = deserializeFlow(doc);
    expect(flow.edges.map(e => e.id)).toEqual(['e1']);
  });

  it('position이 깨져 있으면 0,0으로 복구한다', () => {
    const doc = valid();
    doc.nodes[0].position = { x: 'NaN?', y: null };
    const flow = deserializeFlow(doc);
    expect(flow.nodes[0].position).toEqual({ x: 0, y: 0 });
  });
});

describe('maxNodeIdSuffix', () => {
  it('node-{n} 형식의 최대 suffix를 찾는다', () => {
    expect(maxNodeIdSuffix([{ id: 'node-3' }, { id: 'node-120' }, { id: 'tour-doc-1' }])).toBe(120);
    expect(maxNodeIdSuffix([])).toBe(0);
  });
});
