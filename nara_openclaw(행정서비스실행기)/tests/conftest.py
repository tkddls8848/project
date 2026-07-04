import pytest


@pytest.fixture(autouse=True)
def isolated_runs_dir(tmp_path, monkeypatch):
    """모든 테스트의 run 기록을 임시 디렉터리로 격리한다.

    테스트가 작업 트리(runs/)에 산출물을 남기지 않아야 한다.
    """
    from app import config

    runs_dir = tmp_path / "runs"
    monkeypatch.setattr(config, "RUNS_DIR", runs_dir)
    return runs_dir
