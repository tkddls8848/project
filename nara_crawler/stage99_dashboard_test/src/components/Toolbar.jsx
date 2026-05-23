export function Toolbar({ nodeCount, edgeCount, onClear, onReset, onRun }) {
  return (
    <div
      style={{
        height: 44,
        background: '#080e1a',
        borderBottom: '1px solid #1e2d3d',
        display: 'flex',
        alignItems: 'center',
        padding: '0 14px',
        gap: 10,
        flexShrink: 0,
      }}
    >
      {/* 로고 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <div
          style={{
            width: 24,
            height: 24,
            borderRadius: 5,
            background: 'linear-gradient(135deg, #16a34a, #0ea5e9)',
            display: 'grid',
            placeItems: 'center',
            fontSize: 12,
            fontWeight: 800,
            color: 'white',
          }}
        >
          N
        </div>
        <span style={{ fontWeight: 700, fontSize: 13, color: '#f1f5f9', letterSpacing: '-0.02em' }}>
          Nara Dashboard
        </span>
        <span
          style={{
            fontSize: 8,
            fontWeight: 700,
            color: '#22c55e',
            background: '#052e16',
            border: '1px solid #16a34a44',
            padding: '1px 6px',
            borderRadius: 3,
            letterSpacing: '0.08em',
          }}
        >
          BETA
        </span>
      </div>

      <div style={{ width: 1, height: 20, background: '#1e2d3d', margin: '0 4px' }} />

      {/* 탭 */}
      <NavTab label="워크플로우" active />
      <NavTab label="템플릿" />
      <NavTab label="실행 이력" />

      <div style={{ flex: 1 }} />

      {/* 통계 */}
      <StatChip label="노드" value={nodeCount} color="#22c55e" />
      <StatChip label="연결" value={edgeCount} color="#818cf8" />

      <div style={{ width: 1, height: 20, background: '#1e2d3d', margin: '0 2px' }} />

      {/* 액션 */}
      <GhostBtn onClick={onReset} color="#818cf8">↺ 초기화</GhostBtn>
      <GhostBtn onClick={onClear} color="#f87171">✕ 삭제</GhostBtn>

      <div style={{ width: 1, height: 20, background: '#1e2d3d', margin: '0 2px' }} />

      <PrimaryBtn onClick={onRun}>▶ 실행</PrimaryBtn>
    </div>
  );
}

function NavTab({ label, active }) {
  return (
    <button
      style={{
        background: 'transparent',
        border: 'none',
        borderBottom: active ? '2px solid #22c55e' : '2px solid transparent',
        color: active ? '#22c55e' : '#4b5563',
        fontSize: 12,
        fontWeight: active ? 600 : 400,
        padding: '4px 8px',
        cursor: 'pointer',
        transition: 'color 0.12s',
        marginBottom: '-1px',
      }}
      onMouseEnter={e => { if (!active) e.currentTarget.style.color = '#9ca3af'; }}
      onMouseLeave={e => { if (!active) e.currentTarget.style.color = '#4b5563'; }}
    >
      {label}
    </button>
  );
}

function StatChip({ label, value, color }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11 }}>
      <span style={{ color: '#4b5563' }}>{label}</span>
      <span
        style={{
          background: `${color}18`,
          color,
          border: `1px solid ${color}33`,
          borderRadius: 4,
          padding: '1px 7px',
          fontWeight: 700,
          fontSize: 11,
          minWidth: 24,
          textAlign: 'center',
        }}
      >
        {value}
      </span>
    </div>
  );
}

function GhostBtn({ onClick, color, children }) {
  return (
    <button
      onClick={onClick}
      style={{
        background: 'transparent',
        border: `1px solid ${color}44`,
        borderRadius: 5,
        color,
        fontSize: 11,
        fontWeight: 600,
        padding: '4px 10px',
        cursor: 'pointer',
        transition: 'background 0.12s, border-color 0.12s',
      }}
      onMouseEnter={e => {
        e.currentTarget.style.background = `${color}18`;
        e.currentTarget.style.borderColor = `${color}88`;
      }}
      onMouseLeave={e => {
        e.currentTarget.style.background = 'transparent';
        e.currentTarget.style.borderColor = `${color}44`;
      }}
    >
      {children}
    </button>
  );
}

function PrimaryBtn({ children, onClick }) {
  return (
    <button
      onClick={onClick}
      style={{
        background: '#16a34a',
        border: 'none',
        borderRadius: 5,
        color: 'white',
        fontSize: 11,
        fontWeight: 700,
        padding: '5px 14px',
        cursor: 'pointer',
        letterSpacing: '0.02em',
        transition: 'background 0.12s',
      }}
      onMouseEnter={e => e.currentTarget.style.background = '#15803d'}
      onMouseLeave={e => e.currentTarget.style.background = '#16a34a'}
    >
      {children}
    </button>
  );
}
