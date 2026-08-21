import json


def test_build_relations_writes_derived_jsonl(monkeypatch, tmp_path, fixture_apidata_dir):
    from backend.core import config
    from backend.relations.builder import build_relations

    monkeypatch.setattr(config, "APIDATA_DIR", fixture_apidata_dir)
    output = tmp_path / "relations.jsonl"
    summary = build_relations(output_path=output)

    assert summary["documents"] == 3
    lines = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    # 파일에는 param-overlap·io-chain만 기록한다 (min_shared_params=2라 1개 공유는 제외)
    assert {edge["type"] for edge in lines} == {"io-chain"}
    assert all(edge["status"] == "derived" for edge in lines)
    chain = lines[0]
    assert chain["source"] == "openapi_new:15000003"
    assert chain["target"] == "openapi_new:15000001"


def test_build_relations_skips_non_object_json(monkeypatch, tmp_path, fixture_apidata_dir):
    import shutil
    from backend.core import config
    from backend.relations.builder import build_relations

    apidata = tmp_path / "apidata"
    apidata.mkdir()
    for name in ("15000001_20260101120000.json", "15000003_20260101120000.json"):
        shutil.copy(fixture_apidata_dir / name, apidata / name)
    (apidata / "15999998_20260101120000.json").write_text("[1, 2, 3]", encoding="utf-8")

    monkeypatch.setattr(config, "APIDATA_DIR", apidata)
    summary = build_relations(output_path=tmp_path / "relations.jsonl")
    assert summary["documents"] == 2  # 불량 파일은 건너뛴다
    assert summary["relations"] == 1
