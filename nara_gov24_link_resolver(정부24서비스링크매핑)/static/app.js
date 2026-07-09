const state = {
  summary: null,
  logs: "",
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

function setStatus(message, type = "") {
  const box = $("#statusBox");
  box.textContent = message;
  box.className = `status-box ${type}`.trim();
}

function formatPercent(value) {
  const number = Number(value || 0);
  return `${Math.round(number * 100)}%`;
}

function escapeText(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok || payload.ok === false) {
    throw new Error(payload.error || `HTTP ${response.status}`);
  }
  return payload;
}

async function loadSummary() {
  const payload = await requestJson("/api/summary");
  state.summary = payload.summary;
  render();
}

function renderMetrics() {
  const counts = state.summary?.counts || {};
  $("#metricCandidates").textContent = counts.candidates ?? 0;
  $("#metricReviewed").textContent = counts.reviewed ?? 0;
  $("#metricPending").textContent = counts.pending ?? 0;
  $("#metricMetadata").textContent = counts.metadata ?? 0;
  $("#metricUrlRate").textContent = formatPercent(counts.url_validity_rate);
  $("#metricErrors").textContent = (counts.schema_errors ?? 0) + (counts.broken_links ?? 0);
}

function candidateMatches(record) {
  const query = $("#searchInput").value.trim().toLowerCase();
  const status = $("#statusFilter").value;
  const source = $("#sourceFilter").value;
  const text = [
    record.candidate_id,
    record.title,
    record.url,
    record.matched_query,
    record.matched_service_name,
    record.notes,
  ].join(" ").toLowerCase();

  return (!query || text.includes(query))
    && (!status || record.review_status === status)
    && (!source || record.source === source);
}

function renderCandidates() {
  const rows = $("#candidateRows");
  const candidates = (state.summary?.candidates || []).filter(candidateMatches);
  if (!candidates.length) {
    rows.innerHTML = `<tr><td class="empty" colspan="6">표시할 후보가 없습니다.</td></tr>`;
    return;
  }

  rows.innerHTML = candidates.map((record) => {
    const confidence = Number(record.confidence || 0);
    const width = Math.max(0, Math.min(100, confidence * 100));
    return `
      <tr>
        <td class="id-cell">${escapeText(record.candidate_id)}</td>
        <td class="title-cell">${escapeText(record.title)}</td>
        <td class="url-cell"><a href="${escapeText(record.url)}" target="_blank" rel="noreferrer">${escapeText(record.url)}</a></td>
        <td>${escapeText(record.source)}</td>
        <td>
          <div class="confidence">
            <span>${confidence.toFixed(2)}</span>
            <div class="confidence-bar"><span style="width:${width}%"></span></div>
          </div>
        </td>
        <td>
          <select class="status-select" data-candidate="${encodeURIComponent(record.candidate_id)}">
            ${["pending", "reviewed", "rejected"].map((status) => (
              `<option value="${status}" ${record.review_status === status ? "selected" : ""}>${status}</option>`
            )).join("")}
          </select>
        </td>
      </tr>
    `;
  }).join("");

  $$(".status-select").forEach((select) => {
    select.addEventListener("change", handleStatusChange);
  });
}

function renderMetadata() {
  const rows = $("#metadataRows");
  const metadata = state.summary?.metadata || [];
  if (!metadata.length) {
    rows.innerHTML = `<tr><td class="empty" colspan="6">생성된 메타데이터가 없습니다.</td></tr>`;
    return;
  }

  rows.innerHTML = metadata.map((record) => `
    <tr>
      <td class="id-cell">${escapeText(record.link_id)}</td>
      <td class="title-cell">${escapeText(record.title)}</td>
      <td>${escapeText(record.link_type)}</td>
      <td>${(record.domain_ids || []).map((item) => `<span class="chip">${escapeText(item)}</span>`).join(" ")}</td>
      <td><span class="badge ${escapeText(record.review_status)}">${escapeText(record.review_status)}</span></td>
      <td class="url-cell"><a href="${escapeText(record.url)}" target="_blank" rel="noreferrer">${escapeText(record.url)}</a></td>
    </tr>
  `).join("");
}

function renderReport() {
  const summary = state.summary || {};
  const files = summary.files || {};
  const report = summary.report || {};

  $("#fileList").innerHTML = Object.entries(files).map(([label, info]) => `
    <div>
      <dt>${label}</dt>
      <dd>${info.exists ? `${escapeText(info.path)} · ${escapeText(info.modified_at)}` : `${escapeText(info.path)} · 없음`}</dd>
    </div>
  `).join("");

  const domains = Object.entries(summary.domain_counts || {})
    .sort((a, b) => b[1] - a[1]);
  $("#domainList").innerHTML = domains.length
    ? domains.map(([domain, count]) => `<span class="chip">${escapeText(domain)} ${count}</span>`).join("")
    : `<div class="empty">도메인 집계가 없습니다.</div>`;

  const details = [
    ...(summary.parse_errors || []),
    ...(report.schema_error_details || []),
    ...(report.broken_link_details || []),
  ];
  $("#reportDetails").innerHTML = details.length
    ? `<div class="issue-list">${details.map((item) => `<div class="issue">${escapeText(item)}</div>`).join("")}</div>`
    : `<div class="chip-list">
        <span class="chip">schema_errors ${report.schema_errors ?? 0}</span>
        <span class="chip">broken_links ${report.broken_links ?? 0}</span>
        <span class="chip">duplicate_urls ${report.duplicate_urls ?? 0}</span>
      </div>`;
}

function renderLogs() {
  $("#logOutput").textContent = state.logs || "실행 로그가 없습니다.";
}

function render() {
  renderMetrics();
  renderCandidates();
  renderMetadata();
  renderReport();
  renderLogs();
}

async function handleStatusChange(event) {
  const select = event.currentTarget;
  const candidateId = decodeURIComponent(select.dataset.candidate);
  select.disabled = true;
  try {
    const payload = await requestJson(`/api/candidates/${encodeURIComponent(candidateId)}`, {
      method: "PATCH",
      body: JSON.stringify({ review_status: select.value }),
    });
    state.summary = payload.summary;
    render();
    setStatus(`${candidateId} 상태 저장됨`, "ok");
  } catch (error) {
    setStatus(error.message, "error");
    await loadSummary();
  } finally {
    select.disabled = false;
  }
}

async function handleCandidateSubmit(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = Object.fromEntries(new FormData(form).entries());
  setStatus("후보 저장 중");
  try {
    const payload = await requestJson("/api/candidates", {
      method: "POST",
      body: JSON.stringify(data),
    });
    state.summary = payload.summary;
    form.reset();
    form.elements.source.value = "manual";
    form.elements.review_status.value = "pending";
    form.elements.confidence.value = "0.70";
    form.elements.match_reason.value = "title_keyword_overlap";
    render();
    setStatus(`${payload.record.candidate_id} 저장됨`, "ok");
  } catch (error) {
    setStatus(error.message, "error");
  }
}

function pipelineSteps(runType) {
  if (runType === "all") {
    return ["normalize", "match", "validate"];
  }
  return [runType];
}

async function handleRunClick(event) {
  const button = event.currentTarget;
  const steps = pipelineSteps(button.dataset.run);
  const buttons = $$("[data-run]");
  buttons.forEach((item) => { item.disabled = true; });
  setStatus(`${steps.join(", ")} 실행 중`);

  try {
    const payload = await requestJson("/api/run", {
      method: "POST",
      body: JSON.stringify({ steps }),
    });
    state.summary = payload.summary;
    state.logs = payload.pipeline.results.map((item) => {
      const chunks = [
        `# ${item.step} (exit ${item.returncode})`,
        item.stdout.trim(),
        item.stderr.trim(),
      ].filter(Boolean);
      return chunks.join("\n");
    }).join("\n\n");
    render();
    setStatus(payload.pipeline.ok ? "실행 완료" : "실행 실패", payload.pipeline.ok ? "ok" : "error");
    activateTab("logs");
  } catch (error) {
    setStatus(error.message, "error");
  } finally {
    buttons.forEach((item) => { item.disabled = false; });
  }
}

function activateTab(tabName) {
  $$(".tab").forEach((button) => {
    button.classList.toggle("active", button.dataset.tab === tabName);
  });
  $$(".tab-panel").forEach((panel) => {
    panel.classList.toggle("active", panel.id === `panel-${tabName}`);
  });
}

function wireEvents() {
  $("#candidateForm").addEventListener("submit", handleCandidateSubmit);
  $("#refreshButton").addEventListener("click", async () => {
    setStatus("새로고침 중");
    await loadSummary();
    setStatus("새로고침 완료", "ok");
  });
  $$("#searchInput, #statusFilter, #sourceFilter").forEach((input) => {
    input.addEventListener("input", renderCandidates);
  });
  $$(".tab").forEach((button) => {
    button.addEventListener("click", () => activateTab(button.dataset.tab));
  });
  $$("[data-run]").forEach((button) => {
    button.addEventListener("click", handleRunClick);
  });
}

wireEvents();
loadSummary()
  .then(() => setStatus("준비됨", "ok"))
  .catch((error) => setStatus(error.message, "error"));
