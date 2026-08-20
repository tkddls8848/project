from __future__ import annotations

import asyncio
import sys
import textwrap

import pytest
from fastapi.testclient import TestClient

import main as crawler_main
from backend import main as backend_main
from backend.run_service import (
    DATA_TYPES,
    CrawlRequest,
    CrawlRequestError,
    CrawlRunManager,
)
from nara_common.process_runs import parse_progress, split_stream


# ── 요청 -> CLI argv ────────────────────────────────────────────────────

def test_type_range_request_builds_cli_arguments():
    request = CrawlRequest(data_type="openapi", start=15000000, end=15000100, workers=8)
    assert request.to_argv() == ["openapi", "-s", "15000000", "-e", "15000100", "-w", "8"]


def test_full_request_omits_type_and_range():
    assert CrawlRequest(full=True).to_argv() == ["--full"]


def test_depth_only_request_needs_no_type_or_range():
    request = CrawlRequest(deep=True, harvest=True, harvest_max_hosts=2)
    assert request.to_argv() == ["--deep", "--harvest", "--harvest-max-hosts", "2"]


def test_deep_flags_match_cli_rules():
    with pytest.raises(CrawlRequestError):
        CrawlRequest(full_download=True, data_type="fileData", start=1, end=2).to_argv()
    ok = CrawlRequest(deep=True, full_download=True).to_argv()
    assert "--full-download" in ok and "--deep" in ok


@pytest.mark.parametrize(
    "request_kwargs",
    [
        {},                                             # 아무것도 안 고름
        {"data_type": "openapi"},                       # 범위 없음
        {"data_type": "openapi", "start": 5, "end": 1},  # 역전된 범위
        {"data_type": "nope", "start": 1, "end": 2},     # 없는 타입
        {"full": True, "data_type": "openapi"},          # full과 type 동시
        {"data_type": "openapi", "start": 1, "end": 2, "workers": 0},
    ],
)
def test_invalid_requests_are_rejected(request_kwargs):
    with pytest.raises(CrawlRequestError):
        CrawlRequest(**request_kwargs).to_argv()


def test_data_types_stay_in_sync_with_the_cli():
    """UI가 CLI에 없는 타입을 제시하면 실행이 실패한다."""
    assert set(DATA_TYPES) == set(crawler_main.CRAWLER_CLASSES)


def test_save_failures_make_the_crawl_command_fail():
    with pytest.raises(RuntimeError, match="Failed to save 2 crawl result"):
        crawler_main._raise_for_save_failures(
            {
                "failed_saves": 2,
                "save_errors": ["JSON Save Error: disk full"],
            }
        )


# ── 출력 파싱 ───────────────────────────────────────────────────────────

def test_progress_is_parsed_from_tqdm_lines():
    line = "Crawling documents:  45%|####5     | 45/100 [00:10<00:12,  4.5it/s]"
    assert parse_progress(line) == {
        "label": "Crawling documents",
        "done": 45,
        "total": 100,
        "percent": 45.0,
    }


def test_plain_log_lines_are_not_progress():
    assert parse_progress("Found 120 documents to crawl.") is None
    assert parse_progress("") is None


def test_stream_splits_on_carriage_returns():
    """tqdm은 \\r로 같은 줄을 덮어쓴다. \\n만 보면 진행률이 안 나온다."""
    lines, rest = split_stream("a\rb\nc\r\nd")
    assert lines == ["a", "b", "c"]
    assert rest == "d"


# ── 실행 관리 ───────────────────────────────────────────────────────────

def fake_script(tmp_path, body: str):
    path = tmp_path / "fake_main.py"
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


def test_manager_streams_output_and_completes(tmp_path):
    script = fake_script(tmp_path, """
        import sys
        print("Found 2 documents to crawl.")
        sys.stderr.write("Crawling:  50%|#####     | 1/2 [00:00<00:00,  2it/s]\\r")
        sys.stderr.write("Crawling: 100%|##########| 2/2 [00:01<00:00,  2it/s]\\n")
        print("OPENAPI Crawling Complete.")
    """)

    async def scenario():
        manager = CrawlRunManager(python_executable=sys.executable, script=script)
        created = await manager.create_crawl(CrawlRequest(full=True))
        await manager._runs[created["run_id"]].task
        return manager.snapshot(created["run_id"])

    run = asyncio.run(scenario())
    assert run["status"] == "completed"
    assert run["exit_code"] == 0
    assert run["progress"] == {"label": "Crawling", "done": 2, "total": 2, "percent": 100.0}
    assert "Found 2 documents to crawl." in run["log"]
    assert "OPENAPI Crawling Complete." in run["log"]


def test_manager_reports_a_failing_crawl(tmp_path):
    script = fake_script(tmp_path, """
        import sys
        print("Error: No CSV found")
        sys.exit(2)
    """)

    async def scenario():
        manager = CrawlRunManager(python_executable=sys.executable, script=script)
        created = await manager.create_crawl(CrawlRequest(full=True))
        await manager._runs[created["run_id"]].task
        return manager.snapshot(created["run_id"])

    run = asyncio.run(scenario())
    assert run["status"] == "failed"
    assert run["exit_code"] == 2
    assert "코드 2" in run["error"]


def test_only_one_crawl_runs_at_a_time(tmp_path):
    script = fake_script(tmp_path, """
        import time
        time.sleep(5)
    """)

    async def scenario():
        manager = CrawlRunManager(python_executable=sys.executable, script=script)
        first = await manager.create_crawl(CrawlRequest(full=True))
        try:
            with pytest.raises(RuntimeError):
                await manager.create_crawl(CrawlRequest(full=True))
        finally:
            await manager.stop(first["run_id"])
            await manager._runs[first["run_id"]].task
        return manager.snapshot(first["run_id"])

    run = asyncio.run(scenario())
    assert run["status"] == "cancelled"


# ── HTTP 표면 ───────────────────────────────────────────────────────────

@pytest.fixture
def client(tmp_path, monkeypatch):
    script = fake_script(tmp_path, """
        print("fake crawl")
    """)
    monkeypatch.setattr(
        backend_main,
        "runs",
        CrawlRunManager(python_executable=sys.executable, script=script),
    )
    with TestClient(backend_main.app) as test_client:
        yield test_client


def test_preview_returns_the_command_the_server_would_run(client):
    response = client.post(
        "/runs/preview",
        json={"type": "standard", "start": 1, "end": 9, "full": False},
    )
    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "command": "python main.py standard -s 1 -e 9",
    }


def test_preview_reports_validation_errors_without_running(client):
    response = client.post("/runs/preview", json={"type": "standard"})
    payload = response.json()
    assert payload["ok"] is False
    assert "문서번호" in payload["message"]


def test_invalid_run_request_is_rejected(client):
    response = client.post("/runs", json={"full": True, "type": "openapi"})
    assert response.status_code == 400


def test_run_lifecycle_over_http(client):
    created = client.post("/runs", json={"full": True})
    assert created.status_code == 202
    run_id = created.json()["run_id"]

    snapshot = client.get(f"/runs/{run_id}")
    assert snapshot.status_code == 200
    assert snapshot.json()["command"] == "python main.py --full"

    assert client.get("/runs/does-not-exist").status_code == 404


def test_health_reports_types_and_storage(client):
    payload = client.get("/health").json()
    assert payload["ok"] is True
    assert set(payload["data_types"]) == set(DATA_TYPES)
    assert "documents" in payload["storage"]


def test_control_surface_does_not_enable_cors(client):
    """아무 출처의 페이지가 로컬 크롤을 시작시킬 수 있으면 안 된다."""
    response = client.post(
        "/runs/preview",
        json={"full": True},
        headers={"Origin": "https://evil.example"},
    )
    assert "access-control-allow-origin" not in {k.lower() for k in response.headers}
