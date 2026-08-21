const $ = (selector) => document.querySelector(selector);
const TERMINAL = new Set(["completed", "failed", "cancelled"]);
const CONFIRM_WORD = "연장";

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

/** commit은 체크박스와 확인 문구를 모두 통과해야 켜진다. */
function commitAllowed() {
  return $("#commitInput").checked && $("#confirmInput").value.trim() === CONFIRM_WORD;
}

function extendBody({ commit }) {
  const limit = $("#limitInput").value.trim();
  return {
    command: "extend",
    only: $("#onlyInput").value.trim(),
    limit: limit === "" ? null : Number(limit),
    commit,
    confirm_commit: commit,
  };
}

async function refreshPreview() {
  const commit = $("#commitInput").checked;
  try {
    const result = await fetchJson("/runs/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      // 미리보기는 확인 문구와 무관하게 실제로 돌 명령을 보여준다.
      body: JSON.stringify({ ...extendBody({ commit }), confirm_commit: true }),
    });
    const errorBox = $("#previewError");
    if (result.ok) {
      $("#commandPreview").textContent = result.command;
      errorBox.classList.add("hidden");
    } else {
      $("#commandPreview").textContent = "—";
      errorBox.textContent = result.message;
      errorBox.classList.remove("hidden");
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
  const commit = $("#commitInput").checked;
  $("#confirmField").classList.toggle("hidden", !commit);
  if (!commit) $("#confirmInput").value = "";
  const busy = currentRunId !== null;
  $("#commitButton").disabled = busy || !commitAllowed();
  $("#dryRunButton").disabled = busy;
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

function setRunState(status, command, acceptsStdin) {
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
  $("#stopButton").disabled = finished;
  $("#stdinButton").classList.toggle("hidden", finished || !acceptsStdin);
  $("#loginButton").disabled = !finished;
  $("#reloadAccountsButton").disabled = !finished;
}

function closeStream() {
  if (eventSource) {
    eventSource.close();
    eventSource = null;
  }
}

function listen(runId, acceptsStdin) {
  closeStream();
  eventSource = new EventSource(`/runs/${runId}/events`);
  eventSource.addEventListener("progress", (message) => {
    const event = JSON.parse(message.data);
    appendLog(event.message);
    setRunState(event.status, null, acceptsStdin);
    if (TERMINAL.has(event.status)) finishRun();
  });
  eventSource.addEventListener("error", () => {
    closeStream();
    if (currentRunId) finishRun();
  });
}

async function finishRun() {
  closeStream();
  if (!currentRunId) return;
  const runId = currentRunId;
  currentRunId = null;
  try {
    const run = await fetchJson(`/runs/${runId}`);
    setRunState(run.status, run.command, false);
    if (run.error) appendLog(`[오류] ${run.error}`);
    if (run.metadata?.command === "login" && run.status === "completed") {
      await loadSession();
    }
  } catch (error) {
    appendLog(`[오류] ${error.message}`);
  }
  syncFormState();
}

async function startRun(body, confirmText) {
  if (confirmText && !confirm(confirmText)) return;
  $("#logBox").dataset.ready = "0";
  try {
    const run = await fetchJson("/runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    currentRunId = run.run_id;
    setRunState(run.status, run.command, run.accepts_stdin);
    listen(run.run_id, run.accepts_stdin);
    syncFormState();
  } catch (error) {
    appendLog(`[오류] ${error.message}`);
    setRunState(null);
    syncFormState();
  }
}

async function stopRun() {
  if (!currentRunId) return;
  $("#stopButton").disabled = true;
  try {
    const run = await fetchJson(`/runs/${currentRunId}/stop`, { method: "POST" });
    setRunState(run.status, run.command, false);
  } catch (error) {
    appendLog(`[오류] ${error.message}`);
  }
}

async function sendStdin() {
  if (!currentRunId) return;
  try {
    await fetchJson(`/runs/${currentRunId}/stdin`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: "\n" }),
    });
  } catch (error) {
    appendLog(`[오류] ${error.message}`);
  }
}

async function loadSession() {
  try {
    const health = await fetchJson("/health");
    const session = health.session || {};
    const badge = $("#sessionBadge");
    if (session.authenticated_hint) {
      badge.textContent = "세션 저장됨";
      badge.className = "badge ok";
      const saved = session.saved_at ? new Date(session.saved_at).toLocaleString("ko-KR") : "";
      $("#sessionText").textContent = `${session.list_url} · 저장 ${saved}`;
    } else {
      badge.textContent = "로그인 필요";
      badge.className = "badge missing";
      $("#sessionText").textContent = "저장된 세션이 없습니다. 브라우저 로그인을 먼저 하세요.";
    }
  } catch (error) {
    $("#sessionText").textContent = `상태를 불러오지 못했습니다: ${error.message}`;
  }
}

async function loadAccounts() {
  const box = $("#accountsBox");
  box.textContent = "포털에서 목록을 읽는 중입니다...";
  $("#reloadAccountsButton").disabled = true;
  try {
    const result = await fetchJson("/accounts");
    if (!result.ok) {
      box.textContent = result.message || "목록을 읽지 못했습니다.";
      return;
    }
    if (!result.total) {
      box.textContent = "활용신청 목록에서 행을 찾지 못했습니다.";
      return;
    }
    $("#accountsHint").textContent = `총 ${result.total}건`;
    box.replaceChildren(
      ...result.rows.map((row) => {
        const item = document.createElement("div");
        item.className = "account-row";
        const left = document.createElement("div");
        left.append(
          Object.assign(document.createElement("strong"), {
            textContent: row.name || "(이름 미확인)",
          })
        );
        left.append(document.createElement("br"));
        left.append(
          Object.assign(document.createElement("span"), {
            className: "account-key",
            textContent: row.key || "(식별자 미확인)",
          })
        );
        const right = document.createElement("span");
        right.className = "badge";
        right.textContent = row.status_text || "-";
        item.append(left, right);
        return item;
      })
    );
  } catch (error) {
    box.textContent = `목록을 읽지 못했습니다: ${error.message}`;
  } finally {
    $("#reloadAccountsButton").disabled = currentRunId !== null;
  }
}

/** 새로고침해도 진행 중인 실행에 다시 붙는다. */
async function attachToActiveRun() {
  try {
    const state = await fetchJson("/runs");
    if (!state.active_run_id) return;
    const run = await fetchJson(`/runs/${state.active_run_id}`);
    currentRunId = run.run_id;
    $("#logBox").dataset.ready = "0";
    run.log.forEach(appendLog);
    setRunState(run.status, run.command, run.accepts_stdin);
    listen(run.run_id, run.accepts_stdin);
    syncFormState();
  } catch (error) {
    appendLog(`[오류] ${error.message}`);
  }
}

function bind() {
  ["commitInput", "confirmInput"].forEach((id) =>
    $(`#${id}`).addEventListener("input", syncFormState)
  );
  ["onlyInput", "limitInput"].forEach((id) =>
    $(`#${id}`).addEventListener("input", schedulePreview)
  );

  $("#loginButton").addEventListener("click", () =>
    startRun({ command: "login", manual: $("#manualLoginInput").checked })
  );
  $("#reloadAccountsButton").addEventListener("click", loadAccounts);
  $("#dryRunButton").addEventListener("click", () =>
    startRun(extendBody({ commit: false }))
  );
  $("#commitButton").addEventListener("click", () => {
    if (!commitAllowed()) return;
    startRun(
      extendBody({ commit: true }),
      "포털에 실제 연장을 제출합니다. 되돌릴 수 없습니다. 계속할까요?"
    );
  });
  $("#stopButton").addEventListener("click", stopRun);
  $("#stdinButton").addEventListener("click", sendStdin);
}

bind();
syncFormState();
loadSession();
attachToActiveRun();
