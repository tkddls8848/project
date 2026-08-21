// 논증 그래프의 형식 판정 계층 — LLM 없이 결정형으로 돈다.
//
// 이 모듈이 확정한 것은 해석 단계에서 뒤집을 수 없다. 그래서 여기서는
// 판정이 유일해야 한다. Dung 의미론 중 grounded를 쓰는 이유가 그것이다:
// preferred/stable은 확장이 여러 개 나오고(그리고 NP-hard), 그러면
// "무엇이 살아남는가"에 답이 여럿이라 LLM이 고를 여지가 생긴다.
//
// 지지(support)는 공격 의미론에 섞지 않는다. 둘을 한 계산에 뭉개면 표준적인
// 결과가 나오지 않는다. 공격은 grounded 라벨링으로, 지지는 구조 검사(순환논증·
// 근거 없는 주장)로 각각 다룬다.

export const NODE_KINDS = {
  PREMISE: 'premise', // 전제 — 지지 없이 성립한다고 사용자가 선언한 것
  CLAIM: 'claim',     // 주장 — 지지가 있어야 한다
};

export const EDGE_KINDS = {
  SUPPORT: 'support',
  ATTACK: 'attack',
};

export const LABELS = {
  ACCEPTED: 'accepted',   // grounded 확장에 포함
  REJECTED: 'rejected',   // 확장의 구성원에게 공격당함
  UNDECIDED: 'undecided', // 어느 쪽도 아님 — 미해소 충돌
};

export const FINDING = {
  SUPPORT_CYCLE: 'support-cycle',
  UNSUPPORTED_CLAIM: 'unsupported-claim',
  UNRESOLVED_CONFLICT: 'unresolved-conflict',
  DANGLING_EDGE: 'dangling-edge',
};

function edgesOfKind(edges, kind, nodeIds) {
  return (edges ?? []).filter(
    edge => edge?.kind === kind && nodeIds.has(edge.source) && nodeIds.has(edge.target)
  );
}

/** target -> [source...] */
function incomingMap(edges) {
  const map = new Map();
  edges.forEach(edge => {
    if (!map.has(edge.target)) map.set(edge.target, []);
    map.get(edge.target).push(edge.source);
  });
  return map;
}

/**
 * Dung의 grounded 라벨링.
 *
 * 공격자가 하나도 없는 논증부터 받아들이고, 받아들인 것에게 공격당하는 것을
 * 물리치기를 더 바뀌지 않을 때까지 반복한다. 남는 것이 undecided이며, 서로
 * 공격하는 쌍이 정확히 여기에 남는다 — 그것이 "미해소 모순"이다.
 */
function groundedLabelling(nodeIds, attackEdges) {
  const attackers = incomingMap(attackEdges);
  const accepted = new Set();
  const rejected = new Set();

  for (;;) {
    let changed = false;

    for (const id of nodeIds) {
      if (accepted.has(id) || rejected.has(id)) continue;
      const incoming = attackers.get(id) ?? [];
      if (incoming.every(source => rejected.has(source))) {
        accepted.add(id);
        changed = true;
      }
    }

    for (const id of nodeIds) {
      if (accepted.has(id) || rejected.has(id)) continue;
      const incoming = attackers.get(id) ?? [];
      if (incoming.some(source => accepted.has(source))) {
        rejected.add(id);
        changed = true;
      }
    }

    if (!changed) break;
  }

  const labels = {};
  for (const id of nodeIds) {
    labels[id] = accepted.has(id)
      ? LABELS.ACCEPTED
      : rejected.has(id)
        ? LABELS.REJECTED
        : LABELS.UNDECIDED;
  }
  return labels;
}

/**
 * Tarjan의 강결합 요소(SCC). 한 요소 안의 노드들은 서로 오갈 수 있다.
 */
function stronglyConnectedComponents(nodeIds, outgoing) {
  const index = new Map();
  const lowlink = new Map();
  const onStack = new Set();
  const stack = [];
  const components = [];
  let counter = 0;

  function connect(id) {
    index.set(id, counter);
    lowlink.set(id, counter);
    counter += 1;
    stack.push(id);
    onStack.add(id);

    for (const next of outgoing.get(id) ?? []) {
      if (!index.has(next)) {
        connect(next);
        lowlink.set(id, Math.min(lowlink.get(id), lowlink.get(next)));
      } else if (onStack.has(next)) {
        lowlink.set(id, Math.min(lowlink.get(id), index.get(next)));
      }
    }

    if (lowlink.get(id) === index.get(id)) {
      const component = [];
      for (;;) {
        const member = stack.pop();
        onStack.delete(member);
        component.push(member);
        if (member === id) break;
      }
      components.push(component);
    }
  }

  for (const id of nodeIds) if (!index.has(id)) connect(id);
  return components;
}

/**
 * 얽힌 덩어리 안에서 실제로 되돌아오는 경로 하나를 뽑는다.
 *
 * 덩어리 전체를 보고하되 메시지에는 순서가 있어야 읽힌다. 최단 경로면 충분하다.
 */
function representativeCycle(component, outgoing, selfLoops) {
  const start = component[0];
  if (selfLoops.has(start)) return [start];

  const members = new Set(component);
  const previous = new Map([[start, null]]);
  const queue = [start];

  while (queue.length > 0) {
    const id = queue.shift();
    for (const next of outgoing.get(id) ?? []) {
      if (!members.has(next)) continue;
      if (next === start) {
        const cycle = [];
        for (let at = id; at !== null; at = previous.get(at)) cycle.push(at);
        return cycle.reverse();
      }
      if (!previous.has(next)) {
        previous.set(next, id);
        queue.push(next);
      }
    }
  }
  return component;
}

/**
 * 지지 관계의 순환을 찾는다 — 순환논증(begging the question).
 *
 * 공격의 순환은 오류가 아니다. Dung 의미론에서 정상이며 undecided를 낳는다.
 * 자기 근거로 자기를 떠받치는 것은 지지 관계에서만 오류다.
 *
 * 단순 순환을 경로 탐색으로 열거하면 경로 수만큼 시간이 든다. 지지가 갈라졌다
 * 합쳐지는 모양이 이어지면 순환이 하나도 없는데도 경로가 2^k개라, 노드 73개에서
 * 30초가 걸렸다. 강결합 요소는 O(V+E)로 찾는다. 서로 오갈 수 있는 덩어리가
 * 곧 순환이므로, 얽힌 덩어리 하나를 순환논증 한 건으로 보고한다.
 */
function supportCycles(nodeIds, supportEdges) {
  const outgoing = new Map();
  const selfLoops = new Set();
  supportEdges.forEach(edge => {
    if (edge.source === edge.target) selfLoops.add(edge.source);
    if (!outgoing.has(edge.source)) outgoing.set(edge.source, []);
    outgoing.get(edge.source).push(edge.target);
  });

  return stronglyConnectedComponents(nodeIds, outgoing)
    .filter(component => component.length > 1 || selfLoops.has(component[0]))
    .map(component => ({
      members: component,
      path: representativeCycle(component, outgoing, selfLoops),
    }));
}

function nodeLabelText(node) {
  return String(node?.text ?? node?.id ?? '').trim();
}

/**
 * 그래프를 판정한다. LLM은 이 결과를 뒤집지 못한다.
 *
 * nodes: [{ id, kind, text }]
 * edges: [{ id, kind, source, target }]
 */
export function judgeArgumentGraph(nodes, edges) {
  const list = (nodes ?? []).filter(node => node && node.id);
  const nodeIds = new Set(list.map(node => node.id));
  const byId = new Map(list.map(node => [node.id, node]));

  const attackEdges = edgesOfKind(edges, EDGE_KINDS.ATTACK, nodeIds);
  const supportEdges = edgesOfKind(edges, EDGE_KINDS.SUPPORT, nodeIds);

  const labels = groundedLabelling(nodeIds, attackEdges);
  const findings = [];

  // 존재하지 않는 노드를 가리키는 엣지는 판정에서 제외했으므로 그 사실을 남긴다.
  const dangling = (edges ?? []).filter(
    edge => edge && (!nodeIds.has(edge.source) || !nodeIds.has(edge.target))
  );
  dangling.forEach(edge => {
    findings.push({
      code: FINDING.DANGLING_EDGE,
      severity: 'warning',
      nodeIds: [edge.source, edge.target].filter(id => !nodeIds.has(id)),
      message: '없는 노드를 가리키는 관계가 있어 판정에서 제외했습니다.',
    });
  });

  supportCycles(nodeIds, supportEdges).forEach(cycle => {
    findings.push({
      code: FINDING.SUPPORT_CYCLE,
      severity: 'violation',
      // 얽힌 덩어리 전체를 표시한다. 경로 하나만 짚으면 같은 순환에 걸린
      // 나머지 노드가 아무 표시도 없이 남는다.
      nodeIds: cycle.members,
      message: `순환논증입니다. 지지 관계가 스스로에게 되돌아옵니다: ${
        cycle.path.map(id => nodeLabelText(byId.get(id))).join(' → ')
      } → …`,
    });
  });

  const supported = new Set(supportEdges.map(edge => edge.target));
  list
    .filter(node => node.kind === NODE_KINDS.CLAIM && !supported.has(node.id))
    .forEach(node => {
      findings.push({
        code: FINDING.UNSUPPORTED_CLAIM,
        severity: 'violation',
        nodeIds: [node.id],
        message: `근거가 없는 주장입니다: ${nodeLabelText(node)}`,
      });
    });

  const undecided = list.filter(node => labels[node.id] === LABELS.UNDECIDED);
  if (undecided.length > 0) {
    findings.push({
      code: FINDING.UNRESOLVED_CONFLICT,
      severity: 'violation',
      nodeIds: undecided.map(node => node.id),
      message: `공격이 서로를 상쇄해 판정되지 않은 논증이 ${undecided.length}개 있습니다.`,
    });
  }

  return {
    labels,
    extension: list.filter(node => labels[node.id] === LABELS.ACCEPTED).map(node => node.id),
    rejected: list.filter(node => labels[node.id] === LABELS.REJECTED).map(node => node.id),
    undecided: undecided.map(node => node.id),
    findings,
    counts: {
      nodes: list.length,
      attacks: attackEdges.length,
      supports: supportEdges.length,
      violations: findings.filter(finding => finding.severity === 'violation').length,
    },
  };
}

const LABEL_TEXT = {
  [LABELS.ACCEPTED]: '성립',
  [LABELS.REJECTED]: '논파됨',
  [LABELS.UNDECIDED]: '미판정',
};

/**
 * 판정을 프롬프트로 옮긴다.
 *
 * 해석은 판정을 설명하는 것이지 다시 따지는 것이 아니다. 그래서 라벨을 근거로
 * 제시하고, 뒤집지 말라고 명시한다. 이 제약이 없으면 모델은 논파된 주장을
 * 되살리는 쪽이 더 그럴듯한 글이 되므로 그렇게 한다.
 */
export function buildInterpretationPrompt(nodes, edges, verdict, question = '') {
  const byId = new Map((nodes ?? []).map(node => [node.id, node]));
  const label = id => LABEL_TEXT[verdict.labels[id]] ?? '미판정';

  const nodeLines = (nodes ?? []).map(
    node => `- [${label(node.id)}] (${node.kind}) ${nodeLabelText(node)}`
  );

  const edgeLines = (edges ?? [])
    .filter(edge => byId.has(edge.source) && byId.has(edge.target))
    .map(edge => {
      const arrow = edge.kind === EDGE_KINDS.ATTACK ? '반박함' : '지지함';
      return `- ${nodeLabelText(byId.get(edge.source))} —${arrow}→ ${nodeLabelText(byId.get(edge.target))}`;
    });

  const findingLines = verdict.findings.length > 0
    ? verdict.findings.map(finding => `- (${finding.code}) ${finding.message}`)
    : ['- 없음'];

  return [
    '아래는 형식 판정을 마친 논증 그래프다. 판정은 확정되어 있다.',
    '',
    '규칙:',
    '1. "논파됨"으로 판정된 논증을 성립한다고 쓰지 않는다.',
    '2. "미판정"은 어느 한쪽으로 결론내지 않고, 무엇이 걸려 있는지만 설명한다.',
    '3. 그래프에 없는 주장이나 관계를 새로 만들지 않는다.',
    '4. 위반 사항이 있으면 해석보다 먼저 그것을 지적한다.',
    '',
    question ? `질문: ${question}` : '질문: 이 논증 구조에서 무엇을 결론지을 수 있는가?',
    '',
    '## 논증',
    ...(nodeLines.length > 0 ? nodeLines : ['- 없음']),
    '',
    '## 관계',
    ...(edgeLines.length > 0 ? edgeLines : ['- 없음']),
    '',
    '## 형식 판정',
    `- 성립하는 논증 집합(grounded extension): ${
      verdict.extension.map(id => nodeLabelText(byId.get(id))).join(', ') || '없음'
    }`,
    `- 논파된 논증: ${verdict.rejected.map(id => nodeLabelText(byId.get(id))).join(', ') || '없음'}`,
    `- 미판정 논증: ${verdict.undecided.map(id => nodeLabelText(byId.get(id))).join(', ') || '없음'}`,
    '',
    '## 위반 사항',
    ...findingLines,
    '',
    '## 출력 형식',
    '1. 판정 요약 (무엇이 성립하고 무엇이 무너졌는가)',
    '2. 그렇게 되는 이유를 관계로 설명',
    '3. 미판정으로 남은 쟁점과 그것을 가르려면 무엇이 더 필요한가',
  ].join('\n');
}
