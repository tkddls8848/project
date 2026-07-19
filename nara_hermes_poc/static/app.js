const form = document.querySelector("#design-form");
const queryInput = document.querySelector("#query");
const submitButton = document.querySelector("#submit-button");
const resultsSection = document.querySelector("#results");
const searchStatus = document.querySelector("#search-status");
const combinerStatus = document.querySelector("#combiner-status");
const flowItems = [...document.querySelectorAll("[data-flow]")];

const stageLabels = {
  search: "문서 검색",
  detail: "상세 검토",
  relations: "관계 분석",
  compose: "계획 생성",
};

function setServiceStatus(element, online, detail) {
  element.classList.toggle("online", online);
  element.classList.toggle("offline", !online);
  element.querySelector("small").textContent = detail;
}

async function checkHealth() {
  setServiceStatus(searchStatus, false, "확인 중 · :8000");
  setServiceStatus(combinerStatus, false, "확인 중 · :8003");
  try {
    const response = await fetch("/health");
    const body = await response.json();
    if (!response.ok) throw new Error(body.message || "연결 실패");
    const search = body.upstreams?.search || {};
    const combiner = body.upstreams?.combiner || {};
    const searchOnline = Boolean(search.ok || search.lexical_corpus_total);
    setServiceStatus(
      searchStatus,
      searchOnline,
      searchOnline ? `연결됨 · 문서 ${search.services_total || search.lexical_corpus_total || 0}개` : "인덱스 확인 필요 · :8000",
    );
    setServiceStatus(
      combinerStatus,
      Boolean(combiner.ok),
      combiner.ok ? `연결됨 · ${combiner.model || "모델 준비"}` : "응답 이상 · :8003",
    );
  } catch (error) {
    setServiceStatus(searchStatus, false, "연결 안 됨 · :8000");
    setServiceStatus(combinerStatus, false, "연결 안 됨 · :8003");
  }
}

function parseServiceIds() {
  return document.querySelector("#service-ids").value
    .split(/[,\n]/)
    .map((value) => value.trim())
    .filter(Boolean)
    .slice(0, 3);
}

function setBusy(isBusy) {
  submitButton.disabled = isBusy;
  submitButton.firstElementChild.textContent = isBusy ? "에이전트가 분석 중입니다" : "서비스 계획 만들기";
  if (isBusy) {
    flowItems.forEach((item, index) => item.classList.toggle("active", index === 0));
  }
}

function clearElement(element) {
  while (element.firstChild) element.firstChild.remove();
}

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function renderStages(stages = []) {
  const container = document.querySelector("#stage-strip");
  clearElement(container);
  stages.forEach((stage) => {
    const card = element("div", `stage ${stage.status}`);
    card.append(
      element("strong", "", `${stage.status === "completed" ? "✓ " : ""}${stageLabels[stage.name] || stage.name}`),
      element("small", "", stage.message),
    );
    container.append(card);
  });

  const completed = new Set(stages.filter((stage) => stage.status === "completed").map((stage) => stage.name));
  flowItems.forEach((item) => {
    const name = item.dataset.flow;
    const active = name === "detail"
      ? completed.has("detail") || completed.has("relations")
      : completed.has(name);
    item.classList.toggle("active", active);
  });
}

function renderWarnings(warnings = []) {
  const box = document.querySelector("#warnings");
  if (!warnings.length) {
    box.classList.add("hidden");
    box.textContent = "";
    return;
  }
  box.textContent = `검토 필요: ${warnings.join(" · ")}`;
  box.classList.remove("hidden");
}

function renderDocuments(search, selectedIds) {
  const list = document.querySelector("#document-list");
  const summary = document.querySelector("#search-summary");
  const documents = search?.results || [];
  const diagnostics = search?.diagnostics || {};
  clearElement(list);
  summary.textContent = `${documents.length}개 발견 · ${diagnostics.fusion || "검색"} 방식`;

  if (!documents.length) {
    list.append(element("div", "empty-state", "관련 문서를 찾지 못했습니다. 검색어를 더 구체적으로 작성하거나 벡터 검색을 꺼보세요."));
    return;
  }

  documents.forEach((doc) => {
    const card = element("article", `document ${selectedIds.includes(doc.service_id) ? "selected" : ""}`);
    const title = element("h4", "", doc.name || "이름 없는 API 문서");
    const description = element("p", "", doc.description || "문서 설명이 없습니다.");
    const meta = element("div", "document-meta");
    meta.append(
      element("span", "", selectedIds.includes(doc.service_id) ? "선택됨" : "후보"),
      element("span", "", doc.service_id || ""),
    );
    card.append(title, description, meta);
    list.append(card);
  });
}

function renderRelations(relations) {
  const target = document.querySelector("#relation-result");
  if (!relations) {
    target.textContent = "선택 문서가 한 개이거나 관계 분석을 생략했습니다.";
    return;
  }
  const items = relations.relations || [];
  if (!items.length) {
    target.textContent = "선택 문서 사이에서 파생 관계를 찾지 못했습니다. 독립 단계로 검토하세요.";
    return;
  }
  target.textContent = JSON.stringify(items, null, 2);
}

function renderPlan(plan) {
  const target = document.querySelector("#plan-result");
  if (!plan) {
    target.textContent = "계획 생성을 생략했거나 선택된 문서가 없습니다.";
    return;
  }
  target.textContent = plan.suggestion || JSON.stringify(plan, null, 2);
}

function renderError(error) {
  resultsSection.classList.remove("hidden");
  renderStages([{ name: "search", status: "failed", message: error.message }]);
  renderWarnings([error.message]);
  document.querySelector("#search-summary").textContent = "요청 처리 실패";
  document.querySelector("#document-list").replaceChildren(
    element("div", "empty-state", "상단의 서비스 연결 상태를 확인한 뒤 다시 시도하세요."),
  );
  document.querySelector("#relation-result").textContent = "분석되지 않았습니다.";
  document.querySelector("#plan-result").textContent = "생성되지 않았습니다.";
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  setBusy(true);
  resultsSection.classList.add("hidden");

  const payload = {
    query: queryInput.value.trim(),
    top_k: Number(document.querySelector("#top-k").value),
    use_vector: document.querySelector("#use-vector").checked,
    selected_service_ids: parseServiceIds(),
    compose: document.querySelector("#compose").checked,
  };

  try {
    const response = await fetch("/design", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.message || body.detail || "요청 처리에 실패했습니다.");

    renderStages(body.stages);
    renderWarnings(body.warnings);
    renderDocuments(body.search, body.selected_service_ids);
    renderRelations(body.relations);
    renderPlan(body.plan);
    resultsSection.classList.remove("hidden");
    resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    renderError(error);
    resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
  } finally {
    setBusy(false);
  }
});

document.querySelectorAll("[data-example]").forEach((button) => {
  button.addEventListener("click", () => {
    queryInput.value = button.dataset.example;
    queryInput.focus();
  });
});

document.querySelector("#refresh-health").addEventListener("click", checkHealth);
document.querySelector("#reset-button").addEventListener("click", () => {
  resultsSection.classList.add("hidden");
  queryInput.focus();
  window.scrollTo({ top: document.querySelector(".workspace").offsetTop - 20, behavior: "smooth" });
});

checkHealth();
