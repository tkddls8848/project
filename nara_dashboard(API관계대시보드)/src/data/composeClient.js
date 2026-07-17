// nara_combiner 클라이언트 (vite 프록시 /combiner → 127.0.0.1:8003).

export class ComposeError extends Error {
  constructor(message, errorCode) {
    super(message);
    this.name = 'ComposeError';
    this.errorCode = errorCode;
  }
}

export async function compose(serviceIds, question) {
  let res;
  try {
    res = await fetch('/combiner/compose', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ service_ids: serviceIds, question }),
    });
  } catch {
    throw new ComposeError('nara_combiner 백엔드에 연결할 수 없습니다.', 'CONNECTION');
  }
  const payload = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new ComposeError(
      payload.message || payload.error || `조합 요청 실패 (HTTP ${res.status})`,
      payload.error_code || String(res.status),
    );
  }
  return payload;
}
