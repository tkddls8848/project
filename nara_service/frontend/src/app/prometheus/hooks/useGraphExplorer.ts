/**
 * Main Graph Explorer State Management Hook
 */

import { useState, useCallback } from 'react';
import type { NodeFilters, GraphAppNode, GraphAppEdge } from '../types';

export const useGraphExplorer = () => {
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [expandedNodeIds, setExpandedNodeIds] = useState<Set<string>>(new Set());
  const [nodeFilters, setNodeFilters] = useState<NodeFilters>({
    Document: true,
    Keyword: true,
    Category: true,
    Provider: true,
  });

  const selectNode = useCallback((nodeId: string | null) => {
    setSelectedNodeId(nodeId);
  }, []);

  const clearSelection = useCallback(() => {
    setSelectedNodeId(null);
  }, []);

  const markAsExpanded = useCallback((nodeId: string) => {
    setExpandedNodeIds((prev) => new Set([...prev, nodeId]));
  }, []);

  const isExpanded = useCallback(
    (nodeId: string) => {
      return expandedNodeIds.has(nodeId);
    },
    [expandedNodeIds]
  );

  const toggleFilter = useCallback((type: keyof NodeFilters) => {
    setNodeFilters((prev) => ({
      ...prev,
      [type]: !prev[type],
    }));
  }, []);

  const setAllFilters = useCallback((value: boolean) => {
    setNodeFilters({
      Document: value,
      Keyword: value,
      Category: value,
      Provider: value,
    });
  }, []);

  const applyFiltersToNodes = useCallback(
    (nodes: GraphAppNode[]): GraphAppNode[] => {
      return nodes.map((node) => ({
        ...node,
        hidden: !nodeFilters[node.data.type as keyof NodeFilters],
      }));
    },
    [nodeFilters]
  );

  return {
    selectedNodeId,
    expandedNodeIds,
    nodeFilters,
    selectNode,
    clearSelection,
    markAsExpanded,
    isExpanded,
    toggleFilter,
    setAllFilters,
    applyFiltersToNodes,
  };
};
