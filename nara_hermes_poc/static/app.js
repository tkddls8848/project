const $ = (selector) => document.querySelector(selector);

const form = $("#design-form");
const queryInput = $("#query");
const submitButton = $("#submit-button");
const stopButton = $("#stop-button");
const runBadge = $("#run-mode");
const progress = $("#agent-progress");
let currentRunId = null;
let source = null;
let eventRows = new Map();

const labels = {
  queued: "실행 준비",
  agent: "Hermes MCP",
  search: "문서 탐색",
  detail: "상세 확인",
  relations: "관계 분석",
  compose: "계획 생성",
  critic: "근거 검증",
  completed: "실행 완료",
  failed: "실행 실패",
  cancelled: "실행 중단",
};

const criticLabels = {
  pass: "근거 검증 통과",
  evidence_gap: "근거 부족",
  contradiction: "근거 모순",
  failed: "검증 실패 (결과는 유효)",
  skipped: "검증 생략",
};

function element(tag, options = {}, children = []) {
  const node = document.createElement(tag);
  if (options.className) node.className = options.className;
  if (options.text !== undefined) node.textContent = options.text;
  Object.entries(options.attrs || {}).forEach(([key, value]) => node.setAttribute(key, value));
  (Array.isArray(children) ? children : [children]).filter(Boolean).forEach((child) => node.append(child));
  return node;
}

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.message || body.detail || `요청 실패 (HTTP ${response.status})`);
  return body;
}

function setRunState(status, label = status) {
  runBadge.textContent = label;
  runBadge.className = `run-badge ${status}`;
  submitButton.disabled = status === "running" || status === "queued";
  stopButton.disabled = status !== "running" && status !== "queued";
}

async function refreshHealth() {
  const button = $("#refresh-health");
  const text = $("#system-state");
  button.classList.remove("online", "offline");
  text.textContent = "상태 확인 중";
  try {
    const [health, agent] = await Promise.all([fetchJson("/health"), fetchJson("/agent/health")]);
    const available = Boolean(health.upstreams?.search) && Boolean(health.upstreams?.combiner) && agent.ok;
    button.classList.add(available ? "online" : "offline");
    text.textContent = available ? `Nara · Hermes ${agent.profile}` : "일부 서비스 확인 필요";
  } catch {
    button.classList.add("offline");
    text.textContent = "서비스 연결 확인 필요";
  }
}

function parseIds() {
  return $("#service-ids").value.split(/[,\n]/).map((item) => item.trim()).filter(Boolean).slice(0, 3);
}

function renderEvent(event) {
  let row = eventRows.get(event.name);
  if (!row) {
    row = element("div", { className: "progress-item" }, [element("i"), element("div", {}, [element("strong", { text: labels[event.name] || event.name }), element("small", { text: event.message })]), element("time", { text: "" })]);
    eventRows.set(event.name, row);
    progress.append(row);
  }
  row.className = `progress-item ${event.status}`;
  row.querySelector("small").textContent = event.message;
  row.querySelector("time").textContent = `#${event.sequence}`;
  updateWorkflow(event);
}

function updateWorkflow(event) {
  const stage = event.name === "agent" ? "search" : event.name;
  if (!["search", "detail", "relations", "compose"].includes(stage)) return;
  const target = document.querySelector(`[data-step="${stage}"]`);
  if (!target) return;
  target.classList.remove("active", "completed", "failed");
  target.classList.add(event.status === "running" ? "active" : event.status === "failed" ? "failed" : event.status === "completed" || event.status === "skipped" ? "completed" : "active");
}

function resetWorkflow() {
  document.querySelectorAll(".workflow-step").forEach((node, index) => node.className = `workflow-step${index === 0 ? " active" : ""}`);
}

function renderDocuments(search, selectedIds) {
  const list = $("#document-list");
  const docs = search?.results || [];
  list.replaceChildren();
  $("#search-summary").textContent = `${docs.length}개 문서 · ${search?.diagnostics?.fusion || "검색"}`;
  if (!docs.length) {
    list.append(element("div", { className: "empty-state", text: "관련 API 문서를 찾지 못했습니다." }));
    return;
  }
  docs.forEach((doc) => {
    const card = element("article", { className: `document ${selectedIds.includes(doc.service_id) ? "selected" : ""}` });
    card.append(element("h4", { text: doc.name || doc.service_id }), element("p", { text: doc.description || "설명이 없습니다." }), element("div", { className: "document-meta" }, [element("span", { text: selectedIds.includes(doc.service_id) ? "선택됨" : "후보" }), element("span", { text: doc.service_id || "" })]));
    list.append(card);
  });
}

function renderSelected(ids, details) {
  const list = $("#selected-list");
  list.replaceChildren();
  $("#selected-count").textContent = `${ids.length} / 3`;
  if (!ids.length) { list.textContent = "선택된 API가 없습니다."; return; }
  ids.forEach((id, index) => list.append(element("span", { className: "selected-chip", text: details[index]?.name || id })));
}

function renderResult(result, hermes) {
  if (!result) return;
  renderDocuments(result.search, result.selected_service_ids || []);
  renderSelected(result.selected_service_ids || [], result.details || []);
  const relations = result.relations?.relations || [];
  $("#relation-result").textContent = relations.length ? JSON.stringify(relations, null, 2) : "관계 근거가 없거나 문서가 한 개여서 관계 분석을 생략했습니다.";
  $("#plan-result").textContent = result.plan?.suggestion || "계획 생성을 생략했거나 생성하지 못했습니다.";
  const warnings = [...(result.warnings || [])];
  if (hermes?.status && hermes.status !== "called") warnings.unshift(`Hermes MCP 상태: ${hermes.status}`);
  const box = $("#warnings");
  box.textContent = warnings.join(" · ");
  box.classList.toggle("hidden", !warnings.length);
}

function renderCritic(critic) {
  const box = $("#critic-report");
  box.replaceChildren();
  if (!critic) { box.classList.add("hidden"); return; }
  const issues = (critic.findings || []).filter((finding) => finding.severity !== "info");
  const label = criticLabels[critic.verdict] || critic.verdict;
  box.append(element("span", { className: `critic-badge ${critic.verdict}`, text: issues.length ? `${label} ${issues.length}건` : label }));
  if (issues.length) {
    const list = element("ul", { className: "critic-findings" });
    issues.forEach((finding) => list.append(element("li", {}, [element("strong", { text: `${finding.check} · ${finding.target}` }), element("small", { text: finding.message })])));
    box.append(list);
  }
  box.classList.remove("hidden");
}

async function finishRun() {
  if (!currentRunId) return;
  try {
    const run = await fetchJson(`/agent/design-runs/${currentRunId}`);
    setRunState(run.status, run.status === "completed" ? "완료" : run.status === "failed" ? "실패" : "중단됨");
    renderResult(run.result, run.hermes);
    renderCritic(run.critic);
    $("#export-flow").classList.toggle("hidden", run.status !== "completed" || !run.result);
    $("#agent-summary").textContent = run.hermes?.status === "called" ? "Hermes MCP 검색 호출을 확인하고 구조화된 결과를 완성했습니다." : "구조화된 읽기 전용 결과를 완성했습니다.";
  } catch (error) {
    setRunState("failed", "실패");
    $("#agent-summary").textContent = error.message;
  }
}

function connectEvents(runId) {
  if (source) source.close();
  source = new EventSource(`/agent/design-runs/${runId}/events`);
  source.addEventListener("progress", async (message) => {
    const event = JSON.parse(message.data);
    renderEvent(event);
    if (["completed", "failed", "cancelled"].includes(event.name)) {
      source.close();
      await finishRun();
    }
  });
  source.onerror = async () => {
    source.close();
    await finishRun();
  };
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const query = queryInput.value.trim();
  if (query.length < 2) { queryInput.focus(); return; }
  eventRows = new Map(); progress.replaceChildren(); resetWorkflow();
  $("#warnings").classList.add("hidden");
  $("#critic-report").classList.add("hidden");
  $("#export-flow").classList.add("hidden");
  $("#agent-summary").textContent = "에이전트 실행을 생성하고 있습니다.";
  setRunState("queued", "준비 중");
  try {
    const run = await fetchJson("/agent/design-runs", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ query, top_k: Number($("#top-k").value), use_vector: $("#use-vector").checked, compose: $("#compose").checked, selected_service_ids: parseIds() }) });
    currentRunId = run.run_id;
    run.events.forEach(renderEvent);
    setRunState("running", "실행 중");
    connectEvents(run.run_id);
  } catch (error) {
    setRunState("failed", "실패");
    progress.replaceChildren(element("div", { className: "empty-state", text: error.message }));
  }
});

stopButton.addEventListener("click", async () => { if (currentRunId) await fetchJson(`/agent/design-runs/${currentRunId}/stop`, { method: "POST" }); });
$("#export-flow").addEventListener("click", () => { if (currentRunId) window.open(`/agent/design-runs/${currentRunId}/flow`, "_blank"); });
$("#reset-button").addEventListener("click", () => { if (source) source.close(); currentRunId = null; eventRows = new Map(); progress.replaceChildren(element("div", { className: "empty-state", text: "에이전트 실행 시 MCP 호출과 각 처리 단계가 실시간으로 표시됩니다." })); $("#document-list").replaceChildren(element("div", { className: "empty-state", text: "검색 결과가 여기에 표시됩니다." })); $("#relation-result").textContent = "선택된 문서가 두 개 이상이면 관계 분석 결과가 표시됩니다."; $("#plan-result").textContent = "계획 초안이 여기에 표시됩니다."; $("#selected-list").textContent = "선택된 API가 없습니다."; $("#selected-count").textContent = "0 / 3"; $("#search-summary").textContent = "요청을 입력하면 검색된 문서가 표시됩니다."; $("#agent-summary").textContent = "아직 실행된 도구 호출이 없습니다."; $("#critic-report").classList.add("hidden"); $("#export-flow").classList.add("hidden"); setRunState("idle", "대기"); resetWorkflow(); });
document.querySelectorAll("[data-example]").forEach((button) => button.addEventListener("click", () => { queryInput.value = button.dataset.example; queryInput.focus(); }));
$("#refresh-health").addEventListener("click", refreshHealth);
setRunState("idle", "대기");
refreshHealth();
