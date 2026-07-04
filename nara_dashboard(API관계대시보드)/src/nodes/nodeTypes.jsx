import { BaseNode, Field, Badge } from './BaseNode.jsx';
import { ApiDocNode } from './ApiDocNode.jsx';
import { MergeNode } from './MergeNode.jsx';

const STATUS_COLOR = {
  idle: '#6b7280',
  success: '#22c55e',
  error: '#f87171',
};

function StatusBadge({ status }) {
  if (!status || status === 'idle') return null;
  return <Badge label={status === 'success' ? '실행 완료' : '오류'} color={STATUS_COLOR[status] ?? '#6b7280'} />;
}

function ResultPreview({ results }) {
  if (!results?.length) return null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      <div style={{ fontSize: 9, color: '#4b5563', fontWeight: 700, letterSpacing: '0.06em' }}>
        결과 {results.length}개
      </div>
      {results.slice(0, 5).map(doc => (
        <div key={doc.apiId} style={{
          color: '#cbd5e1',
          background: '#0c1220',
          border: '1px solid #1e2d3d',
          borderRadius: 4,
          fontSize: 9,
          lineHeight: 1.35,
          padding: '3px 6px',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}>
          {doc.name}
        </div>
      ))}
      {results.length > 5 && (
        <div style={{ fontSize: 9, color: '#64748b', padding: '1px 2px' }}>
          +{results.length - 5}개 더
        </div>
      )}
    </div>
  );
}

function OutputRunButton({ onRun, label = '이 출력 실행' }) {
  if (!onRun) return null;

  return (
    <button
      type="button"
      onClick={(event) => {
        event.stopPropagation();
        onRun();
      }}
      onPointerDown={event => event.stopPropagation()}
      style={runButtonStyle}
      onMouseEnter={event => { event.currentTarget.style.background = '#0ea5e9'; }}
      onMouseLeave={event => { event.currentTarget.style.background = '#0284c7'; }}
    >
      ▶ {label}
    </button>
  );
}

// ── SOURCE ───────────────────────────────────────────────────────────────────

export function APISearchNode({ data, selected }) {
  return (
    <BaseNode category="source" icon="🔍" title="API 검색" hasInput={false} selected={selected}>
      <Field label="검색어" value={data.query} />
      <Field label="최대 결과 수" value={data.maxResults ? `${data.maxResults}개` : ''} />
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        <StatusBadge status={data.status} />
        {data.error && <Badge label={data.error} color="#f87171" />}
      </div>
      <ResultPreview results={data.results} />
    </BaseNode>
  );
}

// ── FILTER ───────────────────────────────────────────────────────────────────

export function CategoryFilterNode({ data, selected }) {
  return (
    <BaseNode category="filter" icon="🗂️" title="카테고리 필터" selected={selected}>
      <Field label="카테고리" value={data.category} />
      <div style={{ display: 'flex', gap: 6 }}>
        <Badge label={data.strict ? '엄격 일치' : '부분 일치'} color="#8b5cf6" />
        <StatusBadge status={data.status} />
      </div>
      <ResultPreview results={data.results} />
    </BaseNode>
  );
}

export function ProviderFilterNode({ data, selected }) {
  return (
    <BaseNode category="filter" icon="🏛️" title="제공기관 필터" selected={selected}>
      <Field label="제공기관" value={data.provider} />
      <div style={{ display: 'flex', gap: 6 }}>
        <StatusBadge status={data.status} />
      </div>
      <ResultPreview results={data.results} />
    </BaseNode>
  );
}

export function ScoreFilterNode({ data, selected }) {
  return (
    <BaseNode category="filter" icon="📊" title="점수 필터" selected={selected}>
      <Field label="최소 유사도" value={data.minScore ? `${data.minScore}` : ''} />
      <Field label="상위 N개" value={data.topK ? `${data.topK}개` : ''} />
      <div style={{ display: 'flex', gap: 6 }}>
        <StatusBadge status={data.status} />
      </div>
      <ResultPreview results={data.results} />
    </BaseNode>
  );
}

// ── ANALYSIS ─────────────────────────────────────────────────────────────────

export function RAGChatNode({ data, selected }) {
  const llmColors = { claude: '#f97316', ollama: '#10b981', openai: '#3b82f6' };
  return (
    <BaseNode category="analysis" icon="🤖" title="RAG 채팅" selected={selected}>
      <Field label="프롬프트" value={data.prompt} />
      <div style={{ display: 'flex', gap: 6 }}>
        <Badge label={data.llm || 'claude'} color={llmColors[data.llm] ?? '#10b981'} />
        <Badge label="스트리밍" color="#10b981" />
        <StatusBadge status={data.status} />
      </div>
      {data.analysisPrompt && (
        <Field label="생성된 LLM 컨텍스트" value={`${data.analysisPrompt.length.toLocaleString('ko')}자`} />
      )}
    </BaseNode>
  );
}

export function SummaryNode({ data, selected }) {
  return (
    <BaseNode category="analysis" icon="📝" title="요약" selected={selected}>
      <Field label="최대 길이" value={data.maxLength ? `${data.maxLength}자` : ''} />
    </BaseNode>
  );
}

// ── OUTPUT ────────────────────────────────────────────────────────────────────

export function ExportNode({ data, selected }) {
  const fmtColor = { JSON: '#f59e0b', CSV: '#06b6d4', XLSX: '#22c55e' };
  const exportCount = data.output?.exportRequest?.docs?.length ?? data.results?.length ?? 0;
  return (
    <BaseNode category="output" icon="📤" title="내보내기" hasOutput={false} selected={selected}>
      <Field label="파일명" value={data.filename} />
      <div style={{ display: 'flex', gap: 6 }}>
        <Badge label={data.format || 'JSON'} color={fmtColor[data.format] ?? '#f59e0b'} />
        <StatusBadge status={data.status} />
      </div>
      {exportCount > 0 && <Field label="내보낼 데이터" value={`${exportCount}개 API 문서`} />}
      {data.error && <Badge label={data.error} color="#f87171" />}
      <OutputRunButton onRun={data.onRunOutput} />
    </BaseNode>
  );
}

export function SaveNode({ data, selected }) {
  return (
    <BaseNode category="output" icon="💾" title="워크플로우 저장" hasOutput={false} selected={selected}>
      <Field label="저장 이름" value={data.name} />
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        <Badge label="Prometheus 저장소" color="#f97316" />
        <StatusBadge status={data.status} />
      </div>
      {data.error && <Badge label={data.error} color="#f87171" />}
      <OutputRunButton onRun={data.onRunOutput} />
    </BaseNode>
  );
}

export function ChatOutputNode({ data, selected }) {
  const docCount = data.chatContext?.docs?.length ?? data.output?.docs?.length ?? 0;
  return (
    <BaseNode category="output" icon="💬" title="채팅하기" hasOutput={false} selected={selected}>
      <Field label="Ollama 모델" value={data.model || 'gemma4:e4b'} />
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        <Badge label="local ollama" color="#10b981" />
        <StatusBadge status={data.status} />
      </div>
      {docCount > 0 && <Field label="채팅 컨텍스트" value={`${docCount}개 API 문서`} />}
      {data.error && <Badge label={data.error} color="#f87171" />}
      <OutputRunButton onRun={data.onRunOutput} label="채팅 준비" />
    </BaseNode>
  );
}

// ── 등록 맵 ───────────────────────────────────────────────────────────────────

export const nodeTypes = {
  apiDoc:         ApiDocNode,
  mergeNode:      MergeNode,
  apiSearch:      APISearchNode,
  categoryFilter: CategoryFilterNode,
  providerFilter: ProviderFilterNode,
  scoreFilter:    ScoreFilterNode,
  ragChat:        RAGChatNode,
  summaryNode:    SummaryNode,
  exportNode:     ExportNode,
  saveNode:       SaveNode,
  chatOutput:     ChatOutputNode,
};

const runButtonStyle = {
  width: '100%',
  border: 'none',
  borderRadius: 5,
  background: '#0284c7',
  color: 'white',
  fontSize: 11,
  fontWeight: 800,
  padding: '6px 8px',
  cursor: 'pointer',
  letterSpacing: '0.02em',
  transition: 'background 0.12s',
};
