import pytest

from profiling.address import detect_address_columns, validate_address
from profiling.geo import (
    inspect_coordinate_columns,
    prepare_geocoding_requests,
    records_to_geojson,
    validate_korean_coordinate,
)
from profiling.schema_infer import infer_schema


@pytest.fixture
def korean_location_schema():
    body = (
        "시설명,도로명주소,지번주소,우편번호,위도,경도\n"
        "도서관,서울특별시 중구 세종대로 110,서울특별시 중구 태평로1가 31,04524,37.5665,126.9780\n"
        "박물관,제주특별자치도 제주시 첨단로 242,제주특별자치도 제주시 영평동 2170,63309,33.4507,126.5707\n"
    ).encode("utf-8")
    return infer_schema(body, filename="locations.csv")


def test_address_columns_are_detected_and_scored(korean_location_schema):
    profiles = {profile.name: profile for profile in detect_address_columns(korean_location_schema)}

    assert profiles["도로명주소"].kind == "road"
    assert profiles["도로명주소"].status == "verified"
    assert profiles["지번주소"].format_counts["jibun"] == 2
    assert profiles["우편번호"].valid_sample_ratio == 1.0
    assert all(0.0 <= profile.quality_score <= 1.0 for profile in profiles.values())


@pytest.mark.parametrize(
    ("value", "kind", "status"),
    [
        ("서울특별시 중구 세종대로 110", "road", "verified"),
        ("서울특별시 중구 태평로1가 31", "jibun", "verified"),
        ("04524", "postal", "verified"),
        ("알 수 없음", None, "invalid"),
    ],
)
def test_address_format_validation_is_offline(value, kind, status):
    result = validate_address(value)
    assert result.kind == kind
    assert result.status == status


def test_existing_coordinates_are_checked_against_korea_bounds(korean_location_schema):
    profile = inspect_coordinate_columns(korean_location_schema)

    assert profile.status == "verified"
    assert profile.geocoding_required is False
    assert profile.valid_sample_ratio == 1.0
    assert validate_korean_coordinate(37.5, 126.9).status == "verified"
    assert validate_korean_coordinate(40.7, 126.9).status == "invalid"


def test_missing_coordinates_are_unverified_geocoding_targets():
    schema = infer_schema(
        "이름,주소\nA,부산광역시 해운대구 센텀중앙로 55\n".encode(),
        filename="address.csv",
    )
    profile = inspect_coordinate_columns(schema)
    requests = prepare_geocoding_requests(
        [{"id": "A", "주소": "부산광역시 해운대구 센텀중앙로 55"}],
        address_column="주소",
        id_column="id",
    )

    assert profile.status == "unverified"
    assert profile.geocoding_required is True
    assert requests[0].status == "unverified"


def test_geojson_never_invents_unverified_coordinates():
    geojson = records_to_geojson(
        [
            {"name": "valid", "위도": "37.5665", "경도": "126.9780"},
            {"name": "outside", "위도": "51.5", "경도": "-0.1"},
            {"name": "missing", "위도": "", "경도": ""},
        ]
    )

    assert geojson["features"][0]["geometry"] == {
        "type": "Point",
        "coordinates": [126.978, 37.5665],
    }
    assert geojson["features"][1]["geometry"] is None
    assert geojson["features"][1]["properties"]["coordinate_status"] == "invalid"
    assert geojson["features"][2]["geometry"] is None
    assert geojson["features"][2]["properties"]["coordinate_status"] == "unverified"
