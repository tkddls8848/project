import { Handle, Position } from '@xyflow/react';

export const CATEGORY = {
  source:   { color: '#22c55e', bg: '#052e16', border: '#16a34a', label: 'SOURCE',   icon: '◈' },
  filter:   { color: '#818cf8', bg: '#1e1b4b', border: '#6366f1', label: 'FILTER',   icon: '◈' },
  analysis: { color: '#f59e0b', bg: '#1c1003', border: '#d97706', label: 'ANALYSIS', icon: '◈' },
  output:   { color: '#38bdf8', bg: '#0c1a2e', border: '#0ea5e9', label: 'OUTPUT',   icon: '◈' },
  logic:    { color: '#06b6d4', bg: '#0c2233', border: '#0891b2', label: 'LOGIC',    icon: '◈' },
};

export function BaseNode({ category, icon, title, children, hasInput = true, hasOutput = true, selected }) {
  const cfg = CATEGORY[category];
  return (
    <div
      style={{
        background: '#111827',
        border: `1px solid ${selected ? cfg.color : '#1e2d3d'}`,
        borderTop: `2px solid ${cfg.color}`,
        borderRadius: 8,
        width: 220,
        boxShadow: selected
          ? `0 0 0 1px ${cfg.color}44, 0 8px 32px #00000099`
          : '0 2px 12px #00000055',
        transition: 'border-color 0.15s, box-shadow 0.15s',
        fontFamily: 'inherit',
      }}
    >
      {hasInput && (
        <Handle
          type="target"
          position={Position.Left}
          style={{ background: cfg.color, borderColor: '#0c1220', top: '50%' }}
        />
      )}

      {/* Header */}
      <div
        style={{
          padding: '7px 10px 6px',
          display: 'flex',
          alignItems: 'center',
          gap: 7,
          borderBottom: `1px solid #1e2d3d`,
        }}
      >
        <span style={{ fontSize: 14 }}>{icon}</span>
        <span style={{ color: '#f1f5f9', fontWeight: 600, fontSize: 12, flex: 1, letterSpacing: '-0.01em' }}>
          {title}
        </span>
        <span
          style={{
            fontSize: 8,
            fontWeight: 700,
            letterSpacing: '0.1em',
            color: cfg.color,
            background: `${cfg.color}18`,
            padding: '2px 5px',
            borderRadius: 3,
            border: `1px solid ${cfg.color}33`,
          }}
        >
          {cfg.label}
        </span>
      </div>

      {/* Body */}
      <div style={{ padding: '8px 10px', display: 'flex', flexDirection: 'column', gap: 6 }}>
        {children}
      </div>

      {hasOutput && (
        <Handle
          type="source"
          position={Position.Right}
          style={{ background: cfg.color, borderColor: '#0c1220', top: '50%' }}
        />
      )}
    </div>
  );
}

export function Field({ label, value }) {
  return (
    <div>
      <div style={{ fontSize: 9, color: '#4b5563', marginBottom: 2, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
        {label}
      </div>
      <div
        style={{
          background: '#0c1220',
          border: '1px solid #1e2d3d',
          borderRadius: 4,
          padding: '4px 8px',
          color: value ? '#cbd5e1' : '#374151',
          fontSize: 11,
          fontStyle: value ? 'normal' : 'italic',
        }}
      >
        {value || '미설정'}
      </div>
    </div>
  );
}

export function Badge({ label, color = '#6b7280' }) {
  return (
    <span
      style={{
        display: 'inline-block',
        fontSize: 9,
        fontWeight: 700,
        letterSpacing: '0.05em',
        color,
        background: `${color}18`,
        border: `1px solid ${color}33`,
        padding: '2px 7px',
        borderRadius: 3,
      }}
    >
      {label}
    </span>
  );
}
