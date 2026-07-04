// 출력 노드 내보내기 직렬화 — DOM 의존 없는 순수 함수 모음 (단위 테스트 대상)

export const EXPORT_HEADERS = [
  'apiId',
  'name',
  'provider',
  'topCategory',
  'category',
  'keywords',
  'description',
  'endpoints',
  'fields',
  'searchScore',
];

// 한글 CSV를 Excel에서 바로 열 수 있도록 UTF-8 BOM을 붙인다
export const CSV_BOM = '\ufeff';

export function escapeCsv(value) {
  const text = String(value ?? '');
  return /[",\n\r]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

export function exportRows(docs = []) {
  return docs.map(doc => ({
    apiId: doc.apiId,
    name: doc.name,
    provider: doc.provider,
    topCategory: doc.topCategory,
    category: doc.category,
    keywords: (doc.keywords ?? []).join(', '),
    description: doc.description,
    endpoints: (doc.endpoints ?? []).length,
    fields: (doc.fields ?? []).length,
    searchScore: doc.searchScore ?? '',
  }));
}

export function toCsv(rows) {
  return CSV_BOM + [
    EXPORT_HEADERS.join(','),
    ...rows.map(row => EXPORT_HEADERS.map(header => escapeCsv(row[header])).join(',')),
  ].join('\r\n');
}

export function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

// XLSX 선택 시 실제로는 Excel 호환 HTML 테이블(.xls)을 생성한다
export function toExcelHtml(rows) {
  const head = EXPORT_HEADERS.map(header => `<th>${escapeHtml(header)}</th>`).join('');
  const body = rows.map(row => (
    `<tr>${EXPORT_HEADERS.map(header => `<td>${escapeHtml(row[header])}</td>`).join('')}</tr>`
  )).join('');

  return `<!doctype html><html><head><meta charset="utf-8"></head><body><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></body></html>`;
}

export function toJsonExport(docs, exportedAt = new Date()) {
  return JSON.stringify({ exported_at: exportedAt.toISOString(), docs }, null, 2);
}
