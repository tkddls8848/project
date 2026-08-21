const form = document.querySelector("#searchForm");
const queryInput = document.querySelector("#queryInput");
const topKInput = document.querySelector("#topKInput");
const resultsList = document.querySelector("#resultsList");
const resultCount = document.querySelector("#resultCount");
const statusLine = document.querySelector("#statusLine");
const healthText = document.querySelector("#healthText");
const detailEmpty = document.querySelector("#detailEmpty");
const detailView = document.querySelector("#detailView");
const searchButton = document.querySelector("#searchButton");
const buildCpuButton = document.querySelector("#buildCpuButton");
const buildGpuButton = document.querySelector("#buildGpuButton");
const buildButtons = [buildCpuButton, buildGpuButton];
const buildBar = document.querySelector("#buildBar");
const buildStatusEl = document.querySelector("#buildStatus");
const buildProgress = document.querySelector("#buildProgress");

let currentResults = [];
let buildPollTimer = null;

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function fieldList(fields, limit = 8) {
  if (!fields || fields.length === 0) return `<span class="muted">없음</span>`;
  return fields.slice(0, limit).map((field) => {
    const required = field.required ? `<span class="flag required">필수</span>` : "";
    const concept = field.term_canonical_ko ? `<span class="flag">${escapeHtml(field.term_canonical_ko)}</span>` : "";
    return `
      <li>
        <code>${escapeHtml(field.name || field.path)}</code>
        ${required}
        ${concept}
        <span>${escapeHtml(field.description || field.type || "")}</span>
      </li>
    `;
  }).join("");
}

function endpointList(endpoints) {
  if (!endpoints || endpoints.length === 0) return `<span class="muted">endpoint 없음</span>`;
  return endpoints.map((endpoint) => `
    <li>
      <span class="method">${escapeHtml(endpoint.method || "GET")}</span>
      <code>${escapeHtml(endpoint.path || "")}</code>
      <span>${escapeHtml(endpoint.summary || "")}</span>
    </li>
  `).join("");
}

function renderResults(results) {
  currentResults = results;
  resultCount.textContent = String(results.length);
  resultsList.innerHTML = "";
  if (results.length === 0) {
    statusLine.textContent = "결과가 없습니다.";
    showEmpty();
    return;
  }
  statusLine.textContent = "service_id 중복 제거 후 정렬된 결과입니다.";
  results.forEach((result, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "result-item";
    button.innerHTML = `
      <span class="rank">${index + 1}</span>
      <span class="result-main">
        <strong>${escapeHtml(result.name)}</strong>
        <span>${escapeHtml(result.provider_agency_name || "")} · ${escapeHtml(result.category || "")}</span>
        <small>${escapeHtml((result.match_reasons || []).slice(0, 3).join(" / "))}</small>
      </span>
      <span class="score">${Number(result.score || 0).toFixed(3)}</span>
    `;
    button.addEventListener("click", () => renderDetail(result));
    resultsList.appendChild(button);
  });
  renderDetail(results[0]);
}

function renderDetail(result) {
  detailEmpty.classList.add("hidden");
  detailView.classList.remove("hidden");
  const source = result.source || {};
  detailView.innerHTML = `
    <header class="detail-header">
      <div>
        <h2>${escapeHtml(result.name)}</h2>
        <p>${escapeHtml(result.provider_agency_name || "")} · ${escapeHtml(result.category || "")}</p>
      </div>
      <span class="score large">${Number(result.score || 0).toFixed(3)}</span>
    </header>
    <p class="description">${escapeHtml(result.description || result.display_text || "")}</p>

    <div class="meta-grid">
      <div><span>service_id</span><code>${escapeHtml(result.service_id)}</code></div>
      <div><span>api_type</span><code>${escapeHtml(result.api_type || "")}</code></div>
      <div><span>domain</span><code>${escapeHtml((result.domain_ids || []).join(", "))}</code></div>
      <div><span>concept</span><code>${escapeHtml((result.concept_ids || []).slice(0, 5).join(", "))}</code></div>
    </div>

    <section class="detail-section">
      <h3>Endpoint</h3>
      <ul class="endpoint-list">${endpointList(result.endpoints)}</ul>
    </section>

    <section class="detail-section columns">
      <div>
        <h3>요청 필드 <span>${result.counts?.request_fields || 0}</span></h3>
        <ul class="field-list">${fieldList(result.request_fields)}</ul>
      </div>
      <div>
        <h3>응답 필드 <span>${result.counts?.response_fields || 0}</span></h3>
        <ul class="field-list">${fieldList(result.response_fields)}</ul>
      </div>
    </section>

    <details class="detail-section">
      <summary>검색 근거</summary>
      <ul class="reason-list">
        ${(result.match_reasons || []).map((reason) => `<li>${escapeHtml(reason)}</li>`).join("")}
      </ul>
    </details>

    <details class="detail-section">
      <summary>원본 경로</summary>
      <div class="source-paths">
        <code>${escapeHtml(source.refined_path || "")}</code>
        <code>${escapeHtml(source.raw_path || "")}</code>
      </div>
    </details>
  `;
}

function showEmpty() {
  detailView.classList.add("hidden");
  detailEmpty.classList.remove("hidden");
}

async function loadHealth() {
  try {
    const response = await fetch("/health");
    const data = await response.json();
    healthText.textContent = `인덱스 ${data.index_collection_total ?? "확인 불가"}개 문서`;
  } catch {
    healthText.textContent = "상태 확인 실패";
  }
}

async function runSearch(query) {
  searchButton.disabled = true;
  statusLine.textContent = "검색 중";
  try {
    const response = await fetch("/search", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        query,
        top_k: Number(topKInput.value || 5),
        use_vector: true
      })
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "검색 실패");
    }
    renderResults(data.results || []);
    if (data.diagnostics?.vector_error) {
      statusLine.textContent = "벡터 검색 오류로 lexical 결과를 표시했습니다.";
    }
  } catch (error) {
    statusLine.textContent = error.message;
    resultsList.innerHTML = "";
    resultCount.textContent = "0";
    showEmpty();
  } finally {
    searchButton.disabled = false;
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const query = queryInput.value.trim();
  if (query.length < 2) {
    statusLine.textContent = "두 글자 이상 입력하세요.";
    return;
  }
  runSearch(query);
});

// ── 빌드 ─────────────────────────────────────────────────────────────────────

function setBuildButtonsDisabled(disabled) {
  buildButtons.forEach((btn) => { btn.disabled = disabled; });
}

async function triggerBuild(device) {
  setBuildButtonsDisabled(true);
  try {
    const res = await fetch("/build", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ device })
    });
    const data = await res.json();
    if (!data.ok) {
      alert(data.message);
      setBuildButtonsDisabled(false);
      return;
    }
    startBuildPoll();
  } catch (e) {
    alert("빌드 요청 실패: " + e.message);
    setBuildButtonsDisabled(false);
  }
}

function startBuildPoll() {
  buildBar.classList.remove("hidden");
  if (buildPollTimer) clearInterval(buildPollTimer);
  buildPollTimer = setInterval(pollBuildStatus, 1000);
}

async function pollBuildStatus() {
  try {
    const res = await fetch("/build/status");
    const data = await res.json();

    const pct = data.total > 0 ? Math.round((data.progress / data.total) * 100) : 0;
    buildProgress.value = pct;

    const stepLabel = data.step_name ? `[${data.step}/4] ${data.step_name}` : "";
    const elapsed = data.elapsed_s != null ? ` (${data.elapsed_s}s)` : "";
    buildStatusEl.textContent = `${stepLabel} ${data.message}${elapsed}`.trim();

    if (data.state === "done" || data.state === "error") {
      clearInterval(buildPollTimer);
      buildPollTimer = null;
      setBuildButtonsDisabled(false);
      buildProgress.value = data.state === "done" ? 100 : 0;
      if (data.state === "done") loadHealth();
    }
  } catch (e) {
    buildStatusEl.textContent = "상태 확인 실패";
  }
}

buildCpuButton.addEventListener("click", () => triggerBuild("cpu"));
buildGpuButton.addEventListener("click", () => triggerBuild("gpu"));

loadHealth();
