export const initialNodes = [
  {
    id: 'tour-doc-1',
    type: 'apiDoc',
    position: { x: 60, y: 120 },
    data: { apiId: '15109201' },
  },
  {
    id: 'traffic-doc-1',
    type: 'apiDoc',
    position: { x: 60, y: 330 },
    data: { apiId: '15110257' },
  },
  {
    id: 'merge-1',
    type: 'mergeNode',
    position: { x: 380, y: 210 },
    data: {},
  },
  {
    id: 'ragChat-1',
    type: 'ragChat',
    position: { x: 700, y: 210 },
    data: { prompt: '관광 접근성과 교통 흐름을 결합한 새 서비스를 제안해줘', llm: 'claude' },
  },
  {
    id: 'chat-output-1',
    type: 'chatOutput',
    position: { x: 1000, y: 210 },
    data: { model: 'gemma4:e4b', systemPrompt: '이 API 조합으로 만들 수 있는 서비스를 구체적으로 제안해줘' },
  },
];

export const initialEdges = [
  { id: 'e1', source: 'tour-doc-1', sourceHandle: 'out', target: 'merge-1', targetHandle: 'a' },
  { id: 'e2', source: 'traffic-doc-1', sourceHandle: 'out', target: 'merge-1', targetHandle: 'b' },
  { id: 'e3', source: 'merge-1', sourceHandle: 'out', target: 'ragChat-1' },
  { id: 'e4', source: 'ragChat-1', target: 'chat-output-1' },
];

export const NODE_DEFAULTS = {
  apiDoc:         { apiId: '' },
  mergeNode:      {},
  apiSearch:      { query: '', maxResults: 10 },
  categoryFilter: { category: '', strict: false },
  providerFilter: { provider: '' },
  scoreFilter:    { minScore: 0.5, topK: 10 },
  ragChat:        { prompt: '', llm: 'claude' },
  summaryNode:    { maxLength: 300 },
  exportNode:     { format: 'JSON', filename: 'result' },
  saveNode:       { name: '새 워크플로우' },
  chatOutput:     { model: 'gemma4:e4b', systemPrompt: '이 API 조합으로 만들 수 있는 서비스를 구체적으로 제안해줘' },
};
