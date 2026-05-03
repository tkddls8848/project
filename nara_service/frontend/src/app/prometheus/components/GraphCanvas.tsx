/**
 * Graph Canvas Component for Prometheus Page
 *
 * Why: ReactFlow 캔버스 영역을 별도 컴포넌트로 분리하여
 *      page.tsx의 복잡도를 낮춥니다.
 */

'use client';

import React from 'react';
import {
  ReactFlow,
  Controls,
  Background,
  BackgroundVariant,
  ReactFlowInstance,
  Edge,
  Connection,
  OnNodesChange,
  OnEdgesChange,
  ConnectionMode,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import type { AppNode } from '../types';
import { nodeTypes, edgeTypes } from './CustomFlowElements';

interface GraphCanvasProps {
  // ReactFlow State
  nodes: AppNode[];
  edges: Edge[];
  onNodesChange: OnNodesChange<AppNode>;
  onEdgesChange: OnEdgesChange<Edge>;
  onConnect: (connection: Connection) => void;

  // Instance
  onInit: (instance: ReactFlowInstance<AppNode, Edge>) => void;

  // Event Handlers
  onNodeClick: (event: React.MouseEvent, node: AppNode) => void;
  onNodeDragStart: (event: React.MouseEvent, node: AppNode) => void;
  onNodeDrag: (event: React.MouseEvent, node: AppNode) => void;
  onNodeDragStop: (event: React.MouseEvent, node: AppNode) => void;
  onPaneClick: () => void;

  // Theme
  resolvedTheme?: string;
}

/**
 * Graph Canvas - ReactFlow Visualization
 *
 * Why: 캔버스 영역을 별도 컴포넌트로 분리하여
 *      ReactFlow 관련 로직을 독립적으로 관리합니다.
 */
export function GraphCanvas({
  nodes,
  edges,
  onNodesChange,
  onEdgesChange,
  onConnect,
  onInit,
  onNodeClick,
  onNodeDragStart,
  onNodeDrag,
  onNodeDragStop,
  onPaneClick,
  resolvedTheme,
}: GraphCanvasProps) {
  return (
    <div className="flex-1 relative bg-slate-50 dark:bg-slate-950">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        onInit={onInit}
        onNodeClick={onNodeClick}
        onNodeDragStart={onNodeDragStart}
        onNodeDrag={onNodeDrag}
        onNodeDragStop={onNodeDragStop}
        onPaneClick={onPaneClick}
        connectionMode={ConnectionMode.Loose}
        fitView
        fitViewOptions={{ maxZoom: 0.8, padding: 0.2 }}
      >
        <Controls
          showZoom={false}
          showFitView={true}
          className="dark:bg-muted dark:text-foreground [&>button]:bg-card [&>button]:border-border [&>button>svg]:text-muted-foreground"
        />
        <Background
          variant={BackgroundVariant.Dots}
          gap={12}
          size={1}
          color={resolvedTheme === 'dark' ? '#334155' : '#cbd5e1'}
        />
      </ReactFlow>

      {/* Empty State */}
      {nodes.length === 0 && (
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 pointer-events-none text-center opacity-50">
          <h3 className="text-lg font-semibold">Prometheus Canvas</h3>
          <p className="text-sm">Add nodes from the sidebar to start</p>
        </div>
      )}
    </div>
  );
}
