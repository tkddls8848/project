import { useCallback, useMemo, useState } from 'react';
import {
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  ReactFlow,
  addEdge,
  useEdgesState,
  useNodesState,
} from '@xyflow/react';

import { EDGE_KINDS, LABELS, buildInterpretationPrompt } from './logic/argumentGraph.js';
import {
  ARGUMENT_NODE_TYPES,
  FEED,
  applyVerdict,
  interpretationScope,
  judgeCanvas,
  makeArgumentEdge,
  toArgumentGraph,
  validateConnection,
} from './logic/argumentFlow.js';
import { argumentNodeTypes } from './nodes/argumentNodes.jsx';

const OLLAMA_URL = '/ollama/api/generate';
const MODEL = 'gemma4:e4b';

let counter = 0;
const nextId = prefix => `${prefix}-${++counter}`;

const START_NODES = [
  { id: 'p-0', type: ARGUMENT_NODE_TYPES.PREMISE, position: { x: 60, y: 80 }, data: { text: '' } },
  { id: 'c-0', type: ARGUMENT_NODE_TYPES.CLAIM, position: { x: 380, y: 80 }, data: { text: '' } },
  { id: 'i-0', type: ARGUMENT_NODE_TYPES.INTERPRETATION, position: { x: 700, y: 80 }, data: {} },
];

const BUTTON = {
  background: '#0c1220',
  border: '1px solid #1e2d3d',
  borderRadius: 5,
  color: '#cbd5e1',
  fontSize: 11,
  padding: '5px 10px',
  cursor: 'pointer',
};

function activeButton(active, color) {
  return active
    ? { ...BUTTON, color, borderColor: `${color}66`, background: `${color}18`, fontWeight: 700 }
    : BUTTON;
}

export default function ArgumentBoard() {
  const [nodes, setNodes, onNodesChange] = useNodesState(START_NODES);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [pendingKind, setPendingKind] = useState(EDGE_KINDS.SUPPORT);
  const [notice, setNotice] = useState('');
  const [interpretation, setInterpretation] = useState({ text: '', status: 'idle', error: '' });

  const verdict = useMemo(() => judgeCanvas(nodes, edges), [nodes, edges]);

  const handleTextChange = useCallback((id, text) => {
    setNodes(current => current.map(node => (node.id === id ? { ...node, data: { ...node.data, text } } : node)));
  }, [setNodes]);

  const onConnect = useCallback(connection => {
    const target = nodes.find(node => node.id === connection.target);
    // 해석 노드로 가는 연결은 논증 관계가 아니라 입력이다.
    const kind = target?.type === ARGUMENT_NODE_TYPES.INTERPRETATION ? FEED : pendingKind;
    const check = validateConnection(nodes, edges, connection, kind);
    if (!check.ok) {
      setNotice(check.reason);
      return;
    }
    setNotice('');
    setEdges(current => addEdge(makeArgumentEdge(connection, kind, nextId('edge')), current));
  }, [edges, nodes, pendingKind, setEdges]);

  const addNode = useCallback(type => {
    const id = nextId(type);
    setNodes(current => [
      ...current,
      {
        id,
        type,
        position: { x: 60 + (current.length % 4) * 300, y: 300 + Math.floor(current.length / 4) * 200 },
        data: type === ARGUMENT_NODE_TYPES.INTERPRETATION ? {} : { text: '' },
      },
    ]);
  }, [setNodes]);

  const interpretationNode = nodes.find(node => node.type === ARGUMENT_NODE_TYPES.INTERPRETATION);

  const prompt = useMemo(() => {
    if (!interpretationNode) return '';
    const scope = interpretationScope(nodes, edges, interpretationNode.id);
    const scopeIds = new Set(scope.map(node => node.id));
    const graph = toArgumentGraph(nodes, edges);
    return buildInterpretationPrompt(
      graph.nodes.filter(node => scopeIds.has(node.id)),
      graph.edges.filter(edge => scopeIds.has(edge.source) && scopeIds.has(edge.target)),
      verdict
    );
  }, [edges, interpretationNode, nodes, verdict]);

  const generate = useCallback(async () => {
    if (!prompt) return;
    setInterpretation({ text: '', status: 'running', error: '' });
    try {
      const response = await fetch(OLLAMA_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: MODEL, prompt, stream: false, options: { temperature: 0.2 } }),
      });
      if (!response.ok) throw new Error(`Ollama 응답 오류: HTTP ${response.status}`);
      const payload = await response.json();
      setInterpretation({ text: payload.response ?? '', status: 'done', error: '' });
    } catch (error) {
      setInterpretation({
        text: '',
        status: 'error',
        error: `${error.message} — Ollama가 실행 중이고 ${MODEL}이 pull 되어 있는지 확인하세요.`,
      });
    }
  }, [prompt]);

  const flowNodes = useMemo(() => {
    const labelled = applyVerdict(nodes, verdict);
    return labelled.map(node => {
      if (node.type === ARGUMENT_NODE_TYPES.INTERPRETATION) {
        return {
          ...node,
          data: {
            ...node.data,
            interpretation: interpretation.text,
            status: interpretation.status === 'running' ? 'running' : 'idle',
            error: interpretation.error,
            scopeCount: interpretationScope(nodes, edges, node.id).length,
          },
        };
      }
      return { ...node, data: { ...node.data, onTextChange: handleTextChange } };
    });
  }, [edges, handleTextChange, interpretation, nodes, verdict]);

  const violations = verdict.findings.filter(finding => finding.severity === 'violation');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap',
        padding: '8px 14px', background: '#111623', borderBottom: '1px solid #1e2535',
      }}>
        <span style={{ fontSize: 11, color: '#64748b' }}>노드 추가</span>
        <button style={BUTTON} onClick={() => addNode(ARGUMENT_NODE_TYPES.PREMISE)}>▣ 전제</button>
        <button style={BUTTON} onClick={() => addNode(ARGUMENT_NODE_TYPES.CLAIM)}>◆ 주장</button>
        <button style={BUTTON} onClick={() => addNode(ARGUMENT_NODE_TYPES.INTERPRETATION)}>◎ 해석</button>

        <span style={{ width: 1, height: 18, background: '#1e2535', margin: '0 4px' }} />

        <span style={{ fontSize: 11, color: '#64748b' }}>맺을 관계</span>
        <button
          style={activeButton(pendingKind === EDGE_KINDS.SUPPORT, '#0f766e')}
          onClick={() => setPendingKind(EDGE_KINDS.SUPPORT)}
        >
          지지
        </button>
        <button
          style={activeButton(pendingKind === EDGE_KINDS.ATTACK, '#b91c1c')}
          onClick={() => setPendingKind(EDGE_KINDS.ATTACK)}
        >
          반박
        </button>

        <span style={{ flex: 1 }} />
        {notice && <span style={{ fontSize: 11, color: '#fca5a5' }}>{notice}</span>}
      </div>

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        <div style={{ flex: 1, position: 'relative' }}>
          <ReactFlow
            nodes={flowNodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            nodeTypes={argumentNodeTypes}
            fitView
            fitViewOptions={{ padding: 0.2 }}
            minZoom={0.3}
            maxZoom={2}
            deleteKeyCode="Delete"
          >
            <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#1e2535" />
            <Controls />
            <MiniMap maskColor="#0f111788" style={{ background: '#111623' }} />
          </ReactFlow>
        </div>

        <aside style={{
          width: 340, background: '#111623', borderLeft: '1px solid #1e2535',
          padding: 14, overflow: 'auto', display: 'flex', flexDirection: 'column', gap: 14,
        }}>
          <section>
            <h2 style={{ margin: '0 0 8px', fontSize: 11, color: '#64748b', letterSpacing: '0.08em' }}>형식 판정</h2>
            <dl style={{ margin: 0, fontSize: 12, color: '#cbd5e1', display: 'grid', gap: 4 }}>
              <div><span style={{ color: '#0f766e' }}>성립</span> {verdict.extension.length}</div>
              <div><span style={{ color: '#b91c1c' }}>논파됨</span> {verdict.rejected.length}</div>
              <div><span style={{ color: '#a16207' }}>미판정</span> {verdict.undecided.length}</div>
            </dl>
          </section>

          <section>
            <h2 style={{ margin: '0 0 8px', fontSize: 11, color: '#64748b', letterSpacing: '0.08em' }}>
              위반 사항 {violations.length > 0 ? `(${violations.length})` : ''}
            </h2>
            {violations.length === 0 ? (
              <p style={{ margin: 0, fontSize: 12, color: '#475569' }}>없습니다.</p>
            ) : (
              <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'grid', gap: 6 }}>
                {violations.map((finding, index) => (
                  <li key={`${finding.code}-${index}`} style={{
                    fontSize: 11, color: '#fca5a5', background: '#7f1d1d22',
                    border: '1px solid #b91c1c44', borderRadius: 5, padding: '6px 8px', lineHeight: 1.5,
                  }}>
                    {finding.message}
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <h2 style={{ margin: 0, fontSize: 11, color: '#64748b', letterSpacing: '0.08em', flex: 1 }}>해석</h2>
              <button
                style={{ ...BUTTON, opacity: interpretation.status === 'running' ? 0.5 : 1 }}
                onClick={generate}
                disabled={interpretation.status === 'running' || !prompt}
              >
                {interpretation.status === 'running' ? '생성 중…' : '해석 생성'}
              </button>
            </div>
            <details>
              <summary style={{ fontSize: 11, color: '#64748b', cursor: 'pointer' }}>
                LLM에 보낼 프롬프트 보기
              </summary>
              <pre style={{
                margin: '8px 0 0', background: '#0c1220', border: '1px solid #1e2d3d', borderRadius: 5,
                padding: 8, fontSize: 10, color: '#94a3b8', whiteSpace: 'pre-wrap', maxHeight: 260, overflow: 'auto',
              }}>{prompt}</pre>
            </details>
          </section>
        </aside>
      </div>
    </div>
  );
}
