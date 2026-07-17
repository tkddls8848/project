function topCategory(raw) {
  return (raw ?? '').split(' - ')[0].trim() || '기타';
}

function parseKeywords(raw) {
  return (raw ?? '')
    .split(/[,，]/)
    .map(k => k.trim())
    .filter(Boolean);
}

// 카탈로그는 빌드 타임 번들이 아니라 nara_search 백엔드(GET /api/catalog)에서
// 런타임에 로딩한다. apiDocs/apiDocMap은 같은 참조를 유지한 채 내용만 채워지므로
// 기존 소비자(노드·팔레트·워크플로우 엔진)는 로딩 완료 후 그대로 동작한다.
export const apiDocs = [];
export const apiDocMap = {};

let loadState = 'idle'; // idle | loading | ready | error
let loadError = '';

function toClientDoc(raw) {
  return {
    apiId: raw.api_id ?? '',
    serviceId: raw.service_id ?? '',
    name: raw.name ?? raw.api_id ?? '',
    provider: raw.provider ?? '',
    topCategory: topCategory(raw.category),
    category: raw.category ?? '',
    keywords: Array.isArray(raw.keywords) ? raw.keywords : parseKeywords(raw.keywords),
    description: raw.description ?? '',
    fields: raw.fields ?? [],
    endpoints: raw.endpoints ?? [],
  };
}

export async function loadCatalog({ force = false } = {}) {
  if (!force && (loadState === 'ready' || loadState === 'loading')) {
    return { state: loadState, error: loadError };
  }
  loadState = 'loading';
  try {
    const res = await fetch('/api/catalog');
    if (!res.ok) throw new Error(`카탈로그 응답 오류 (HTTP ${res.status})`);
    const payload = await res.json();
    const docs = (payload.docs ?? [])
      .map(toClientDoc)
      .sort((a, b) => a.topCategory.localeCompare(b.topCategory, 'ko'));

    apiDocs.length = 0;
    apiDocs.push(...docs);
    Object.keys(apiDocMap).forEach(key => delete apiDocMap[key]);
    docs.forEach(doc => { apiDocMap[doc.apiId] = doc; });

    loadState = 'ready';
    loadError = '';
  } catch (error) {
    // 실패 시 이전에 로딩된 문서는 유지한다 (기능 저하 모드)
    loadState = 'error';
    loadError = error?.message || 'nara_search 백엔드에 연결할 수 없습니다.';
  }
  return { state: loadState, error: loadError };
}

function normalizeText(value) {
  return String(value ?? '').toLocaleLowerCase('ko');
}

function compactText(value) {
  return normalizeText(value).replace(/[^\p{L}\p{N}]+/gu, '');
}

function queryTerms(query) {
  return normalizeText(query)
    .split(/[\s,，/|]+/)
    .map(term => term.trim())
    .filter(Boolean);
}

function ngrams(value, size = 2) {
  const text = compactText(value);
  if (text.length === 0) return [];
  if (text.length <= size) return [text];

  const grams = [];
  for (let i = 0; i <= text.length - size; i += 1) {
    grams.push(text.slice(i, i + size));
  }
  return grams;
}

function overlapRatio(term, text) {
  const queryGrams = new Set(ngrams(term));
  if (queryGrams.size === 0) return 0;

  const textGrams = new Set(ngrams(text));
  let hits = 0;
  queryGrams.forEach(gram => {
    if (textGrams.has(gram)) hits += 1;
  });

  return hits / queryGrams.size;
}

function scoreDoc(doc, terms) {
  if (terms.length === 0) return 1;

  const fields = doc.fields.map(field => `${field.key} ${field.desc}`).join(' ');
  const endpoints = doc.endpoints.map(endpoint => `${endpoint.method} ${endpoint.path} ${endpoint.description}`).join(' ');
  const haystacks = [
    { text: doc.name, weight: 5 },
    { text: doc.keywords.join(' '), weight: 4 },
    { text: `${doc.topCategory} ${doc.category}`, weight: 3 },
    { text: doc.provider, weight: 2 },
    { text: doc.description, weight: 2 },
    { text: fields, weight: 1 },
    { text: endpoints, weight: 1 },
  ];

  return terms.reduce((sum, term) => {
    const termScore = haystacks.reduce((hitSum, item) => {
      const normalized = normalizeText(item.text);
      const compact = compactText(item.text);
      const compactTerm = compactText(term);

      if (normalized.includes(term)) return hitSum + item.weight;
      if (compactTerm && compact.includes(compactTerm)) return hitSum + item.weight * 0.8;

      const fuzzy = compactTerm.length >= 2 ? overlapRatio(compactTerm, compact) : 0;
      return fuzzy >= 0.5 ? hitSum + item.weight * fuzzy * 0.45 : hitSum;
    }, 0);
    return sum + termScore;
  }, 0);
}

function broadScoreDoc(doc, terms) {
  if (terms.length === 0) return 1;

  const blob = [
    doc.name,
    doc.keywords.join(' '),
    doc.topCategory,
    doc.category,
    doc.provider,
    doc.description,
    doc.fields.map(field => `${field.key} ${field.desc}`).join(' '),
    doc.endpoints.map(endpoint => `${endpoint.method} ${endpoint.path} ${endpoint.description}`).join(' '),
  ].join(' ');

  return terms.reduce((sum, term) => {
    const ratio = overlapRatio(term, blob);
    return sum + (ratio >= 0.25 ? ratio : 0);
  }, 0);
}

export function toWorkflowDoc(doc, extra = {}) {
  return {
    apiId: doc.apiId,
    name: doc.name,
    provider: doc.provider,
    topCategory: doc.topCategory,
    category: doc.category,
    keywords: doc.keywords,
    description: doc.description,
    fields: doc.fields,
    endpoints: doc.endpoints,
    ...extra,
  };
}

export function searchApiDocs(query, maxResults = 10) {
  const terms = queryTerms(query);
  const limit = Math.max(1, Number(maxResults) || 10);
  const strictResults = apiDocs
    .map(doc => ({ doc, score: scoreDoc(doc, terms) }))
    .filter(item => item.score > 0)
    .sort((a, b) => b.score - a.score || a.doc.name.localeCompare(b.doc.name, 'ko'));

  const seen = new Set(strictResults.map(item => item.doc.apiId));
  const broadResults = strictResults.length >= limit
    ? []
    : apiDocs
        .filter(doc => !seen.has(doc.apiId))
        .map(doc => ({ doc, score: broadScoreDoc(doc, terms) }))
        .filter(item => item.score > 0)
        .sort((a, b) => b.score - a.score || a.doc.name.localeCompare(b.doc.name, 'ko'));

  return [...strictResults, ...broadResults]
    .slice(0, limit)
    .map(item => toWorkflowDoc(item.doc, {
      searchScore: item.score,
      searchReason: terms.length > 0 ? terms.join(', ') : '전체 문서',
    }));
}

export function uniqueDocs(docs) {
  const seen = new Set();
  return docs.filter(doc => {
    if (!doc?.apiId || seen.has(doc.apiId)) return false;
    seen.add(doc.apiId);
    return true;
  });
}
