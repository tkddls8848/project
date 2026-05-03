import { useMemo } from 'react';
import { Edge } from '@xyflow/react';
import { isHierarchyRelation } from '../types/hierarchyTypes';

interface UseGraphFilteringProps {
  edges: Edge[];
  showHierarchyRelations: boolean;
  showLinkRelations: boolean;
}

/**
 * Filter edges based on hierarchy and link relations toggles
 */
export const useGraphFiltering = ({
  edges,
  showHierarchyRelations,
  showLinkRelations,
}: UseGraphFilteringProps) => {
  const filteredEdges = useMemo(() => {
    return edges.filter(edge => {
      const edgeType = edge.type;
      const hierarchyType = edge.data?.hierarchyType as string | undefined;
      const relationship = edge.data?.relationship as string | undefined;

      // Filter hierarchy relations
      if (!showHierarchyRelations) {
        if (edgeType === 'hierarchy' || isHierarchyRelation(hierarchyType)) {
          return false;
        }
      }

      // Filter link relations (positive/negative)
      if (!showLinkRelations) {
        if (edgeType === 'default' && (relationship === 'positive' || relationship === 'negative')) {
          return false;
        }
      }

      return true;
    });
  }, [edges, showHierarchyRelations, showLinkRelations]);

  return { filteredEdges };
};
