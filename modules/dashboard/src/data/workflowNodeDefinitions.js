const PALETTE_CATEGORY_ORDER = ['logic', 'source', 'filter', 'analysis', 'output'];

export const WORKFLOW_NODE_DEFINITIONS = Object.freeze([
  {
    type: 'apiDoc',
    label: 'API 문서',
    category: 'source',
    defaultData: { apiId: '' },
    palette: { mode: 'catalog' },
    propertyFields: [
      { key: 'apiId', label: 'API 문서', type: 'select' },
    ],
    minimapColor: '#22c55e',
  },
  {
    type: 'mergeNode',
    label: '병합 (Merge)',
    category: 'logic',
    defaultData: {},
    palette: {
      icon: '⊕',
      label: '병합 (Merge)',
      desc: '두 API 문서를 합쳐 LLM 컨텍스트 생성',
    },
    propertyFields: [],
    // 기존 미니맵은 mergeNode를 source fallback 색으로 표시했다.
    minimapColor: '#22c55e',
  },
  {
    type: 'apiSearch',
    label: 'API 검색',
    category: 'source',
    defaultData: { query: '', maxResults: 10 },
    palette: { icon: '🔍', label: 'API 검색', desc: '공공 API 문서 검색' },
    propertyFields: [
      { key: 'query', label: '검색어', type: 'text', placeholder: '예: 여행경보' },
      { key: 'maxResults', label: '최대 결과 수', type: 'number', min: 1, max: 50, step: 1, suffix: '개' },
    ],
    minimapColor: '#22c55e',
  },
  {
    type: 'categoryFilter',
    label: '카테고리 필터',
    category: 'filter',
    defaultData: { category: '', strict: false },
    palette: { icon: '🗂️', label: '카테고리 필터', desc: '분류 기준 필터링' },
    propertyFields: [
      { key: 'category', label: '카테고리', type: 'text', placeholder: '예: 교통, 복지' },
      { key: 'strict', label: '엄격 일치', type: 'checkbox', fmt: value => value ? '엄격 일치' : '부분 일치' },
    ],
    minimapColor: '#818cf8',
  },
  {
    type: 'providerFilter',
    label: '제공기관 필터',
    category: 'filter',
    defaultData: { provider: '' },
    palette: { icon: '🏛️', label: '제공기관 필터', desc: '기관명 기준 필터링' },
    propertyFields: [
      { key: 'provider', label: '제공기관', type: 'text', placeholder: '예: 국토교통부' },
    ],
    minimapColor: '#818cf8',
  },
  {
    type: 'scoreFilter',
    label: '점수 필터',
    category: 'filter',
    defaultData: { minScore: 0.5, topK: 10 },
    palette: { icon: '📊', label: '점수 필터', desc: '유사도 점수 기준' },
    propertyFields: [
      { key: 'minScore', label: '최소 유사도', type: 'number', min: 0, max: 1, step: 0.05 },
      { key: 'topK', label: '상위 N개', type: 'number', min: 1, max: 50, step: 1, suffix: '개' },
    ],
    minimapColor: '#818cf8',
  },
  {
    type: 'ragChat',
    label: 'RAG 채팅',
    category: 'analysis',
    defaultData: { prompt: '', llm: 'claude' },
    palette: { icon: '🤖', label: 'RAG 채팅', desc: 'LLM 기반 분석 채팅' },
    propertyFields: [
      {
        key: 'llm',
        label: 'LLM 엔진',
        type: 'select',
        options: [
          { value: 'claude', label: 'Claude' },
          { value: 'ollama', label: 'Ollama' },
          { value: 'openai', label: 'OpenAI' },
        ],
      },
      { key: 'prompt', label: '프롬프트', type: 'textarea', rows: 4, placeholder: '이 API들을 조합하면 어떤 서비스가 가능한가?' },
    ],
    minimapColor: '#f59e0b',
  },
  {
    type: 'summaryNode',
    label: '요약',
    category: 'analysis',
    defaultData: { maxLength: 300 },
    palette: { icon: '📝', label: '요약', desc: '결과 요약 생성' },
    propertyFields: [
      { key: 'maxLength', label: '최대 길이', type: 'number', min: 50, max: 4000, step: 50, suffix: '자' },
    ],
    minimapColor: '#f59e0b',
  },
  {
    type: 'exportNode',
    label: '내보내기',
    category: 'output',
    defaultData: { format: 'JSON', filename: 'result' },
    palette: { icon: '📤', label: '내보내기', desc: 'JSON / CSV / XLSX' },
    propertyFields: [
      {
        key: 'format',
        label: '형식',
        type: 'select',
        options: [
          { value: 'JSON', label: 'JSON' },
          { value: 'CSV', label: 'CSV' },
          { value: 'XLSX', label: 'XLSX' },
        ],
      },
      { key: 'filename', label: '파일명', type: 'text', placeholder: 'result' },
    ],
    minimapColor: '#38bdf8',
  },
  {
    type: 'saveNode',
    label: '워크플로우 저장',
    category: 'output',
    defaultData: { name: '새 워크플로우' },
    palette: { icon: '💾', label: '워크플로우 저장', desc: '플로우 JSON 다운로드' },
    propertyFields: [
      { key: 'name', label: '저장 이름', type: 'text', placeholder: '새 워크플로우' },
    ],
    minimapColor: '#38bdf8',
  },
  {
    type: 'chatOutput',
    label: '채팅하기',
    category: 'output',
    defaultData: {
      model: 'gemma4:e4b',
      systemPrompt: '이 API 조합으로 만들 수 있는 서비스를 구체적으로 제안해줘',
    },
    palette: { icon: '💬', label: '채팅하기', desc: 'Ollama gemma4:e4b와 컨텍스트 채팅' },
    propertyFields: [
      { key: 'model', label: 'Ollama 모델', type: 'text', placeholder: 'gemma4:e4b' },
      { key: 'systemPrompt', label: '기본 질문', type: 'textarea', rows: 4 },
    ],
    minimapColor: '#38bdf8',
  },
]);

export const WORKFLOW_NODE_TYPES = Object.freeze(
  WORKFLOW_NODE_DEFINITIONS.map(definition => definition.type)
);

export const NODE_DEFAULTS = Object.freeze(Object.fromEntries(
  WORKFLOW_NODE_DEFINITIONS.map(definition => [definition.type, definition.defaultData])
));

export const PALETTE_NODE_TYPES = Object.freeze(
  WORKFLOW_NODE_DEFINITIONS
    .filter(definition => definition.palette)
    .map(definition => definition.type)
);

export const NODE_PALETTE = Object.freeze(
  PALETTE_CATEGORY_ORDER.map(category => ({
    category,
    nodes: WORKFLOW_NODE_DEFINITIONS
      .filter(definition => definition.category === category && definition.palette?.mode !== 'catalog')
      .map(definition => ({ type: definition.type, ...definition.palette })),
  })).filter(group => group.nodes.length > 0)
);

export const NODE_PROPERTY_META = Object.freeze(Object.fromEntries(
  WORKFLOW_NODE_DEFINITIONS.map(definition => [definition.type, {
    label: definition.label,
    category: definition.category,
    fields: definition.propertyFields,
  }])
));

export const KNOWN_NODE_TYPES = WORKFLOW_NODE_TYPES;

export const MINIMAP_NODE_COLORS = Object.freeze(Object.fromEntries(
  WORKFLOW_NODE_DEFINITIONS.map(definition => [definition.type, definition.minimapColor])
));
