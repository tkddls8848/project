import { describe, expect, it } from 'vitest';
import {
  buildInterpretationPrompt,
  EDGE_KINDS,
  FINDING,
  judgeArgumentGraph,
  LABELS,
  NODE_KINDS,
} from '../argumentGraph.js';

const premise = (id, text) => ({ id, kind: NODE_KINDS.PREMISE, text });
const claim = (id, text) => ({ id, kind: NODE_KINDS.CLAIM, text });
const supports = (source, target) => ({ id: `s-${source}-${target}`, kind: EDGE_KINDS.SUPPORT, source, target });
const attacks = (source, target) => ({ id: `a-${source}-${target}`, kind: EDGE_KINDS.ATTACK, source, target });

const codes = verdict => verdict.findings.map(finding => finding.code);

describe('grounded 라벨링 — 살아남는 논증 집합', () => {
  it('공격받지 않는 논증은 성립한다', () => {
    const verdict = judgeArgumentGraph([premise('a', 'A')], []);
    expect(verdict.labels.a).toBe(LABELS.ACCEPTED);
    expect(verdict.extension).toEqual(['a']);
  });

  it('성립한 논증에게 공격당하면 논파된다', () => {
    const verdict = judgeArgumentGraph(
      [premise('a', 'A'), premise('b', 'B')],
      [attacks('a', 'b')]
    );
    expect(verdict.labels).toMatchObject({ a: LABELS.ACCEPTED, b: LABELS.REJECTED });
  });

  it('공격자가 논파되면 그 대상은 되살아난다', () => {
    // a -> b -> c : b가 논파되므로 c는 방어된다.
    const verdict = judgeArgumentGraph(
      [premise('a', 'A'), premise('b', 'B'), premise('c', 'C')],
      [attacks('a', 'b'), attacks('b', 'c')]
    );
    expect(verdict.labels).toMatchObject({
      a: LABELS.ACCEPTED,
      b: LABELS.REJECTED,
      c: LABELS.ACCEPTED,
    });
  });

  it('서로 공격하면 양쪽 다 미판정으로 남는다 — 미해소 모순', () => {
    const verdict = judgeArgumentGraph(
      [premise('a', 'A'), premise('b', 'B')],
      [attacks('a', 'b'), attacks('b', 'a')]
    );
    expect(verdict.undecided.sort()).toEqual(['a', 'b']);
    expect(verdict.extension).toEqual([]);
    expect(codes(verdict)).toContain(FINDING.UNRESOLVED_CONFLICT);
  });

  it('공격의 순환은 오류가 아니다 — 순환논증으로 보고하지 않는다', () => {
    const verdict = judgeArgumentGraph(
      [premise('a', 'A'), premise('b', 'B')],
      [attacks('a', 'b'), attacks('b', 'a')]
    );
    expect(codes(verdict)).not.toContain(FINDING.SUPPORT_CYCLE);
  });
});

describe('지지 구조 검사', () => {
  it('지지가 스스로에게 되돌아오면 순환논증이다', () => {
    const verdict = judgeArgumentGraph(
      [claim('a', 'A'), claim('b', 'B')],
      [supports('a', 'b'), supports('b', 'a')]
    );
    const cycle = verdict.findings.find(finding => finding.code === FINDING.SUPPORT_CYCLE);
    expect(cycle).toBeDefined();
    expect(cycle.nodeIds.sort()).toEqual(['a', 'b']);
    expect(cycle.severity).toBe('violation');
  });

  it('자기 자신을 지지하는 것도 순환논증이다', () => {
    const verdict = judgeArgumentGraph([claim('a', 'A')], [supports('a', 'a')]);
    expect(codes(verdict)).toContain(FINDING.SUPPORT_CYCLE);
  });

  it('지지가 없는 주장은 근거 없는 주장이다', () => {
    const verdict = judgeArgumentGraph([claim('a', 'A')], []);
    const finding = verdict.findings.find(item => item.code === FINDING.UNSUPPORTED_CLAIM);
    expect(finding.nodeIds).toEqual(['a']);
  });

  it('전제는 지지가 없어도 문제가 아니다', () => {
    const verdict = judgeArgumentGraph([premise('a', 'A')], []);
    expect(codes(verdict)).not.toContain(FINDING.UNSUPPORTED_CLAIM);
  });

  it('전제가 주장을 지지하면 근거를 갖춘 것이다', () => {
    const verdict = judgeArgumentGraph(
      [premise('p', '전제'), claim('c', '주장')],
      [supports('p', 'c')]
    );
    expect(codes(verdict)).toEqual([]);
    expect(verdict.extension.sort()).toEqual(['c', 'p']);
  });

  it('얽힌 순환은 덩어리 하나로 보고하고 구성원을 모두 표시한다', () => {
    // a→b→c→a 와 b→d→b 가 b를 공유한다. 한 덩어리다.
    const nodes = ['a', 'b', 'c', 'd'].map(id => claim(id, id.toUpperCase()));
    const verdict = judgeArgumentGraph(nodes, [
      supports('a', 'b'), supports('b', 'c'), supports('c', 'a'),
      supports('b', 'd'), supports('d', 'b'),
    ]);

    const cycles = verdict.findings.filter(finding => finding.code === FINDING.SUPPORT_CYCLE);
    expect(cycles).toHaveLength(1);
    expect([...cycles[0].nodeIds].sort()).toEqual(['a', 'b', 'c', 'd']);
  });

  it('따로 떨어진 순환은 각각 보고한다', () => {
    const nodes = ['a', 'b', 'c', 'd'].map(id => claim(id, id.toUpperCase()));
    const verdict = judgeArgumentGraph(nodes, [
      supports('a', 'b'), supports('b', 'a'),
      supports('c', 'd'), supports('d', 'c'),
    ]);

    expect(
      verdict.findings.filter(finding => finding.code === FINDING.SUPPORT_CYCLE)
    ).toHaveLength(2);
  });
});

describe('순환 검출 비용', () => {
  /** 지지가 갈라졌다 합쳐지기를 k번 반복한다. 순환은 없지만 경로는 2^k개다. */
  function diamondChain(k) {
    const nodes = [premise('n0', 'n0')];
    const edges = [];
    for (let i = 0; i < k; i += 1) {
      const [left, right, next] = [`a${i}`, `b${i}`, `n${i + 1}`];
      nodes.push(premise(left, left), premise(right, right), premise(next, next));
      edges.push(
        supports(`n${i}`, left), supports(`n${i}`, right),
        supports(left, next), supports(right, next),
      );
    }
    return { nodes, edges };
  }

  it('경로가 아니라 노드 수에 비례한다', () => {
    // 경로를 하나씩 훑던 구현은 노드 73개(k=24)에서 30초가 걸렸다.
    // k=40이면 경로가 1조 개를 넘으므로, 끝난다는 것 자체가 회귀 방지선이다.
    const { nodes, edges } = diamondChain(40);

    const started = performance.now();
    const verdict = judgeArgumentGraph(nodes, edges);
    const elapsed = performance.now() - started;

    expect(verdict.counts.nodes).toBe(121);
    expect(elapsed).toBeLessThan(1000);
  });

  it('갈라졌다 합쳐지는 구조는 순환이 아니다', () => {
    const { nodes, edges } = diamondChain(6);
    expect(codes(judgeArgumentGraph(nodes, edges))).not.toContain(FINDING.SUPPORT_CYCLE);
  });
});

describe('망가진 입력', () => {
  it('없는 노드를 가리키는 관계는 판정에서 빼고 보고한다', () => {
    const verdict = judgeArgumentGraph([premise('a', 'A')], [attacks('ghost', 'a')]);
    expect(verdict.labels.a).toBe(LABELS.ACCEPTED);
    expect(codes(verdict)).toContain(FINDING.DANGLING_EDGE);
  });

  it('빈 그래프도 판정된다', () => {
    const verdict = judgeArgumentGraph([], []);
    expect(verdict.extension).toEqual([]);
    expect(verdict.counts.nodes).toBe(0);
  });
});

describe('해석 프롬프트', () => {
  const nodes = [premise('p', '측정소가 서울에 있다'), claim('c', '서울 대기질을 알 수 있다'), premise('x', '측정소가 고장났다')];
  const edges = [supports('p', 'c'), attacks('x', 'p')];

  it('판정 결과와 뒤집기 금지 규칙을 담는다', () => {
    const verdict = judgeArgumentGraph(nodes, edges);
    const prompt = buildInterpretationPrompt(nodes, edges, verdict, '무엇을 결론지을 수 있나?');

    expect(prompt).toContain('판정은 확정되어 있다');
    expect(prompt).toContain('"논파됨"으로 판정된 논증을 성립한다고 쓰지 않는다');
    expect(prompt).toContain('무엇을 결론지을 수 있나?');
    // 라벨이 논증마다 붙어 나간다
    expect(prompt).toContain('[논파됨] (premise) 측정소가 서울에 있다');
    expect(prompt).toContain('[성립] (premise) 측정소가 고장났다');
    // 관계가 방향과 함께 나간다
    expect(prompt).toContain('측정소가 고장났다 —반박함→ 측정소가 서울에 있다');
  });

  it('위반 사항이 없으면 없다고 적는다', () => {
    const clean = [premise('p', '전제'), claim('c', '주장')];
    const cleanEdges = [supports('p', 'c')];
    const prompt = buildInterpretationPrompt(clean, cleanEdges, judgeArgumentGraph(clean, cleanEdges));
    expect(prompt).toContain('## 위반 사항\n- 없음');
  });
});
