import json
from pathlib import Path

from . import config
from .schemas import RunRecord


def ensure_runs_dir(path: Path | None = None) -> Path:
    # config.RUNS_DIR을 호출 시점에 읽어 테스트가 임시 디렉터리로 격리할 수 있게 한다.
    target = path or config.RUNS_DIR
    target.mkdir(parents=True, exist_ok=True)
    return target


def save_run(record: RunRecord, path: Path | None = None) -> None:
    target = ensure_runs_dir(path)
    run_path = target / f"{record.run_id}.json"
    run_path.write_text(record.model_dump_json(indent=2), encoding="utf-8")


def load_run(run_id: str, path: Path | None = None) -> RunRecord | None:
    target = ensure_runs_dir(path)
    run_path = target / f"{run_id}.json"
    if not run_path.exists():
        return None
    return RunRecord(**json.loads(run_path.read_text(encoding="utf-8")))
