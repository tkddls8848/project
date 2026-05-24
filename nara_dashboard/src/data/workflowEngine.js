import { apiDocMap, searchApiDocs, toWorkflowDoc, uniqueDocs } from './apiDocs.js';

function inputEdgesFor(nodeId, edges) {
  return edges.filter(edge => edge.target === nodeId);
}

function topoSort(nodes, edges) {
  const nodeIds = new Set(nodes.map(node => node.id));
  const indegree = new Map(nodes.map(node => [node.id, 0]));
  const outgoing = new Map(nodes.map(node => [node.id, []]));

  edges.forEach(edge => {
    if (!nodeIds.has(edge.source) || !nodeIds.has(edge.target)) return;
    indegree.set(edge.target, (indegree.get(edge.target) ?? 0) + 1);
    outgoing.get(edge.source)?.push(edge.target);
  });

  const queue = nodes.filter(node => (indegree.get(node.id) ?? 0) === 0);
  const sorted = [];

  while (queue.length > 0) {
    const node = queue.shift();
    sorted.push(node);

    for (const targetId of outgoing.get(node.id) ?? []) {
      const nextDegree = (indegree.get(targetId) ?? 0) - 1;
      indegree.set(targetId, nextDegree);
      if (nextDegree === 0) {
        const target = nodes.find(candidate => candidate.id === targetId);
        if (target) queue.push(target);
      }
    }
  }

  return sorted.length === nodes.length ? sorted : nodes;
}

function outputDocsFor(node) {
  if (!node) return [];

  if (node.type === 'apiDoc') {
    const doc = apiDocMap[node.data?.apiId];
    return doc ? [toWorkflowDoc(doc)] : [];
  }

  return node.data?.output?.docs ?? node.data?.results ?? [];
}

function outputPromptFor(node) {
  if (!node) return '';
  return node.data?.output?.prompt ?? node.data?.analysisPrompt ?? '';
}

function collectInputDocs(node, edges, byId) {
  return uniqueDocs(
    inputEdgesFor(node.id, edges).flatMap(edge => outputDocsFor(byId.get(edge.source)))
  );
}

function collectInputPrompts(node, edges, byId) {
  return inputEdgesFor(node.id, edges)
    .map(edge => outputPromptFor(byId.get(edge.source)))
    .filter(Boolean);
}

function filterByCategory(docs, category, strict) {
  const needle = String(category ?? '').trim().toLocaleLowerCase('ko');
  if (!needle) return docs;

  return docs.filter(doc => {
    const candidates = [
      doc.topCategory,
      doc.category,
      doc.keywords?.join(' '),
      doc.name,
      doc.description,
    ].map(value => String(value ?? '').toLocaleLowerCase('ko'));

    return strict
      ? candidates.some(value => value === needle)
      : candidates.some(value => value.includes(needle));
  });
}

function filterByProvider(docs, provider) {
  const needle = String(provider ?? '').trim().toLocaleLowerCase('ko');
  if (!needle) return docs;
  return docs.filter(doc => String(doc.provider ?? '').toLocaleLowerCase('ko').includes(needle));
}

function topByScore(docs, topK) {
  return [...docs]
    .sort((a, b) => (b.searchScore ?? 0) - (a.searchScore ?? 0) || a.name.localeCompare(b.name, 'ko'))
    .slice(0, Math.max(1, Number(topK) || 10));
}

function normalizedTerms(value) {
  return String(value ?? '')
    .toLocaleLowerCase('ko')
    .split(/[\s,，/|]+/)
    .map(term => term.trim())
    .filter(Boolean);
}

function fieldBlob(doc) {
  return (doc.fields ?? [])
    .map(field => `${field.key} ${field.desc}`)
    .join(' ')
    .toLocaleLowerCase('ko');
}

function filterByFields(docs, includeFields, mode = 'any') {
  const terms = normalizedTerms(includeFields);
  if (terms.length === 0) return docs;

  return docs.filter(doc => {
    const blob = fieldBlob(doc);
    const hits = terms.filter(term => blob.includes(term));
    return mode === 'all' ? hits.length === terms.length : hits.length > 0;
  });
}

function conditionPasses(docs, condition, value) {
  if (condition === 'multiDomain') {
    return new Set(docs.map(doc => doc.topCategory || doc.category).filter(Boolean)).size >= 2;
  }

  if (condition === 'hasJoinKey') {
    return findJoinPlan(docs).joinKeys.length > 0;
  }

  return docs.length >= Math.max(1, Number(value) || 2);
}

function expansionQuery(docs, query) {
  const seed = String(query ?? '').trim();
  if (seed) return seed;

  return uniqueDocs(docs)
    .flatMap(doc => [
      doc.topCategory,
      ...(doc.keywords ?? []).slice(0, 4),
      doc.name,
    ])
    .filter(Boolean)
    .join(' ');
}

function keyType(field) {
  const text = `${field.key} ${field.desc}`.toLocaleLowerCase('ko');
  if (/(addr|address|주소|도로명|위치|location|lat|lon|xcrd|ycrd|좌표)/.test(text)) return 'location';
  if (/(date|dt|ymd|일자|날짜|년월|시간|time)/.test(text)) return 'time';
  if (/(code|cd|코드|id|식별|번호|no)/.test(text)) return 'code';
  if (/(name|nm|명칭|이름|기관명|학교명|업체명)/.test(text)) return 'name';
  return '';
}

function findJoinPlan(docs) {
  const unique = uniqueDocs(docs);
  const exactCounts = new Map();
  const typeCounts = new Map();

  unique.forEach(doc => {
    const exactKeys = new Set((doc.fields ?? []).map(field => field.key));
    exactKeys.forEach(key => exactCounts.set(key, (exactCounts.get(key) ?? 0) + 1));

    const types = new Set((doc.fields ?? []).map(keyType).filter(Boolean));
    types.forEach(type => typeCounts.set(type, (typeCounts.get(type) ?? 0) + 1));
  });

  const joinKeys = [...exactCounts.entries()]
    .filter(([, count]) => count >= 2)
    .map(([key, count]) => ({ key, match: 'exact', count }));

  const semanticKeys = [...typeCounts.entries()]
    .filter(([, count]) => count >= 2)
    .map(([type, count]) => ({ key: type, match: 'semantic', count }));

  return {
    joinKeys: [...joinKeys, ...semanticKeys].slice(0, 8),
    docs: unique.map(doc => ({
      apiId: doc.apiId,
      name: doc.name,
      candidateFields: (doc.fields ?? [])
        .filter(field => keyType(field))
        .slice(0, 8),
    })),
  };
}

function schemaDiff(docs) {
  const [left, right] = uniqueDocs(docs);
  if (!left || !right) return null;

  const leftKeys = new Set((left.fields ?? []).map(field => field.key));
  const rightKeys = new Set((right.fields ?? []).map(field => field.key));
  const common = [...leftKeys].filter(key => rightKeys.has(key));

  return {
    left: left.name,
    right: right.name,
    common,
    leftOnly: [...leftKeys].filter(key => !rightKeys.has(key)),
    rightOnly: [...rightKeys].filter(key => !leftKeys.has(key)),
  };
}

function mergedContext(docs) {
  const fieldKeys = uniqueDocs(docs)
    .flatMap(doc => doc.fields ?? [])
    .map(field => field.key);

  return {
    docs,
    fieldKeys: [...new Set(fieldKeys)],
    prompt: buildAnalysisPrompt(docs),
  };
}

function buildAnalysisPrompt(docs, userPrompt = '이 API들을 조합하면 어떤 서비스가 가능한가?') {
  const blocks = docs.map((doc, index) => {
    const fields = (doc.fields ?? [])
      .slice(0, 12)
      .map(field => `- ${field.key}: ${field.desc}`)
      .join('\n') || '- 필드 정보 없음';
    const endpoints = (doc.endpoints ?? [])
      .slice(0, 3)
      .map(endpoint => `- ${endpoint.method} ${endpoint.path}: ${endpoint.description}`)
      .join('\n') || '- 엔드포인트 정보 없음';

    return [
      `API ${index + 1}. ${doc.name}`,
      `제공기관: ${doc.provider}`,
      `도메인: ${doc.category || doc.topCategory}`,
      `키워드: ${(doc.keywords ?? []).join(', ') || '-'}`,
      `설명: ${doc.description || '-'}`,
      '제공 필드:',
      fields,
      '엔드포인트:',
      endpoints,
    ].join('\n');
  });

  return [
    '다음 공공 API 문서들을 서로 다른 논리 노드의 입력으로 보고, 단일 API만으로는 알 수 없는 조합 활용 방안을 도출하라.',
    `사용자 질문: ${userPrompt}`,
    '',
    blocks.join('\n\n---\n\n'),
    '',
    '출력 형식:',
    '1. 조합 가능한 서비스 아이디어',
    '2. 어떤 API 필드를 어떻게 연결하는지',
    '3. 이종 도메인 결합으로 생기는 새 가치',
    '4. 구현 시 필요한 추가 조건',
  ].join('\n');
}

function executeNode(node, edges, byId) {
  if (node.type === 'apiSearch') {
    const results = searchApiDocs(node.data?.query, node.data?.maxResults);
    return {
      ...node.data,
      status: 'success',
      results,
      output: { kind: 'apiDocs', docs: results },
      error: '',
    };
  }

  if (node.type === 'apiDoc') {
    const docs = outputDocsFor(node);
    return {
      ...node.data,
      status: docs.length > 0 ? 'success' : 'error',
      output: { kind: 'apiDocs', docs },
      error: docs.length > 0 ? '' : 'API 문서를 찾을 수 없습니다.',
    };
  }

  const inputDocs = collectInputDocs(node, edges, byId);

  if (node.type === 'categoryFilter') {
    const docs = filterByCategory(inputDocs, node.data?.category, node.data?.strict);
    return { ...node.data, status: 'success', results: docs, output: { kind: 'apiDocs', docs }, error: '' };
  }

  if (node.type === 'providerFilter') {
    const docs = filterByProvider(inputDocs, node.data?.provider);
    return { ...node.data, status: 'success', results: docs, output: { kind: 'apiDocs', docs }, error: '' };
  }

  if (node.type === 'scoreFilter') {
    const docs = topByScore(inputDocs, node.data?.topK);
    return { ...node.data, status: 'success', results: docs, output: { kind: 'apiDocs', docs }, error: '' };
  }

  if (node.type === 'fieldFilter') {
    const docs = filterByFields(inputDocs, node.data?.includeFields, node.data?.mode);
    return { ...node.data, status: 'success', results: docs, output: { kind: 'apiDocs', docs }, error: '' };
  }

  if (node.type === 'ifNode') {
    const pass = conditionPasses(inputDocs, node.data?.condition, node.data?.value);
    return {
      ...node.data,
      status: pass ? 'success' : 'error',
      results: pass ? inputDocs : [],
      output: { kind: 'apiDocs', docs: pass ? inputDocs : [] },
      error: pass ? '' : '조건을 통과하지 못했습니다.',
    };
  }

  if (node.type === 'semanticExpand') {
    const query = expansionQuery(inputDocs, node.data?.query);
    const expanded = searchApiDocs(query, node.data?.maxResults);
    const docs = uniqueDocs([...inputDocs, ...expanded]);
    return {
      ...node.data,
      status: 'success',
      results: docs,
      output: { kind: 'apiDocs', docs, expansionQuery: query },
      error: '',
    };
  }

  if (node.type === 'joinNode') {
    const joinPlan = findJoinPlan(inputDocs);
    return {
      ...node.data,
      status: inputDocs.length >= 2 ? 'success' : 'error',
      results: inputDocs,
      output: { kind: 'joinPlan', docs: inputDocs, joinPlan },
      error: inputDocs.length >= 2 ? '' : 'Join에는 최소 2개 API 문서가 필요합니다.',
    };
  }

  if (node.type === 'schemaDiff') {
    const diff = schemaDiff(inputDocs);
    return {
      ...node.data,
      status: diff ? 'success' : 'error',
      results: inputDocs,
      output: { kind: 'schemaDiff', docs: inputDocs, schemaDiff: diff },
      error: diff ? '' : '스키마 비교에는 최소 2개 API 문서가 필요합니다.',
    };
  }

  if (node.type === 'mergeNode') {
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
  }

  if (node.type === 'ragChat') {
    const prompt = buildAnalysisPrompt(inputDocs, node.data?.prompt);
    return {
      ...node.data,
      status: inputDocs.length > 0 ? 'success' : 'idle',
      analysisPrompt: inputDocs.length > 0 ? prompt : '',
      output: { kind: 'analysisPrompt', docs: inputDocs, prompt },
      error: '',
    };
  }

  if (node.type === 'chatOutput') {
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
  }

  return {
    ...node.data,
    status: 'success',
    output: { kind: 'passthrough', docs: inputDocs },
    error: '',
  };
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
