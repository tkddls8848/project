import json

import pytest

from profiling.quality import ProfileOptions, generate_quality_report
from profiling.schema_infer import infer_schema


@pytest.fixture
def quality_csv():
    return (
        "id,region,value,note\n"
        "001,서울,10,ok\n"
        "002,서울,11,ok\n"
        "003,,12,\n"
        "004,부산,13,ok\n"
        "004,부산,13,ok\n"
        "005,부산,200,bad\n"
    ).encode("utf-8")


def test_quality_report_covers_missing_duplicates_distributions_and_outliers(quality_csv):
    schema = infer_schema(quality_csv, filename="fixture.csv")
    report = generate_quality_report(schema, quality_csv)
    columns = {column["name"]: column for column in report.columns}

    assert report.mode == "sample"
    assert report.dataset["observed_rows"] == 6
    assert report.dataset["duplicate_rows"] == 1
    assert report.dataset["duplicate_ratio"] == pytest.approx(1 / 6)
    assert columns["region"]["missing_ratio"] == pytest.approx(1 / 6)
    assert columns["value"]["distribution"]["kind"] == "numeric"
    assert any(item["column"] == "value" and item["kind"] == "iqr" for item in report.outlier_candidates)
    assert json.loads(report.to_json())["scope"]["population_estimates"] == "unverified"


def test_explicit_full_mode_and_optional_html_are_machine_safe(quality_csv):
    schema = infer_schema(quality_csv, filename="fixture.csv")
    report = generate_quality_report(schema, quality_csv, options=ProfileOptions(full=True))

    assert report.mode == "full"
    assert report.scope["population_estimates"] == "verified"
    assert "<table>" in report.to_html(title="Fixture & quality")
    assert "Fixture &amp; quality" in report.to_html(title="Fixture & quality")


def test_default_row_cap_is_explicit_and_does_not_claim_full():
    schema = {
        "status": "ok",
        "format": "csv",
        "delimiter": ",",
        "columns": [{"name": "value", "inferred_type": "integer", "null_ratio": 0.0}],
    }
    records = ({"value": number} for number in range(5))
    report = generate_quality_report(schema, records, options=ProfileOptions(max_rows=3))

    assert report.dataset["observed_rows"] == 3
    assert report.scope["row_limit_reached"] is True
    assert report.mode == "sample"


def test_type_mismatch_is_reported_as_an_anomaly_candidate():
    schema = {
        "status": "ok",
        "format": "csv",
        "delimiter": ",",
        "columns": [{"name": "count", "inferred_type": "integer", "null_ratio": 0.0}],
    }
    report = generate_quality_report(schema, [{"count": "1"}, {"count": "oops"}])

    consistency = report.columns[0]["type_consistency"]
    assert consistency["ratio"] == 0.5
    assert report.outlier_candidates == [
        {
            "column": "count",
            "kind": "type_mismatch",
            "row_number": 2,
            "value": "oops",
            "observed_type": "string",
        }
    ]
