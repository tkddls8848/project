import json

from app.freshness import check_document_freshness


def write_manifest(storage_dir, name, started_at, checksum):
    manifests = storage_dir / "manifests"
    manifests.mkdir(parents=True, exist_ok=True)
    (manifests / name).write_text(json.dumps({
        "started_at": started_at,
        "runs": [{"files": [{
            "path": "openapi_new/15000827.json",
            "checksum": checksum,
        }]}],
    }), encoding="utf-8")


def test_changed_checksum_after_index_is_stale(tmp_path):
    write_manifest(tmp_path, "before.json", "2026-07-01T00:00:00+00:00", "sha256:before")
    write_manifest(tmp_path, "after.json", "2026-07-03T00:00:00+00:00", "sha256:after")

    report = check_document_freshness(
        ["openapi_new:15000827"], tmp_path, "2026-07-02T00:00:00+00:00"
    )

    assert report[0].status == "stale"
    assert report[0].checksum == "sha256:after"


def test_unchanged_checksum_after_index_is_fresh(tmp_path):
    write_manifest(tmp_path, "before.json", "2026-07-01T00:00:00+00:00", "sha256:same")
    write_manifest(tmp_path, "after.json", "2026-07-03T00:00:00+00:00", "sha256:same")

    report = check_document_freshness(
        ["openapi_new:15000827"], tmp_path, "2026-07-02T00:00:00+00:00"
    )

    assert report[0].status == "fresh"


def test_missing_index_timestamp_stays_unverified(tmp_path):
    write_manifest(tmp_path, "manifest.json", "2026-07-01T00:00:00+00:00", "sha256:any")

    report = check_document_freshness(["openapi_new:15000827"], tmp_path, "")

    assert report[0].status == "unverified"
    assert "빌드 시각" in report[0].message