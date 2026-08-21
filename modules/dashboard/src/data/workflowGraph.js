import { apiDocMap, toWorkflowDoc, uniqueDocs } from './apiDocs.js';

function inputEdgesFor(nodeId, edges) {
  return edges.filter(edge => edge.target === nodeId);
}

export function topoSort(nodes, edges) {
  const nodeIds = new Set(nodes.map(node => node.id));
  const indegree = new Map(nodes.map(node => [node.id, 0]));
  const outgoing = new Map(nodes.map(node => [node.id, []]));

  edges.forEach(edge => {
    if (!nodeIds.has(edge.source) || !nodeIds.has(edge.target)) return;
    indegree.set(edge.target, (indegree.get(edge.target) ?? 0) + 1);
    outgoing.get(edge.source)?.push(edge.target);
  });

  const queue = nodes.filter(node => (indegree.get(node.id) ?? 0) === 0);
  const sorted = [];

  while (queue.length > 0) {
    const node = queue.shift();
    sorted.push(node);

    for (const targetId of outgoing.get(node.id) ?? []) {
      const nextDegree = (indegree.get(targetId) ?? 0) - 1;
      indegree.set(targetId, nextDegree);
      if (nextDegree === 0) {
        const target = nodes.find(candidate => candidate.id === targetId);
        if (target) queue.push(target);
      }
    }
  }

  // 순환이 있으면 기존 동작대로 원래 배열 순서로 실행한다.
  return sorted.length === nodes.length ? sorted : nodes;
}

export function outputDocsFor(node) {
  if (!node) return [];

  if (node.type === 'apiDoc') {
    const doc = node.data?.doc ?? apiDocMap[node.data?.apiId];
    return doc ? [toWorkflowDoc(doc)] : [];
  }

  return node.data?.output?.docs ?? node.data?.results ?? [];
}

function outputPromptFor(node) {
  if (!node) return '';
  return node.data?.output?.prompt ?? node.data?.analysisPrompt ?? '';
}

export function collectInputDocs(node, edges, byId) {
  return uniqueDocs(
    inputEdgesFor(node.id, edges).flatMap(edge => outputDocsFor(byId.get(edge.source)))
  );
}

export function collectInputPrompts(node, edges, byId) {
  return inputEdgesFor(node.id, edges)
    .map(edge => outputPromptFor(byId.get(edge.source)))
    .filter(Boolean);
}

export function upstreamNodeIds(targetNodeId, edges) {
  const byTarget = new Map();
  edges.forEach(edge => {
    if (!byTarget.has(edge.target)) byTarget.set(edge.target, []);
    byTarget.get(edge.target).push(edge.source);
  });

  const visited = new Set();
  const stack = [targetNodeId];

  while (stack.length > 0) {
    const nodeId = stack.pop();
    if (visited.has(nodeId)) continue;
    visited.add(nodeId);

    for (const sourceId of byTarget.get(nodeId) ?? []) {
      stack.push(sourceId);
    }
  }

  return visited;
}
