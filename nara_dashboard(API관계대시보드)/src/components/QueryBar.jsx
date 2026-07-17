import { useState } from 'react';

export function QueryBar({ onQuery, busy, error }) {
  const [query, setQuery] = useState('');

  const submit = () => {
    const trimmed = query.trim();
    if (trimmed.length >= 2 && !busy) onQuery(trimmed);
  };

  return (
    <div style={{
      background: '#0b1322', borderBottom: '1px solid #1e2d3d',
      padding: '8px 14px', display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0,
    }}>
      <span style={{ fontSize: 12, color: '#64748b', flexShrink: 0 }}>자연어 질의</span>
      <input
        value={query}
        onChange={e => setQuery(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter') submit(); }}
        placeholder="예: 부모님 병원 이동을 지원받으려면?"
        style={{
          flex: 1, maxWidth: 560, background: '#111827', color: '#e2e8f0',
          border: '1px solid #1e2d3d', borderRadius: 6, padding: '6px 10px', fontSize: 12,
        }}
      />
      <button onClick={submit} disabled={busy} style={{
        background: busy ? '#1e2d3d' : '#16a34a', color: 'white', border: 'none',
        borderRadius: 6, padding: '6px 14px', fontSize: 12, fontWeight: 700,
        cursor: busy ? 'wait' : 'pointer',
      }}>
        {busy ? '검색 중…' : '검색 → 노드 배치'}
      </button>
      {error && <span style={{ fontSize: 11, color: '#f87171' }}>{error}</span>}
    </div>
  );
}
