import { searchApiDocs } from './apiDocs.js';
import {
  collectInputDocs,
  collectInputPrompts,
  outputDocsFor,
  topoSort,
  upstreamNodeIds,
} from './workflowGraph.js';
import {
  buildAnalysisPrompt,
  exportFilename,
  filterByCategory,
  filterByProvider,
  mergedContext,
  normalizeExportFormat,
  topByScore,
} from './workflowOperators.js';

const NODE_EXECUTORS = {
  apiSearch(node) {
    const results = searchApiDocs(node.data?.query, node.data?.maxResults);
    return {
      ...node.data,
      status: 'success',
      results,
      output: { kind: 'apiDocs', docs: results },
      error: '',
    };
  },

  apiDoc(node) {
    const docs = outputDocsFor(node);
    return {
      ...node.data,
      status: docs.length > 0 ? 'success' : 'error',
      output: { kind: 'apiDocs', docs },
      error: docs.length > 0 ? '' : 'API 문서를 찾을 수 없습니다.',
    };
  },

  categoryFilter(node, { inputDocs }) {
    const docs = filterByCategory(inputDocs, node.data?.category, node.data?.strict);
    return { ...node.data, status: 'success', results: docs, output: { kind: 'apiDocs', docs }, error: '' };
  },

  providerFilter(node, { inputDocs }) {
    const docs = filterByProvider(inputDocs, node.data?.provider);
    return { ...node.data, status: 'success', results: docs, output: { kind: 'apiDocs', docs }, error: '' };
  },

  scoreFilter(node, { inputDocs }) {
    const docs = topByScore(inputDocs, node.data?.topK, node.data?.minScore);
    return { ...node.data, status: 'success', results: docs, output: { kind: 'apiDocs', docs }, error: '' };
  },

  mergeNode(node, { inputDocs }) {
    if (inputDocs.length === 0) {
      return {
        ...node.data,
        status: 'error',
        results: [],
        output: { kind: 'mergedContext', docs: [] },
        error: '연결된 입력 API 문서가 없습니다.',
      };
    }

    const output = { kind: 'mergedContext', ...mergedContext(inputDocs) };
    return { ...node.data, status: 'success', results: inputDocs, output, error: '' };
  },

  ragChat(node, { inputDocs }) {
    const prompt = buildAnalysisPrompt(inputDocs, node.data?.prompt);
    return {
      ...node.data,
      status: inputDocs.length > 0 ? 'success' : 'idle',
      analysisPrompt: inputDocs.length > 0 ? prompt : '',
      output: { kind: 'analysisPrompt', docs: inputDocs, prompt },
      error: '',
    };
  },

  chatOutput(node, { inputDocs, edges, byId }) {
    const upstreamPrompts = collectInputPrompts(node, edges, byId);
    const prompt = upstreamPrompts[0] || buildAnalysisPrompt(inputDocs, node.data?.systemPrompt);

    if (inputDocs.length === 0) {
      return {
        ...node.data,
        status: 'error',
        chatContext: { docs: [], prompt: '', model: node.data?.model ?? 'gemma4:e4b' },
        output: { kind: 'chatContext', docs: [], prompt: '' },
        error: '채팅에 사용할 입력 컨텍스트가 없습니다.',
      };
    }

    return {
      ...node.data,
      status: 'success',
      chatContext: {
        docs: inputDocs,
        prompt,
        model: node.data?.model ?? 'gemma4:e4b',
      },
      output: { kind: 'chatContext', docs: inputDocs, prompt },
      error: '',
    };
  },

  saveNode(node, { inputDocs }) {
    // 워크플로우 정의를 JSON 파일로 내보낸다 (Node-RED flow export 방식).
    // 실제 다운로드는 App이 saveRequest를 보고 수행한다.
    return {
      ...node.data,
      status: 'success',
      results: inputDocs,
      output: {
        kind: 'saveRequest',
        docs: inputDocs,
        saveRequest: { name: String(node.data?.name || '새 워크플로우') },
      },
      error: '',
    };
  },

  exportNode(node, { inputDocs }) {
    if (inputDocs.length === 0) {
      return {
        ...node.data,
        status: 'error',
        output: { kind: 'export', docs: [], exportRequest: null },
        error: '내보낼 입력 데이터가 없습니다.',
      };
    }

    const format = normalizeExportFormat(node.data?.format);
    return {
      ...node.data,
      status: 'success',
      results: inputDocs,
      output: {
        kind: 'export',
        docs: inputDocs,
        exportRequest: {
          format,
          filename: exportFilename(node.data?.filename, format),
          docs: inputDocs,
        },
      },
      error: '',
    };
  },
};

function executeNode(node, edges, byId) {
  const executor = NODE_EXECUTORS[node.type];
  if (!executor) {
    return {
      ...node.data,
      status: 'error',
      results: [],
      output: { kind: 'unsupported', docs: [] },
      error: `이 노드 유형은 실행을 지원하지 않습니다: ${node.type}`,
    };
  }

  const inputDocs = node.type === 'apiSearch' || node.type === 'apiDoc'
    ? []
    : collectInputDocs(node, edges, byId);
  return executor(node, { inputDocs, edges, byId });
}

export function runWorkflow(nodes, edges) {
  const nextById = new Map(nodes.map(node => [
    node.id,
    {
      ...node,
      data: {
        ...node.data,
        status: 'idle',
        error: '',
      },
    },
  ]));

  for (const node of topoSort(nodes, edges)) {
    const current = nextById.get(node.id);
    const data = executeNode(current, edges, nextById);
    nextById.set(node.id, { ...current, data });
  }

  return nodes.map(node => nextById.get(node.id) ?? node);
}

export function runWorkflowForOutput(nodes, edges, outputNodeId) {
  const targetIds = upstreamNodeIds(outputNodeId, edges);
  const targetNodes = nodes.filter(node => targetIds.has(node.id));
  const targetEdges = edges.filter(edge => targetIds.has(edge.source) && targetIds.has(edge.target));

  const nextById = new Map(nodes.map(node => [
    node.id,
    targetIds.has(node.id)
      ? {
          ...node,
          data: {
            ...node.data,
            status: 'idle',
            error: '',
          },
        }
      : node,
  ]));

  for (const node of topoSort(targetNodes, targetEdges)) {
    const current = nextById.get(node.id);
    const data = executeNode(current, targetEdges, nextById);
    nextById.set(node.id, { ...current, data });
  }

  return nodes.map(node => nextById.get(node.id) ?? node);
}
