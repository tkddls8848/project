// Vite eager glob import — bundles all API JSON files at build time
const modules = import.meta.glob('../../apidata/*.json', { eager: true });

function extractFields(doc) {
  const defs = doc.swagger_json?.definitions ?? {};
  // Prefer 'items' (actual data record), then fall back to all defs
  const targetDefs = defs.items ? [defs.items] : Object.values(defs);
  const fields = [];
  const seen = new Set();
  const containerKeys = new Set([
    'response',
    'header',
    'body',
    'items',
    'item',
    'resultCode',
    'resultMsg',
    'totalCount',
    'numOfRows',
    'pageNo',
  ]);

  const collect = (schema, parentKey = '') => {
    if (!schema || typeof schema !== 'object') return;
    if (schema.properties && typeof schema.properties === 'object') {
      for (const [key, val] of Object.entries(schema.properties)) {
        if (containerKeys.has(key)) {
          collect(val, key);
          continue;
        }

        if (val?.properties || val?.items?.properties) {
          collect(val.properties ? val : val.items, key);
          continue;
        }

        if (seen.has(key)) continue;
        seen.add(key);
        fields.push({ key, desc: val?.description ?? parentKey ? `${parentKey}.${key}` : key });
      }
    }

    if (schema.items) collect(schema.items, parentKey);
  };

  for (const def of targetDefs) {
    collect(def);
  }
  return fields;
}

function extractEndpoints(doc) {
  return (doc.endpoints ?? []).map(ep => ({
    method: ep.method ?? 'GET',
    path: ep.path ?? '',
    description: ep.description ?? '',
  }));
}

function topCategory(raw) {
  return (raw ?? '').split(' - ')[0].trim() || '기타';
}

function parseKeywords(raw) {
  return (raw ?? '')
    .split(/[,，]/)
    .map(k => k.trim())
    .filter(Boolean);
}

export const apiDocs = Object.values(modules).map(mod => {
  const doc = mod.default ?? mod;
  return {
    apiId:       doc.api_id ?? '',
    name:        doc.info?.목록명 ?? doc.api_id ?? '',
    provider:    doc.info?.제공기관 ?? '',
    topCategory: topCategory(doc.info?.분류체계),
    category:    doc.info?.분류체계 ?? '',
    keywords:    parseKeywords(doc.info?.키워드),
    description: doc.info?.설명 ?? '',
    fields:      extractFields(doc),
    endpoints:   extractEndpoints(doc),
  };
}).sort((a, b) => a.topCategory.localeCompare(b.topCategory, 'ko'));

export const apiDocMap = Object.fromEntries(apiDocs.map(d => [d.apiId, d]));

function normalizeText(value) {
  return String(value ?? '').toLocaleLowerCase('ko');
}

function queryTerms(query) {
  return normalizeText(query)
    .split(/[\s,，/|]+/)
    .map(term => term.trim())
    .filter(Boolean);
}

function scoreDoc(doc, terms) {
  if (terms.length === 0) return 1;

  const fields = doc.fields.map(field => `${field.key} ${field.desc}`).join(' ');
  const haystacks = [
    { text: doc.name, weight: 5 },
    { text: doc.keywords.join(' '), weight: 4 },
    { text: `${doc.topCategory} ${doc.category}`, weight: 3 },
    { text: doc.provider, weight: 2 },
    { text: doc.description, weight: 2 },
    { text: fields, weight: 1 },
  ];

  return terms.reduce((sum, term) => {
    const termScore = haystacks.reduce((hitSum, item) => {
      return normalizeText(item.text).includes(term) ? hitSum + item.weight : hitSum;
    }, 0);
    return sum + termScore;
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
  return apiDocs
    .map(doc => ({ doc, score: scoreDoc(doc, terms) }))
    .filter(item => item.score > 0)
    .sort((a, b) => b.score - a.score || a.doc.name.localeCompare(b.doc.name, 'ko'))
    .slice(0, Math.max(1, Number(maxResults) || 10))
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
