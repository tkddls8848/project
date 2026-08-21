const $ = (selector) => document.querySelector(selector);
const TERMINAL = new Set(["completed", "failed", "cancelled"]);

let currentRunId = null;
let eventSource = null;
let previewTimer = null;

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  let payload = null;
  try {
    payload = await response.json();
  } catch (error) {
    payload = null;
  }
  if (!response.ok) {
    throw new Error(payload?.detail || payload?.message || `요청 실패 (${response.status})`);
  }
  return payload;
}

function mode() {
  return document.querySelector('input[name="mode"]:checked').value;
}

/** 폼을 서버가 받는 요청 본문으로 옮긴다. 명령 조립은 서버가 한다. */
function requestBody() {
  const selected = mode();
  const workers = $("#workersInput").value.trim();
  const body = {
    full: selected === "full",
    workers: workers === "" ? null : Number(workers),
    skip_update: $("#skipUpdateInput").checked,
    force_update: $("#forceUpdateInput").checked,
    deep: $("#deepInput").checked,
    full_download: $("#fullDownloadInput").checked,
    harvest: $("#harvestInput").checked,
    harvest_max_hosts: Number($("#harvestHostsInput").value || 4),
  };
  if (selected === "type") {
    const start = $("#startInput").value.trim();
    const end = $("#endInput").value.trim();
    body.type = $("#typeInput").value;
    body.start = start === "" ? null : Number(start);
    body.end = end === "" ? null : Number(end);
  }
  return body;
}

async function refreshPreview() {
  try {
    const result = await fetchJson("/runs/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestBody()),
    });
    const errorBox = $("#previewError");
    if (result.ok) {
      $("#commandPreview").textContent = result.command;
      errorBox.classList.add("hidden");
      $("#startButton").disabled = currentRunId !== null;
    } else {
      $("#commandPreview").textContent = "—";
      errorBox.textContent = result.message;
      errorBox.classList.remove("hidden");
      $("#startButton").disabled = true;
    }
  } catch (error) {
    $("#previewError").textContent = error.message;
    $("#previewError").classList.remove("hidden");
  }
}

function schedulePreview() {
  clearTimeout(previewTimer);
  previewTimer = setTimeout(refreshPreview, 150);
}

function syncFormState() {
  const selected = mode();
  $("#typeFields").classList.toggle("hidden", selected !== "type");
  $("#fullDownloadInput").disabled = !$("#deepInput").checked;
  if (!$("#deepInput").checked) $("#fullDownloadInput").checked = false;
  $("#harvestHostsInput").disabled = !$("#harvestInput").checked;
  schedulePreview();
}

function appendLog(text) {
  const box = $("#logBox");
  if (box.dataset.ready !== "1") {
    box.textContent = "";
    box.dataset.ready = "1";
  }
  const atBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 40;
  box.textContent += `${text}\n`;
  if (atBottom) box.scrollTop = box.scrollHeight;
}

function setProgress(progress) {
  if (!progress) return;
  $("#progressLabel").textContent = progress.label;
  $("#progressCount").textContent = `${progress.done} / ${progress.total} (${progress.percent}%)`;
  $("#progressBar").value = progress.percent;
}

function setRunState(status, command) {
  const badge = $("#runBadge");
  const labels = {
    running: "실행 중",
    stopping: "중단 중",
    completed: "완료",
    failed: "실패",
    cancelled: "중단됨",
  };
  badge.textContent = labels[status] || "대기";
  badge.className = `badge ${status || "idle"}`;
  if (command) $("#runCommand").textContent = command;

  const finished = !status || TERMINAL.has(status);
  $("#startButton").disabled = !finished;
  $("#stopButton").disabled = finished;
}

function closeStream() {
  if (eventSource) {
    eventSource.close();
    eventSource = null;
  }
}

function listen(runId) {
  closeStream();
  eventSource = new EventSource(`/runs/${runId}/events`);
  eventSource.addEventListener("progress", (message) => {
    const event = JSON.parse(message.data);
    if (event.kind === "progress") {
      setProgress(event.progress);
    } else {
      appendLog(event.message);
    }
    setRunState(event.status);
    if (TERMINAL.has(event.status)) finishRun();
  });
  eventSource.addEventListener("error", () => {
    // 스트림이 끊겨도 상태는 스냅샷으로 확정한다.
    closeStream();
    if (currentRunId) finishRun();
  });
}

async function finishRun() {
  closeStream();
  if (!currentRunId) return;
  const runId = currentRunId;
  try {
    const run = await fetchJson(`/runs/${runId}`);
    setRunState(run.status, run.command);
    if (run.error) appendLog(`[오류] ${run.error}`);
  } catch (error) {
    appendLog(`[오류] ${error.message}`);
  }
  currentRunId = null;
  $("#startButton").disabled = false;
  $("#stopButton").disabled = true;
  await Promise.all([loadHealth(), loadRecent()]);
  refreshPreview();
}

async function startRun() {
  const body = requestBody();
  const heavy = body.full || body.full_download || body.harvest;
  if (heavy && !confirm("외부 사이트에 부하가 큰 작업입니다. 실행할까요?")) return;

  $("#startButton").disabled = true;
  $("#logBox").dataset.ready = "0";
  $("#progressBar").value = 0;
  $("#progressLabel").textContent = "시작하는 중";
  $("#progressCount").textContent = "";
  try {
    const run = await fetchJson("/runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    currentRunId = run.run_id;
    setRunState(run.status, run.command);
    listen(run.run_id);
  } catch (error) {
    appendLog(`[오류] ${error.message}`);
    setRunState(null);
    $("#startButton").disabled = false;
  }
}

async function stopRun() {
  if (!currentRunId) return;
  $("#stopButton").disabled = true;
  try {
    const run = await fetchJson(`/runs/${currentRunId}/stop`, { method: "POST" });
    setRunState(run.status, run.command);
  } catch (error) {
    appendLog(`[오류] ${error.message}`);
  }
}

async function loadRange() {
  const dataType = $("#typeInput").value;
  const hint = $("#rangeHint");
  hint.textContent = "CSV를 읽는 중입니다. 큰 파일은 수십 초 걸립니다.";
  $("#rangeButton").disabled = true;
  try {
    const range = await fetchJson(`/metadata/${dataType}/range`);
    if (range.available) {
      $("#startInput").value = range.min;
      $("#endInput").value = range.max;
      hint.textContent = `${dataType}: ${range.min.toLocaleString()} – ${range.max.toLocaleString()}`;
      schedulePreview();
    } else {
      hint.textContent = range.reason || "범위를 확인할 수 없습니다.";
    }
  } catch (error) {
    hint.textContent = error.message;
  } finally {
    $("#rangeButton").disabled = false;
  }
}

async function loadHealth() {
  try {
    const health = await fetchJson("/health");
    const selectedType = $("#typeInput").value;
    $("#typeInput").replaceChildren(
      ...(health.ui_data_types || []).map((dataType) => {
        const option = document.createElement("option");
        option.value = dataType;
        option.textContent = dataType;
        return option;
      })
    );
    if (health.ui_data_types?.includes(selectedType)) {
      $("#typeInput").value = selectedType;
    }
    schedulePreview();
    const documents = health.storage?.documents || {};
    $("#healthText").textContent = health.storage?.exists
      ? `저장 문서 ${health.storage.total_documents.toLocaleString()}건`
      : "api_storage가 아직 없습니다. 크롤을 먼저 실행하세요.";
    $("#storageChips").replaceChildren(
      ...Object.entries(documents).map(([name, count]) => {
        const chip = document.createElement("span");
        chip.className = "chip";
        chip.textContent = `${name} ${count.toLocaleString()}`;
        return chip;
      })
    );
  } catch (error) {
    $("#healthText").textContent = `상태를 불러오지 못했습니다: ${error.message}`;
  }
}

async function loadRecent() {
  const box = $("#recentList");
  try {
    const state = await fetchJson("/storage");
    const crawls = state.recent_crawls || [];
    if (!crawls.length) {
      box.textContent = "아직 크롤 기록이 없습니다.";
      return;
    }
    box.replaceChildren(
      ...crawls.map((crawl) => {
        const row = document.createElement("div");
        row.className = "recent-row";
        const left = document.createElement("div");
        const types = crawl.types.filter(Boolean).join(", ") || "심화 단계";
        left.append(Object.assign(document.createElement("strong"), { textContent: crawl.crawl_run_id }));
        left.append(document.createElement("br"));
        left.append(document.createTextNode(types));
        const right = document.createElement("div");
        right.textContent = `성공 ${crawl.total_success.toLocaleString()} / 실패 ${crawl.total_failed.toLocaleString()}`;
        row.append(left, right);
        return row;
      })
    );
  } catch (error) {
    box.textContent = `기록을 불러오지 못했습니다: ${error.message}`;
  }
}

/** 새로고침해도 진행 중인 크롤에 다시 붙는다. */
async function attachToActiveRun() {
  try {
    const state = await fetchJson("/runs");
    if (!state.active_run_id) return;
    const run = await fetchJson(`/runs/${state.active_run_id}`);
    currentRunId = run.run_id;
    $("#logBox").dataset.ready = "0";
    run.log.forEach(appendLog);
    setProgress(run.progress);
    setRunState(run.status, run.command);
    listen(run.run_id);
  } catch (error) {
    appendLog(`[오류] ${error.message}`);
  }
}

function bind() {
  document.querySelectorAll('input[name="mode"]').forEach((radio) =>
    radio.addEventListener("change", syncFormState)
  );
  ["deepInput", "harvestInput"].forEach((id) =>
    $(`#${id}`).addEventListener("change", syncFormState)
  );
  [
    "typeInput", "startInput", "endInput", "workersInput",
    "skipUpdateInput", "forceUpdateInput", "fullDownloadInput", "harvestHostsInput",
  ].forEach((id) => $(`#${id}`).addEventListener("input", schedulePreview));

  $("#rangeButton").addEventListener("click", loadRange);
  $("#startButton").addEventListener("click", startRun);
  $("#stopButton").addEventListener("click", stopRun);
}

bind();
syncFormState();
loadHealth();
loadRecent();
attachToActiveRun();
