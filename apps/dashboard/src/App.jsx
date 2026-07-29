import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
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
import { loadCatalog } from './data/apiDocs.js';
import { runWorkflowForOutput } from './data/workflowEngine.js';
import { exportRows, toCsv, toExcelHtml, toJsonExport } from './data/exporters.js';
import { FlowImportError, deserializeFlow, flowToJson, maxNodeIdSuffix } from './data/flowIO.js';
import { NodePalette } from './components/NodePalette.jsx';
import { NodeProperties } from './components/NodeProperties.jsx';
import { RelationProperties } from './components/RelationProperties.jsx';
import { Toolbar } from './components/Toolbar.jsx';
import { OllamaChatModal } from './components/OllamaChatModal.jsx';
import { QueryBar } from './components/QueryBar.jsx';
import { ComposePanel } from './components/ComposePanel.jsx';
import { fetchRelations, searchDocsWithDetails } from './data/searchClient.js';
import { approveRelationEdge, placeSearchResults } from './data/relationEdges.js';
import { apiDocMap } from './data/apiDocs.js';
import { CATEGORY } from './nodes/BaseNode.jsx';

let idCounter = 100;
const nextId = () => `node-${++idCounter}`;

const EDGE_STYLE = {
  stroke: '#475569',
  strokeWidth: 2,
};

const OUTPUT_NODE_TYPES = new Set(['exportNode', 'saveNode', 'chatOutput']);

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

  downloadBlob(toJsonExport(exportRequest.docs), exportRequest.filename, 'application/json;charset=utf-8');
}

function downloadFlow(nodes, edges, name) {
  const base = String(name || 'workflow')
    .trim()
    .replace(/[\\/:*?"<>|]+/g, '-')
    .replace(/\s+/g, '_') || 'workflow';
  downloadBlob(flowToJson(nodes, edges, { name }), `${base}.flow.json`, 'application/json;charset=utf-8');
}

export default function App() {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const [selectedNode, setSelectedNode] = useState(null);
  const [selectedEdgeId, setSelectedEdgeId] = useState(null);
  const [activeChatContext, setActiveChatContext] = useState(null);
  const { screenToFlowPosition } = useReactFlow();
  const reactFlowWrapper = useRef(null);
  const [catalog, setCatalog] = useState({ state: 'loading', error: '' });

  useEffect(() => {
    loadCatalog().then(setCatalog);
  }, []);

  const retryCatalog = useCallback(() => {
    setCatalog({ state: 'loading', error: '' });
    loadCatalog({ force: true }).then(setCatalog);
  }, []);

  const [queryState, setQueryState] = useState({ busy: false, error: '' });
  const [composeTargets, setComposeTargets] = useState(null);

  const handleOpenCompose = useCallback(() => {
    const targets = nodes
      .filter(node => node.selected && node.type === 'apiDoc')
      .map(node => {
        const doc = node.data?.doc ?? apiDocMap[node.data?.apiId];
        return doc ? { serviceId: doc.serviceId ?? doc.apiId, name: doc.name } : null;
      })
      .filter(Boolean)
      .slice(0, 3); // combiner 계약: 1~3개
    if (targets.length === 0) {
      window.alert('조합할 API 문서 노드를 먼저 선택하세요 (Shift+클릭으로 복수 선택).');
      return;
    }
    setComposeTargets(targets);
  }, [nodes]);

  const handleNaturalQuery = useCallback(async (query) => {
    setQueryState({ busy: true, error: '' });
    try {
      const docs = await searchDocsWithDetails(query, 6);
      if (docs.length === 0) {
        setQueryState({ busy: false, error: '검색 결과가 없습니다.' });
        return;
      }
      let relations = [];
      try {
        relations = await fetchRelations(docs.map(doc => doc.serviceId));
      } catch {
        // 관계 조회 실패는 기능 저하 모드: 노드만 배치한다
      }
      const placed = placeSearchResults(docs, relations, nextId);
      setNodes(nds => nds.concat(placed.nodes));
      setEdges(eds => eds.concat(placed.edges));
      setQueryState({ busy: false, error: '' });
    } catch (error) {
      setQueryState({ busy: false, error: error.message });
    }
  }, [setNodes, setEdges]);

  const onConnect = useCallback(
    (connection) =>
      setEdges((eds) =>
        addEdge({ ...connection, style: EDGE_STYLE, type: 'smoothstep' }, eds)
      ),
    [setEdges]
  );

  const onSelectionChange = useCallback(({ nodes: selected, edges: selectedEdges }) => {
    setSelectedNode(selected.length === 1 ? selected[0] : null);
    setSelectedEdgeId(
      selected.length === 0 && selectedEdges.length === 1 ? selectedEdges[0].id : null
    );
  }, []);

  const handleApproveRelation = useCallback((edgeId) => {
    setEdges(eds => approveRelationEdge(eds, edgeId));
  }, [setEdges]);

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
        setSelectedEdgeId(null);
      }
    },
    [nodes, setNodes, setEdges]
  );

  const handleReset = () => {
    setNodes(initialNodes);
    setEdges(initialEdges);
    setSelectedNode(null);
    setSelectedEdgeId(null);
    setActiveChatContext(null);
  };

  const handleClear = () => {
    setNodes([]);
    setEdges([]);
    setSelectedNode(null);
    setSelectedEdgeId(null);
    setActiveChatContext(null);
  };

  const handleExportFlow = useCallback(() => {
    downloadFlow(nodes, edges, '워크플로우');
  }, [nodes, edges]);

  const handleImportFlow = useCallback((jsonText) => {
    try {
      const flow = deserializeFlow(jsonText);
      idCounter = Math.max(idCounter, maxNodeIdSuffix(flow.nodes));
      setNodes(flow.nodes);
      setEdges(flow.edges.map(edge => ({ ...edge, style: EDGE_STYLE })));
      setSelectedNode(null);
      setSelectedEdgeId(null);
      setActiveChatContext(null);
    } catch (error) {
      const message = error instanceof FlowImportError
        ? error.message
        : '워크플로우 파일을 읽을 수 없습니다.';
      window.alert(`가져오기 실패: ${message}`);
    }
  }, [setNodes, setEdges]);

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

    const saveNode = nextNodes.find((node) => (
      node.id === outputNodeId &&
      node.type === 'saveNode' &&
      node.data?.output?.saveRequest
    ));
    if (saveNode) {
      const name = saveNode.data.output.saveRequest.name;
      downloadFlow(nodes, edges, name);
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
        onExportFlow={handleExportFlow}
        onImportFlow={handleImportFlow}
        onCompose={handleOpenCompose}
      />

      {catalog.state === 'error' && (
        <div style={{
          background: '#450a0a', borderBottom: '1px solid #7f1d1d', color: '#fca5a5',
          padding: '6px 14px', fontSize: 12, display: 'flex', alignItems: 'center', gap: 10,
        }}>
          <span>nara_search 백엔드에 연결할 수 없습니다 — 카탈로그가 빈 상태로 동작합니다. ({catalog.error})</span>
          <button onClick={retryCatalog} style={{
            background: 'transparent', border: '1px solid #f8717144', borderRadius: 5,
            color: '#f87171', fontSize: 11, padding: '2px 8px', cursor: 'pointer',
          }}>다시 시도</button>
        </div>
      )}

      <QueryBar onQuery={handleNaturalQuery} busy={queryState.busy} error={queryState.error} />

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        <NodePalette />

        <div ref={reactFlowWrapper} style={{ flex: 1, position: 'relative' }}>
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

          {composeTargets && (
            <ComposePanel
              key={composeTargets.map(t => t.serviceId).join(',')}
              targets={composeTargets}
              onClose={() => setComposeTargets(null)}
            />
          )}
        </div>

        {(() => {
          const selectedEdge = selectedEdgeId ? edges.find(e => e.id === selectedEdgeId) : null;
          return selectedEdge?.data?.relation ? (
            <RelationProperties edge={selectedEdge} onApprove={handleApproveRelation} />
          ) : (
            <NodeProperties node={liveSelectedNode} edges={edges} onUpdateData={handleUpdateNodeData} />
          );
        })()}
      </div>

      <OllamaChatModal
        open={Boolean(activeChatContext)}
        context={activeChatContext}
        onClose={() => setActiveChatContext(null)}
      />
    </div>
  );
}
