"""Authoritative inventory for flat OpenAPI detail documents."""

from pathlib import Path


def build_flat_file_index(apidata_dir: Path) -> dict[str, Path]:
    """Return the newest JSON file for each API ID in ``apidata_dir``.

    Crawler output is named either ``{api_id}.json`` or
    ``{api_id}_{timestamp}.json``.  Search results must be limited to this
    inventory because these are the documents the detail endpoint can serve.
    """
    if not apidata_dir.exists():
        return {}

    files_by_id: dict[str, Path] = {}
    for path in sorted(apidata_dir.glob("**/*.json")):
        api_id = path.stem.split("_", 1)[0].strip()
        if api_id:
            files_by_id[api_id] = path
    return files_by_id
