import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from tqdm import tqdm


KST = timezone(timedelta(hours=9))


def find_project_root(start: Path) -> Path:
    """`.nara-root` 마커를 위로 훑어 저장소 루트를 찾는다.

    디렉터리 깊이에 의존하지 않으므로 모듈을 services/ 아래로 옮겨도 같은 지점을 가리킨다.
    마커를 못 찾으면 예전 규약(모듈이 루트의 직계 자식)으로 폴백한다.

    모듈 간 import 금지 제약 때문에 이 함수는 각 모듈에 복제되어 있다.
    """
    for candidate in (start, *start.parents):
        if (candidate / ".nara-root").is_file():
            return candidate
    return start.parent


class CrawlRunManager:
    """공유 데이터 루트(nara_storage)와 크롤 실행 기록을 관리한다."""

    def __init__(self, base_dir: str | Path):
        # base_dir = 크롤러 프로젝트 루트. 데이터 루트는 .nara-root 마커로 찾는다
        # (마커가 없으면 예전 규약대로 base_dir의 부모). run 폴더 없이 평면 저장.
        self.base_dir = Path(base_dir)
        self.storage_dir = find_project_root(self.base_dir) / "nara_storage"
        self.manifests_dir = self.storage_dir / "manifests"

    @staticmethod
    def create_run_id(now: datetime | None = None) -> str:
        now = now or datetime.now(KST)
        return now.astimezone(KST).strftime("%Y-%m-%dT%H-%M-%S")

    def get_raw_output_dir(self, data_type: str) -> Path:
        return self.storage_dir / data_type

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
            rel_path = path.relative_to(self.storage_dir).as_posix()
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
        self.manifests_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = self.manifests_dir / f"{crawl_run_id}.json"
        with manifest_path.open("w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
        return manifest_path
