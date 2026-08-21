"""빌드 시작 경로와 인덱스 없는 첫 실행을 확인한다."""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _install_fake_build_dependencies(monkeypatch):
    import numpy as np

    from backend.core import config, faiss_io

    class FakeIndex:
        def __init__(self, _dim):
            self.ntotal = 0

        def add(self, embeddings):
            self.ntotal = len(embeddings)

    class FakeSentenceTransformer:
        def __init__(self, _model_path, device):
            self.device = device
            self.max_seq_length = None

        def encode(self, batch, **_kwargs):
            return np.ones((len(batch), 2), dtype="float32")

    monkeypatch.setitem(sys.modules, "faiss", SimpleNamespace(IndexFlatIP=FakeIndex))
    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        SimpleNamespace(SentenceTransformer=FakeSentenceTransformer),
    )
    monkeypatch.setattr(config, "ensure_local_model", lambda: "fake-model")
    monkeypatch.setattr(
        faiss_io,
        "write_index",
        lambda _index, path: Path(path).write_bytes(b"fake-index"),
    )


@pytest.fixture(autouse=True)
def idle_build_status():
    """build_status는 모듈 전역이다. 테스트가 running을 남기면 뒤가 물린다."""
    from backend.indexing.index_builder import build_status

    build_status.update(state="idle", started_at=None, finished_at=None, message="")
    yield
    build_status.update(state="idle", started_at=None, finished_at=None, message="")


def test_second_build_is_rejected_while_one_is_reserved(app_client, monkeypatch):
    """자리 잡기는 스레드가 아니라 엔드포인트에서 끝나야 한다.

    running을 스레드 안에서 세우면, 그 스레드가 뜨기 전에 들어온 두 번째 요청도
    idle을 보고 통과한다. 빌드 두 개가 같은 FAISS·메타데이터 파일을 덮어쓴다.
    여기서는 run_build이 아무것도 하지 않으므로, 스레드가 상태를 세워 주는 일이
    없다. 그래도 두 번째 요청은 막혀야 한다.
    """
    from backend import main

    monkeypatch.setattr(main, "resolve_device", lambda device: "cpu")
    monkeypatch.setattr(main, "run_build", lambda **kwargs: None)

    first = app_client.post("/build", json={"device": "cpu"})
    second = app_client.post("/build", json={"device": "cpu"})

    assert first.json()["ok"] is True
    assert second.json()["ok"] is False
    assert "이미 빌드 중" in second.json()["message"]


def test_device_failure_does_not_hold_the_build_slot(app_client, monkeypatch):
    """디바이스 확인에서 막히면 자리를 잡은 적이 없어야 한다."""
    from backend import main
    from backend.indexing.index_builder import build_status

    def _no_gpu(device):
        raise RuntimeError("CUDA를 쓸 수 없습니다.")

    monkeypatch.setattr(main, "resolve_device", _no_gpu)

    response = app_client.post("/build", json={"device": "gpu"})

    assert response.json()["ok"] is False
    assert build_status.state == "idle"


def test_failed_build_does_not_publish_build_time(app_client, monkeypatch):
    from backend import main
    from backend.core import config
    from backend.indexing.index_builder import build_status, run_build

    _install_fake_build_dependencies(monkeypatch)
    config.BUILD_MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.BUILD_MANIFEST_PATH.write_text(
        json.dumps({"built_at": "2026-01-01T00:00:00+09:00"}),
        encoding="utf-8",
    )

    def fail_after_artifacts_are_written():
        raise RuntimeError("reload failed")

    run_build(on_complete=fail_after_artifacts_are_written)

    assert build_status.state == "error"
    assert main.index_built_at() == ""


def test_successful_build_publishes_manifest_build_time(app_client, monkeypatch):
    from backend import main
    from backend.core import config
    from backend.indexing.index_builder import build_status, run_build

    _install_fake_build_dependencies(monkeypatch)

    run_build()

    manifest = json.loads(config.BUILD_MANIFEST_PATH.read_text(encoding="utf-8"))
    assert build_status.state == "done"
    assert manifest == {"built_at": main.index_built_at()}
    datetime.fromisoformat(manifest["built_at"])
    assert app_client.get("/health").json()["index_built_at"] == manifest["built_at"]


def test_app_imports_without_an_index_on_a_cp949_pipe(tmp_path):
    """인덱스가 없는 첫 실행에서 앱이 기동해야 한다.

    안내 문구에는 cp949로 인코딩되지 않는 문자가 있다. stdout이 파이프면
    (콘솔 리다이렉트·서비스 실행) 그 print가 UnicodeEncodeError를 내는데,
    하필 예외 처리 안에서 터지므로 backend.main import 자체가 끊긴다.
    """
    environment = {
        **os.environ,
        "PYTHONIOENCODING": "cp949",
        "NARA_SEARCH_STORAGE_DIR": str(tmp_path / "empty-storage"),
    }
    environment.pop("PYTHONUTF8", None)

    result = subprocess.run(
        [sys.executable, "-c", "import backend.main; print('imported')"],
        cwd=str(PROJECT_ROOT),
        env=environment,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    assert b"imported" in result.stdout
