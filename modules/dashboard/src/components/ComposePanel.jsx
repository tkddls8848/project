import { useState } from 'react';
import { compose } from '../data/composeClient.js';

const DEFAULT_QUESTION = '이 API들을 조합하면 어떤 행정 서비스 계획을 만들 수 있나?';

export function ComposePanel({ targets, onClose }) {
  const [question, setQuestion] = useState(DEFAULT_QUESTION);
  const [state, setState] = useState({ loading: false, result: null, error: '' });

  const run = async () => {
    setState({ loading: true, result: null, error: '' });
    try {
      const result = await compose(targets.map(t => t.serviceId), question.trim() || DEFAULT_QUESTION);
      setState({ loading: false, result, error: '' });
    } catch (error) {
      setState({ loading: false, result: null, error: error.message });
    }
  };

  return (
    <div style={{
      position: 'absolute', top: 0, right: 0, bottom: 0, width: 380, zIndex: 20,
      background: '#0b1322', borderLeft: '1px solid #1e2d3d', color: '#e2e8f0',
      padding: 16, overflowY: 'auto', fontSize: 12, boxShadow: '-8px 0 32px #00000088',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
        <span style={{ fontWeight: 700, fontSize: 13 }}>⚡ 조합 제안 (nara_combiner)</span>
        <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer' }}>✕</button>
      </div>

      <div style={{ color: '#94a3b8', marginBottom: 6 }}>대상 API {targets.length}건</div>
      <ul style={{ margin: '0 0 10px', paddingLeft: 16 }}>
        {targets.map(t => <li key={t.serviceId}>{t.name}</li>)}
      </ul>

      <textarea
        value={question}
        onChange={e => setQuestion(e.target.value)}
        rows={3}
        maxLength={500}
        style={{
          width: '100%', boxSizing: 'border-box', background: '#111827', color: '#e2e8f0',
          border: '1px solid #1e2d3d', borderRadius: 6, padding: 8, fontSize: 12, resize: 'vertical',
        }}
      />
      <button onClick={run} disabled={state.loading} style={{
        marginTop: 8, background: state.loading ? '#1e2d3d' : '#16a34a', color: 'white',
        border: 'none', borderRadius: 6, padding: '6px 14px', fontSize: 12, fontWeight: 700,
        cursor: state.loading ? 'wait' : 'pointer',
      }}>
        {state.loading ? 'LLM 제안 생성 중…' : '조합 제안 요청'}
      </button>

      {state.error && (
        <div style={{ marginTop: 10, color: '#f87171' }}>{state.error}</div>
      )}
      {state.result && (
        <div style={{ marginTop: 12 }}>
          {state.result.warning && (
            <div style={{ color: '#f59e0b', marginBottom: 8 }}>⚠ {state.result.warning}</div>
          )}
          {state.result.missing?.length > 0 && (
            <div style={{ color: '#f87171', marginBottom: 8 }}>
              카탈로그에 없는 ID: {state.result.missing.join(', ')}
            </div>
          )}
          <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>{state.result.suggestion}</div>
          <div style={{ marginTop: 10, color: '#475569', fontSize: 10 }}>
            {state.result.model} · {state.result.elapsed_ms}ms{state.result.truncated ? ' · 길이 제한으로 잘림' : ''}
          </div>
        </div>
      )}
    </div>
  );
}
