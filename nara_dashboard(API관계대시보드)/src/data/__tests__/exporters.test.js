import { describe, expect, it } from 'vitest';

import {
  CSV_BOM,
  EXPORT_HEADERS,
  escapeCsv,
  escapeHtml,
  exportRows,
  toCsv,
  toExcelHtml,
  toJsonExport,
} from '../exporters.js';

const SAMPLE_DOC = {
  apiId: '15000001',
  name: '대기오염정보 "실시간"',
  provider: '한국환경공단',
  topCategory: '환경기상',
  category: '환경기상 - 대기',
  keywords: ['미세먼지', '대기질'],
  description: '시도별, 실시간\n측정정보',
  endpoints: [{ method: 'GET', path: '/a', description: '' }],
  fields: [{ key: 'pm10Value', desc: '미세먼지 농도' }],
  searchScore: 4.2,
};

describe('escapeCsv', () => {
  it('쉼표·따옴표·개행이 있으면 따옴표로 감싸고 내부 따옴표를 이스케이프한다', () => {
    expect(escapeCsv('a,b')).toBe('"a,b"');
    expect(escapeCsv('say "hi"')).toBe('"say ""hi"""');
    expect(escapeCsv('line1\nline2')).toBe('"line1\nline2"');
  });

  it('일반 텍스트와 null은 그대로/빈 문자열로 처리한다', () => {
    expect(escapeCsv('한국환경공단')).toBe('한국환경공단');
    expect(escapeCsv(null)).toBe('');
  });
});

describe('exportRows', () => {
  it('문서를 헤더와 같은 키의 평면 행으로 변환한다', () => {
    const [row] = exportRows([SAMPLE_DOC]);
    expect(Object.keys(row)).toEqual(EXPORT_HEADERS);
    expect(row.keywords).toBe('미세먼지, 대기질');
    expect(row.endpoints).toBe(1);
    expect(row.fields).toBe(1);
  });

  it('누락 필드가 있어도 안전하다', () => {
    const [row] = exportRows([{ apiId: 'x', name: 'n' }]);
    expect(row.keywords).toBe('');
    expect(row.endpoints).toBe(0);
    expect(row.searchScore).toBe('');
  });
});

describe('toCsv', () => {
  it('BOM + 헤더 + CRLF 행으로 직렬화한다', () => {
    const csv = toCsv(exportRows([SAMPLE_DOC]));
    expect(csv.startsWith(CSV_BOM)).toBe(true);
    const lines = csv.slice(CSV_BOM.length).split('\r\n');
    expect(lines[0]).toBe(EXPORT_HEADERS.join(','));
    expect(lines[1]).toContain('한국환경공단');
    expect(lines[1]).toContain('"대기오염정보 ""실시간"""');
  });

  it('빈 입력은 헤더만 출력한다', () => {
    const csv = toCsv([]);
    expect(csv).toBe(CSV_BOM + EXPORT_HEADERS.join(','));
  });
});

describe('toExcelHtml', () => {
  it('HTML 테이블로 직렬화하고 특수문자를 이스케이프한다', () => {
    const html = toExcelHtml(exportRows([{ ...SAMPLE_DOC, name: '<script>&x' }]));
    expect(html).toContain('<meta charset="utf-8">');
    expect(html).toContain('&lt;script&gt;&amp;x');
    expect(html).not.toContain('<script>&x');
  });
});

describe('toJsonExport', () => {
  it('exported_at과 원본 docs를 담은 JSON을 만든다', () => {
    const at = new Date('2026-07-04T00:00:00Z');
    const parsed = JSON.parse(toJsonExport([SAMPLE_DOC], at));
    expect(parsed.exported_at).toBe('2026-07-04T00:00:00.000Z');
    expect(parsed.docs).toHaveLength(1);
    expect(parsed.docs[0].apiId).toBe('15000001');
  });
});
