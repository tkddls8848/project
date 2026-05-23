import { useEffect, useRef, useState } from 'react';

const OLLAMA_URL = '/ollama/api/generate';

function buildPrompt(context, messages, question) {
  const docs = context?.docs ?? [];
  const docSummary = docs.map((doc, index) => {
    const fields = (doc.fields ?? [])
      .slice(0, 16)
      .map(field => `- ${field.key}: ${field.desc}`)
      .join('\n') || '- 필드 정보 없음';

    return [
      `문서 ${index + 1}: ${doc.name}`,
      `제공기관: ${doc.provider}`,
      `분류: ${doc.category || doc.topCategory}`,
      `키워드: ${(doc.keywords ?? []).join(', ') || '-'}`,
      `설명: ${doc.description || '-'}`,
      '필드:',
      fields,
    ].join('\n');
  }).join('\n\n---\n\n');

  const history = messages
    .slice(-6)
    .map(message => `${message.role === 'user' ? '사용자' : '어시스턴트'}: ${message.content}`)
    .join('\n\n');

  return [
    '너는 공공 API 문서를 조합해 새로운 활용 방안을 도출하는 분석가다.',
    '단일 API 설명에 없는 교차 도메인 활용, 연결 가능한 필드, 구현 제약을 구체적으로 답하라.',
    '',
    '[워크플로우가 만든 기본 컨텍스트]',
    context?.prompt || '기본 컨텍스트 없음',
    '',
    '[포함된 API 문서]',
    docSummary || '문서 없음',
    '',
    '[최근 대화]',
    history || '대화 없음',
    '',
    `[사용자 질문]\n${question}`,
  ].join('\n');
}

export function OllamaChatModal({ open, context, onClose }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('이 API들을 조합하면 어떤 서비스가 가능한가?');
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState('');
  const responseRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    setMessages([]);
    setInput('이 API들을 조합하면 어떤 서비스가 가능한가?');
    setError('');
  }, [open, context]);

  useEffect(() => {
    responseRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages, isGenerating]);

  if (!open) return null;

  const docs = context?.docs ?? [];
  const model = context?.model || 'gemma4:e4b';

  const submit = async () => {
    const question = input.trim();
    if (!question || isGenerating) return;

    const nextMessages = [...messages, { role: 'user', content: question }];
    setMessages([...nextMessages, { role: 'assistant', content: '' }]);
    setInput('');
    setIsGenerating(true);
    setError('');

    try {
      const response = await fetch(OLLAMA_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model,
          prompt: buildPrompt(context, messages, question),
          stream: true,
          options: {
            temperature: 0.3,
            top_p: 0.9,
          },
        }),
      });

      if (!response.ok) {
        throw new Error(`Ollama 응답 오류: HTTP ${response.status}`);
      }
      if (!response.body) {
        throw new Error('Ollama 스트림을 읽을 수 없습니다.');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.trim()) continue;
          const chunk = JSON.parse(line);
          if (chunk.response) {
            setMessages(current => {
              const updated = [...current];
              const last = updated[updated.length - 1];
              updated[updated.length - 1] = {
                ...last,
                content: `${last.content}${chunk.response}`,
              };
              return updated;
            });
          }
        }
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(`${message}\nOllama가 실행 중인지, 모델 ${model}이 pull 되어 있는지, 브라우저 CORS 허용이 되어 있는지 확인하세요.`);
      setMessages(current => current.filter((message, index) => {
        return !(index === current.length - 1 && message.role === 'assistant' && !message.content);
      }));
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div style={backdropStyle} onMouseDown={onClose}>
      <div style={modalStyle} onMouseDown={e => e.stopPropagation()}>
        <div style={headerStyle}>
          <div>
            <div style={{ fontSize: 14, fontWeight: 800, color: '#f1f5f9' }}>
              API 조합 채팅
            </div>
            <div style={{ fontSize: 11, color: '#64748b', marginTop: 3 }}>
              Ollama · {model} · {docs.length}개 API 문서
            </div>
          </div>
          <button onClick={onClose} style={iconButtonStyle} aria-label="닫기">×</button>
        </div>

        <div style={bodyStyle}>
          <aside style={sidebarStyle}>
            <div style={sectionTitleStyle}>CONTEXT</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {docs.map(doc => (
                <div key={doc.apiId} style={docCardStyle}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: '#dbeafe', lineHeight: 1.35 }}>
                    {doc.name}
                  </div>
                  <div style={{ fontSize: 9, color: '#64748b', marginTop: 4 }}>
                    {doc.provider} · {doc.topCategory}
                  </div>
                </div>
              ))}
            </div>
          </aside>

          <main style={chatStyle}>
            <div style={messagesStyle}>
              {messages.length === 0 && !error && (
                <div style={emptyStyle}>
                  실행된 Merge/RAG 컨텍스트를 바탕으로 질문하세요.
                </div>
              )}

              {messages.map((message, index) => (
                <div
                  key={`${message.role}-${index}`}
                  style={{
                    ...bubbleStyle,
                    alignSelf: message.role === 'user' ? 'flex-end' : 'flex-start',
                    background: message.role === 'user' ? '#164e63' : '#111827',
                    borderColor: message.role === 'user' ? '#0891b2' : '#1e2d3d',
                  }}
                >
                  <div style={{ fontSize: 9, color: '#94a3b8', fontWeight: 700, marginBottom: 5 }}>
                    {message.role === 'user' ? 'USER' : 'OLLAMA'}
                  </div>
                  <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>
                    {message.content || (isGenerating ? '응답 생성 중...' : '')}
                  </div>
                </div>
              ))}

              {error && <div style={errorStyle}>{error}</div>}
              <div ref={responseRef} />
            </div>

            <div style={inputWrapStyle}>
              <textarea
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    submit();
                  }
                }}
                disabled={isGenerating}
                placeholder="API 조합에 대해 질문하세요"
                style={textareaStyle}
              />
              <button
                onClick={submit}
                disabled={isGenerating || !input.trim()}
                style={{
                  ...sendButtonStyle,
                  opacity: isGenerating || !input.trim() ? 0.5 : 1,
                  cursor: isGenerating || !input.trim() ? 'not-allowed' : 'pointer',
                }}
              >
                {isGenerating ? '생성 중' : '전송'}
              </button>
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}

const backdropStyle = {
  position: 'fixed',
  inset: 0,
  zIndex: 1000,
  background: '#020617cc',
  display: 'grid',
  placeItems: 'center',
  padding: 24,
};

const modalStyle = {
  width: 'min(1040px, 96vw)',
  height: 'min(760px, 90vh)',
  background: '#080e1a',
  border: '1px solid #1e2d3d',
  borderRadius: 8,
  boxShadow: '0 24px 80px #000000aa',
  display: 'flex',
  flexDirection: 'column',
  overflow: 'hidden',
};

const headerStyle = {
  padding: '14px 16px',
  borderBottom: '1px solid #1e2d3d',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
};

const iconButtonStyle = {
  width: 28,
  height: 28,
  borderRadius: 5,
  border: '1px solid #334155',
  background: '#0f172a',
  color: '#cbd5e1',
  fontSize: 18,
  cursor: 'pointer',
};

const bodyStyle = {
  flex: 1,
  minHeight: 0,
  display: 'flex',
};

const sidebarStyle = {
  width: 270,
  borderRight: '1px solid #1e2d3d',
  padding: 12,
  overflowY: 'auto',
  background: '#0a1120',
};

const sectionTitleStyle = {
  fontSize: 9,
  color: '#64748b',
  fontWeight: 800,
  letterSpacing: '0.12em',
  marginBottom: 8,
};

const docCardStyle = {
  background: '#0c1220',
  border: '1px solid #1e2d3d',
  borderRadius: 5,
  padding: 8,
};

const chatStyle = {
  flex: 1,
  minWidth: 0,
  display: 'flex',
  flexDirection: 'column',
};

const messagesStyle = {
  flex: 1,
  minHeight: 0,
  overflowY: 'auto',
  padding: 16,
  display: 'flex',
  flexDirection: 'column',
  gap: 12,
};

const emptyStyle = {
  height: '100%',
  display: 'grid',
  placeItems: 'center',
  color: '#475569',
  fontSize: 12,
};

const bubbleStyle = {
  maxWidth: '78%',
  border: '1px solid #1e2d3d',
  borderRadius: 7,
  padding: '10px 12px',
  color: '#dbeafe',
  fontSize: 12,
};

const errorStyle = {
  whiteSpace: 'pre-wrap',
  background: '#450a0a',
  border: '1px solid #991b1b',
  color: '#fecaca',
  borderRadius: 6,
  padding: 10,
  fontSize: 12,
  lineHeight: 1.5,
};

const inputWrapStyle = {
  borderTop: '1px solid #1e2d3d',
  padding: 12,
  display: 'flex',
  gap: 8,
  background: '#0a1120',
};

const textareaStyle = {
  flex: 1,
  minHeight: 42,
  maxHeight: 110,
  resize: 'vertical',
  borderRadius: 5,
  border: '1px solid #1e2d3d',
  background: '#0c1220',
  color: '#e2e8f0',
  padding: '9px 10px',
  fontFamily: 'inherit',
  fontSize: 12,
  outline: 'none',
};

const sendButtonStyle = {
  width: 76,
  borderRadius: 5,
  border: 'none',
  background: '#0891b2',
  color: 'white',
  fontWeight: 800,
  fontSize: 12,
};
