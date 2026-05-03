import { Edge } from '@xyflow/react';
import { AppNode } from '../types';
import { HierarchyRelationType } from '../types/hierarchyTypes';

interface NodePosition {
  x: number;
  y: number;
}

interface HandlePositions {
  sourceHandle: string;
  targetHandle: string;
}

/**
 * Determine optimal connection handles based on node positions
 *
 * Prioritizes horizontal connections over vertical when possible.
 * Analyzes relative positions to select the most visually appropriate handles.
 */
export const determineHandlePositions = (
  sourcePos: NodePosition,
  targetPos: NodePosition
): HandlePositions => {
  const dx = Math.abs(targetPos.x - sourcePos.x);
  const dy = Math.abs(targetPos.y - sourcePos.y);

  // Horizontal connection (prioritized)
  if (dx >= dy) {
    return {
      sourceHandle: targetPos.x > sourcePos.x ? 'right' : 'left',
      targetHandle: targetPos.x > sourcePos.x ? 'left' : 'right',
    };
  }

  // Vertical connection
  return {
    sourceHandle: targetPos.y > sourcePos.y ? 'bottom' : 'top',
    targetHandle: targetPos.y > sourcePos.y ? 'top' : 'bottom',
  };
};

interface HierarchyEdgeConfig {
  sourceId: string;
  targetId: string;
  hierarchyType: HierarchyRelationType;
}

/**
 * Create a hierarchy relationship edge between two nodes
 */
export const createHierarchyEdge = (
  nodes: AppNode[],
  config: HierarchyEdgeConfig
): Edge | null => {
  const sourceNode = nodes.find((n) => n.id === config.sourceId);
  const targetNode = nodes.find((n) => n.id === config.targetId);

  if (!sourceNode || !targetNode) {
    console.error('Source or target node not found');
    return null;
  }

  const { sourceHandle, targetHandle } = determineHandlePositions(
    sourceNode.position,
    targetNode.position
  );

  return {
    id: `hierarchy-${sourceNode.id}-${targetNode.id}-${Date.now()}`,
    source: sourceNode.id,
    target: targetNode.id,
    type: 'hierarchy',
    data: {
      hierarchyType: config.hierarchyType,
    },
    sourceHandle,
    targetHandle,
  };
};

interface LinkEdgeConfig {
  sourceId: string;
  targetId: string;
  relationType: 'positive' | 'negative';
}

/**
 * Create a link relationship edge between two nodes
 */
export const createLinkEdge = (
  nodes: AppNode[],
  config: LinkEdgeConfig
): Edge | null => {
  const sourceNode = nodes.find((n) => n.id === config.sourceId);
  const targetNode = nodes.find((n) => n.id === config.targetId);

  if (!sourceNode || !targetNode) {
    console.error('Source or target node not found');
    return null;
  }

  const { sourceHandle, targetHandle } = determineHandlePositions(
    sourceNode.position,
    targetNode.position
  );

  return {
    id: `rel-${sourceNode.id}-${targetNode.id}-${Date.now()}`,
    source: sourceNode.id,
    target: targetNode.id,
    type: 'default',
    data: {
      relationship: config.relationType,
    },
    sourceHandle,
    targetHandle,
  };
};
