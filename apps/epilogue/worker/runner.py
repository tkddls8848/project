from __future__ import annotations

import argparse
import queue
import sys
import threading
import time
from pathlib import Path
from typing import Any


def _load_project_root() -> Path:
    current_file = Path(__file__).resolve()
    marker_parent = next((candidate for candidate in current_file.parents if (candidate / ".nara-root").is_file()), None)
    if marker_parent is None:
        raise RuntimeError("repository marker .nara-root was not found")
    libraries = marker_parent / "libs"
    if str(libraries) not in sys.path:
        sys.path.insert(0, str(libraries))
    from nara_common.paths import find_project_root

    return find_project_root(current_file)


PROJECT_ROOT = _load_project_root()

from adapters.base import AdapterResult
from adapters.registry import AdapterRegistry
from domain.operations import OperationSpec
from infra.database import Database
from infra.secrets import allowlisted_result


class WorkerRunner:
    def __init__(
        self,
        database: Database,
        operation_registry: AdapterRegistry,
        *,
        worker_id: str,
        lease_seconds: float = 30,
    ):
        self.database = database
        self.operation_registry = operation_registry
        self.worker_id = worker_id
        self.lease_seconds = lease_seconds

    def _call_with_timeout(
        self,
        run_id: str,
        spec: OperationSpec,
        adapter,
        inputs: dict[str, Any],
        key: str,
        timeout: float,
    ) -> AdapterResult:
        results: queue.Queue[AdapterResult] = queue.Queue(maxsize=1)

        def invoke() -> None:
            try:
                results.put(adapter.execute(spec, inputs, key), block=False)
            except Exception:
                results.put(AdapterResult(status="failed", error_code="adapter_failure"), block=False)

        thread = threading.Thread(target=invoke, name=f"adapter-{spec.operation_id}", daemon=True)
        thread.start()
        deadline = time.monotonic() + timeout
        heartbeat_interval = max(0.001, min(self.lease_seconds / 3, 5.0))
        while thread.is_alive() and time.monotonic() < deadline:
            thread.join(min(heartbeat_interval, max(0, deadline - time.monotonic())))
            if thread.is_alive() and not self.database.renew_lease(run_id, self.worker_id, self.lease_seconds):
                return AdapterResult(status="outcome_unknown", error_code="worker_lease_lost")
        if thread.is_alive():
            return AdapterResult(status="outcome_unknown", error_code="step_timeout")
        try:
            return results.get_nowait()
        except queue.Empty:
            return AdapterResult(status="failed", error_code="adapter_failure")

    def run_once(self) -> bool:
        run = self.database.acquire_next_run(self.worker_id, lease_seconds=self.lease_seconds)
        if run is None:
            return False
        plan = run["plan"]
        guidance: list[str] = []

        pending = {step.step_id: step for step in plan.steps}
        completed_order: list[str] = []
        while pending:
            progressed = False
            for step_id, step in list(pending.items()):
                if not set(step.depends_on) <= set(completed_order):
                    continue
                progressed = True
                pending.pop(step_id)
                if self.database.is_cancel_requested(run["run_id"]):
                    self.database.finalize_run(run["run_id"], self.worker_id, "cancelled")
                    return True

                current = self.database.get_run_internal(run["run_id"])
                step_states = {item["step_id"]: item["status"] for item in current["steps"]}
                dependency_states = [step_states[dependency] for dependency in step.depends_on]
                if any(state != "succeeded" for state in dependency_states):
                    self.database.block_step(run["run_id"], step_id, self.worker_id, "dependency_failed")
                    completed_order.append(step_id)
                    continue
                if step_states[step_id] not in {"pending", "running"}:
                    completed_order.append(step_id)
                    continue

                spec = self.operation_registry.get(step.operation_id, step.operation_version)
                attempt_state, marker = self.database.prepare_step_attempt(run["run_id"], step_id, self.worker_id)
                if attempt_state == "in_flight":
                    self.database.finish_step(
                        run["run_id"],
                        step_id,
                        self.worker_id,
                        status="outcome_unknown",
                        receipt=marker or {},
                        error_code="crash_during_adapter_call",
                    )
                    guidance.append(spec.recovery_guidance)
                    completed_order.append(step_id)
                    continue
                if attempt_state != "execute":
                    completed_order.append(step_id)
                    continue

                resolved_inputs = self.operation_registry.resolve_inputs(plan, step_id, current["input_json"])
                adapter = self.operation_registry.adapter_for(spec.adapter)
                result = self._call_with_timeout(
                    run["run_id"],
                    spec,
                    adapter,
                    resolved_inputs,
                    marker["step_idempotency_key"],
                    min(step.timeout_seconds, 300),
                )
                attempts = 1
                while result.status == "retryable" and spec.safe_retry and attempts < spec.max_attempts:
                    attempts += 1
                    result = self._call_with_timeout(
                        run["run_id"],
                        spec,
                        adapter,
                        resolved_inputs,
                        marker["step_idempotency_key"],
                        min(step.timeout_seconds, 300),
                    )
                if result.status == "retryable":
                    result = AdapterResult(status="failed", error_code="retry_limit_reached")
                safe_receipt = allowlisted_result(result.receipt, spec.result_fields)
                self.database.finish_step(
                    run["run_id"],
                    step_id,
                    self.worker_id,
                    status=result.status,
                    receipt=safe_receipt,
                    error_code=result.error_code,
                )
                if result.status in {"failed", "outcome_unknown", "awaiting_user"}:
                    guidance.append(spec.recovery_guidance)
                completed_order.append(step_id)
            if not progressed:
                raise RuntimeError("validated plan could not make dependency progress")

        current = self.database.get_run_internal(run["run_id"])
        statuses = [item["status"] for item in current["steps"]]
        if "outcome_unknown" in statuses:
            target = "outcome_unknown"
        elif "awaiting_user" in statuses:
            target = "awaiting_user"
        elif "failed" in statuses or "blocked" in statuses:
            target = "partially_succeeded" if "succeeded" in statuses else "failed"
        elif statuses and all(status == "succeeded" for status in statuses):
            target = "succeeded"
        else:
            target = "failed"
        self.database.finalize_run(
            run["run_id"],
            self.worker_id,
            target,
            guidance=" ".join(dict.fromkeys(guidance)) or None,
        )
        return True


def build_default_runner(worker_id: str) -> WorkerRunner:
    database = Database(PROJECT_ROOT / "api_storage" / "epilogue" / "epilogue.sqlite3")
    registry = AdapterRegistry.from_json(PROJECT_ROOT / "services" / "epilogue" / "config" / "operations.json")
    return WorkerRunner(database, registry, worker_id=worker_id)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Nara executor lease worker.")
    parser.add_argument("--worker-id", default="local-worker")
    parser.add_argument("--once", action="store_true", help="Process at most one queued/expired run.")
    arguments = parser.parse_args()
    runner = build_default_runner(arguments.worker_id)
    if arguments.once:
        runner.run_once()
        return 0
    try:
        while True:
            if not runner.run_once():
                time.sleep(0.5)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
