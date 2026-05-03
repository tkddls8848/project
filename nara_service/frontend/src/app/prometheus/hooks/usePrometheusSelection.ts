import { useState, useCallback } from 'react';
import { Edge } from '@xyflow/react';

interface UsePrometheusSelectionReturn {
  selectedGroupId: string | null;
  selectedDocId: string | null;
  selectedEdge: Edge | null;
  setSelectedGroupId: (id: string | null) => void;
  setSelectedDocId: (id: string | null) => void;
  setSelectedEdge: (edge: Edge | null) => void;
  clearSelection: () => void;
}

/**
 * Centralized selection state management for Prometheus page
 *
 * Manages selection of groups, documents, and edges.
 * Provides a unified interface for selection state across components.
 */
export const usePrometheusSelection = (): UsePrometheusSelectionReturn => {
  const [selectedGroupId, setSelectedGroupId] = useState<string | null>(null);
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<Edge | null>(null);

  const clearSelection = useCallback(() => {
    setSelectedGroupId(null);
    setSelectedDocId(null);
    setSelectedEdge(null);
  }, []);

  return {
    selectedGroupId,
    selectedDocId,
    selectedEdge,
    setSelectedGroupId,
    setSelectedDocId,
    setSelectedEdge,
    clearSelection,
  };
};
