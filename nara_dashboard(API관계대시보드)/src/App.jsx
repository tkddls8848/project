import { useCallback, useMemo, useRef, useState } from 'react';
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
import { runWorkflowForOutput } from './data/workflowEngine.js';
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

const OUTPUT_NODE_TYPES = new Set(['exportNode', 'saveNode', 'chatOutput']);

function escapeCsv(value) {
  const text = String(value ?? '');
  return /[",\n\r]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

function exportRows(docs = []) {
  return docs.map(doc => ({
    apiId: doc.apiId,
    name: doc.name,
    provider: doc.provider,
    topCategory: doc.topCategory,
    category: doc.category,
    keywords: (doc.keywords ?? []).join(', '),
    description: doc.description,
    endpoints: (doc.endpoints ?? []).length,
    fields: (doc.fields ?? []).length,
    searchScore: doc.searchScore ?? '',
  }));
}

function toCsv(rows) {
  const headers = ['apiId', 'name', 'provider', 'topCategory', 'category', 'keywords', 'description', 'endpoints', 'fields', 'searchScore'];
  return [
    headers.join(','),
    ...rows.map(row => headers.map(header => escapeCsv(row[header])).join(',')),
  ].join('\r\n');
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function toExcelHtml(rows) {
  const headers = ['apiId', 'name', 'provider', 'topCategory', 'category', 'keywords', 'description', 'endpoints', 'fields', 'searchScore'];
  const head = headers.map(header => `<th>${escapeHtml(header)}</th>`).join('');
  const body = rows.map(row => (
    `<tr>${headers.map(header => `<td>${escapeHtml(row[header])}</td>`).join('')}</tr>`
  )).join('');

  return `<!doctype html><html><head><meta charset="utf-8"></head><body><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></body></html>`;
}

function downloadBlob(content, filename, type) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function downloadExport(exportRequest) {
  if (!exportRequest?.docs?.length) return;

  const format = String(exportRequest.format || 'JSON').toUpperCase();
  const rows = exportRows(exportRequest.docs);

  if (format === 'CSV') {
    downloadBlob(toCsv(rows), exportRequest.filename, 'text/csv;charset=utf-8');
    return;
  }

  if (format === 'XLSX') {
    downloadBlob(toExcelHtml(rows), exportRequest.filename, 'application/vnd.ms-excel;charset=utf-8');
    return;
  }

  downloadBlob(
    JSON.stringify({ exported_at: new Date().toISOString(), docs: exportRequest.docs }, null, 2),
    exportRequest.filename,
    'application/json;charset=utf-8'
  );
}

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
      const target = e.target;
      const isEditableTarget = target instanceof HTMLElement && (
        target.tagName === 'INPUT' ||
        target.tagName === 'TEXTAREA' ||
        target.tagName === 'SELECT' ||
        target.isContentEditable
      );

      if (isEditableTarget) return;

      if (e.key === 'Delete') {
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

  const handleRunOutput = useCallback((outputNodeId) => {
    const nextNodes = runWorkflowForOutput(nodes, edges, outputNodeId);
    setNodes(nextNodes);

    const exportNode = nextNodes.find((node) => (
      node.id === outputNodeId &&
      node.type === 'exportNode' &&
      node.data?.status === 'success'
    ));
    if (exportNode?.data?.output?.exportRequest) {
      downloadExport(exportNode.data.output.exportRequest);
    }

    const chatNode = nextNodes.find((node) => (
      node.id === outputNodeId &&
      node.type === 'chatOutput' &&
      node.data?.status === 'success'
    ));
    if (chatNode?.data?.chatContext) {
      setActiveChatContext(chatNode.data.chatContext);
      setSelectedNode(chatNode);
    }
  }, [edges, nodes, setNodes]);

  const handleUpdateNodeData = useCallback(
    (nodeId, patch) => {
      setNodes((nds) =>
        nds.map((node) => {
          if (node.id !== nodeId) return node;

          const {
            status,
            error,
            results,
            output,
            analysisPrompt,
            chatContext,
            ...stableData
          } = node.data ?? {};

          return {
            ...node,
            data: {
              ...stableData,
              ...patch,
              status: 'idle',
              error: '',
            },
          };
        })
      );
    },
    [setNodes]
  );

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

  const flowNodes = useMemo(
    () => nodes.map(node => {
      if (!OUTPUT_NODE_TYPES.has(node.type)) return node;
      return {
        ...node,
        data: {
          ...node.data,
          onRunOutput: () => handleRunOutput(node.id),
        },
      };
    }),
    [handleRunOutput, nodes]
  );

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
      />

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        <NodePalette />

        <div ref={reactFlowWrapper} style={{ flex: 1 }}>
          <ReactFlow
            nodes={flowNodes}
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
            deleteKeyCode="Delete"
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

        <NodeProperties
          node={liveSelectedNode}
          edges={edges}
          onUpdateData={handleUpdateNodeData}
        />
      </div>

      <OllamaChatModal
        open={Boolean(activeChatContext)}
        context={activeChatContext}
        onClose={() => setActiveChatContext(null)}
      />
    </div>
  );
}
