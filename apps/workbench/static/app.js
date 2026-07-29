const $ = (selector, root = document) => root.querySelector(selector);
const MAX_COMPOSE_SERVICES = 3;

const state = {
  results: [],
  resultMode: "search",
  resultTotal: 0,
  diagnostics: null,
  category: "",
  selected: [],
  details: new Map(),
  relations: [],
  health: null,
  searchRequest: 0,
  relationRequest: 0,
  composeRequest: 0,
  searchBusy: false,
  relationBusy: false,
  composeBusy: false,
  analysisStartedAt: 0,
  analysisTimer: null,
  planText: "",
};

const relationLabels = {
  "io-chain": "입출력 연결",
  "param-overlap": "요청값 공유",
  "same-agency": "같은 제공기관",
  "same-domain": "같은 분야",
};

const relationTones = {
  "io-chain": "chain",
  "param-overlap": "param",
  "same-agency": "agency",
  "same-domain": "domain",
};

function element(tag, options = {}, children = []) {
  const node = document.createElement(tag);
  if (options.className) node.className = options.className;
  if (options.text !== undefined) node.textContent = options.text;
  if (options.attrs) {
    Object.entries(options.attrs).forEach(([key, value]) => {
      if (value !== undefined && value !== null) node.setAttribute(key, String(value));
    });
  }
  const normalized = Array.isArray(children) ? children : [children];
  normalized.filter(Boolean).forEach((child) => node.append(child));
  return node;
}

function svgElement(tag, attrs = {}) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, String(value)));
  return node;
}

async function fetchJson(url, init) {
  let response;
  try {
    response = await fetch(url, init);
  } catch {
    throw new Error("통합 앱 서버에 연결할 수 없습니다.");
  }
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.message || payload.detail || `요청 실패 (HTTP ${response.status})`);
  }
  return payload;
}

function toast(message, tone = "default") {
  const region = $("#toastRegion");
  const item = element("div", {
    className: "toast",
    text: message,
    attrs: { "data-tone": tone },
  });
  region.append(item);
  window.setTimeout(() => item.remove(), 3600);
}

function apiName(serviceId) {
  const detail = state.details.get(serviceId);
  if (detail?.name) return detail.name;
  const result = state.results.find((item) => item.service_id === serviceId);
  return result?.name || serviceId;
}

function apiProvider(serviceId) {
  const detail = state.details.get(serviceId);
  if (detail?.provider_agency_name) return detail.provider_agency_name;
  const result = state.results.find((item) => item.service_id === serviceId);
  return result?.provider_agency_name || result?.provider || "제공기관 미상";
}

function shortText(value, length = 20) {
  const text = String(value || "").trim();
  return text.length > length ? `${text.slice(0, length - 1)}…` : text;
}

function normalizeCatalogDoc(doc) {
  return {
    service_id: doc.service_id,
    name: doc.name || doc.service_id,
    provider_agency_name: doc.provider || "",
    category: doc.category || "",
    description: doc.description || "",
    score: null,
    match_reasons: [],
  };
}

function updateSummary() {
  $("#heroResultCount").textContent = state.resultTotal.toLocaleString("ko-KR");
  $("#heroSelectedCount").textContent = String(state.selected.length);
  $("#heroRelationCount").textContent = String(state.relations.length);
  $("#selectedCount").textContent = `${state.selected.length} / ${MAX_COMPOSE_SERVICES}`;

  const hasSelection = state.selected.length > 0;
  const hasPlan = Boolean(state.planText);
  const isComposing = state.composeBusy || hasPlan;
  const activeStage = isComposing ? 3 : hasSelection ? 2 : 1;
  const steps = [
    { node: $("#stepSearch"), index: 1 },
    { node: $("#stepRelation"), index: 2 },
    { node: $("#stepCompose"), index: 3 },
  ];

  steps.forEach(({ node, index }) => {
    const status = hasPlan
      ? "complete"
      : index < activeStage
        ? "complete"
        : index === activeStage
          ? "active"
          : "pending";
    node.dataset.state = status;
    node.classList.toggle("is-active", status === "active");
    node.classList.toggle("is-complete", status === "complete");
    if (status === "active") {
      node.setAttribute("aria-current", "step");
    } else {
      node.removeAttribute("aria-current");
    }
  });

  $("#stepSearch").classList.toggle("is-updating", state.searchBusy);
  $("#stepRelation").classList.toggle("is-updating", state.relationBusy);
  $("#stepCompose").classList.toggle("is-updating", state.composeBusy);

  $("#stepSearch small").textContent = state.searchBusy
    ? "문서 색인을 검색하고 있습니다"
    : hasSelection
      ? `${state.selected.length}개 문서 선택 완료`
      : state.results.length
        ? `검색 결과 ${state.resultTotal.toLocaleString("ko-KR")}건 · 문서를 선택하세요`
        : "자연어·키워드 검색";
  $("#stepRelation small").textContent = state.relationBusy
    ? "선택 문서의 연결 근거 분석 중"
    : state.selected.length === 0
      ? "기관·분야·입출력 근거"
      : state.selected.length < 2
        ? "문서를 하나 더 선택하세요"
        : `관계 ${state.relations.length}개 확인 · 조합 가능`;
  $("#stepCompose small").textContent = state.composeBusy
    ? "서비스 계획 생성 중"
    : hasPlan
      ? "검토용 계획 초안 생성 완료"
      : "LLM 기반 계획 초안";
}

function renderLoadingResults() {
  const list = $("#resultsList");
  list.replaceChildren();
  for (let index = 0; index < 4; index += 1) {
    list.append(
      element("article", { className: "result-card is-loading" }, [
        element("div", { className: "skeleton" }),
        element("div", { className: "skeleton" }),
        element("div", { className: "skeleton" }),
      ]),
    );
  }
  $("#resultsSummary").textContent = "문서 색인을 조회하고 있습니다.";
}

function populateCategories() {
  const select = $("#categoryFilter");
  const current = state.category;
  const categories = [...new Set(state.results.map((item) => item.category).filter(Boolean))]
    .sort((a, b) => a.localeCompare(b, "ko"));
  select.replaceChildren(element("option", { text: "전체 분야", attrs: { value: "" } }));
  categories.forEach((category) => {
    select.append(element("option", { text: category, attrs: { value: category } }));
  });
  select.value = categories.includes(current) ? current : "";
  state.category = select.value;
}

function renderResults() {
  const list = $("#resultsList");
  const filtered = state.category
    ? state.results.filter((item) => item.category === state.category)
    : state.results;
  const visible = filtered.slice(0, 120);

  list.replaceChildren();
  $("#resultTools").hidden = state.results.length === 0;
  $("#clearResultsButton").hidden = state.results.length === 0;

  if (!state.results.length) {
    const empty = element("div", { className: "empty-state" }, [
      element("span", { className: "empty-state__icon", text: "⌕" }),
      element("strong", { text: "아직 표시할 API 문서가 없습니다." }),
      element("p", {
        text: "위 검색창에 필요한 서비스나 데이터를 문장으로 입력해 보세요.",
      }),
    ]);
    list.append(empty);
    $("#resultsSummary").textContent = "검색어를 입력해 문서를 찾으세요.";
    updateSummary();
    return;
  }

  visible.forEach((item, index) => {
    const selected = state.selected.includes(item.service_id);
    const checkbox = element("input", {
      attrs: {
        type: "checkbox",
        "aria-label": `${item.name} ${selected ? "선택 해제" : "선택"}`,
      },
    });
    checkbox.checked = selected;
    checkbox.disabled =
      state.composeBusy ||
      (!selected && state.selected.length >= MAX_COMPOSE_SERVICES);
    checkbox.addEventListener("change", () => toggleSelection(item.service_id));

    const score = item.score === null || item.score === undefined
      ? "CATALOG"
      : `점수 ${Number(item.score).toFixed(4)}`;
    const detailButton = element("button", {
      className: "detail-link",
      text: "문서 상세",
      attrs: { type: "button" },
    });
    detailButton.addEventListener("click", () => showDetail(item.service_id));

    const card = element(
      "article",
      {
        className: "result-card",
        attrs: {
          "data-selected": selected,
          "data-service-id": item.service_id,
        },
      },
      [
        element("div", { className: "result-card__check" }, checkbox),
        element("div", { className: "result-card__body" }, [
          element("div", { className: "result-card__top" }, [
            element("span", {
              className: "result-rank",
              text: String(index + 1).padStart(2, "0"),
            }),
            element("span", { className: "result-score", text: score }),
          ]),
          element("h4", { text: item.name || item.service_id }),
          element("p", {
            className: "result-provider",
            text: item.provider_agency_name || item.provider || "제공기관 미상",
          }),
          element("p", {
            className: "result-description",
            text: item.description || "문서 설명이 제공되지 않았습니다.",
          }),
          element("div", { className: "result-card__footer" }, [
            element("span", {
              className: "category-label",
              text: item.category || "분류 없음",
            }),
            detailButton,
          ]),
        ]),
      ],
    );
    list.append(card);
  });

  if (filtered.length > visible.length) {
    list.append(
      element("p", {
        className: "muted-copy",
        text: `${filtered.length.toLocaleString("ko-KR")}건 중 앞의 ${visible.length}건을 표시합니다. 위 검색으로 범위를 좁힐 수 있습니다.`,
        attrs: { style: "padding: 12px;" },
      }),
    );
  }

  const modeLabel = state.resultMode === "catalog" ? "전체 카탈로그" : "검색 결과";
  const renderedLabel = filtered.length > visible.length
    ? ` · 상위 ${visible.length.toLocaleString("ko-KR")}건 표시`
    : ` · ${visible.length.toLocaleString("ko-KR")}건 모두 표시`;
  $("#resultsSummary").textContent =
    `${modeLabel} ${filtered.length.toLocaleString("ko-KR")}건${renderedLabel}`;
  updateSummary();
}

function renderDiagnostics() {
  const target = $("#searchDiagnostics");
  if (!state.diagnostics) {
    target.textContent = state.resultMode === "catalog" ? "문서 카탈로그" : "";
    return;
  }
  const { fusion, vector_candidates: vector, lexical_candidates: lexical } = state.diagnostics;
  const channel = fusion === "rrf"
    ? "벡터+렉시컬"
    : fusion === "vector"
      ? "벡터"
      : fusion === "lexical"
        ? "렉시컬"
        : "일치 없음";
  target.textContent = `${channel} · V ${vector || 0} / L ${lexical || 0}`;
}

async function searchDocuments(query) {
  const requestId = ++state.searchRequest;
  state.searchBusy = true;
  updateSummary();
  renderLoadingResults();
  $("#searchButton").disabled = true;
  $("#catalogButton").disabled = true;
  $("#searchButton span").textContent = "검색 중…";
  try {
    const payload = await fetchJson("/api/search/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query,
        top_k: 20,
        use_vector: $("#vectorToggle").checked,
      }),
    });
    if (requestId !== state.searchRequest) return;
    state.results = payload.results || [];
    state.resultTotal = state.results.length;
    state.resultMode = "search";
    state.diagnostics = payload.diagnostics || null;
    state.category = "";
    populateCategories();
    renderDiagnostics();
    renderResults();
    if (!state.results.length) toast("검색 결과가 없습니다. 검색어를 바꿔 보세요.");
  } catch (error) {
    if (requestId !== state.searchRequest) return;
    state.results = [];
    state.resultTotal = 0;
    renderResults();
    $("#resultsList").replaceChildren(
      element("div", { className: "error-panel", text: error.message }),
    );
    $("#resultsSummary").textContent = "검색 서비스를 확인해 주세요.";
    toast(error.message, "error");
  } finally {
    if (requestId === state.searchRequest) {
      state.searchBusy = false;
      $("#searchButton").disabled = false;
      $("#catalogButton").disabled = false;
      $("#searchButton span").textContent = "API 찾기";
      $("#catalogButton").textContent = "전체 문서 보기";
      updateSummary();
    }
  }
}

async function browseCatalog() {
  const requestId = ++state.searchRequest;
  state.searchBusy = true;
  updateSummary();
  renderLoadingResults();
  $("#searchButton").disabled = true;
  $("#catalogButton").disabled = true;
  $("#catalogButton").textContent = "불러오는 중…";
  try {
    const payload = await fetchJson("/api/search/catalog");
    if (requestId !== state.searchRequest) return;
    state.results = (payload.docs || []).map(normalizeCatalogDoc);
    state.resultTotal = payload.total ?? state.results.length;
    state.resultMode = "catalog";
    state.diagnostics = null;
    state.category = "";
    populateCategories();
    renderDiagnostics();
    renderResults();
  } catch (error) {
    if (requestId !== state.searchRequest) return;
    state.results = [];
    state.resultTotal = 0;
    renderResults();
    $("#resultsList").replaceChildren(
      element("div", { className: "error-panel", text: error.message }),
    );
    toast(error.message, "error");
  } finally {
    if (requestId === state.searchRequest) {
      state.searchBusy = false;
      $("#searchButton").disabled = false;
      $("#catalogButton").disabled = false;
      $("#searchButton span").textContent = "API 찾기";
      $("#catalogButton").textContent = "전체 문서 보기";
      updateSummary();
    }
  }
}

async function ensureDetail(serviceId) {
  if (state.details.has(serviceId)) return state.details.get(serviceId);
  const detail = await fetchJson(`/api/search/services/${encodeURIComponent(serviceId)}`);
  state.details.set(serviceId, detail);
  renderSelected();
  renderGraph();
  return detail;
}

async function toggleSelection(serviceId) {
  if (state.composeBusy) {
    toast("조합 분석이 끝난 뒤 선택 항목을 변경할 수 있습니다.");
    return;
  }
  if (state.selected.includes(serviceId)) {
    state.selected = state.selected.filter((id) => id !== serviceId);
  } else {
    if (state.selected.length >= MAX_COMPOSE_SERVICES) {
      toast(`조합기는 최대 ${MAX_COMPOSE_SERVICES}개의 API 문서를 받을 수 있습니다.`, "error");
      return;
    }
    state.selected.push(serviceId);
    ensureDetail(serviceId).catch((error) => {
      toast(`${apiName(serviceId)} 상세조회 실패: ${error.message}`, "error");
    });
  }
  state.planText = "";
  state.relations = [];
  state.relationBusy = false;
  $("#composeResult").hidden = true;
  $("#composePlaceholder").hidden = false;
  renderResults();
  renderSelected();
  renderGraph();
  await refreshRelations();
}

function renderSelected() {
  const target = $("#selectedList");
  target.replaceChildren();
  if (!state.selected.length) {
    target.append(
      element("p", {
        className: "muted-copy",
        text: "왼쪽 검색 결과에서 조합할 API를 선택하세요.",
      }),
    );
  } else {
    state.selected.forEach((serviceId) => {
      const remove = element("button", {
        text: "×",
        attrs: {
          type: "button",
          title: `${apiName(serviceId)} 선택 해제`,
          "aria-label": `${apiName(serviceId)} 선택 해제`,
          disabled: state.composeBusy ? "" : undefined,
        },
      });
      remove.addEventListener("click", () => toggleSelection(serviceId));
      target.append(
        element("span", { className: "selected-chip" }, [
          element("span", { text: apiName(serviceId) }),
          remove,
        ]),
      );
    });
  }
  $("#composeButton").disabled = state.composeBusy || state.selected.length === 0;
  updateSummary();
}

async function refreshRelations() {
  const requestId = ++state.relationRequest;
  if (state.selected.length < 2) {
    state.relationBusy = false;
    state.relations = [];
    renderGraph();
    renderEvidence();
    return;
  }

  state.relationBusy = true;
  updateSummary();
  $("#relationSummary").textContent = "선택 문서의 관계 근거를 계산하고 있습니다.";
  try {
    const params = new URLSearchParams({ ids: state.selected.join(",") });
    const payload = await fetchJson(`/api/search/relations?${params}`);
    if (requestId !== state.relationRequest) return;
    state.relations = payload.relations || [];
    if (payload.missing?.length) {
      toast(`관계 분석에서 ${payload.missing.length}개 문서를 찾지 못했습니다.`, "error");
    }
  } catch (error) {
    if (requestId !== state.relationRequest) return;
    state.relations = [];
    toast(`관계 분석 실패: ${error.message}`, "error");
  }
  state.relationBusy = false;
  renderGraph();
  renderEvidence();
}

function graphPositions(width, height, count) {
  const positions = [];
  if (count === 1) {
    return [{ x: width / 2, y: height / 2 }];
  }
  if (count <= 4) {
    const radiusX = Math.min(width * 0.29, 190);
    const radiusY = Math.min(height * 0.29, 120);
    for (let index = 0; index < count; index += 1) {
      const angle = -Math.PI / 2 + (Math.PI * 2 * index) / count;
      positions.push({
        x: width / 2 + Math.cos(angle) * radiusX,
        y: height / 2 + Math.sin(angle) * radiusY,
      });
    }
    return positions;
  }

  const columns = width < 520 ? 2 : 3;
  const rows = Math.ceil(count / columns);
  const padX = 92;
  const padY = 58;
  for (let index = 0; index < count; index += 1) {
    const column = index % columns;
    const row = Math.floor(index / columns);
    positions.push({
      x: padX + (column * (width - padX * 2)) / Math.max(1, columns - 1),
      y: padY + (row * (height - padY * 2)) / Math.max(1, rows - 1),
    });
  }
  return positions;
}

function renderGraph() {
  const graph = $("#relationGraph");
  const empty = $("#relationEmpty");
  const surface = $("#relationSurface");
  const width = Math.max(surface.clientWidth, 360);
  const height = surface.clientHeight || 420;
  graph.setAttribute("viewBox", `0 0 ${width} ${height}`);
  graph.replaceChildren();

  if (!state.selected.length) {
    graph.setAttribute("hidden", "");
    empty.removeAttribute("hidden");
    $("#relationSummary").textContent = "문서를 2개 이상 선택하면 연결 근거를 분석합니다.";
    updateSummary();
    return;
  }

  graph.removeAttribute("hidden");
  empty.setAttribute("hidden", "");
  const positions = graphPositions(width, height, state.selected.length);
  const byId = new Map(state.selected.map((id, index) => [id, positions[index]]));

  const defs = svgElement("defs");
  const marker = svgElement("marker", {
    id: "arrow-chain",
    viewBox: "0 0 10 10",
    refX: "8",
    refY: "5",
    markerWidth: "5",
    markerHeight: "5",
    orient: "auto-start-reverse",
  });
  marker.append(svgElement("path", { d: "M 0 0 L 10 5 L 0 10 z", fill: "#0f9f72" }));
  defs.append(marker);
  graph.append(defs);

  const pairCounts = new Map();
  state.relations.forEach((relation) => {
    const source = byId.get(relation.source);
    const target = byId.get(relation.target);
    if (!source || !target) return;
    const pairKey = [relation.source, relation.target].sort().join("|");
    const pairIndex = pairCounts.get(pairKey) || 0;
    pairCounts.set(pairKey, pairIndex + 1);

    const dx = target.x - source.x;
    const dy = target.y - source.y;
    const length = Math.max(Math.hypot(dx, dy), 1);
    const offset = (pairIndex - 0.5) * 11;
    const controlX = (source.x + target.x) / 2 - (dy / length) * offset;
    const controlY = (source.y + target.y) / 2 + (dx / length) * offset;
    const path = svgElement("path", {
      d: `M ${source.x} ${source.y} Q ${controlX} ${controlY} ${target.x} ${target.y}`,
      class: "graph-edge",
      "data-tone": relationTones[relation.type] || "domain",
    });
    if (relation.type === "io-chain") path.setAttribute("marker-end", "url(#arrow-chain)");
    const title = svgElement("title");
    title.textContent = `${relationLabels[relation.type] || relation.type}: ${(relation.evidence || []).join(", ")}`;
    path.append(title);
    graph.append(path);
  });

  const nodeWidth = 160;
  const nodeHeight = 62;
  state.selected.forEach((serviceId, index) => {
    const position = positions[index];
    const group = svgElement("g", {
      class: "graph-node",
      transform: `translate(${position.x - nodeWidth / 2}, ${position.y - nodeHeight / 2})`,
      tabindex: "0",
      role: "button",
      "aria-label": `${apiName(serviceId)} 문서 상세 보기`,
    });
    group.append(svgElement("rect", { width: nodeWidth, height: nodeHeight, rx: "5" }));
    group.append(
      svgElement("rect", {
        class: "node-accent",
        width: "3",
        height: nodeHeight,
        rx: "1.5",
      }),
    );
    const indexText = svgElement("text", {
      class: "node-index",
      x: "12",
      y: "16",
    });
    indexText.textContent = `API ${String(index + 1).padStart(2, "0")}`;
    group.append(indexText);

    const titleText = svgElement("text", {
      class: "node-title",
      x: "12",
      y: "33",
    });
    titleText.textContent = shortText(apiName(serviceId), 11);
    group.append(titleText);

    const providerText = svgElement("text", {
      class: "node-provider",
      x: "12",
      y: "48",
    });
    providerText.textContent = shortText(apiProvider(serviceId), 13);
    group.append(providerText);

    const open = () => showDetail(serviceId);
    group.addEventListener("click", open);
    group.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        open();
      }
    });
    graph.append(group);
  });

  $("#relationSummary").textContent =
    state.selected.length < 2
      ? "문서를 하나 더 선택하면 연결 근거를 분석합니다."
      : `${state.selected.length}개 문서에서 ${state.relations.length}개 관계를 발견했습니다.`;
  updateSummary();
}

function renderEvidence() {
  const target = $("#relationEvidenceList");
  target.replaceChildren();
  $("#relationEvidenceCount").textContent = `${state.relations.length}건`;
  if (!state.relations.length) {
    target.className = "";
    target.append(
      element("p", {
        className: "muted-copy",
        text: state.selected.length >= 2
          ? "현재 문서 조합에서 자동 도출된 관계가 없습니다. 직접 조합 검토는 계속할 수 있습니다."
          : "관계가 발견되면 문서 필드와 기관·분야 근거를 표시합니다.",
      }),
    );
    updateSummary();
    return;
  }

  target.className = "relation-evidence-list";
  state.relations.forEach((relation) => {
    const evidence = (relation.evidence || []).join(" · ") || "근거 정보 없음";
    target.append(
      element(
        "article",
        {
          className: "evidence-card",
          attrs: { "data-tone": relationTones[relation.type] || "domain" },
        },
        [
          element("div", { className: "evidence-card__top" }, [
            element("strong", { text: relationLabels[relation.type] || relation.type }),
            element("span", {
              text: `${Math.round(Number(relation.confidence || 0) * 100)}%`,
            }),
          ]),
          element("p", { text: evidence }),
        ],
      ),
    );
  });
  updateSummary();
}

function appendDetailSection(root, title, rows, kind) {
  const section = element("section", { className: "detail-section" });
  section.append(element("h3", { text: title }));
  if (!rows?.length) {
    section.append(element("p", { className: "muted-copy", text: "표시할 항목이 없습니다." }));
    root.append(section);
    return;
  }
  const container = element("div", { className: kind === "field" ? "field-grid" : "" });
  rows.slice(0, 24).forEach((row) => {
    if (kind === "endpoint") {
      container.append(
        element("div", { className: "endpoint-row" }, [
          element("code", { text: row.method || "GET" }),
          element("div", {}, [
            element("code", { text: row.path || "-" }),
            element("br"),
            element("span", { text: row.summary || row.description || "" }),
          ]),
        ]),
      );
    } else {
      container.append(
        element("div", { className: "field-row" }, [
          element("code", { text: row.name || row.key || "-" }),
          element("span", {
            text: row.description || row.desc || (row.required ? "필수 입력" : ""),
          }),
        ]),
      );
    }
  });
  section.append(container);
  root.append(section);
}

function renderDetail(detail) {
  $("#detailServiceId").textContent = detail.service_id || "API DOCUMENT";
  $("#detailTitle").textContent = detail.name || "문서 상세";
  $("#detailProvider").textContent =
    [detail.provider_agency_name, detail.category].filter(Boolean).join(" · ");

  const body = $("#detailBody");
  body.replaceChildren();
  body.append(
    element("p", {
      className: "detail-description",
      text: detail.description || "문서 설명이 제공되지 않았습니다.",
    }),
  );

  const endpoints = detail.endpoints || [];
  const requestFields = detail.request_fields || [];
  const responseFields = detail.response_fields || [];
  body.append(
    element("div", { className: "detail-stats" }, [
      element("div", {}, [
        element("strong", { text: String(endpoints.length) }),
        element("span", { text: "엔드포인트" }),
      ]),
      element("div", {}, [
        element("strong", { text: String(requestFields.length) }),
        element("span", { text: "요청 필드" }),
      ]),
      element("div", {}, [
        element("strong", { text: String(responseFields.length) }),
        element("span", { text: "응답 필드" }),
      ]),
    ]),
  );
  appendDetailSection(body, "엔드포인트", endpoints, "endpoint");
  appendDetailSection(body, "요청 필드", requestFields, "field");
  appendDetailSection(body, "응답 필드", responseFields, "field");

  if (detail.source?.url) {
    body.append(
      element("a", {
        className: "source-link",
        text: "공식 데이터 출처 열기 ↗",
        attrs: {
          href: detail.source.url,
          target: "_blank",
          rel: "noreferrer",
        },
      }),
    );
  }
}

async function showDetail(serviceId) {
  const dialog = $("#detailDialog");
  $("#detailServiceId").textContent = serviceId;
  $("#detailTitle").textContent = "문서를 불러오는 중입니다.";
  $("#detailProvider").textContent = "";
  $("#detailBody").replaceChildren(
    element("p", { className: "muted-copy", text: "상세 문서와 필드 정보를 확인하고 있습니다." }),
  );
  if (!dialog.open) dialog.showModal();
  try {
    const detail = await ensureDetail(serviceId);
    renderDetail(detail);
  } catch (error) {
    $("#detailTitle").textContent = "문서를 불러오지 못했습니다.";
    $("#detailBody").replaceChildren(
      element("div", { className: "error-panel", text: error.message }),
    );
  }
}

function setComposeBusy(busy) {
  state.composeBusy = busy;
  const button = $("#composeButton");
  button.disabled = busy || state.selected.length === 0;
  button.textContent = busy ? "조합 분석 중…" : "조합안 만들기";
  renderResults();
  renderSelected();
}

function formatElapsed(seconds) {
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`;
}

function updateAnalysisStatus() {
  const seconds = Math.max(
    0,
    Math.floor((performance.now() - state.analysisStartedAt) / 1000),
  );
  let title = "조합 요청 준비 중";
  let detail = `선택한 API 문서 ${state.selected.length}건을 조합기에 전달하고 있습니다.`;
  if (seconds >= 5 && seconds < 30) {
    title = "API 연결 구조 추론 중";
    detail = "Thinking 모드로 API 간 입출력과 연결 흐름을 추론하고 있습니다.";
  } else if (seconds >= 30 && seconds < 90) {
    title = "행정 서비스 흐름 구성 중";
    detail = "서비스 단계, 필요한 사용자 입력과 주의사항을 구성하고 있습니다.";
  } else if (seconds >= 90) {
    title = "심층 분석 계속 진행 중";
    detail = "분석이 계속 진행 중입니다. 서버는 최대 210초까지 응답을 기다립니다.";
  }
  $("#analysisElapsed").textContent = formatElapsed(seconds);
  $("#analysisStatusTitle").textContent = title;
  $("#analysisStatusDetail").textContent = detail;
  $("#stepCompose small").textContent = title;
}

function beginAnalysisStatus() {
  state.analysisStartedAt = performance.now();
  $("#analysisStatus").hidden = false;
  $("#composeResult").hidden = true;
  $("#composePlaceholder").hidden = true;
  updateAnalysisStatus();
  if (state.analysisTimer !== null) window.clearInterval(state.analysisTimer);
  state.analysisTimer = window.setInterval(updateAnalysisStatus, 1000);
}

function endAnalysisStatus() {
  if (state.analysisTimer !== null) {
    window.clearInterval(state.analysisTimer);
    state.analysisTimer = null;
  }
  $("#analysisStatus").hidden = true;
}

async function composePlan() {
  const question = $("#composeQuestion").value.trim();
  if (!state.selected.length || !question) return;
  const requestId = ++state.composeRequest;
  setComposeBusy(true);
  beginAnalysisStatus();
  $("#composeMeta").replaceChildren();
  try {
    const payload = await fetchJson("/api/combiner/compose", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        service_ids: state.selected,
        question,
      }),
    });
    if (requestId !== state.composeRequest) return;
    endAnalysisStatus();
    $("#composeResult").hidden = false;
    state.planText = payload.suggestion || "";
    const meta = $("#composeMeta");
    meta.replaceChildren();
    (payload.domains || []).forEach((domain) => {
      meta.append(element("span", { text: domain }));
    });
    if (payload.model) meta.append(element("span", { text: payload.model }));
    if (payload.elapsed_ms !== undefined) {
      meta.append(element("span", { text: `${payload.elapsed_ms}ms` }));
    }
    if (payload.warning) {
      meta.append(
        element("span", {
          text: payload.warning,
          attrs: { "data-tone": "warning" },
        }),
      );
    }
    if (payload.missing?.length) {
      meta.append(
        element("span", {
          text: `누락 ${payload.missing.length}건`,
          attrs: { "data-tone": "warning" },
        }),
      );
    }
    $("#composeResultText").textContent = state.planText || "생성된 제안이 없습니다.";
    updateSummary();
  } catch (error) {
    if (requestId !== state.composeRequest) return;
    endAnalysisStatus();
    $("#composeResult").hidden = false;
    state.planText = "";
    $("#composeMeta").replaceChildren(
      element("span", { text: "연결 오류", attrs: { "data-tone": "warning" } }),
    );
    $("#composeResultText").replaceChildren(
      element("div", {
        className: "error-panel",
        text: `${error.message} 검색과 관계 검토는 계속 사용할 수 있습니다.`,
      }),
    );
    toast(error.message, "error");
  } finally {
    if (requestId === state.composeRequest) {
      endAnalysisStatus();
      setComposeBusy(false);
    }
  }
}

async function checkHealth(showFeedback = false) {
  const dot = $("#overallStatusDot");
  const label = $("#overallStatusText");
  label.textContent = "상태 확인 중";
  dot.dataset.state = "";
  try {
    state.health = await fetchJson("/api/workspace/health");
    dot.dataset.state = state.health.state;
    label.textContent =
      state.health.state === "ready"
        ? "모든 서비스 연결"
        : state.health.state === "degraded"
          ? "일부 서비스 연결"
          : "서비스 연결 안 됨";
    if (showFeedback) toast(label.textContent);
  } catch {
    state.health = {
      state: "offline",
      services: {
        search: { reachable: false },
        combiner: { reachable: false },
      },
    };
    dot.dataset.state = "offline";
    label.textContent = "통합 서버 연결 안 됨";
    if (showFeedback) toast(label.textContent, "error");
  }
  renderStatus();
}

function renderStatus() {
  const target = $("#statusDetails");
  target.replaceChildren();
  const services = state.health?.services || {};
  const definitions = [
    ["search", "API 문서 검색", "자연어·렉시컬 검색과 관계 분석"],
    ["combiner", "API 문서 조합", "Ollama 기반 서비스 계획 초안"],
  ];
  definitions.forEach(([key, title, description]) => {
    const status = services[key] || {};
    const payload = status.payload || {};
    const thinking = payload.generation?.think ? " · THINKING ON" : "";
    const details = key === "search" && status.reachable
      ? `${description} · 문서 ${Number(payload.services_total || payload.lexical_corpus_total || 0).toLocaleString("ko-KR")}건`
      : key === "combiner" && status.reachable
        ? `${description} · ${payload.model || "모델 확인됨"}${thinking}`
        : description;
    target.append(
      element("div", { className: "status-card" }, [
        element("div", {}, [
          element("strong", { text: title }),
          element("small", { text: details }),
        ]),
        element("span", {
          text: status.reachable ? "연결됨" : "연결 안 됨",
          attrs: { "data-ready": status.reachable ? "true" : "false" },
        }),
      ]),
    );
  });
}

function clearResults() {
  state.results = [];
  state.resultTotal = 0;
  state.resultMode = "search";
  state.diagnostics = null;
  state.category = "";
  populateCategories();
  renderDiagnostics();
  renderResults();
}

function resetWorkspace() {
  state.results = [];
  state.resultTotal = 0;
  state.resultMode = "search";
  state.diagnostics = null;
  state.category = "";
  state.selected = [];
  state.relations = [];
  state.searchBusy = false;
  state.relationBusy = false;
  state.searchRequest += 1;
  state.relationRequest += 1;
  state.composeRequest += 1;
  state.planText = "";
  endAnalysisStatus();
  state.composeBusy = false;
  $("#searchInput").value = "";
  $("#composeQuestion").value = "이 API들을 조합하면 어떤 행정 서비스 계획을 만들 수 있나?";
  $("#composeResult").hidden = true;
  $("#composePlaceholder").hidden = false;
  populateCategories();
  renderDiagnostics();
  renderResults();
  renderSelected();
  renderGraph();
  renderEvidence();
  setComposeBusy(false);
  updateQuestionLength();
  toast("작업 공간을 초기화했습니다.");
}

function updateQuestionLength() {
  const value = $("#composeQuestion").value;
  $("#questionLength").textContent = `${value.length} / 500`;
}

function bindEvents() {
  $("#searchForm").addEventListener("submit", (event) => {
    event.preventDefault();
    const query = $("#searchInput").value.trim();
    if (query.length < 2) {
      toast("두 글자 이상의 검색어를 입력해 주세요.", "error");
      $("#searchInput").focus();
      return;
    }
    searchDocuments(query);
  });

  document.querySelectorAll("[data-example]").forEach((button) => {
    button.addEventListener("click", () => {
      $("#searchInput").value = button.dataset.example;
      searchDocuments(button.dataset.example);
    });
  });

  $("#catalogButton").addEventListener("click", browseCatalog);
  $("#clearResultsButton").addEventListener("click", clearResults);
  $("#resetButton").addEventListener("click", resetWorkspace);
  $("#categoryFilter").addEventListener("change", (event) => {
    state.category = event.target.value;
    renderResults();
  });

  $("#composeQuestion").addEventListener("input", updateQuestionLength);
  $("#composeForm").addEventListener("submit", (event) => {
    event.preventDefault();
    composePlan();
  });

  $("#copyPlanButton").addEventListener("click", async () => {
    if (!state.planText) return;
    try {
      await navigator.clipboard.writeText(state.planText);
      toast("조합 초안을 복사했습니다.");
    } catch {
      toast("브라우저에서 클립보드 사용을 허용해 주세요.", "error");
    }
  });

  $("#closeDetailButton").addEventListener("click", () => $("#detailDialog").close());
  $("#closeStatusButton").addEventListener("click", () => $("#statusDialog").close());
  $("#systemStateButton").addEventListener("click", () => {
    renderStatus();
    $("#statusDialog").showModal();
  });
  $("#refreshStatusButton").addEventListener("click", () => checkHealth(true));

  [$("#detailDialog"), $("#statusDialog")].forEach((dialog) => {
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) dialog.close();
    });
  });

  let resizeFrame = 0;
  const observer = new ResizeObserver(() => {
    cancelAnimationFrame(resizeFrame);
    resizeFrame = requestAnimationFrame(renderGraph);
  });
  observer.observe($("#relationSurface"));
}

function init() {
  bindEvents();
  populateCategories();
  renderResults();
  renderSelected();
  renderGraph();
  renderEvidence();
  updateQuestionLength();
  checkHealth();
  window.setInterval(checkHealth, 30000);
}

init();
