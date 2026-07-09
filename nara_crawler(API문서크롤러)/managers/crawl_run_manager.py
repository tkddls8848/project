import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from tqdm import tqdm


KST = timezone(timedelta(hours=9))


class CrawlRunManager:
    """Manage crawler run directories and manifests."""

    def __init__(self, base_dir: str | Path):
        self.base_dir = Path(base_dir)
        self.runs_dir = self.base_dir / "apidata"

    @staticmethod
    def create_run_id(now: datetime | None = None) -> str:
        now = now or datetime.now(KST)
        return now.astimezone(KST).strftime("%Y-%m-%dT%H-%M-%S")

    def get_run_dir(self, crawl_run_id: str) -> Path:
        return self.runs_dir / crawl_run_id

    def get_raw_output_dir(self, crawl_run_id: str, data_type: str) -> Path:
        return self.get_run_dir(crawl_run_id) / data_type

    @staticmethod
    def sha256_file(path: str | Path) -> str:
        digest = hashlib.sha256()
        with Path(path).open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                digest.update(chunk)
        return f"sha256:{digest.hexdigest()}"

    @staticmethod
    def now_iso() -> str:
        return datetime.now(KST).isoformat()

    def _build_file_record(self, file_path: str) -> Optional[Dict[str, Any]]:
        path = Path(file_path)
        if not path.exists():
            return None
        try:
            rel_path = path.relative_to(self.base_dir).as_posix()
        except ValueError:
            rel_path = path.as_posix()
        return {
            "path": rel_path,
            "size_bytes": path.stat().st_size,
            "checksum": self.sha256_file(path),
        }

    def build_file_records(self, saved_files: Iterable[str], max_workers: int = 32) -> List[Dict[str, Any]]:
        files = list(saved_files)
        if not files:
            return []

        # Hashing is I/O bound (read every file from disk), so parallelize like
        # the save step. executor.map preserves input order; tqdm makes the
        # otherwise-silent pass visible so it can't be mistaken for a hang.
        records: List[Dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for record in tqdm(
                executor.map(self._build_file_record, files),
                total=len(files),
                desc="Hashing files",
                unit="file",
            ):
                if record is not None:
                    records.append(record)
        return records

    def save_manifest(self, crawl_run_id: str, manifest: Dict[str, Any]) -> Path:
        run_dir = self.get_run_dir(crawl_run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = run_dir / "manifest.json"
        with manifest_path.open("w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
        return manifest_path
