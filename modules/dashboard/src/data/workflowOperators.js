import { uniqueDocs } from './apiDocs.js';

export function filterByCategory(docs, category, strict) {
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

export function filterByProvider(docs, provider) {
  const needle = String(provider ?? '').trim().toLocaleLowerCase('ko');
  if (!needle) return docs;
  return docs.filter(doc => String(doc.provider ?? '').toLocaleLowerCase('ko').includes(needle));
}

export function topByScore(docs, topK, minScore) {
  const thresholdText = String(minScore ?? '').trim();
  const threshold = thresholdText === '' ? null : Number(thresholdText);
  const candidates = Number.isFinite(threshold)
    ? docs.filter(doc => (doc.searchScore ?? 0) >= threshold)
    : docs;

  return [...candidates]
    .sort((a, b) => (b.searchScore ?? 0) - (a.searchScore ?? 0) || a.name.localeCompare(b.name, 'ko'))
    .slice(0, Math.max(1, Number(topK) || 10));
}

export function buildAnalysisPrompt(docs, userPrompt = '이 API들을 조합하면 어떤 서비스가 가능한가?') {
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

export function mergedContext(docs) {
  const fieldKeys = uniqueDocs(docs)
    .flatMap(doc => doc.fields ?? [])
    .map(field => field.key);

  return {
    docs,
    fieldKeys: [...new Set(fieldKeys)],
    prompt: buildAnalysisPrompt(docs),
  };
}

export function normalizeExportFormat(format) {
  return String(format || 'JSON').trim().toUpperCase();
}

export function exportFilename(filename, format) {
  const base = String(filename || 'result')
    .trim()
    .replace(/[\\/:*?"<>|]+/g, '-')
    .replace(/\s+/g, '_') || 'result';
  const ext = normalizeExportFormat(format).toLowerCase() === 'xlsx' ? 'xls' : normalizeExportFormat(format).toLowerCase();
  return base.toLowerCase().endsWith(`.${ext}`) ? base : `${base}.${ext}`;
}
