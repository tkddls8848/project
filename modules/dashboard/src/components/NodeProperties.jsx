import { CATEGORY } from '../nodes/BaseNode.jsx';
import { apiDocMap, apiDocs } from '../data/apiDocs.js';
import { NODE_PROPERTY_META } from '../data/workflowNodeDefinitions.js';

function Section({ title, children }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <div
        style={{
          fontSize: 9,
          fontWeight: 700,
          letterSpacing: '0.12em',
          color: '#374151',
          marginBottom: 8,
          paddingBottom: 5,
          borderBottom: '1px solid #1e2d3d',
        }}
      >
        {title}
      </div>
      {children}
    </div>
  );
}

function PropRow({ label, value, color }) {
  const empty = value === undefined || value === null || value === '';
  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ fontSize: 9, color: '#4b5563', fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 3 }}>
        {label}
      </div>
      <div
        style={{
          background: '#0c1220',
          border: '1px solid #1e2d3d',
          borderRadius: 4,
          padding: '5px 8px',
          fontSize: 11,
          color: empty ? '#374151' : (color || '#cbd5e1'),
          fontStyle: empty ? 'italic' : 'normal',
          wordBreak: 'break-word',
          lineHeight: 1.5,
        }}
      >
        {empty ? '미설정' : String(value)}
      </div>
    </div>
  );
}

function parseValue(field, value, checked) {
  if (field.type === 'checkbox') return checked;
  if (field.type === 'number') {
    if (value === '') return '';
    const numberValue = Number(value);
    return Number.isFinite(numberValue) ? numberValue : value;
  }
  return value;
}

function EditableField({ field, value, onChange }) {
  const { key, label, type = 'text', options = [], rows = 3, placeholder = '' } = field;
  const id = `field-${key}`;

  return (
    <label htmlFor={id} style={{ display: 'block', marginBottom: 9 }}>
      <div style={fieldLabelStyle}>{label}</div>
      {type === 'checkbox' ? (
        <div style={checkboxWrapStyle}>
          <input
            id={id}
            type="checkbox"
            checked={Boolean(value)}
            onChange={e => onChange(parseValue(field, e.target.value, e.target.checked))}
            style={checkboxStyle}
          />
          <span>{value ? '켜짐' : '꺼짐'}</span>
        </div>
      ) : type === 'select' ? (
        <select
          id={id}
          value={value ?? ''}
          onChange={e => onChange(parseValue(field, e.target.value, e.target.checked))}
          style={inputStyle}
        >
          <option value="">선택 안 함</option>
          {options.map(option => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      ) : type === 'textarea' ? (
        <textarea
          id={id}
          value={value ?? ''}
          rows={rows}
          placeholder={placeholder}
          onChange={e => onChange(parseValue(field, e.target.value, e.target.checked))}
          style={{ ...inputStyle, minHeight: rows * 22, resize: 'vertical', lineHeight: 1.45 }}
        />
      ) : (
        <input
          id={id}
          type={type}
          min={field.min}
          max={field.max}
          step={field.step}
          value={value ?? ''}
          placeholder={placeholder}
          onChange={e => onChange(parseValue(field, e.target.value, e.target.checked))}
          style={inputStyle}
        />
      )}
    </label>
  );
}

function EmptyState() {
  return (
    <div
      style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 10,
        color: '#1e2d3d',
        padding: 24,
        textAlign: 'center',
      }}
    >
      <div style={{ fontSize: 28, opacity: 0.4 }}>◈</div>
      <div style={{ fontSize: 11, color: '#374151', lineHeight: 1.7 }}>
        노드를 클릭하면<br />속성이 표시됩니다
      </div>
    </div>
  );
}

export function NodeProperties({ node, edges, onUpdateData }) {
  if (!node) {
    return (
      <div
        style={{
          width: 240,
          background: '#0a1120',
          borderLeft: '1px solid #1e2d3d',
          display: 'flex',
          flexDirection: 'column',
          flexShrink: 0,
        }}
      >
        <PanelHeader />
        <EmptyState />
      </div>
    );
  }

  const baseMeta = NODE_PROPERTY_META[node.type] ?? { label: node.type, category: 'source', fields: [] };
  const meta = node.type === 'apiDoc'
    ? {
        ...baseMeta,
        fields: baseMeta.fields.map(field => ({
          ...field,
          options: apiDocs.map(doc => ({
            value: doc.apiId,
            label: `${doc.name} (${doc.apiId})`,
          })),
        })),
      }
    : baseMeta;
  const cfg = CATEGORY[meta.category];
  const inEdges = edges.filter(e => e.target === node.id).length;
  const outEdges = edges.filter(e => e.source === node.id).length;

  return (
    <div
      style={{
        width: 240,
        background: '#0a1120',
        borderLeft: '1px solid #1e2d3d',
        display: 'flex',
        flexDirection: 'column',
        flexShrink: 0,
        overflowY: 'auto',
      }}
    >
      <PanelHeader />

      {/* Node identity */}
      <div style={{ padding: '12px 14px', borderBottom: '1px solid #1e2d3d' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
          <div
            style={{
              width: 28,
              height: 28,
              borderRadius: 6,
              background: `${cfg.color}18`,
              border: `1px solid ${cfg.color}44`,
              display: 'grid',
              placeItems: 'center',
              fontSize: 14,
            }}
          >
            {cfg.icon}
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: '#f1f5f9', letterSpacing: '-0.01em', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {meta.label}
            </div>
            <div style={{ fontSize: 9, color: cfg.color, fontWeight: 700, letterSpacing: '0.08em', marginTop: 1 }}>
              {cfg.label}
            </div>
          </div>
        </div>

        <div
          style={{
            fontSize: 9,
            color: '#374151',
            background: '#080e1a',
            border: '1px solid #1e2d3d',
            borderRadius: 4,
            padding: '3px 8px',
            fontFamily: 'monospace',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          id: {node.id}
        </div>
      </div>

      {/* Properties */}
      <div style={{ padding: '12px 14px', flex: 1 }}>
        <Section title="SETTINGS">
          {meta.fields.length > 0 ? (
            meta.fields.map(field => (
              <EditableField
                key={field.key}
                field={field}
                value={node.data?.[field.key]}
                onChange={value => onUpdateData?.(node.id, { [field.key]: value })}
              />
            ))
          ) : (
            <div style={emptySettingsStyle}>
              이 노드는 연결된 입력을 그대로 병합하므로 별도 설정값이 없습니다.
            </div>
          )}
        </Section>

        {node.type === 'apiDoc' && <ApiDocProperties apiId={node.data?.apiId} doc={node.data?.doc} />}

        <ExecutionProperties data={node.data} />

        <Section title="CONNECTIONS">
          <div style={{ display: 'flex', gap: 8 }}>
            <ConnChip label="입력" count={inEdges} color="#818cf8" />
            <ConnChip label="출력" count={outEdges} color="#22c55e" />
          </div>
        </Section>

        <Section title="POSITION">
          <div style={{ display: 'flex', gap: 6 }}>
            <PropRow label="X" value={Math.round(node.position?.x ?? 0)} />
            <PropRow label="Y" value={Math.round(node.position?.y ?? 0)} />
          </div>
        </Section>
      </div>
    </div>
  );
}

function ExecutionProperties({ data }) {
  const results = data?.results ?? data?.output?.docs ?? [];
  const fieldKeys = data?.output?.fieldKeys ?? [];
  const prompt = data?.analysisPrompt ?? data?.output?.prompt ?? '';

  if (!data?.status && results.length === 0 && !prompt) return null;

  return (
    <Section title="EXECUTION">
      <PropRow label="상태" value={data?.status || 'idle'} color={data?.status === 'error' ? '#f87171' : '#22c55e'} />
      {data?.error && <PropRow label="오류" value={data.error} color="#f87171" />}
      {results.length > 0 && (
        <>
          <PropRow label="출력 API" value={`${results.length}개`} />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginBottom: 8 }}>
            {results.slice(0, 5).map(doc => (
              <div key={doc.apiId} style={{
                background: '#0c1220',
                border: '1px solid #1e2d3d',
                borderRadius: 4,
                padding: '5px 7px',
              }}>
                <div style={{ fontSize: 10, color: '#cbd5e1', fontWeight: 600, lineHeight: 1.35 }}>
                  {doc.name}
                </div>
                <div style={{ fontSize: 8, color: '#4b5563', marginTop: 2 }}>
                  {doc.provider} · {doc.topCategory}
                </div>
              </div>
            ))}
          </div>
        </>
      )}
      {fieldKeys.length > 0 && (
        <PropRow label="병합 필드" value={`${fieldKeys.length}개: ${fieldKeys.slice(0, 12).join(', ')}`} />
      )}
      {prompt && (
        <PropRow label="LLM 프롬프트" value={prompt.length > 700 ? `${prompt.slice(0, 700)}...` : prompt} />
      )}
    </Section>
  );
}

function PanelHeader() {
  return (
    <div
      style={{
        padding: '12px 14px 10px',
        borderBottom: '1px solid #1e2d3d',
        flexShrink: 0,
      }}
    >
      <div style={{ fontSize: 9, fontWeight: 700, color: '#4b5563', letterSpacing: '0.12em' }}>
        PROPERTIES
      </div>
      <div style={{ fontSize: 9, color: '#374151', marginTop: 3 }}>
        선택한 노드의 속성
      </div>
    </div>
  );
}

function ApiDocProperties({ apiId, doc: embeddedDoc }) {
  const doc = embeddedDoc ?? apiDocMap[apiId];
  if (!doc) return <PropRow label="API ID" value={apiId} />;

  const cfg = CATEGORY.source;
  return (
    <>
      <Section title="API 정보">
        <PropRow label="API 명" value={doc.name} />
        <PropRow label="제공기관" value={doc.provider} />
        <PropRow label="분류" value={doc.category} />
        <PropRow label="키워드" value={doc.keywords.join(', ')} />
      </Section>
      <Section title="제공 데이터 필드">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          {doc.fields.slice(0, 10).map(f => (
            <div key={f.key} style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
              <span style={{
                fontSize: 9, fontFamily: 'monospace',
                color: cfg.color, background: `${cfg.color}12`,
                padding: '1px 5px', borderRadius: 3, flexShrink: 0,
              }}>
                {f.key}
              </span>
              <span style={{ fontSize: 9, color: '#4b5563' }}>{f.desc}</span>
            </div>
          ))}
          {doc.fields.length > 10 && (
            <div style={{ fontSize: 9, color: '#374151' }}>+{doc.fields.length - 10}개 더</div>
          )}
          {doc.fields.length === 0 && (
            <div style={{ fontSize: 9, color: '#374151', fontStyle: 'italic' }}>필드 정보 없음</div>
          )}
        </div>
      </Section>
      <Section title="엔드포인트">
        {doc.endpoints.slice(0, 3).map((ep, i) => (
          <div key={i} style={{ marginBottom: 5 }}>
            <div style={{ display: 'flex', gap: 5, alignItems: 'center', marginBottom: 2 }}>
              <span style={{
                fontSize: 8, fontWeight: 700,
                color: '#38bdf8', background: '#38bdf818',
                border: '1px solid #38bdf833', borderRadius: 3, padding: '1px 4px',
              }}>
                {ep.method}
              </span>
              <span style={{ fontSize: 9, fontFamily: 'monospace', color: '#94a3b8' }}>{ep.path}</span>
            </div>
            <div style={{ fontSize: 9, color: '#4b5563' }}>{ep.description}</div>
          </div>
        ))}
      </Section>
    </>
  );
}

function ConnChip({ label, count, color }) {
  return (
    <div style={{ flex: 1, textAlign: 'center' }}>
      <div
        style={{
          background: `${color}18`,
          border: `1px solid ${color}33`,
          borderRadius: 5,
          padding: '6px 4px 4px',
        }}
      >
        <div style={{ fontSize: 16, fontWeight: 700, color, lineHeight: 1 }}>{count}</div>
        <div style={{ fontSize: 8, color: '#4b5563', marginTop: 3, fontWeight: 600, letterSpacing: '0.06em' }}>{label}</div>
      </div>
    </div>
  );
}

const fieldLabelStyle = {
  fontSize: 9,
  color: '#4b5563',
  fontWeight: 700,
  letterSpacing: '0.06em',
  textTransform: 'uppercase',
  marginBottom: 4,
};

const inputStyle = {
  width: '100%',
  boxSizing: 'border-box',
  background: '#0c1220',
  border: '1px solid #1e2d3d',
  borderRadius: 4,
  padding: '6px 8px',
  fontSize: 11,
  color: '#cbd5e1',
  outline: 'none',
};

const checkboxWrapStyle = {
  display: 'flex',
  alignItems: 'center',
  gap: 8,
  background: '#0c1220',
  border: '1px solid #1e2d3d',
  borderRadius: 4,
  padding: '6px 8px',
  fontSize: 11,
  color: '#cbd5e1',
};

const checkboxStyle = {
  width: 14,
  height: 14,
  accentColor: '#22c55e',
};

const emptySettingsStyle = {
  background: '#0c1220',
  border: '1px solid #1e2d3d',
  borderRadius: 4,
  padding: '8px',
  fontSize: 10,
  color: '#64748b',
  lineHeight: 1.5,
};
