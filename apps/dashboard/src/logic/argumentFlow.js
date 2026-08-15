// React Flow 캔버스와 형식 판정 계층 사이의 순수 어댑터.
//
// 연결 규칙을 여기에 두는 이유: 같은 표를 onConnect(연결 시점 거부)와
// 판정(실행 시점 검사) 양쪽이 써야 한다. 두 곳에 따로 적으면 어긋난다.

import { EDGE_KINDS, LABELS, NODE_KINDS, judgeArgumentGraph } from './argumentGraph.js';

export const ARGUMENT_NODE_TYPES = {
  PREMISE: 'premise',
  CLAIM: 'claim',
  INTERPRETATION: 'interpretation',
};

// 논증으로 취급되는 노드 — 판정 대상이다. 해석 노드는 산출물이라 제외된다.
const ARGUING = new Set([ARGUMENT_NODE_TYPES.PREMISE, ARGUMENT_NODE_TYPES.CLAIM]);

// 해석 노드로 들어가는 엣지는 지지/반박이 아니다. 논증이 아니라 입력이다.
export const FEED = 'feed';

export const EDGE_STYLES = {
  [EDGE_KINDS.SUPPORT]: { stroke: '#0f766e', strokeWidth: 2 },
  [EDGE_KINDS.ATTACK]: { stroke: '#b91c1c', strokeWidth: 2, strokeDasharray: '6 4' },
  [FEED]: { stroke: '#64748b', strokeWidth: 1.5, strokeDasharray: '2 3' },
};

export const LABEL_STYLES = {
  [LABELS.ACCEPTED]: { border: '#0f766e', badge: '성립' },
  [LABELS.REJECTED]: { border: '#b91c1c', badge: '논파됨' },
  [LABELS.UNDECIDED]: { border: '#a16207', badge: '미판정' },
};

export function isArguingNode(node) {
  return ARGUING.has(node?.type);
}

/** 캔버스 상태에서 판정 대상 그래프만 뽑는다. */
export function toArgumentGraph(nodes, edges) {
  const arguing = (nodes ?? []).filter(isArguingNode);
  const ids = new Set(arguing.map(node => node.id));

  return {
    nodes: arguing.map(node => ({
      id: node.id,
      kind: node.type === ARGUMENT_NODE_TYPES.PREMISE ? NODE_KINDS.PREMISE : NODE_KINDS.CLAIM,
      text: node.data?.text ?? '',
    })),
    edges: (edges ?? [])
      .filter(edge => edge?.data?.kind === EDGE_KINDS.SUPPORT || edge?.data?.kind === EDGE_KINDS.ATTACK)
      .filter(edge => ids.has(edge.source) && ids.has(edge.target))
      .map(edge => ({
        id: edge.id,
        kind: edge.data.kind,
        source: edge.source,
        target: edge.target,
      })),
  };
}

export function judgeCanvas(nodes, edges) {
  const graph = toArgumentGraph(nodes, edges);
  return judgeArgumentGraph(graph.nodes, graph.edges);
}

/**
 * 연결을 허용할지 정한다.
 *
 * 자기 자신을 지지하는 연결은 **막지 않는다**. 그건 연결 오류가 아니라 순환논증이고,
 * 판정 계층이 지적해야 할 대상이다. 여기서 막으면 사용자는 자신이 무엇을 하려 했는지
 * 알 수 없게 된다.
 */
export function validateConnection(nodes, edges, connection, kind) {
  const byId = new Map((nodes ?? []).map(node => [node.id, node]));
  const source = byId.get(connection?.source);
  const target = byId.get(connection?.target);

  if (!source || !target) {
    return { ok: false, reason: '연결할 노드를 찾을 수 없습니다.' };
  }

  if (source.type === ARGUMENT_NODE_TYPES.INTERPRETATION) {
    return { ok: false, reason: '해석은 산출물이라 다른 노드로 이어지지 않습니다.' };
  }

  if (target.type === ARGUMENT_NODE_TYPES.INTERPRETATION) {
    if (kind !== FEED) {
      return { ok: false, reason: '해석 노드로는 지지·반박이 아니라 입력으로 연결합니다.' };
    }
    if (!isArguingNode(source)) {
      return { ok: false, reason: '해석에는 전제나 주장만 입력할 수 있습니다.' };
    }
  } else {
    if (!isArguingNode(source) || !isArguingNode(target)) {
      return { ok: false, reason: '지지·반박은 전제와 주장 사이에만 맺을 수 있습니다.' };
    }
    if (kind !== EDGE_KINDS.SUPPORT && kind !== EDGE_KINDS.ATTACK) {
      return { ok: false, reason: '관계 유형은 지지 또는 반박이어야 합니다.' };
    }
  }

  const duplicate = (edges ?? []).some(
    edge => edge.source === connection.source
      && edge.target === connection.target
      && edge.data?.kind === kind
  );
  if (duplicate) {
    return { ok: false, reason: '같은 관계가 이미 있습니다.' };
  }

  return { ok: true };
}

export function makeArgumentEdge(connection, kind, id) {
  return {
    id: id ?? `edge-${connection.source}-${connection.target}-${kind}`,
    source: connection.source,
    target: connection.target,
    type: 'smoothstep',
    label: kind === EDGE_KINDS.SUPPORT ? '지지' : kind === EDGE_KINDS.ATTACK ? '반박' : '입력',
    animated: kind === EDGE_KINDS.ATTACK,
    style: EDGE_STYLES[kind],
    data: { kind },
  };
}

/**
 * 판정 결과를 노드에 적어 넣는다.
 *
 * 판정은 캔버스가 아니라 그래프에서 나온다. 노드는 그것을 표시만 한다 —
 * 여기서 라벨을 고쳐 쓰면 형식 계층이 확정한 것을 UI가 뒤집는 셈이 된다.
 */
export function applyVerdict(nodes, verdict) {
  const byNode = new Map();
  verdict.findings.forEach(finding => {
    (finding.nodeIds ?? []).forEach(id => {
      if (!byNode.has(id)) byNode.set(id, []);
      byNode.get(id).push(finding.code);
    });
  });

  return (nodes ?? []).map(node => {
    if (!isArguingNode(node)) return node;
    const label = verdict.labels[node.id] ?? LABELS.UNDECIDED;
    return {
      ...node,
      data: { ...node.data, label, findings: byNode.get(node.id) ?? [] },
    };
  });
}

/** 해석 노드가 받는 상류 논증 — 연결이 없으면 그래프 전체를 대상으로 본다. */
export function interpretationScope(nodes, edges, interpretationId) {
  const fed = new Set(
    (edges ?? [])
      .filter(edge => edge.target === interpretationId && edge.data?.kind === FEED)
      .map(edge => edge.source)
  );

  const arguing = (nodes ?? []).filter(isArguingNode);
  if (fed.size === 0) return arguing;
  return arguing.filter(node => fed.has(node.id));
}
