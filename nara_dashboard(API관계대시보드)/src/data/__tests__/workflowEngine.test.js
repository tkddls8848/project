import { beforeEach, describe, expect, it, vi } from 'vitest';

// apidata/는 Git에 포함되지 않으므로 카탈로그·검색만 fixture로 대체한다.
// uniqueDocs / toWorkflowDoc 등 순수 로직은 실제 구현을 그대로 쓴다.
const FIXTURE_DOCS = [
  {
    apiId: '15000001',
    name: '대기오염정보',
    provider: '한국환경공단',
    topCategory: '환경기상',
    category: '환경기상 - 대기',
    keywords: ['미세먼지', '대기질'],
    description: '시도별 실시간 측정정보',
    fields: [
      { key: 'sidoName', desc: '시도 이름' },
      { key: 'dataTime', desc: '측정일시' },
      { key: 'stationCode', desc: '측정소 코드' },
    ],
    endpoints: [{ method: 'GET', path: '/getAir', description: '측정정보 조회' }],
  },
  {
    apiId: '15000002',
    name: '버스도착정보',
    provider: '국토교통부',
    topCategory: '교통물류',
    category: '교통물류',
    keywords: ['버스', '대중교통'],
    description: '정류소별 버스 도착 정보',
    fields: [
      { key: 'stationCode', desc: '정류소 코드' },
      { key: 'arrivalTime', desc: '도착예정시간' },
    ],
    endpoints: [{ method: 'GET', path: '/getBus', description: '도착정보 조회' }],
  },
  {
    apiId: '15000003',
    name: '관광지정보',
    provider: '한국관광공사',
    topCategory: '문화관광',
    category: '문화관광',
    keywords: ['관광', '여행'],
    description: '전국 관광지 목록',
    fields: [{ key: 'addr1', desc: '주소' }],
    endpoints: [],
  },
];

vi.mock('../apiDocs.js', async importOriginal => {
  const actual = await importOriginal();
  return {
    ...actual,
    apiDocs: FIXTURE_DOCS,
    apiDocMap: Object.fromEntries(FIXTURE_DOCS.map(doc => [doc.apiId, doc])),
    searchApiDocs: (query, maxResults = 10) => {
      const needle = String(query ?? '').trim();
      return FIXTURE_DOCS
        .filter(doc => !needle || JSON.stringify(doc).includes(needle))
        .slice(0, Math.max(1, Number(maxResults) || 10))
        .map(doc => actual.toWorkflowDoc(doc, { searchScore: 1, searchReason: needle || '전체 문서' }));
    },
  };
});

const { runWorkflow, runWorkflowForOutput } = await import('../workflowEngine.js');

function node(id, type, data = {}) {
  return { id, type, position: { x: 0, y: 0 }, data };
}

function edge(source, target) {
  return { id: `${source}->${target}`, source, target };
}

function dataOf(nodes, id) {
  return nodes.find(candidate => candidate.id === id).data;
}

describe('runWorkflow', () => {
  it('apiDoc → categoryFilter → exportNode 파이프라인이 순서대로 실행된다', () => {
    const nodes = [
      node('doc1', 'apiDoc', { apiId: '15000001' }),
      node('doc2', 'apiDoc', { apiId: '15000003' }),
      node('filter', 'categoryFilter', { category: '환경기상' }),
      node('export', 'exportNode', { format: 'CSV', filename: '결과 파일' }),
    ];
    const edges = [edge('doc1', 'filter'), edge('doc2', 'filter'), edge('filter', 'export')];

    const result = runWorkflow(nodes, edges);

    const filter = dataOf(result, 'filter');
    expect(filter.status).toBe('success');
    expect(filter.results.map(doc => doc.apiId)).toEqual(['15000001']);

    const exportData = dataOf(result, 'export');
    expect(exportData.status).toBe('success');
    expect(exportData.output.exportRequest.format).toBe('CSV');
    expect(exportData.output.exportRequest.filename).toBe('결과_파일.csv');
  });

  it('미존재 apiId를 가진 apiDoc 노드는 error가 된다', () => {
    const result = runWorkflow([node('doc', 'apiDoc', { apiId: '99999999' })], []);
    const data = dataOf(result, 'doc');
    expect(data.status).toBe('error');
    expect(data.error).toContain('API 문서');
  });

  it('joinNode는 문서 2개 이상에서 공통 키를 찾는다', () => {
    const nodes = [
      node('doc1', 'apiDoc', { apiId: '15000001' }),
      node('doc2', 'apiDoc', { apiId: '15000002' }),
      node('join', 'joinNode', {}),
    ];
    const result = runWorkflow(nodes, [edge('doc1', 'join'), edge('doc2', 'join')]);
    const join = dataOf(result, 'join');
    expect(join.status).toBe('success');
    const exactKeys = join.output.joinPlan.joinKeys.filter(key => key.match === 'exact');
    expect(exactKeys.map(key => key.key)).toContain('stationCode');
  });

  it('joinNode는 입력 1개면 error다', () => {
    const nodes = [node('doc1', 'apiDoc', { apiId: '15000001' }), node('join', 'joinNode', {})];
    const result = runWorkflow(nodes, [edge('doc1', 'join')]);
    expect(dataOf(result, 'join').status).toBe('error');
  });

  it('ifNode multiDomain 조건은 도메인 2개 이상일 때만 통과한다', () => {
    const pass = runWorkflow(
      [
        node('doc1', 'apiDoc', { apiId: '15000001' }),
        node('doc2', 'apiDoc', { apiId: '15000002' }),
        node('cond', 'ifNode', { condition: 'multiDomain' }),
      ],
      [edge('doc1', 'cond'), edge('doc2', 'cond')]
    );
    expect(dataOf(pass, 'cond').status).toBe('success');

    const fail = runWorkflow(
      [node('doc1', 'apiDoc', { apiId: '15000001' }), node('cond', 'ifNode', { condition: 'multiDomain' })],
      [edge('doc1', 'cond')]
    );
    expect(dataOf(fail, 'cond').status).toBe('error');
    expect(dataOf(fail, 'cond').results).toEqual([]);
  });

  it('mergeNode는 입력이 없으면 error, 있으면 프롬프트를 만든다', () => {
    const empty = runWorkflow([node('merge', 'mergeNode', {})], []);
    expect(dataOf(empty, 'merge').status).toBe('error');

    const merged = runWorkflow(
      [
        node('doc1', 'apiDoc', { apiId: '15000001' }),
        node('doc2', 'apiDoc', { apiId: '15000002' }),
        node('merge', 'mergeNode', {}),
      ],
      [edge('doc1', 'merge'), edge('doc2', 'merge')]
    );
    const data = dataOf(merged, 'merge');
    expect(data.status).toBe('success');
    expect(data.output.fieldKeys).toContain('stationCode');
    expect(data.output.prompt).toContain('대기오염정보');
    expect(data.output.prompt).toContain('버스도착정보');
  });

  it('saveNode는 미구현임을 명시하고 아무것도 저장하지 않는다', () => {
    const result = runWorkflow(
      [node('doc1', 'apiDoc', { apiId: '15000001' }), node('save', 'saveNode', {})],
      [edge('doc1', 'save')]
    );
    const data = dataOf(result, 'save');
    expect(data.status).toBe('success');
    expect(data.output.persisted).toBe(false);
    expect(data.output.note).toContain('미구현');
  });

  it('exportNode는 입력이 없으면 error이고 exportRequest를 만들지 않는다', () => {
    const result = runWorkflow([node('export', 'exportNode', { format: 'JSON' })], []);
    const data = dataOf(result, 'export');
    expect(data.status).toBe('error');
    expect(data.output.exportRequest).toBeNull();
  });

  it('exportNode 파일명은 특수문자를 정리하고 XLSX는 .xls 확장자를 쓴다', () => {
    const result = runWorkflow(
      [
        node('doc1', 'apiDoc', { apiId: '15000001' }),
        node('export', 'exportNode', { format: 'XLSX', filename: 'a/b:c*d?' }),
      ],
      [edge('doc1', 'export')]
    );
    const request = dataOf(result, 'export').output.exportRequest;
    expect(request.filename).toBe('a-b-c-d-.xls');
    expect(request.format).toBe('XLSX');
  });

  it('apiSearch는 검색 결과를 output.docs로 내보낸다', () => {
    const result = runWorkflow([node('search', 'apiSearch', { query: '미세먼지', maxResults: 5 })], []);
    const data = dataOf(result, 'search');
    expect(data.status).toBe('success');
    expect(data.results.map(doc => doc.apiId)).toEqual(['15000001']);
  });
});

describe('runWorkflowForOutput', () => {
  const buildGraph = () => {
    const nodes = [
      node('doc1', 'apiDoc', { apiId: '15000001' }),
      node('doc2', 'apiDoc', { apiId: '15000002' }),
      node('exportA', 'exportNode', { format: 'JSON', filename: 'a' }),
      node('exportB', 'exportNode', { format: 'JSON', filename: 'b' }),
    ];
    const edges = [edge('doc1', 'exportA'), edge('doc2', 'exportB')];
    return { nodes, edges };
  };

  it('대상 출력의 upstream만 실행하고 나머지는 건드리지 않는다', () => {
    const { nodes, edges } = buildGraph();
    const result = runWorkflowForOutput(nodes, edges, 'exportA');

    expect(dataOf(result, 'exportA').status).toBe('success');
    expect(dataOf(result, 'doc1').status).toBe('success');
    // exportB 계열은 실행되지 않아 초기 데이터가 유지된다
    expect(dataOf(result, 'exportB').status).toBeUndefined();
    expect(dataOf(result, 'doc2').status).toBeUndefined();
  });

  it('다이아몬드 그래프에서 중복 문서를 dedupe한다', () => {
    const nodes = [
      node('doc1', 'apiDoc', { apiId: '15000001' }),
      node('filterA', 'categoryFilter', { category: '' }),
      node('filterB', 'providerFilter', { provider: '' }),
      node('merge', 'mergeNode', {}),
    ];
    const edges = [
      edge('doc1', 'filterA'),
      edge('doc1', 'filterB'),
      edge('filterA', 'merge'),
      edge('filterB', 'merge'),
    ];
    const result = runWorkflowForOutput(nodes, edges, 'merge');
    expect(dataOf(result, 'merge').results.map(doc => doc.apiId)).toEqual(['15000001']);
  });
});
