import { CATEGORY } from '../nodes/BaseNode.jsx';
import { apiDocs } from '../data/apiDocs.js';

const PALETTE = [
  {
    category: 'logic',
    nodes: [
      { type: 'mergeNode', icon: '⊕', label: '병합 (Merge)', desc: '두 API 문서를 합쳐 LLM 컨텍스트 생성' },
    ],
  },
  {
    category: 'source',
    nodes: [
      { type: 'apiSearch', icon: '🔍', label: 'API 검색', desc: '공공 API 문서 검색' },
    ],
  },
  {
    category: 'filter',
    nodes: [
      { type: 'categoryFilter', icon: '🗂️', label: '카테고리 필터', desc: '분류 기준 필터링' },
      { type: 'providerFilter', icon: '🏛️', label: '제공기관 필터', desc: '기관명 기준 필터링' },
      { type: 'scoreFilter',    icon: '📊', label: '점수 필터',     desc: '유사도 점수 기준' },
    ],
  },
  {
    category: 'analysis',
    nodes: [
      { type: 'ragChat',    icon: '🤖', label: 'RAG 채팅', desc: 'LLM 기반 분석 채팅' },
      { type: 'summaryNode', icon: '📝', label: '요약',    desc: '결과 요약 생성' },
    ],
  },
  {
    category: 'output',
    nodes: [
      { type: 'exportNode', icon: '📤', label: '내보내기',        desc: 'JSON / CSV / XLSX' },
      { type: 'saveNode',   icon: '💾', label: '워크플로우 저장', desc: '플로우 JSON 다운로드' },
      { type: 'chatOutput', icon: '💬', label: '채팅하기',        desc: 'Ollama gemma4:e4b와 컨텍스트 채팅' },
    ],
  },
];

// ── API Doc palette item (drag encodes apiId separately)
function ApiDocItem({ doc }) {
  const cfg = CATEGORY.source;

  const onDragStart = (e) => {
    e.dataTransfer.setData('application/reactflow', 'apiDoc');
    e.dataTransfer.setData('application/reactflow-apiid', doc.apiId);
    e.dataTransfer.effectAllowed = 'move';
  };

  return (
    <div
      className="palette-item"
      draggable
      onDragStart={onDragStart}
      title={doc.description}
      style={{
        background: '#0e1829',
        border: '1px solid #1e2d3d',
        borderLeft: `2px solid ${cfg.color}`,
        borderRadius: 5,
        padding: '5px 8px',
        cursor: 'grab',
        transition: 'background 0.12s',
      }}
      onMouseEnter={e => { e.currentTarget.style.background = '#131f30'; }}
      onMouseLeave={e => { e.currentTarget.style.background = '#0e1829'; }}
    >
      <div style={{ fontSize: 10, fontWeight: 600, color: '#e2e8f0', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {doc.name}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginTop: 2 }}>
        <span style={{
          fontSize: 8, color: cfg.color,
          background: `${cfg.color}12`, border: `1px solid ${cfg.color}33`,
          padding: '0 4px', borderRadius: 2, fontWeight: 700,
        }}>
          {doc.topCategory}
        </span>
        <span style={{ fontSize: 8, color: '#4b5563', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {doc.provider}
        </span>
      </div>
    </div>
  );
}

// ── Generic node palette item
function PaletteItem({ type, icon, label, desc, color }) {
  const onDragStart = (e) => {
    e.dataTransfer.setData('application/reactflow', type);
    e.dataTransfer.effectAllowed = 'move';
  };

  return (
    <div
      className="palette-item"
      draggable
      onDragStart={onDragStart}
      style={{
        background: '#0e1829',
        border: '1px solid #1e2d3d',
        borderLeft: `2px solid ${color}`,
        borderRadius: 6,
        padding: '7px 9px',
        cursor: 'grab',
        transition: 'background 0.12s, border-color 0.12s',
      }}
      onMouseEnter={e => {
        e.currentTarget.style.background = '#131f30';
        e.currentTarget.style.borderColor = `${color}88`;
        e.currentTarget.style.borderLeftColor = color;
      }}
      onMouseLeave={e => {
        e.currentTarget.style.background = '#0e1829';
        e.currentTarget.style.borderColor = '#1e2d3d';
        e.currentTarget.style.borderLeftColor = color;
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ fontSize: 15 }}>{icon}</span>
        <div>
          <div style={{ fontSize: 11, fontWeight: 600, color: '#e2e8f0' }}>{label}</div>
          <div style={{ fontSize: 9, color: '#4b5563', marginTop: 1 }}>{desc}</div>
        </div>
      </div>
    </div>
  );
}

export function NodePalette() {
  return (
    <div
      style={{
        width: 210,
        background: '#0a1120',
        borderRight: '1px solid #1e2d3d',
        display: 'flex',
        flexDirection: 'column',
        overflowY: 'auto',
        flexShrink: 0,
      }}
    >
      {/* ── API 문서 섹션 */}
      <div style={{ borderBottom: '1px solid #1e2d3d' }}>
        <div style={{ padding: '10px 12px 8px' }}>
          <div style={{ fontSize: 9, fontWeight: 700, color: CATEGORY.source.color, letterSpacing: '0.12em' }}>
            API 문서
          </div>
          <div style={{ fontSize: 9, color: '#374151', marginTop: 2 }}>
            {apiDocs.length}개 · 드래그하여 캔버스에 추가
          </div>
        </div>
        <div style={{
          maxHeight: 260,
          overflowY: 'auto',
          padding: '0 10px 10px',
          display: 'flex',
          flexDirection: 'column',
          gap: 3,
        }}>
          {apiDocs.map(doc => (
            <ApiDocItem key={doc.apiId} doc={doc} />
          ))}
        </div>
      </div>

      {/* ── 노드 카탈로그 섹션 */}
      <div style={{ padding: '10px 12px 8px', borderBottom: '1px solid #1e2d3d' }}>
        <div style={{ fontSize: 9, fontWeight: 700, color: '#4b5563', letterSpacing: '0.12em' }}>
          NODE CATALOG
        </div>
      </div>

      <div style={{ padding: '10px 10px', display: 'flex', flexDirection: 'column', gap: 12 }}>
        {PALETTE.map(({ category, nodes }) => {
          const cfg = CATEGORY[category];
          return (
            <div key={category}>
              <div style={{
                fontSize: 9, fontWeight: 700, letterSpacing: '0.12em',
                color: cfg.color, marginBottom: 5, paddingLeft: 1,
                display: 'flex', alignItems: 'center', gap: 5,
              }}>
                <span style={{ opacity: 0.6 }}>{cfg.icon}</span>
                {cfg.label}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {nodes.map((node) => (
                  <PaletteItem key={node.type} {...node} color={cfg.color} />
                ))}
              </div>
            </div>
          );
        })}
      </div>

      <div style={{
        marginTop: 'auto',
        padding: '10px 12px',
        borderTop: '1px solid #1e2d3d',
        fontSize: 9, color: '#374151', lineHeight: 1.8,
      }}>
        <div>• 핸들 드래그 → 연결</div>
        <div>• 클릭 → 속성 표시</div>
        <div>• Delete → 삭제</div>
      </div>
    </div>
  );
}
