// nara_search 백엔드 클라이언트 (vite 프록시 /api → 127.0.0.1:8000).
// 검색 결과에는 fields가 없으므로 상세조회로 보강해 워크플로우 doc을 만든다.

function apiIdOf(serviceId) {
  const idx = String(serviceId ?? '').lastIndexOf(':');
  return idx >= 0 ? String(serviceId).slice(idx + 1) : String(serviceId ?? '');
}

async function backendFetch(input, init) {
  let res;
  try {
    res = await fetch(input, init);
  } catch {
    throw new Error('nara_search 백엔드에 연결할 수 없습니다.');
  }
  return res;
}

export function detailToWorkflowDoc(detail) {
  const category = detail.category ?? '';
  return {
    apiId: apiIdOf(detail.service_id),
    serviceId: detail.service_id ?? '',
    name: detail.name ?? '',
    provider: detail.provider_agency_name ?? '',
    topCategory: category.split(' - ')[0].trim() || '기타',
    category,
    keywords: detail.keywords ?? [],
    description: detail.description ?? '',
    fields: (detail.response_fields ?? []).map(f => ({ key: f.name, desc: f.description || f.name })),
    endpoints: (detail.endpoints ?? []).map(e => ({
      method: e.method ?? 'GET',
      path: e.path ?? '',
      description: e.summary ?? '',
    })),
  };
}

export async function searchRemote(query, topK = 6) {
  const res = await backendFetch('/api/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, top_k: topK }),
  });
  if (!res.ok) throw new Error(`검색 실패 (HTTP ${res.status})`);
  const payload = await res.json();
  return payload.results ?? [];
}

export async function fetchDetail(serviceId) {
  const res = await backendFetch(`/api/services/${encodeURIComponent(serviceId)}`);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`상세조회 실패 (HTTP ${res.status})`);
  return res.json();
}

export async function fetchRelations(serviceIds) {
  const res = await backendFetch(`/api/relations?ids=${encodeURIComponent(serviceIds.join(','))}`);
  if (!res.ok) throw new Error(`관계 조회 실패 (HTTP ${res.status})`);
  const payload = await res.json();
  return payload.relations ?? [];
}

export async function searchDocsWithDetails(query, topK = 6) {
  const results = await searchRemote(query, topK);
  const details = await Promise.all(results.map(r => fetchDetail(r.service_id)));
  return details.filter(Boolean).map(detailToWorkflowDoc);
}
