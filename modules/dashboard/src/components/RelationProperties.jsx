// 선택된 관계 엣지의 근거(evidence)를 보여주고 승인하는 우측 패널.
const TYPE_LABEL = {
  'same-agency': '같은 제공기관',
  'same-domain': '같은 분류체계',
  'param-overlap': '요청 파라미터 공유',
  'io-chain': '응답→요청 연결',
  'llm-suggested': 'LLM 제안',
};

export function RelationProperties({ edge, onApprove }) {
  const rel = edge?.data?.relation;
  if (!rel) return null;

  const approved = rel.status === 'approved';
  return (
    <div style={{
      width: 280, flexShrink: 0, background: '#0b1322', borderLeft: '1px solid #1e2d3d',
      padding: 14, overflowY: 'auto', color: '#e2e8f0', fontSize: 12,
    }}>
      <div style={{ fontWeight: 700, marginBottom: 4 }}>관계 근거</div>
      <div style={{ color: '#f59e0b', fontWeight: 700, marginBottom: 8 }}>
        {TYPE_LABEL[rel.type] ?? rel.type}
      </div>
      <div style={{ color: '#94a3b8', marginBottom: 4 }}>근거</div>
      <ul style={{ margin: '0 0 10px', paddingLeft: 16 }}>
        {rel.evidence.map(line => <li key={line} style={{ marginBottom: 3 }}>{line}</li>)}
      </ul>
      <div style={{ color: '#94a3b8', marginBottom: 10 }}>
        confidence {rel.confidence} · {rel.status === 'derived' ? '기계 도출' : rel.status}
        {rel.generatedAt ? ` · ${rel.generatedAt}` : ''}
      </div>
      {approved ? (
        <div style={{ color: '#22c55e', fontWeight: 700 }}>✓ 승인됨 — 워크플로우 엣지로 확정</div>
      ) : (
        <button onClick={() => onApprove(edge.id)} style={{
          background: '#16a34a', color: 'white', border: 'none', borderRadius: 6,
          padding: '6px 14px', fontSize: 12, fontWeight: 700, cursor: 'pointer',
        }}>이 관계 승인</button>
      )}
    </div>
  );
}
