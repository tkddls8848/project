import { useCallback } from 'react';
import { Connection, ReactFlowInstance, Edge } from '@xyflow/react';
import { addEdge } from '@xyflow/react';
import { AppNode, APIDoc } from '../types';
import { getConnectedComponents } from '../utils';
import type { GraphNodeData } from '../types';

interface UseGraphHandlersProps {
  reactFlowInstance: ReactFlowInstance<AppNode, Edge> | null;
  setSelectedDocId: (id: string | null) => void;
  setSelectedGroupId: (id: string | null) => void;
  interactionMode: 'relationship' | 'hierarchy';
  selectNodeForRelationship: (node: GraphNodeData) => void;
  setEdges: React.Dispatch<React.SetStateAction<Edge[]>>;
  updateGroups: () => void;
  nodes: AppNode[];
  setNodes: React.Dispatch<React.SetStateAction<AppNode[]>>;
  handleDeleteNode: (nodeId: string) => void;
}

export const useGraphHandlers = ({
  reactFlowInstance,
  setSelectedDocId,
  setSelectedGroupId,
  interactionMode,
  selectNodeForRelationship,
  setEdges,
  updateGroups,
  nodes,
  setNodes,
  handleDeleteNode,
}: UseGraphHandlersProps) => {
  const onConnect = useCallback(
    (params: Connection) => {
      setEdges((eds) => addEdge(params, eds));
      setTimeout(updateGroups, 100);
    },
    [setEdges, updateGroups]
  );

  const onNodeClick = useCallback(
    (event: React.MouseEvent, node: AppNode) => {
      // Set selected doc ID for insights
      if (node.type === 'contextNode' && node.data.id) {
        setSelectedDocId(node.data.id);

        // Handle interaction mode
        if (interactionMode === 'relationship' || interactionMode === 'hierarchy') {
          selectNodeForRelationship({
            id: node.id,
            label: node.data.title || node.id,
            type: 'Document',
            properties: node.data,
          });
        }
      }

      if (node.type === 'groupNode') {
        setSelectedGroupId(node.id);
      } else {
        const currentEdges = reactFlowInstance?.getEdges() || [];
        const allNodes = reactFlowInstance?.getNodes() || [];
        const appNodes = allNodes as AppNode[];

        const dataNodes = appNodes.filter((n) => n.type !== 'groupNode');
        const components = getConnectedComponents(dataNodes, currentEdges);

        const component = components.find((c) => c.includes(node.id));
        if (component) {
          const groupId = `group-${component.sort().join('-')}`;
          setSelectedGroupId(groupId);
        } else {
          setSelectedGroupId(null);
        }
      }
    },
    [reactFlowInstance, setSelectedGroupId, setSelectedDocId, interactionMode, selectNodeForRelationship]
  );

  const onPaneClick = useCallback(() => {
    setSelectedGroupId(null);
  }, [setSelectedGroupId]);

  const addToCanvas = useCallback(
    (doc: APIDoc) => {
      // Check for duplicates
      const exists = nodes.some((node) => {
        return node.type === 'contextNode' && node.data.id === doc.id;
      });

      if (exists) {
        alert("이미 추가된 노드입니다.");
        return;
      }

      const newNode: AppNode = {
        id: `${doc.id}-${Date.now()}`,
        type: 'contextNode',
        position: {
          x: Math.random() * 400 + 100,
          y: Math.random() * 300 + 100,
        },
        data: { ...doc, onDelete: handleDeleteNode },
      };
      setNodes((nds) => nds.concat(newNode));
    },
    [nodes, setNodes, handleDeleteNode]
  );

  return {
    onConnect,
    onNodeClick,
    onPaneClick,
    addToCanvas,
  };
};
