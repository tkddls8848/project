import { useState } from 'react';

import App from './App.jsx';
import ArgumentBoard from './ArgumentBoard.jsx';

// 논증 보드와 기존 API 워크플로를 나란히 둔다. 도메인(공공 API 조합)을 버릴지는
// 아직 정해지지 않았으므로 지우지 않고 모드로 가른다.
const MODES = [
  { id: 'argument', label: '논증' },
  { id: 'workflow', label: 'API 워크플로' },
];

const TAB = {
  background: 'transparent',
  border: '1px solid transparent',
  borderRadius: 5,
  color: '#64748b',
  fontSize: 12,
  padding: '4px 12px',
  cursor: 'pointer',
};

const ACTIVE_TAB = {
  ...TAB,
  color: '#e2e8f0',
  background: '#1e2535',
  borderColor: '#2c3a52',
  fontWeight: 600,
};

export default function Root() {
  const [mode, setMode] = useState('argument');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <nav style={{
        display: 'flex', alignItems: 'center', gap: 6,
        padding: '6px 14px', background: '#0c1017', borderBottom: '1px solid #1e2535',
      }}>
        <span style={{ fontSize: 12, fontWeight: 700, color: '#e2e8f0', marginRight: 8 }}>Nara Dashboard</span>
        {MODES.map(item => (
          <button
            key={item.id}
            style={mode === item.id ? ACTIVE_TAB : TAB}
            onClick={() => setMode(item.id)}
          >
            {item.label}
          </button>
        ))}
      </nav>

      <div style={{ flex: 1, overflow: 'hidden' }}>
        {mode === 'argument' ? <ArgumentBoard /> : <App />}
      </div>
    </div>
  );
}
