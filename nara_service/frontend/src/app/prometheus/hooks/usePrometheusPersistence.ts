import { useState } from 'react';
import { Edge, ReactFlowInstance } from '@xyflow/react';
import { signIn, useSession } from 'next-auth/react';
import { Prometheus, AppNode } from '../types';

export function usePrometheusPersistence(
  reactFlowInstance: ReactFlowInstance<AppNode> | null,
  setNodes: React.Dispatch<React.SetStateAction<AppNode[]>>,
  setEdges: React.Dispatch<React.SetStateAction<Edge[]>>,
  onDeleteNode: (id: string) => void
) {
  const { data: session } = useSession();
  const [saveModalOpen, setSaveModalOpen] = useState(false);
  const [loadModalOpen, setLoadModalOpen] = useState(false);
  const [savedPrometheuss, setSavedPrometheuss] = useState<Prometheus[]>([]);

  const handleSaveClick = () => {
    if (!session) {
      alert('로그인이 필요한 기능입니다.');
      signIn();
      return;
    }
    setSaveModalOpen(true);
  };

  const handleLoadClick = async () => {
    if (!session?.user?.email) {
      alert('로그인이 필요한 기능입니다.');
      signIn();
      return;
    }
    try {
      const res = await fetch(
        `/api/backend/prometheus?user_id=${session.user.email}`
      );
      if (res.ok) {
        const data = await res.json();
        setSavedPrometheuss(data.prometheuss);
        setLoadModalOpen(true);
      }
    } catch (error) {
      console.error('Failed to load prometheuss', error);
    }
  };

  const handleSavePrometheus = async (name: string) => {
    if (!session?.user?.email || !reactFlowInstance) return;

    // Filter out group nodes before saving
    const allNodes = reactFlowInstance.getNodes();
    const dataNodes = allNodes.filter((n) => n.type !== 'groupNode');
    const allEdges = reactFlowInstance.getEdges();

    console.log('💾 [Saving Prometheus]', {
      totalEdges: allEdges.length,
      hierarchyEdges: allEdges.filter(e => e.type === 'hierarchy').length,
      linkEdges: allEdges.filter(e => e.type === 'default' && e.data?.relationship).length,
      edges: allEdges,
    });

    try {
      const res = await fetch('/api/backend/prometheus', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: session.user.email,
          name,
          nodes: dataNodes,
          edges: allEdges,
        }),
      });

      if (!res.ok) throw new Error('Failed to save');
    } catch (error) {
      console.error(error);
    }
  };

  const handleLoadSelect = (prometheus: Prometheus) => {
    // Re-attach handlers as functions are not serializable
    const restoredNodes = (prometheus.nodes || []).map((n: any) => ({
      ...n,
      data: {
        ...n.data,
        onDelete: onDeleteNode,
      },
    }));

    console.log('🔄 [Loading Prometheus]', {
      totalEdges: prometheus.edges?.length || 0,
      edges: prometheus.edges,
    });

    setNodes(restoredNodes);
    setEdges(prometheus.edges || []);
  };

  const handleDeletePrometheus = async (id: string) => {
    if (!session?.user?.email) return;
    try {
      const res = await fetch(
        `/api/backend/prometheus/${id}?user_id=${session.user.email}`,
        {
          method: 'DELETE',
        }
      );
      if (res.ok) {
        setSavedPrometheuss((prev) => prev.filter((w) => w.id !== id));
      }
    } catch (e) {
      console.error(e);
    }
  };

  return {
    saveModalOpen,
    setSaveModalOpen,
    loadModalOpen,
    setLoadModalOpen,
    savedPrometheuss,
    handleSaveClick,
    handleLoadClick,
    handleSavePrometheus,
    handleLoadSelect,
    handleDeletePrometheus,
  };
}
