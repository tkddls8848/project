import { Handle, Position } from '@xyflow/react';
import { CATEGORY } from './BaseNode.jsx';
import { apiDocMap } from '../data/apiDocs.js';

const DOMAIN_COLOR = {
  '일반공공행정': '#818cf8',
  '보건': '#f87171',
  '복지': '#fb923c',
  '교통': '#38bdf8',
  '환경': '#4ade80',
  '농림': '#a3e635',
  '문화': '#c084fc',
  '산업': '#fbbf24',
  '교육': '#34d399',
  '과학': '#67e8f9',
};

function domainColor(cat) {
  for (const [key, color] of Object.entries(DOMAIN_COLOR)) {
    if (cat.includes(key)) return color;
  }
  return '#6b7280';
}

export function ApiDocNode({ data, selected }) {
  const cfg = CATEGORY.source;
  const doc = apiDocMap[data.apiId];

  if (!doc) {
    return (
      <div style={wrapStyle(cfg, selected)}>
        <Handle type="source" id="out" position={Position.Right}
          style={{ background: cfg.color, borderColor: '#0c1220' }} />
        <div style={{ padding: '10px', color: '#4b5563', fontSize: 11 }}>
          API 문서를 찾을 수 없음<br />
          <span style={{ fontSize: 9, fontFamily: 'monospace' }}>{data.apiId}</span>
        </div>
      </div>
    );
  }

  const dColor = domainColor(doc.topCategory);
  const keywords = doc.keywords.slice(0, 3);
  const fields = doc.fields.slice(0, 5);

  return (
    <div style={wrapStyle(cfg, selected)}>
      <Handle type="source" id="out" position={Position.Right}
        style={{ background: cfg.color, borderColor: '#0c1220', top: '50%' }} />

      {/* Header */}
      <div style={{
        padding: '7px 10px 6px',
        borderBottom: '1px solid #1e2d3d',
        display: 'flex',
        alignItems: 'flex-start',
        gap: 7,
      }}>
        <span style={{ fontSize: 14, flexShrink: 0 }}>📄</span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{
            color: '#f1f5f9',
            fontWeight: 700,
            fontSize: 11,
            lineHeight: 1.35,
            letterSpacing: '-0.01em',
            wordBreak: 'break-word',
          }}>
            {doc.name}
          </div>
          <div style={{ fontSize: 9, color: '#4b5563', marginTop: 2 }}>{doc.provider}</div>
        </div>
        <span style={badgeStyle(cfg.color)}>{cfg.label}</span>
      </div>

      {/* Domain + Keywords */}
      <div style={{ padding: '6px 10px', borderBottom: '1px solid #1a2535', display: 'flex', flexDirection: 'column', gap: 5 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 5, flexWrap: 'wrap' }}>
          <span style={chipStyle(dColor)}>{doc.topCategory}</span>
          {keywords.map(k => (
            <span key={k} style={chipStyle('#374151', '#6b728018', '#6b728033')}>{k}</span>
          ))}
        </div>
      </div>

      {/* Output fields */}
      {fields.length > 0 && (
        <div style={{ padding: '6px 10px 8px' }}>
          <div style={{ fontSize: 8, fontWeight: 700, color: '#374151', letterSpacing: '0.1em', marginBottom: 4 }}>
            제공 데이터 필드
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {fields.map(f => (
              <div key={f.key} style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
                <span style={{
                  fontSize: 9, fontFamily: 'monospace',
                  color: cfg.color, background: `${cfg.color}12`,
                  padding: '1px 5px', borderRadius: 3, flexShrink: 0,
                }}>
                  {f.key}
                </span>
                <span style={{ fontSize: 9, color: '#4b5563', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {f.desc}
                </span>
              </div>
            ))}
          </div>
          {doc.fields.length > 5 && (
            <div style={{ fontSize: 9, color: '#374151', marginTop: 4 }}>
              +{doc.fields.length - 5}개 더
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function wrapStyle(cfg, selected) {
  return {
    background: '#111827',
    border: `1px solid ${selected ? cfg.color : '#1e2d3d'}`,
    borderTop: `2px solid ${cfg.color}`,
    borderRadius: 8,
    width: 240,
    boxShadow: selected
      ? `0 0 0 1px ${cfg.color}44, 0 8px 32px #00000099`
      : '0 2px 12px #00000055',
    transition: 'border-color 0.15s, box-shadow 0.15s',
    fontFamily: 'inherit',
  };
}

function badgeStyle(color) {
  return {
    fontSize: 8,
    fontWeight: 700,
    letterSpacing: '0.1em',
    color,
    background: `${color}18`,
    padding: '2px 5px',
    borderRadius: 3,
    border: `1px solid ${color}33`,
    flexShrink: 0,
  };
}

function chipStyle(color, bg, border) {
  return {
    display: 'inline-block',
    fontSize: 8,
    fontWeight: 700,
    letterSpacing: '0.04em',
    color,
    background: bg ?? `${color}18`,
    border: `1px solid ${border ?? color + '55'}`,
    padding: '1px 5px',
    borderRadius: 3,
  };
}
