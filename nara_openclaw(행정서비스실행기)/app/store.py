import json
from pathlib import Path

from .config import RUNS_DIR
from .schemas import RunRecord


def ensure_runs_dir(path: Path | None = None) -> Path:
    target = path or RUNS_DIR
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
