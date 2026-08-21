from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest


SUMMARY_MODULE = Path(__file__).resolve().parents[1] / "static" / "run_summary.js"


def summarize(run: dict) -> str:
    script = """
const { summarizeRun } = require(process.argv[1]);
const run = JSON.parse(process.argv[2]);
process.stdout.write(summarizeRun(run));
"""
    completed = subprocess.run(
        ["node", "-e", script, str(SUMMARY_MODULE), json.dumps(run)],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout


@pytest.mark.parametrize("status", ["failed", "cancelled"])
def test_terminal_failure_summary_prioritizes_run_error(status):
    message = summarize(
        {
            "status": status,
            "error": "Gateway 연결이 끊겼습니다.",
            "hermes": {"status": "failed"},
        }
    )

    assert message.startswith("Gateway 연결이 끊겼습니다.")


def test_non_completed_hermes_status_is_explicit_without_success_claim():
    message = summarize(
        {"status": "completed", "hermes": {"status": "failed"}}
    )

    assert "Hermes Gateway 상태: failed" in message
    assert "완료했습니다" not in message


def test_skipped_hermes_summary_says_it_was_not_called():
    message = summarize(
        {"status": "completed", "hermes": {"status": "skipped"}}
    )

    assert "Hermes Gateway를 호출하지 않고" in message
