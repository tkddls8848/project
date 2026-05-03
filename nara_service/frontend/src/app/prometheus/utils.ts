import { FileText, Link2, Code2, FileJson, Database } from 'lucide-react';
import { Edge } from '@xyflow/react';
import type { AppNode, GraphAppNode, GraphAppEdge } from './types';

export const getTypeIcon = (category: string) => {
  switch (category) {
    case 'fileData': return FileText;
    case 'openapi_link': return Link2;
    case 'openapi_new': return Code2;
    case 'openapi_old': return FileJson;
    case 'standard': return Database;
    default: return FileJson;
  }
};

export const getTypeDisplayName = (category: string): string => {
  switch (category) {
    case 'fileData': return '파일데이터';
    case 'openapi_link': return 'OpenAPI(링크)';
    case 'openapi_new': return 'OpenAPI(신)';
    case 'openapi_old': return 'OpenAPI(구)';
    case 'standard': return '표준데이터셋';
    default: return category;
  }
};

export const getConnectedComponents = (nodes: AppNode[], edges: Edge[]) => {
  const adj = new Map<string, string[]>();
  nodes.forEach(node => adj.set(node.id, []));
  edges.forEach(edge => {
    if (adj.has(edge.source) && adj.has(edge.target)) {
      adj.get(edge.source)?.push(edge.target);
      adj.get(edge.target)?.push(edge.source);
    }
  });

  const visited = new Set<string>();
  const components: string[][] = [];

  nodes.forEach(node => {
    if (node.type === 'groupNode') return;
    if (!visited.has(node.id)) {
      const component: string[] = [];
      const stack = [node.id];
      visited.add(node.id);
      while (stack.length > 0) {
        const u = stack.pop()!;
        component.push(u);
        adj.get(u)?.forEach(v => {
          if (!visited.has(v)) {
            visited.add(v);
            stack.push(v);
          }
        });
      }
      if (component.length >= 1) { 
         components.push(component);
      }
    }
  });
  return components;
};

/**
 * Extract node and edge IDs from path response
 */
export const extractPathIds = (
  path: string[],
  relationships: Array<{ source: string; target: string; type: string }>
): { nodeIds: Set<string>; edgeIds: Set<string> } => {
  const nodeIds = new Set<string>(path);
  const edgeIds = new Set<string>();

  // Create edge IDs from relationships
  relationships.forEach((rel) => {
    // Edge ID format: source-target or reactflow__edge-source-target
    edgeIds.add(`${rel.source}-${rel.target}`);
    edgeIds.add(`reactflow__edge-${rel.source}-${rel.target}`);
  });

  return { nodeIds, edgeIds };
};

/**
 * Apply highlight to nodes and edges in path
 */
export const applyHighlight = (
  nodes: GraphAppNode[],
  edges: GraphAppEdge[],
  nodeIds: Set<string>,
  edgeIds: Set<string>
): { nodes: GraphAppNode[]; edges: GraphAppEdge[] } => {
  const highlightedNodes = nodes.map((node) => ({
    ...node,
    data: {
      ...node.data,
      highlighted: nodeIds.has(node.id),
      dimmed: !nodeIds.has(node.id),
    },
  })) as GraphAppNode[];

  const highlightedEdges = edges.map((edge) => {
    const isHighlighted = edgeIds.has(edge.id);
    return {
      ...edge,
      animated: isHighlighted,
      style: {
        ...edge.style,
        stroke: isHighlighted ? '#3b82f6' : edge.style?.stroke || '#b1b1b7',
        strokeWidth: isHighlighted ? 3 : edge.style?.strokeWidth || 2,
        opacity: isHighlighted ? 1 : 0.3,
      },
    };
  });

  return { nodes: highlightedNodes, edges: highlightedEdges };
};

/**
 * Clear highlight from all nodes and edges
 */
export const clearHighlight = (
  nodes: GraphAppNode[],
  edges: GraphAppEdge[]
): { nodes: GraphAppNode[]; edges: GraphAppEdge[] } => {
  const clearedNodes = nodes.map((node) => ({
    ...node,
    data: {
      ...node.data,
      highlighted: false,
      dimmed: false,
    },
  })) as GraphAppNode[];

  const clearedEdges = edges.map((edge) => ({
    ...edge,
    animated: false,
    style: {
      ...edge.style,
      opacity: 1,
      strokeWidth: edge.style?.strokeWidth || 2,
    },
  }));

  return { nodes: clearedNodes, edges: clearedEdges };
};