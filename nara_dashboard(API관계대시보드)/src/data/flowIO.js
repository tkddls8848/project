// 워크플로우 JSON 내보내기/가져오기 (Node-RED의 flow export/import 패턴).
// DOM 의존 없는 순수 함수 — 단위 테스트 대상.

export const FLOW_FORMAT = 'nara-dashboard-flow';
export const FLOW_VERSION = 1;

// src/nodes/nodeTypes.jsx 등록 맵과 동기화해서 유지한다.
export const KNOWN_NODE_TYPES = Object.freeze([
  'apiDoc',
  'mergeNode',
  'apiSearch',
  'categoryFilter',
  'providerFilter',
  'scoreFilter',
  'ragChat',
  'summaryNode',
  'exportNode',
  'saveNode',
  'chatOutput',
]);

// 실행 결과·콜백 등 저장하면 안 되는 런타임 필드
const RUNTIME_DATA_KEYS = new Set([
  'status',
  'error',
  'results',
  'output',
  'analysisPrompt',
  'chatContext',
  'onRunOutput',
]);

export class FlowImportError extends Error {}

export function sanitizeNodeData(data = {}) {
  const clean = {};
  for (const [key, value] of Object.entries(data)) {
    if (RUNTIME_DATA_KEYS.has(key)) continue;
    if (typeof value === 'function') continue;
    clean[key] = value;
  }
  return clean;
}

function toPosition(position) {
  const x = Number(position?.x);
  const y = Number(position?.y);
  return {
    x: Number.isFinite(x) ? x : 0,
    y: Number.isFinite(y) ? y : 0,
  };
}

export function serializeFlow(nodes = [], edges = [], meta = {}) {
  const nodeIds = new Set(nodes.map(node => node.id));
  return {
    format: FLOW_FORMAT,
    version: FLOW_VERSION,
    name: String(meta.name || '새 워크플로우'),
    exported_at: (meta.exportedAt instanceof Date ? meta.exportedAt : new Date()).toISOString(),
    nodes: nodes.map(node => ({
      id: String(node.id),
      type: String(node.type),
      position: toPosition(node.position),
      data: sanitizeNodeData(node.data),
    })),
    edges: edges
      .filter(edge => nodeIds.has(edge.source) && nodeIds.has(edge.target))
      .map(edge => ({
        id: String(edge.id ?? `${edge.source}->${edge.target}`),
        source: String(edge.source),
        target: String(edge.target),
        ...(edge.sourceHandle ? { sourceHandle: edge.sourceHandle } : {}),
        ...(edge.targetHandle ? { targetHandle: edge.targetHandle } : {}),
      })),
  };
}

export function flowToJson(nodes, edges, meta = {}) {
  return JSON.stringify(serializeFlow(nodes, edges, meta), null, 2);
}

export function deserializeFlow(raw) {
  let doc = raw;
  if (typeof raw === 'string') {
    try {
      doc = JSON.parse(raw);
    } catch {
      throw new FlowImportError('JSON 파싱에 실패했습니다.');
    }
  }
  if (!doc || typeof doc !== 'object') {
    throw new FlowImportError('워크플로우 JSON 형식이 아닙니다.');
  }
  if (doc.format !== FLOW_FORMAT) {
    throw new FlowImportError(`알 수 없는 형식입니다: ${String(doc.format || '(없음)')}`);
  }
  if (doc.version !== FLOW_VERSION) {
    throw new FlowImportError(`지원하지 않는 버전입니다: ${String(doc.version)}`);
  }
  if (!Array.isArray(doc.nodes)) {
    throw new FlowImportError('nodes 배열이 없습니다.');
  }

  const seenIds = new Set();
  const nodes = doc.nodes.map((node, index) => {
    const id = String(node?.id ?? '');
    if (!id) throw new FlowImportError(`노드 ${index}에 id가 없습니다.`);
    if (seenIds.has(id)) throw new FlowImportError(`중복 노드 id: ${id}`);
    seenIds.add(id);

    const type = String(node?.type ?? '');
    if (!KNOWN_NODE_TYPES.includes(type)) {
      throw new FlowImportError(`지원하지 않는 노드 타입: ${type || '(없음)'}`);
    }

    return {
      id,
      type,
      position: toPosition(node?.position),
      data: {
        ...sanitizeNodeData(node?.data && typeof node.data === 'object' ? node.data : {}),
        status: 'idle',
        error: '',
      },
    };
  });

  const edges = (Array.isArray(doc.edges) ? doc.edges : [])
    .filter(edge => seenIds.has(String(edge?.source)) && seenIds.has(String(edge?.target)))
    .map((edge, index) => ({
      id: String(edge.id ?? `imported-edge-${index}`),
      source: String(edge.source),
      target: String(edge.target),
      ...(edge.sourceHandle ? { sourceHandle: String(edge.sourceHandle) } : {}),
      ...(edge.targetHandle ? { targetHandle: String(edge.targetHandle) } : {}),
    }));

  return {
    name: String(doc.name || '가져온 워크플로우'),
    nodes,
    edges,
  };
}

// 가져온 노드 id("node-123")와 새로 만들 id가 충돌하지 않도록 최대 suffix를 찾는다.
export function maxNodeIdSuffix(nodes = []) {
  let max = 0;
  for (const node of nodes) {
    const match = /^node-(\d+)$/.exec(String(node?.id ?? ''));
    if (match) max = Math.max(max, Number(match[1]));
  }
  return max;
}
