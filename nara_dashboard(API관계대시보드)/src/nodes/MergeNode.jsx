import { Handle, Position, useEdges, useNodes } from '@xyflow/react';
import { CATEGORY } from './BaseNode.jsx';
import { apiDocMap } from '../data/apiDocs.js';

function resolveApiName(node, docs = []) {
  if (!node) return null;
  if (docs.length === 1) return docs[0].name;
  if (docs.length > 1) return `${docs.length}개 API 문서`;
  if (node.type === 'apiDoc') {
    return apiDocMap[node.data?.apiId]?.name ?? node.data?.apiId ?? '?';
  }
  return node.data?.label ?? node.type ?? '?';
}

function docsFromNode(node) {
  if (!node) return [];
  if (node.type === 'apiDoc') {
    const doc = apiDocMap[node.data?.apiId];
    return doc ? [doc] : [];
  }
  return node.data?.output?.docs ?? node.data?.results ?? [];
}

function uniqueDocs(docs) {
  const seen = new Set();
  return docs.filter(doc => {
    if (!doc?.apiId || seen.has(doc.apiId)) return false;
    seen.add(doc.apiId);
    return true;
  });
}

export function MergeNode({ id, data, selected }) {
  const cfg = CATEGORY.logic;
  const edges = useEdges();
  const nodes = useNodes();

  const inEdges = edges.filter(e => e.target === id);
  const edgeA = inEdges.find(e => e.targetHandle === 'a') ?? inEdges[0] ?? null;
  const edgeB = inEdges.find(e => e.targetHandle === 'b') ?? inEdges[1] ?? null;

  const nodeA = edgeA ? nodes.find(n => n.id === edgeA.source) ?? null : null;
  const nodeB = edgeB ? nodes.find(n => n.id === edgeB.source) ?? null : null;

  const docsA = docsFromNode(nodeA);
  const docsB = docsFromNode(nodeB);
  const inputDocs = uniqueDocs(inEdges.flatMap(edge => docsFromNode(nodes.find(n => n.id === edge.source))));

  const nameA = resolveApiName(nodeA, docsA);
  const nameB = resolveApiName(nodeB, docsB);
  const inputFields = inputDocs.flatMap(doc => doc.fields ?? []);

  // merged unique field keys for preview
  const mergedKeys = [...new Set(inputFields.map(f => f.key))].slice(0, 8);
  const statusColor = data?.status === 'error' ? '#f87171' : '#22c55e';

  return (
    <div style={{
      background: '#111827',
      border: `1px solid ${selected ? cfg.color : '#1e2d3d'}`,
      borderTop: `2px solid ${cfg.color}`,
      borderRadius: 8,
      width: 240,
      boxShadow: selected
        ? `0 0 0 1px ${cfg.color}44, 0 8px 32px #00000099`
        : '0 2px 12px #00000055',
      transition: 'border-color 0.15s, box-shadow 0.15s',
      fontFamily: 'inherit',
      position: 'relative',
    }}>

      {/* Input handles */}
      <Handle type="target" id="a" position={Position.Left}
        style={{ background: cfg.color, borderColor: '#0c1220', top: '35%' }} />
      <Handle type="target" id="b" position={Position.Left}
        style={{ background: cfg.color, borderColor: '#0c1220', top: '65%' }} />

      {/* Output handle */}
      <Handle type="source" id="out" position={Position.Right}
        style={{ background: cfg.color, borderColor: '#0c1220', top: '50%' }} />

      {/* Header */}
      <div style={{
        padding: '7px 10px 6px',
        borderBottom: '1px solid #1e2d3d',
        display: 'flex',
        alignItems: 'center',
        gap: 7,
      }}>
        <span style={{ fontSize: 14 }}>⊕</span>
        <span style={{ color: '#f1f5f9', fontWeight: 600, fontSize: 12, flex: 1, letterSpacing: '-0.01em' }}>
          병합 (Merge)
        </span>
        <span style={{
          fontSize: 8, fontWeight: 700, letterSpacing: '0.1em',
          color: cfg.color, background: `${cfg.color}18`,
          padding: '2px 5px', borderRadius: 3, border: `1px solid ${cfg.color}33`,
        }}>
          {cfg.label}
        </span>
        {data?.status && data.status !== 'idle' && (
          <span style={{
            fontSize: 8, fontWeight: 700, letterSpacing: '0.08em',
            color: statusColor, background: `${statusColor}18`,
            padding: '2px 5px', borderRadius: 3, border: `1px solid ${statusColor}33`,
          }}>
            {data.status === 'success' ? 'OK' : 'ERR'}
          </span>
        )}
      </div>

      {/* Slot display */}
      <div style={{ padding: '8px 10px', display: 'flex', flexDirection: 'column', gap: 5 }}>
        <SlotRow label="A" name={nameA} color={cfg.color} />
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '2px 0' }}>
          <span style={{ fontSize: 10, color: '#374151' }}>+</span>
        </div>
        <SlotRow label="B" name={nameB} color={cfg.color} />
      </div>

      {/* Merged fields preview — only when both connected */}
      {mergedKeys.length > 0 && (
        <div style={{ padding: '6px 10px 8px', borderTop: '1px solid #1a2535' }}>
          <div style={{ fontSize: 8, fontWeight: 700, color: '#374151', letterSpacing: '0.1em', marginBottom: 4 }}>
            병합 컨텍스트 ({inputDocs.length}개 API · {inputFields.length}개 필드)
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
            {mergedKeys.map(key => (
              <span key={key} style={{
                fontSize: 8, fontFamily: 'monospace',
                color: cfg.color, background: `${cfg.color}12`,
                padding: '1px 5px', borderRadius: 3,
                border: `1px solid ${cfg.color}22`,
              }}>
                {key}
              </span>
            ))}
            {inputFields.length > 8 && (
              <span style={{ fontSize: 8, color: '#374151' }}>
                +{inputFields.length - 8}
              </span>
            )}
          </div>
        </div>
      )}

      {data?.error && (
        <div style={{ padding: '6px 10px 8px', borderTop: '1px solid #1a2535', fontSize: 9, color: '#f87171' }}>
          {data.error}
        </div>
      )}
    </div>
  );
}

function SlotRow({ label, name, color }) {
  const connected = name !== null;
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: 6,
      background: connected ? `${color}0c` : '#0c1220',
      border: `1px solid ${connected ? color + '33' : '#1e2d3d'}`,
      borderRadius: 4,
      padding: '4px 7px',
      minHeight: 26,
    }}>
      <span style={{
        fontSize: 8, fontWeight: 800,
        color: connected ? color : '#374151',
        background: connected ? `${color}22` : '#1a2535',
        border: `1px solid ${connected ? color + '44' : '#1e2d3d'}`,
        borderRadius: 3,
        padding: '1px 5px',
        flexShrink: 0,
        letterSpacing: '0.06em',
      }}>
        {label}
      </span>
      <span style={{
        fontSize: 10,
        color: connected ? '#cbd5e1' : '#374151',
        fontStyle: connected ? 'normal' : 'italic',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap',
        flex: 1,
      }}>
        {connected ? name : '연결 대기 중...'}
      </span>
    </div>
  );
}
