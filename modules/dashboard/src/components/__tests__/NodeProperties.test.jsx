import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';

import { NodeProperties } from '../NodeProperties.jsx';
import { apiDocs } from '../../data/apiDocs.js';

describe('NodeProperties', () => {
  beforeEach(() => {
    apiDocs.length = 0;
  });

  afterEach(() => {
    apiDocs.length = 0;
  });

  it('apiDoc 선택지는 모듈 로드 후에 채워진 카탈로그를 반영한다', () => {
    const render = () => renderToStaticMarkup(
      <NodeProperties
        node={{ id: 'doc', type: 'apiDoc', position: { x: 0, y: 0 }, data: { apiId: '' } }}
        edges={[]}
        onUpdateData={() => {}}
      />
    );

    expect(render()).not.toContain('새 API (catalog-1)');

    apiDocs.push({
      apiId: 'catalog-1',
      name: '새 API',
      provider: '제공기관',
      topCategory: '기타',
      category: '기타',
      keywords: [],
      description: '',
      fields: [],
      endpoints: [],
    });

    expect(render()).toContain('새 API (catalog-1)');
  });
});
