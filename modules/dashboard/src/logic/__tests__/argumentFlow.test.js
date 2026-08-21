import { describe, expect, it } from 'vitest';
import { EDGE_KINDS, LABELS } from '../argumentGraph.js';
import {
  ARGUMENT_NODE_TYPES,
  FEED,
  applyVerdict,
  interpretationScope,
  judgeCanvas,
  makeArgumentEdge,
  toArgumentGraph,
  validateConnection,
} from '../argumentFlow.js';

const node = (id, type, text) => ({ id, type, position: { x: 0, y: 0 }, data: { text } });
const premise = (id, text) => node(id, ARGUMENT_NODE_TYPES.PREMISE, text);
const claim = (id, text) => node(id, ARGUMENT_NODE_TYPES.CLAIM, text);
const interpretation = id => node(id, ARGUMENT_NODE_TYPES.INTERPRETATION, '');
const edge = (source, target, kind) => ({ id: `${source}-${target}-${kind}`, source, target, data: { kind } });

describe('toArgumentGraph', () => {
  it('해석 노드와 입력 엣지는 판정 대상에서 제외한다', () => {
    const nodes = [premise('p', '전제'), claim('c', '주장'), interpretation('i')];
    const edges = [edge('p', 'c', EDGE_KINDS.SUPPORT), edge('c', 'i', FEED)];

    const graph = toArgumentGraph(nodes, edges);

    expect(graph.nodes.map(item => item.id)).toEqual(['p', 'c']);
    expect(graph.edges).toHaveLength(1);
    expect(graph.edges[0].kind).toBe(EDGE_KINDS.SUPPORT);
  });

  it('캔버스의 다른 노드 타입은 무시한다', () => {
    const nodes = [premise('p', '전제'), node('x', 'apiDoc', '')];
    expect(toArgumentGraph(nodes, []).nodes.map(item => item.id)).toEqual(['p']);
  });
});

describe('validateConnection', () => {
  const nodes = [premise('p', '전제'), claim('c', '주장'), interpretation('i'), node('x', 'apiDoc', '')];

  it('전제와 주장 사이 지지·반박을 허용한다', () => {
    expect(validateConnection(nodes, [], { source: 'p', target: 'c' }, EDGE_KINDS.SUPPORT).ok).toBe(true);
    expect(validateConnection(nodes, [], { source: 'p', target: 'c' }, EDGE_KINDS.ATTACK).ok).toBe(true);
  });

  it('해석 노드에서 밖으로 나가는 연결을 막는다', () => {
    const result = validateConnection(nodes, [], { source: 'i', target: 'c' }, FEED);
    expect(result.ok).toBe(false);
    expect(result.reason).toContain('산출물');
  });

  it('해석 노드로는 지지·반박이 아니라 입력으로만 잇는다', () => {
    expect(validateConnection(nodes, [], { source: 'p', target: 'i' }, EDGE_KINDS.SUPPORT).ok).toBe(false);
    expect(validateConnection(nodes, [], { source: 'p', target: 'i' }, FEED).ok).toBe(true);
  });

  it('논증이 아닌 노드는 지지·반박에 참여할 수 없다', () => {
    expect(validateConnection(nodes, [], { source: 'x', target: 'c' }, EDGE_KINDS.SUPPORT).ok).toBe(false);
  });

  it('같은 관계를 두 번 맺지 않는다', () => {
    const existing = [edge('p', 'c', EDGE_KINDS.SUPPORT)];
    expect(validateConnection(nodes, existing, { source: 'p', target: 'c' }, EDGE_KINDS.SUPPORT).ok).toBe(false);
    // 유형이 다르면 별개의 관계다
    expect(validateConnection(nodes, existing, { source: 'p', target: 'c' }, EDGE_KINDS.ATTACK).ok).toBe(true);
  });

  it('자기 지지는 막지 않는다 — 연결 오류가 아니라 순환논증이다', () => {
    expect(validateConnection(nodes, [], { source: 'c', target: 'c' }, EDGE_KINDS.SUPPORT).ok).toBe(true);
    const verdict = judgeCanvas([claim('c', '주장')], [edge('c', 'c', EDGE_KINDS.SUPPORT)]);
    expect(verdict.findings.map(item => item.code)).toContain('support-cycle');
  });
});

describe('applyVerdict', () => {
  it('판정 라벨과 위반 코드를 노드에 적는다', () => {
    const nodes = [premise('a', 'A'), premise('b', 'B'), interpretation('i')];
    const edges = [edge('a', 'b', EDGE_KINDS.ATTACK)];
    const verdict = judgeCanvas(nodes, edges);

    const next = applyVerdict(nodes, verdict);

    expect(next[0].data.label).toBe(LABELS.ACCEPTED);
    expect(next[1].data.label).toBe(LABELS.REJECTED);
    expect(next[2]).toBe(nodes[2]); // 해석 노드는 그대로 둔다
  });

  it('근거 없는 주장에 위반 코드가 붙는다', () => {
    const nodes = [claim('c', '주장')];
    const next = applyVerdict(nodes, judgeCanvas(nodes, []));
    expect(next[0].data.findings).toContain('unsupported-claim');
  });
});

describe('makeArgumentEdge', () => {
  it('유형에 따라 라벨과 표시가 달라진다', () => {
    const support = makeArgumentEdge({ source: 'a', target: 'b' }, EDGE_KINDS.SUPPORT);
    const attack = makeArgumentEdge({ source: 'a', target: 'b' }, EDGE_KINDS.ATTACK);

    expect(support.label).toBe('지지');
    expect(support.animated).toBe(false);
    expect(attack.label).toBe('반박');
    expect(attack.animated).toBe(true);
    expect(attack.data.kind).toBe(EDGE_KINDS.ATTACK);
  });
});

describe('interpretationScope', () => {
  const nodes = [premise('p', '전제'), claim('c', '주장'), interpretation('i')];

  it('입력이 연결돼 있으면 그 상류만 대상으로 한다', () => {
    const scope = interpretationScope(nodes, [edge('p', 'i', FEED)], 'i');
    expect(scope.map(item => item.id)).toEqual(['p']);
  });

  it('입력이 없으면 그래프 전체를 대상으로 한다', () => {
    const scope = interpretationScope(nodes, [], 'i');
    expect(scope.map(item => item.id)).toEqual(['p', 'c']);
  });
});
