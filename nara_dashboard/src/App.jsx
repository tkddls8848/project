import { useCallback, useRef, useState } from 'react';
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  addEdge,
  useNodesState,
  useEdgesState,
  useReactFlow,
} from '@xyflow/react';

import { nodeTypes } from './nodes/nodeTypes.jsx';
import { initialNodes, initialEdges, NODE_DEFAULTS } from './data/initialFlow.js';
import { runWorkflow } from './data/workflowEngine.js';
import { NodePalette } from './components/NodePalette.jsx';
import { NodeProperties } from './components/NodeProperties.jsx';
import { Toolbar } from './components/Toolbar.jsx';
import { OllamaChatModal } from './components/OllamaChatModal.jsx';
import { CATEGORY } from './nodes/BaseNode.jsx';

let idCounter = 100;
const nextId = () => `node-${++idCounter}`;

const EDGE_STYLE = {
  stroke: '#475569',
  strokeWidth: 2,
};

export default function App() {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const [selectedNode, setSelectedNode] = useState(null);
  const [activeChatContext, setActiveChatContext] = useState(null);
  const { screenToFlowPosition } = useReactFlow();
  const reactFlowWrapper = useRef(null);

  const onConnect = useCallback(
    (connection) =>
      setEdges((eds) =>
        addEdge({ ...connection, style: EDGE_STYLE, type: 'smoothstep' }, eds)
      ),
    [setEdges]
  );

  const onSelectionChange = useCallback(
    ({ nodes: selected }) => {
      if (selected.length === 1) {
        setSelectedNode(selected[0]);
      } else {
        setSelectedNode(null);
      }
    },
    []
  );

  const onDragOver = useCallback((e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
  }, []);

  const onDrop = useCallback(
    (e) => {
      e.preventDefault();
      const type = e.dataTransfer.getData('application/reactflow');
      if (!type || !(type in NODE_DEFAULTS)) return;

      const position = screenToFlowPosition({ x: e.clientX, y: e.clientY });
      const baseData = { ...(NODE_DEFAULTS[type] ?? {}) };

      // API doc nodes carry their apiId via a separate transfer key
      if (type === 'apiDoc') {
        const apiId = e.dataTransfer.getData('application/reactflow-apiid');
        if (!apiId) return;
        baseData.apiId = apiId;
      }

      setNodes((nds) => nds.concat({ id: nextId(), type, position, data: baseData }));
    },
    [screenToFlowPosition, setNodes]
  );

  const onKeyDown = useCallback(
    (e) => {
      if (e.key === 'Delete' || e.key === 'Backspace') {
        setNodes((nds) => nds.filter((n) => !n.selected));
        setEdges((eds) =>
          eds.filter((ed) => {
            if (ed.selected) return false;
            return nodes.some((node) => node.id === ed.source && node.selected)
              ? false
              : !nodes.some((node) => node.id === ed.target && node.selected);
          })
        );
        setSelectedNode(null);
      }
    },
    [nodes, setNodes, setEdges]
  );

  const handleReset = () => {
    setNodes(initialNodes);
    setEdges(initialEdges);
    setSelectedNode(null);
    setActiveChatContext(null);
  };

  const handleClear = () => {
    setNodes([]);
    setEdges([]);
    setSelectedNode(null);
    setActiveChatContext(null);
  };

  const handleRun = () => {
    const nextNodes = runWorkflow(nodes, edges);
    setNodes(nextNodes);

    const chatNode = nextNodes.find((node) => node.type === 'chatOutput' && node.data?.status === 'success');
    if (chatNode?.data?.chatContext) {
      setActiveChatContext(chatNode.data.chatContext);
      setSelectedNode(chatNode);
    }
  };

  const minimapColor = (node) => {
    const typeToCategory = {
      apiSearch: 'source',
      categoryFilter: 'filter', providerFilter: 'filter', scoreFilter: 'filter',
      ragChat: 'analysis', summaryNode: 'analysis',
      exportNode: 'output', saveNode: 'output', chatOutput: 'output',
    };
    return CATEGORY[typeToCategory[node.type] ?? 'source'].color;
  };

  // Keep selectedNode in sync when nodes change (e.g. after reset)
  const liveSelectedNode = selectedNode
    ? nodes.find((n) => n.id === selectedNode.id) ?? null
    : null;

  return (
    <div
      style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}
      onKeyDown={onKeyDown}
      tabIndex={-1}
    >
      <Toolbar
        nodeCount={nodes.length}
        edgeCount={edges.length}
        onClear={handleClear}
        onReset={handleReset}
        onRun={handleRun}
      />

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        <NodePalette />

        <div ref={reactFlowWrapper} style={{ flex: 1 }}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onDrop={onDrop}
            onDragOver={onDragOver}
            onSelectionChange={onSelectionChange}
            nodeTypes={nodeTypes}
            defaultEdgeOptions={{ type: 'smoothstep', style: EDGE_STYLE }}
            fitView
            fitViewOptions={{ padding: 0.2 }}
            minZoom={0.3}
            maxZoom={2}
            snapToGrid
            snapGrid={[16, 16]}
            deleteKeyCode={['Delete', 'Backspace']}
          >
            <Background
              variant={BackgroundVariant.Dots}
              gap={20}
              size={1}
              color="#1e2535"
            />
            <Controls />
            <MiniMap
              nodeColor={minimapColor}
              maskColor="#0f111788"
              style={{ background: '#111623' }}
            />
          </ReactFlow>
        </div>

        <NodeProperties node={liveSelectedNode} edges={edges} />
      </div>

      <OllamaChatModal
        open={Boolean(activeChatContext)}
        context={activeChatContext}
        onClose={() => setActiveChatContext(null)}
      />
    </div>
  );
}
