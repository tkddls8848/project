'use client';

import React, { useState, useCallback, useEffect } from 'react';
import {
  useNodesState,
  useEdgesState,
  Edge,
  ReactFlowInstance,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { useTheme } from 'next-themes';
import { APIDoc, Prometheus, AppNode } from './types';
import { Sidebar } from './components/Sidebar';
import { ChatInterface } from './components/ChatInterface';
import { PrometheusHeader } from './components/PrometheusHeader';
import { PrometheusFooter } from './components/PrometheusFooter';
import { SavePrometheusModal } from './components/SavePrometheusModal';
import { LoadPrometheusModal } from './components/LoadPrometheusModal';
import { LoginModal } from '@/components/LoginModal';
import { ZarathustraChat } from './components/ZarathustraChat';
import { RelationshipChatModal } from './components/RelationshipChatModal';
import { RelationshipModal } from './components/RelationshipModal';
import { GraphCanvas } from './components/GraphCanvas';
import { RightSidebar } from './components/RightSidebar';

// Hooks
import { usePrometheusLayout } from './hooks/usePrometheusLayout';
import { usePrometheusChat } from './hooks/usePrometheusChat';
import { usePrometheusPersistence } from './hooks/usePrometheusPersistence';
import { usePrometheusSearch } from './hooks/usePrometheusSearch';
import { useGraphExplorer } from './hooks/useGraphExplorer';
import { useRelationshipMode } from './hooks/useRelationshipMode';
import { useGraphStats } from './hooks/useGraphStats';
import { usePrometheusModals } from './hooks/usePrometheusModals';
import { usePrometheusSelection } from './hooks/usePrometheusSelection';
import { useGraphHandlers } from './hooks/useGraphHandlers';
import { useGraphFiltering } from './hooks/useGraphFiltering';
import { useRelationshipCreation } from './hooks/useRelationshipCreation';

// --- Main Page Component ---
export default function PrometheusPage() {
  const { resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  const [rightSidebarOpen, setRightSidebarOpen] = useState(true);
  const [interactionMode, setInteractionMode] = useState<'relationship' | 'hierarchy'>('relationship');
  const [showHierarchyRelations, setShowHierarchyRelations] = useState(true);
  const [showLinkRelations, setShowLinkRelations] = useState(true);

  // Centralized modal state
  const { isOpen, openModal, closeModal } = usePrometheusModals();

  // Centralized selection state
  const { selectedDocId, setSelectedDocId, selectedGroupId, setSelectedGroupId } = usePrometheusSelection();

  // Custom Hooks
  const {
    searchQuery,
    setSearchQuery,
    searchResults,
    isSearching,
    handleSearch,
  } = usePrometheusSearch();

  // ReactFlow State
  const [nodes, setNodes, onNodesChange] = useNodesState<AppNode>([]);
  const [edges, setEdges, onEdgesState] = useEdgesState<Edge>([]);
  const [reactFlowInstance, setReactFlowInstance] = useState<ReactFlowInstance<AppNode, Edge> | null>(null);

  // Handlers
  const handleDeleteNode = useCallback(
    (nodeId: string) => {
      setNodes((nds) => nds.filter((node) => node.id !== nodeId));
      setEdges((eds) =>
        eds.filter((edge) => edge.source !== nodeId && edge.target !== nodeId)
      );
    },
    [setNodes, setEdges]
  );

  // --- Initialize Custom Hooks ---

  const {
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
  } = usePrometheusChat(reactFlowInstance, selectedGroupId);

  const { updateGroups, onNodeDragStart, onNodeDrag, onNodeDragStop } =
    usePrometheusLayout(
      reactFlowInstance,
      setNodes,
      setSelectedGroupId,
      handleGroupChatClick
    );

  const {
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
  } = usePrometheusPersistence(
    reactFlowInstance,
    setNodes,
    setEdges,
    handleDeleteNode
  );

  const {
    nodeFilters,
    toggleFilter,
    setAllFilters,
  } = useGraphExplorer();

  const {
    selection: relationshipSelection,
    selectNodeForRelationship,
    clearSelection: clearRelationshipSelection,
    canCreateRelationship,
    openModal: openRelationshipModal,
    closeModal: closeRelationshipModal,
    isModalOpen: isRelationshipModalOpen,
  } = useRelationshipMode();

  // Hierarchy and Link modal handlers
  const openHierarchyModal = useCallback(() => {
    if (relationshipSelection.selectedNodes.length >= 2) {
      openModal('hierarchy');
    }
  }, [relationshipSelection.selectedNodes.length, openModal]);

  const openLinkModal = useCallback(() => {
    if (relationshipSelection.selectedNodes.length >= 2) {
      openModal('link');
    }
  }, [relationshipSelection.selectedNodes.length, openModal]);

  const { handleCreateHierarchyRelationship, handleCreateLinkRelationship } =
    useRelationshipCreation({
      nodes,
      setEdges,
      clearRelationshipSelection,
      closeModal,
    });

  const { stats, isLoadingStats, refreshStats } = useGraphStats();

  // Graph handlers
  const { onConnect, onNodeClick, onPaneClick, addToCanvas } = useGraphHandlers({
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
  });

  // Graph filtering
  const { filteredEdges } = useGraphFiltering({
    edges,
    showHierarchyRelations,
    showLinkRelations,
  });

  // --- Effects & Handlers ---

  useEffect(() => {
    setMounted(true);
  }, []);

  // Update groups when edges/nodes change
  useEffect(() => {
    if (!nodes.length) return;
  }, [edges.length, nodes.length]);

  const loadSelectWrapper = (prometheus: Prometheus) => {
      handleLoadSelect(prometheus);
      setTimeout(updateGroups, 100);
  };

  const activeGroupDocs = getGroupDocs(activeChatGroupId);

  if (!mounted) return null;

  return (
    <div className="flex flex-col h-screen w-full bg-background overflow-hidden">
      <PrometheusHeader
        onSave={handleSaveClick}
        onLoad={handleLoadClick}
        onLoginClick={() => openModal('login')}
      />

      <div className="flex flex-1 overflow-hidden">
        <Sidebar
          searchQuery={searchQuery}
          setSearchQuery={setSearchQuery}
          handleSearch={handleSearch}
          isSearching={isSearching}
          searchResults={searchResults}
          addToCanvas={addToCanvas}
          nodeFilters={nodeFilters}
          toggleFilter={toggleFilter}
          setAllFilters={setAllFilters}
        />

        <div className="flex-1 flex flex-col h-full relative">
          <GraphCanvas
            nodes={nodes}
            edges={filteredEdges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesState}
            onConnect={onConnect}
            onInit={setReactFlowInstance}
            onNodeClick={onNodeClick}
            onNodeDragStart={onNodeDragStart}
            onNodeDrag={onNodeDrag}
            onNodeDragStop={onNodeDragStop}
            onPaneClick={onPaneClick}
            resolvedTheme={resolvedTheme}
          />
        </div>

        <RightSidebar
          rightSidebarOpen={rightSidebarOpen}
          setRightSidebarOpen={setRightSidebarOpen}
          interactionMode={interactionMode}
          setInteractionMode={setInteractionMode}
          relationshipSelection={relationshipSelection}
          selectNodeForRelationship={selectNodeForRelationship}
          clearRelationshipSelection={clearRelationshipSelection}
          canCreateRelationship={canCreateRelationship}
          openRelationshipModal={openLinkModal}
          openHierarchyModal={openHierarchyModal}
          selectedDocId={selectedDocId}
          searchResults={searchResults}
          addToCanvas={addToCanvas}
          showHierarchyRelations={showHierarchyRelations}
          setShowHierarchyRelations={setShowHierarchyRelations}
          showLinkRelations={showLinkRelations}
          setShowLinkRelations={setShowLinkRelations}
        />

        <ChatInterface
          open={chatModalOpen}
          onOpenChange={setChatModalOpen}
          groupId={activeChatGroupId}
          groupDocs={activeGroupDocs}
          chatResponse={chatResponse}
          isGenerating={isGenerating}
          chatMessage={chatMessage}
          setChatMessage={setChatMessage}
          handleChatSubmit={handleChatSubmit}
          modalResponseEndRef={modalResponseEndRef}
        />

        <SavePrometheusModal
          open={saveModalOpen}
          onOpenChange={setSaveModalOpen}
          onSave={handleSavePrometheus}
        />

        <LoadPrometheusModal
          open={loadModalOpen}
          onOpenChange={setLoadModalOpen}
          prometheuss={savedPrometheuss}
          onLoad={loadSelectWrapper}
          onDelete={handleDeletePrometheus}
        />

        <LoginModal
          open={isOpen('login')}
          onOpenChange={(open) => open ? openModal('login') : closeModal('login')}
        />

        <RelationshipChatModal
          open={isRelationshipModalOpen}
          onOpenChange={(open) => !open && closeRelationshipModal()}
          selectedNodes={relationshipSelection.selectedNodes}
        />

        <RelationshipModal
          type="hierarchy"
          open={isOpen('hierarchy')}
          onOpenChange={(open) => open ? openModal('hierarchy') : closeModal('hierarchy')}
          selectedNodes={relationshipSelection.selectedNodes}
          onCreateHierarchy={handleCreateHierarchyRelationship}
        />

        <RelationshipModal
          type="link"
          open={isOpen('link')}
          onOpenChange={(open) => open ? openModal('link') : closeModal('link')}
          selectedNodes={relationshipSelection.selectedNodes}
          onCreateLink={handleCreateLinkRelationship}
        />

        <ZarathustraChat />
      </div>
      <PrometheusFooter />

      <style jsx global>{`
        .custom-scrollbar::-webkit-scrollbar {
          width: 4px;
        }
        .custom-scrollbar::-webkit-scrollbar-track {
          background: transparent;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background: var(--border);
          border-radius: 4px;
        }
        .writing-mode-vertical {
          writing-mode: vertical-rl;
          text-orientation: mixed;
        }
      `}</style>
    </div>
  );
}