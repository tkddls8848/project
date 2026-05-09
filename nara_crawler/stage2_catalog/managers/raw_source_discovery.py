import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class RawFileRef:
    data_type: str
    api_type: str
    source_object_id: str
    raw_path: Path
    crawl_run_id: Optional[str]
    is_legacy: bool
    is_refined: bool = False


def _source_id_from_path(path: Path) -> str:
    return path.stem.split("_", 1)[0]


def _source_id_from_refined_path(path: Path) -> str:
    match = re.search(r"_(\d+)_refined$", path.stem)
    if match:
        return match.group(1)
    return _source_id_from_path(path)


def _iter_json_files(path: Path):
    if not path.exists():
        return
    for file_path in path.rglob("*.json"):
        if file_path.name in {"manifest.json"} or file_path.name.endswith("_summary.json"):
            continue
        yield file_path


def discover_raw_files(
    base_dir: Path,
    data_type: str | None = None,
    crawl_run_id: str | None = None,
    include_legacy: bool = False,
) -> list[RawFileRef]:
    refs: list[RawFileRef] = []
    data_root = base_dir / "data"

    runs_root = data_root / "01_raw"
    run_dirs = []
    if crawl_run_id:
        run_dirs = [runs_root / crawl_run_id]
    elif runs_root.exists():
        run_dirs = [p for p in runs_root.iterdir() if p.is_dir()]

    for run_dir in run_dirs:
        if not run_dir.exists():
            continue
        for candidate_type in ("openapi", "fileData", "standard"):
            if data_type and data_type != candidate_type:
                continue
            type_dir = run_dir / candidate_type
            for file_path in _iter_json_files(type_dir) or []:
                api_type = file_path.parent.name if candidate_type == "openapi" else candidate_type
                refs.append(
                    RawFileRef(
                        data_type=candidate_type,
                        api_type=api_type,
                        source_object_id=_source_id_from_path(file_path),
                        raw_path=file_path,
                        crawl_run_id=run_dir.name,
                        is_legacy=False,
                    )
                )

    if include_legacy:
        legacy_root = data_root / "raw_data"
        legacy_specs = [
            ("openapi", "openapi_new", legacy_root / "01_openapi_results" / "openapi_new"),
            ("openapi", "openapi_old", legacy_root / "01_openapi_results" / "openapi_old"),
            ("openapi", "openapi_link", legacy_root / "01_openapi_results" / "openapi_link"),
            ("fileData", "fileData", legacy_root / "02_fileData_results"),
            ("standard", "standard", legacy_root / "03_standard_results"),
        ]
        for candidate_type, api_type, folder in legacy_specs:
            if data_type and data_type != candidate_type:
                continue
            for file_path in _iter_json_files(folder) or []:
                if file_path.name == "mappings.json":
                    continue
                refs.append(
                    RawFileRef(
                        data_type=candidate_type,
                        api_type=api_type,
                        source_object_id=_source_id_from_path(file_path),
                        raw_path=file_path,
                        crawl_run_id="legacy",
                        is_legacy=True,
                    )
                )

    return sorted(refs, key=lambda r: (r.crawl_run_id or "", r.data_type, r.api_type, r.source_object_id))


def discover_refined_files(
    base_dir: Path,
    data_type: str | None = None,
) -> list[RawFileRef]:
    refs: list[RawFileRef] = []
    refined_root = base_dir / "data" / "refined_data"
    if not refined_root.exists():
        return refs

    for folder in refined_root.iterdir():
        if not folder.is_dir():
            continue
        if folder.name.startswith("openapi"):
            candidate_type = "openapi"
            api_type = folder.name
        else:
            candidate_type = folder.name
            api_type = folder.name
        if data_type and data_type != candidate_type:
            continue
        for file_path in _iter_json_files(folder) or []:
            refs.append(
                RawFileRef(
                    data_type=candidate_type,
                    api_type=api_type,
                    source_object_id=_source_id_from_refined_path(file_path),
                    raw_path=file_path,
                    crawl_run_id="refined",
                    is_legacy=False,
                    is_refined=True,
                )
            )

    return sorted(refs, key=lambda r: (r.data_type, r.api_type, r.source_object_id))
