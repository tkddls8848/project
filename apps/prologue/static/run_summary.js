function summarizeRun(run) {
  const status = run?.status;
  const hermesStatus = run?.hermes?.status;
  const error = typeof run?.error === "string" ? run.error.trim() : "";
  const hermesFact = hermesStatus ? ` (Hermes Gateway 상태: ${hermesStatus})` : "";

  if (["failed", "cancelled"].includes(status) && error) {
    return `${error}${hermesStatus === "completed" ? "" : hermesFact}`;
  }
  if (status === "failed") return `실행에 실패했습니다.${hermesFact}`;
  if (status === "cancelled") return `실행이 중단되었습니다.${hermesFact}`;
  if (hermesStatus === "completed") {
    return "Hermes Gateway가 MCP 오케스트레이션을 완료했고 Orchestrator가 읽기 전용 결과를 준비했습니다.";
  }
  if (hermesStatus === "skipped") {
    return "요청이 문서를 직접 지정해 Hermes Gateway를 호출하지 않고 읽기 전용 결과를 준비했습니다.";
  }
  return `실행 결과가 반환되었지만 Hermes Gateway 상태: ${hermesStatus || "확인 불가"}입니다.`;
}

if (typeof module !== "undefined") module.exports = { summarizeRun };
