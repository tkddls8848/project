import { useCallback, useRef } from 'react';
import { ReactFlowInstance } from '@xyflow/react';
import { AppNode } from '../types';
import { getConnectedComponents } from '../utils';

export function usePrometheusLayout(
  reactFlowInstance: ReactFlowInstance<AppNode> | null,
  setNodes: React.Dispatch<React.SetStateAction<AppNode[]>>,
  setSelectedGroupId: (id: string | null) => void,
  handleGroupChatClick: (groupId: string) => void
) {
  const groupDragRef = useRef<{ id: string; x: number; y: number } | null>(null);

  const handleDeleteGroup = useCallback((groupId: string) => {
    setNodes((nds) => nds.filter((n) => n.id !== groupId));
    setSelectedGroupId(null);
  }, [setNodes, setSelectedGroupId]);

  const updateGroups = useCallback(() => {
    setNodes((currentNodes) => {
      const dataNodes = currentNodes.filter((n) => n.type !== 'groupNode');
      const currentEdges = reactFlowInstance?.getEdges() || [];

      const components = getConnectedComponents(dataNodes, currentEdges);

      let newNodes = [...dataNodes];
      const groupNodes: AppNode[] = [];

      components.forEach((componentNodeIds, index) => {
        const groupId = `group-${componentNodeIds.sort().join('-')}`;

        const componentNodes = newNodes.filter((n) =>
          componentNodeIds.includes(n.id)
        );
        if (componentNodes.length === 0) return;

        const minX = Math.min(...componentNodes.map((n) => n.position.x));
        const minY = Math.min(...componentNodes.map((n) => n.position.y));
        const maxX = Math.max(
          ...componentNodes.map((n) => n.position.x + (n.width || 320))
        );
        const maxY = Math.max(
          ...componentNodes.map((n) => n.position.y + (n.height || 200))
        );

        const padding = 50;

        groupNodes.push({
          id: groupId,
          type: 'groupNode',
          position: { x: minX - padding, y: minY - padding },
          data: {
            label: `Group ${index + 1}`,
            onClick: setSelectedGroupId,
            onChatClick: handleGroupChatClick,
            onDelete: handleDeleteGroup,
            nodeIds: componentNodeIds, // Store component node IDs for dragging
          },
          style: {
            width: maxX - minX + padding * 2,
            height: maxY - minY + padding * 2,
            zIndex: -1,
          },
        });
      });

      return [...groupNodes, ...newNodes];
    });
  }, [reactFlowInstance, setNodes, setSelectedGroupId, handleGroupChatClick, handleDeleteGroup]);

  const onNodeDragStart = useCallback((event: React.MouseEvent, node: AppNode) => {
    if (node.type === 'groupNode') {
      groupDragRef.current = {
        id: node.id,
        x: node.position.x,
        y: node.position.y,
      };
    }
  }, []);

  const onNodeDrag = useCallback(
    (event: React.MouseEvent, node: AppNode) => {
      if (
        node.type === 'groupNode' &&
        groupDragRef.current &&
        groupDragRef.current.id === node.id
      ) {
        const dx = node.position.x - groupDragRef.current.x;
        const dy = node.position.y - groupDragRef.current.y;

        if (dx !== 0 || dy !== 0) {
          setNodes((nds) =>
            nds.map((n) => {
              if (
                node.data.nodeIds &&
                (node.data.nodeIds as string[]).includes(n.id)
              ) {
                return {
                  ...n,
                  position: {
                    x: n.position.x + dx,
                    y: n.position.y + dy,
                  },
                };
              }
              return n;
            })
          );
          groupDragRef.current = {
            id: node.id,
            x: node.position.x,
            y: node.position.y,
          };
        }
      }
    },
    [setNodes]
  );

  const onNodeDragStop = useCallback(() => {
    groupDragRef.current = null;
  }, []);

  return { updateGroups, onNodeDragStart, onNodeDrag, onNodeDragStop };
}