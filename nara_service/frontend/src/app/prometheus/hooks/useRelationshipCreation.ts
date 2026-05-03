import { useCallback } from 'react';
import { Edge } from '@xyflow/react';
import { AppNode } from '../types';
import { HierarchyRelationType } from '../types/hierarchyTypes';
import { createHierarchyEdge, createLinkEdge } from '../utils/relationshipUtils';

interface UseRelationshipCreationProps {
  nodes: AppNode[];
  setEdges: React.Dispatch<React.SetStateAction<Edge[]>>;
  clearRelationshipSelection: () => void;
  closeModal: (modal: 'hierarchy' | 'link') => void;
}

export const useRelationshipCreation = ({
  nodes,
  setEdges,
  clearRelationshipSelection,
  closeModal,
}: UseRelationshipCreationProps) => {
  const handleCreateHierarchyRelationship = useCallback(
    (sourceId: string, targetId: string, hierarchyType: HierarchyRelationType) => {
      const newEdge = createHierarchyEdge(nodes, {
        sourceId,
        targetId,
        hierarchyType,
      });

      if (newEdge) {
        setEdges((eds) => [...eds, newEdge]);
        clearRelationshipSelection();
        closeModal('hierarchy');
      }
    },
    [nodes, setEdges, clearRelationshipSelection, closeModal]
  );

  const handleCreateLinkRelationship = useCallback(
    (sourceId: string, targetId: string, relationType: 'positive' | 'negative') => {
      const newEdge = createLinkEdge(nodes, {
        sourceId,
        targetId,
        relationType,
      });

      if (newEdge) {
        setEdges((eds) => [...eds, newEdge]);
        clearRelationshipSelection();
        closeModal('link');
      }
    },
    [nodes, setEdges, clearRelationshipSelection, closeModal]
  );

  return {
    handleCreateHierarchyRelationship,
    handleCreateLinkRelationship,
  };
};
