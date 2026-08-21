import { describe, expect, it } from 'vitest';

import { nodeTypes } from '../../nodes/nodeTypes.jsx';
import {
  NODE_DEFAULTS,
  PALETTE_NODE_TYPES,
  WORKFLOW_NODE_TYPES,
} from '../workflowNodeDefinitions.js';
import { KNOWN_NODE_TYPES } from '../flowIO.js';

describe('workflow node definitions', () => {
  it('기본값·팔레트·가져오기·렌더러 타입 목록이 서로 일치한다', () => {
    expect(Object.keys(NODE_DEFAULTS)).toEqual(WORKFLOW_NODE_TYPES);
    expect(PALETTE_NODE_TYPES).toEqual(WORKFLOW_NODE_TYPES);
    expect(KNOWN_NODE_TYPES).toEqual(WORKFLOW_NODE_TYPES);
    expect(Object.keys(nodeTypes)).toEqual(WORKFLOW_NODE_TYPES);
  });
});
