// 검색 결과 doc과 derived 관계를 캔버스 노드·엣지로 변환 — DOM 의존 없는 순수 함수.

export const SUGGESTED_EDGE_STYLE = { stroke: '#f59e0b', strokeWidth: 1.5, strokeDasharray: '6 4' };
export const APPROVED_EDGE_STYLE = { stroke: '#475569', strokeWidth: 2 };

export function placeSearchResults(docs, relations, makeId, origin = { x: 80, y: 120 }) {
  const nodes = docs.map((doc, index) => ({
    id: makeId(),
    type: 'apiDoc',
    position: {
      x: origin.x + (index % 3) * 280,
      y: origin.y + Math.floor(index / 3) * 240,
    },
    data: { apiId: doc.apiId, doc },
  }));

  const idByService = new Map(docs.map((doc, index) => [doc.serviceId, nodes[index].id]));
  const edges = (relations ?? [])
    .filter(rel => idByService.has(rel.source) && idByService.has(rel.target))
    .map(rel => ({
      id: `rel-${rel.id}`,
      source: idByService.get(rel.source),
      target: idByService.get(rel.target),
      type: 'smoothstep',
      label: rel.type,
      animated: true,
      style: SUGGESTED_EDGE_STYLE,
      data: { relation: rel },
    }));

  return { nodes, edges };
}

export function approveRelationEdge(edges, edgeId) {
  return edges.map(edge => {
    if (edge.id !== edgeId || !edge.data?.relation) return edge;
    return {
      ...edge,
      animated: false,
      style: APPROVED_EDGE_STYLE,
      data: { ...edge.data, relation: { ...edge.data.relation, status: 'approved' } },
    };
  });
}
