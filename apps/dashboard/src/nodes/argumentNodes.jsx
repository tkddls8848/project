import { Handle, Position } from '@xyflow/react';

import { FINDING, LABELS } from '../logic/argumentGraph.js';
import { ARGUMENT_NODE_TYPES, LABEL_STYLES } from '../logic/argumentFlow.js';

const FINDING_TEXT = {
  [FINDING.SUPPORT_CYCLE]: '순환논증',
  [FINDING.UNSUPPORTED_CLAIM]: '근거 없음',
  [FINDING.UNRESOLVED_CONFLICT]: '미해소 충돌',
  [FINDING.DANGLING_EDGE]: '끊긴 관계',
};

const KIND_META = {
  [ARGUMENT_NODE_TYPES.PREMISE]: { title: '전제', icon: '▣', hint: '지지 없이 성립한다고 두는 것' },
  [ARGUMENT_NODE_TYPES.CLAIM]: { title: '주장', icon: '◆', hint: '지지가 있어야 하는 것' },
};

function Shell({ accent, children, selected }) {
  return (
    <div
      style={{
        background: '#111827',
        border: `1px solid ${selected ? accent : '#1e2d3d'}`,
        borderLeft: `3px solid ${accent}`,
        borderRadius: 8,
        width: 240,
        boxShadow: selected ? `0 0 0 1px ${accent}44, 0 8px 32px #00000099` : '0 2px 12px #00000055',
        transition: 'border-color 0.15s, box-shadow 0.15s',
      }}
    >
      {children}
    </div>
  );
}

function VerdictBadge({ label }) {
  const style = LABEL_STYLES[label] ?? LABEL_STYLES[LABELS.UNDECIDED];
  return (
    <span
      style={{
        fontSize: 9,
        fontWeight: 700,
        letterSpacing: '0.05em',
        color: style.border,
        background: `${style.border}18`,
        border: `1px solid ${style.border}33`,
        padding: '2px 7px',
        borderRadius: 3,
        whiteSpace: 'nowrap',
      }}
    >
      {style.badge}
    </span>
  );
}

function FindingList({ findings }) {
  if (!findings?.length) return null;
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
      {findings.map(code => (
        <span
          key={code}
          style={{
            fontSize: 9,
            color: '#fca5a5',
            background: '#7f1d1d33',
            border: '1px solid #b91c1c55',
            padding: '1px 5px',
            borderRadius: 3,
          }}
        >
          {FINDING_TEXT[code] ?? code}
        </span>
      ))}
    </div>
  );
}

/** 전제와 주장은 텍스트를 담고 판정을 표시한다는 점에서 같다. 차이는 근거 요구뿐이다. */
function ArgumentNode({ id, type, data, selected }) {
  const meta = KIND_META[type];
  const label = data?.label ?? LABELS.UNDECIDED;
  const accent = (LABEL_STYLES[label] ?? LABEL_STYLES[LABELS.UNDECIDED]).border;

  return (
    <Shell accent={accent} selected={selected}>
      <Handle type="target" position={Position.Left} style={{ background: accent, borderColor: '#0c1220' }} />

      <div
        style={{
          padding: '7px 10px 6px',
          display: 'flex',
          alignItems: 'center',
          gap: 7,
          borderBottom: '1px solid #1e2d3d',
        }}
      >
        <span style={{ fontSize: 13 }}>{meta.icon}</span>
        <span style={{ color: '#f1f5f9', fontWeight: 600, fontSize: 12, flex: 1 }}>{meta.title}</span>
        <VerdictBadge label={label} />
      </div>

      <div style={{ padding: '8px 10px', display: 'flex', flexDirection: 'column', gap: 6 }}>
        <textarea
          className="nodrag"
          value={data?.text ?? ''}
          onChange={event => data?.onTextChange?.(id, event.target.value)}
          placeholder={meta.hint}
          rows={3}
          style={{
            width: '100%',
            resize: 'vertical',
            background: '#0c1220',
            border: '1px solid #1e2d3d',
            borderRadius: 4,
            padding: '6px 8px',
            color: '#e2e8f0',
            fontSize: 11,
            lineHeight: 1.5,
            fontFamily: 'inherit',
          }}
        />
        <FindingList findings={data?.findings} />
      </div>

      <Handle type="source" position={Position.Right} style={{ background: accent, borderColor: '#0c1220' }} />
    </Shell>
  );
}

export function PremiseNode(props) {
  return <ArgumentNode {...props} type={ARGUMENT_NODE_TYPES.PREMISE} />;
}

export function ClaimNode(props) {
  return <ArgumentNode {...props} type={ARGUMENT_NODE_TYPES.CLAIM} />;
}

/** 해석 노드는 판정 대상이 아니다. 판정을 받아 글로 옮기는 산출물이다. */
export function InterpretationNode({ data, selected }) {
  const accent = '#38bdf8';
  const text = data?.interpretation ?? '';
  const busy = data?.status === 'running';

  return (
    <Shell accent={accent} selected={selected}>
      <Handle type="target" position={Position.Left} style={{ background: accent, borderColor: '#0c1220' }} />

      <div
        style={{
          padding: '7px 10px 6px',
          display: 'flex',
          alignItems: 'center',
          gap: 7,
          borderBottom: '1px solid #1e2d3d',
        }}
      >
        <span style={{ fontSize: 13 }}>◎</span>
        <span style={{ color: '#f1f5f9', fontWeight: 600, fontSize: 12, flex: 1 }}>해석</span>
        <span style={{ fontSize: 9, color: '#64748b' }}>{busy ? '생성 중' : `논증 ${data?.scopeCount ?? 0}`}</span>
      </div>

      <div style={{ padding: '8px 10px', display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div
          style={{
            background: '#0c1220',
            border: '1px solid #1e2d3d',
            borderRadius: 4,
            padding: '6px 8px',
            color: text ? '#cbd5e1' : '#374151',
            fontSize: 11,
            lineHeight: 1.6,
            fontStyle: text ? 'normal' : 'italic',
            maxHeight: 180,
            overflow: 'auto',
            whiteSpace: 'pre-wrap',
          }}
        >
          {text || '판정을 근거로 해석을 생성합니다.'}
        </div>
        {data?.error ? (
          <span style={{ fontSize: 10, color: '#fca5a5' }}>{data.error}</span>
        ) : null}
      </div>
    </Shell>
  );
}

export const argumentNodeTypes = {
  [ARGUMENT_NODE_TYPES.PREMISE]: PremiseNode,
  [ARGUMENT_NODE_TYPES.CLAIM]: ClaimNode,
  [ARGUMENT_NODE_TYPES.INTERPRETATION]: InterpretationNode,
};
