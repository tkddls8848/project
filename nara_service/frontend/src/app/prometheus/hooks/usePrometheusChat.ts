import { useState, useRef, useCallback } from 'react';
import { Edge, ReactFlowInstance, Node } from '@xyflow/react';
import { APIDoc, AppNode, APIDocData } from '../types';
import { getConnectedComponents } from '../utils';

export function usePrometheusChat(
  reactFlowInstance: ReactFlowInstance<AppNode, Edge> | null,
  selectedGroupId: string | null
) {
  const [chatMessage, setChatMessage] = useState('');
  const [chatResponse, setChatResponse] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [chatModalOpen, setChatModalOpen] = useState(false);
  const [activeChatGroupId, setActiveChatGroupId] = useState<string | null>(null);

  const modalResponseEndRef = useRef<HTMLDivElement>(null);

  const handleGroupChatClick = useCallback((groupId: string) => {
    setActiveChatGroupId(groupId);
    setChatModalOpen(true);
    setChatResponse('');
    setChatMessage('');
  }, []);

  const getGroupDocs = useCallback((groupId: string | null) => {
    if (!groupId || !reactFlowInstance) return [];

    const currentEdges = reactFlowInstance.getEdges();
    const allNodes = reactFlowInstance.getNodes(); // Typed as AppNode[] via ReactFlowInstance generic
    
    // Type Guard for contextNode
    const isContextNode = (n: AppNode): n is Node<APIDocData, 'contextNode'> => n.type === 'contextNode';
    const dataNodes = allNodes.filter(isContextNode);
    
    const components = getConnectedComponents(dataNodes, currentEdges);

    const targetComponent = components.find(
      (c) => `group-${c.sort().join('-')}` === groupId
    );

    if (targetComponent) {
      return dataNodes
        .filter((n) => targetComponent.includes(n.id))
        .map((n) => n.data);
    }
    return [];
  }, [reactFlowInstance]);

  const handleChatSubmit = async () => {
    if (!chatMessage.trim()) return;

    const currentQuery = chatMessage;
    setChatMessage('');
    setIsGenerating(true);
    setChatResponse('');

    // Context Collection
    let contextDocs: APIDoc[] = [];
    let relationships: string[] = [];

    const currentEdges = reactFlowInstance?.getEdges() || [];
    const allNodes = reactFlowInstance?.getNodes() || [];
    
    const isContextNode = (n: AppNode): n is Node<APIDocData, 'contextNode'> => n.type === 'contextNode';
    const dataNodes = allNodes.filter(isContextNode);

    let relevantNodes: Node<APIDocData, 'contextNode'>[] = [];
    const activeGroupId = chatModalOpen ? activeChatGroupId : selectedGroupId;

    if (activeGroupId) {
      const components = getConnectedComponents(dataNodes, currentEdges);
      const targetComponent = components.find(
        (c) => `group-${c.sort().join('-')}` === activeGroupId
      );

      if (targetComponent) {
        relevantNodes = dataNodes.filter((n) =>
          targetComponent.includes(n.id)
        );
      }
    } else {
      relevantNodes = dataNodes;
    }

    contextDocs = relevantNodes.map((n) => n.data);

    // Relationship Extraction
    const relevantEdges = currentEdges.filter(
      (e: Edge) =>
        relevantNodes.some((n) => n.id === e.source) &&
        relevantNodes.some((n) => n.id === e.target)
    );

    relevantEdges.forEach((e: Edge) => {
      const sourceNode = relevantNodes.find((n) => n.id === e.source);
      const targetNode = relevantNodes.find((n) => n.id === e.target);
      const relType = e.data?.relationship as string;

      if (sourceNode && targetNode && relType && relType !== 'none') {
        const relLabel =
          relType === 'positive'
            ? '긍정적 관계 (Positive)'
            : '부정적 관계 (Negative)';
        relationships.push(
          `"${sourceNode.data.title}" -> ${relLabel} -> "${targetNode.data.title}"`
        );
      }
    });

    try {
      const res = await fetch('/api/backend/prometheus/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: currentQuery,
          context_docs: contextDocs,
          relationships: relationships,
        }),
      });

      if (!res.ok) throw new Error('Chat failed');
      if (!res.body) throw new Error('No response body');

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const json = JSON.parse(line);
            if (json.type === 'token') {
              setChatResponse((prev) => prev + json.data);
            }
          } catch (e) {
            console.error('Error parsing stream:', e);
          }
        }
      }
    } catch (error) {
      console.error(error);
      setChatResponse('Error generating response. Please try again.');
    } finally {
      setIsGenerating(false);
    }
  };

  return {
    chatMessage,
    setChatMessage,
    chatResponse,
    isGenerating,
    chatModalOpen,
    setChatModalOpen,
    activeChatGroupId,
    handleGroupChatClick,
    handleChatSubmit,
    getGroupDocs,
    modalResponseEndRef,
  };
}
