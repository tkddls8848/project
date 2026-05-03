'use client';

/**
 * Relationship Creation Mode Hook
 * Phase 3: User-defined custom relationships between documents
 */

import { useState, useCallback } from 'react';
import type { GraphNodeData } from '../types';

export interface RelationshipSelection {
  selectedNodes: GraphNodeData[];
}

export const useRelationshipMode = () => {
  const [selection, setSelection] = useState<RelationshipSelection>({
    selectedNodes: [],
  });
  const [isModalOpen, setIsModalOpen] = useState(false);

  const selectNodeForRelationship = useCallback((node: GraphNodeData) => {
    // Only Document nodes can have custom relationships
    if (node.type !== 'Document') {
      return;
    }

    setSelection((prev) => {
      // Check if node is already selected
      const isAlreadySelected = prev.selectedNodes.some(n => n.id === node.id);

      if (isAlreadySelected) {
        // Remove node from selection
        return {
          selectedNodes: prev.selectedNodes.filter(n => n.id !== node.id)
        };
      } else {
        // Add node to selection
        return {
          selectedNodes: [...prev.selectedNodes, node]
        };
      }
    });
  }, []);

  const clearSelection = useCallback(() => {
    setSelection({ selectedNodes: [] });
  }, []);

  const openModal = useCallback(() => {
    setIsModalOpen(true);
  }, []);

  const closeModal = useCallback(() => {
    setIsModalOpen(false);
  }, []);

  return {
    selection,
    isModalOpen,
    selectNodeForRelationship,
    clearSelection,
    openModal,
    closeModal,
    canCreateRelationship: selection.selectedNodes.length >= 2,
  };
};
