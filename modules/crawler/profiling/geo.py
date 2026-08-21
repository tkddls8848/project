"""Offline coordinate validation and GeoJSON generation for map consumers."""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Protocol, Sequence


# A deliberately conservative bounding box that includes Jeju and Korean islands.
KOREA_LATITUDE_RANGE = (32.0, 39.5)
KOREA_LONGITUDE_RANGE = (124.0, 132.0)

_LATITUDE_NAMES = {"lat", "latitude", "위도", "y", "ycoord", "ycoordinate", "y좌표"}
_LONGITUDE_NAMES = {"lon", "lng", "long", "longitude", "경도", "x", "xcoord", "xcoordinate", "x좌표"}


@dataclass(frozen=True)
class CoordinateValidation:
    status: str
    latitude: Optional[float]
    longitude: Optional[float]
    reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CoordinateProfile:
    latitude_column: Optional[str]
    longitude_column: Optional[str]
    status: str
    valid_sample_ratio: Optional[float]
    sampled_pairs: int
    geocoding_required: bool
    reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GeocodingRequest:
    """A provider-neutral request record; this module never sends it."""

    record_id: str
    address: str
    status: str = "unverified"


class GeocodingProvider(Protocol):
    """Interface boundary for an integration owned outside this repository."""

    def geocode(self, request: GeocodingRequest) -> CoordinateValidation:
        ...


def validate_korean_coordinate(latitude: Any, longitude: Any) -> CoordinateValidation:
    """Validate numeric WGS84-like coordinates against South Korea's bounds."""

    lat = _coordinate_float(latitude)
    lon = _coordinate_float(longitude)
    if lat is None or lon is None:
        return CoordinateValidation("unverified", lat, lon, "missing or non-numeric coordinate")
    if not (KOREA_LATITUDE_RANGE[0] <= lat <= KOREA_LATITUDE_RANGE[1]):
        return CoordinateValidation("invalid", lat, lon, "latitude outside South Korea bounds")
    if not (KOREA_LONGITUDE_RANGE[0] <= lon <= KOREA_LONGITUDE_RANGE[1]):
        return CoordinateValidation("invalid", lat, lon, "longitude outside South Korea bounds")
    return CoordinateValidation("verified", lat, lon)


def inspect_coordinate_columns(schema: Any) -> CoordinateProfile:
    """Detect latitude/longitude columns and validate paired T3 sample values."""

    columns = list(_schema_columns(schema))
    latitude = next((column for column in columns if _axis(_field(column, "name", "")) == "lat"), None)
    longitude = next((column for column in columns if _axis(_field(column, "name", "")) == "lon"), None)
    lat_name = str(_field(latitude, "name", "")) if latitude is not None else None
    lon_name = str(_field(longitude, "name", "")) if longitude is not None else None

    if latitude is None or longitude is None:
        missing = "both coordinate columns" if latitude is None and longitude is None else "one coordinate column"
        return CoordinateProfile(
            lat_name,
            lon_name,
            "unverified",
            None,
            0,
            True,
            f"{missing} missing; mark records as geocoding targets",
        )

    lat_samples = list(_field(latitude, "sample_values", []) or [])
    lon_samples = list(_field(longitude, "sample_values", []) or [])
    validations = [
        validate_korean_coordinate(lat, lon) for lat, lon in zip(lat_samples, lon_samples)
    ]
    if not validations:
        return CoordinateProfile(
            lat_name, lon_name, "unverified", None, 0, False, "coordinate columns have no paired samples"
        )

    valid = sum(result.status == "verified" for result in validations)
    ratio = valid / len(validations)
    status = "verified" if valid == len(validations) else "invalid"
    reason = None if status == "verified" else "one or more sampled coordinates are invalid or unverified"
    return CoordinateProfile(
        lat_name, lon_name, status, round(ratio, 3), len(validations), False, reason
    )


detect_coordinate_columns = inspect_coordinate_columns


def prepare_geocoding_requests(
    records: Iterable[Mapping[str, Any]],
    *,
    address_column: str,
    id_column: Optional[str] = None,
) -> List[GeocodingRequest]:
    """Prepare offline candidates without contacting a geocoding service."""

    requests: List[GeocodingRequest] = []
    for index, record in enumerate(records):
        address = str(record.get(address_column, "")).strip()
        if not address:
            continue
        record_id = str(record.get(id_column, index)) if id_column else str(index)
        requests.append(GeocodingRequest(record_id=record_id, address=address))
    return requests


def records_to_geojson(
    records: Iterable[Mapping[str, Any]],
    *,
    latitude_column: Optional[str] = None,
    longitude_column: Optional[str] = None,
) -> Dict[str, Any]:
    """Convert rows to GeoJSON, retaining unverified rows with null geometry.

    No coordinate is synthesized.  Invalid, absent, or non-numeric coordinates
    produce ``geometry: null`` and an explicit status in feature properties.
    """

    rows = list(records)
    if rows and (latitude_column is None or longitude_column is None):
        keys = list(rows[0].keys())
        latitude_column = latitude_column or next((key for key in keys if _axis(key) == "lat"), None)
        longitude_column = longitude_column or next((key for key in keys if _axis(key) == "lon"), None)

    features: List[Dict[str, Any]] = []
    statuses: List[str] = []
    for record in rows:
        validation = validate_korean_coordinate(
            record.get(latitude_column) if latitude_column else None,
            record.get(longitude_column) if longitude_column else None,
        )
        statuses.append(validation.status)
        properties = dict(record)
        properties["coordinate_status"] = validation.status
        if validation.reason:
            properties["coordinate_reason"] = validation.reason
        geometry = None
        if validation.status == "verified":
            geometry = {
                "type": "Point",
                "coordinates": [validation.longitude, validation.latitude],
            }
        features.append({"type": "Feature", "geometry": geometry, "properties": properties})

    collection_status = "verified"
    if any(status == "invalid" for status in statuses):
        collection_status = "invalid"
    elif not statuses or any(status == "unverified" for status in statuses):
        collection_status = "unverified"
    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "coordinate_status": collection_status,
            "latitude_column": latitude_column,
            "longitude_column": longitude_column,
        },
    }


to_geojson = records_to_geojson


def _axis(name: Any) -> Optional[str]:
    normalized = re.sub(r"[\s_.-]+", "", str(name).strip().lower())
    if normalized in _LATITUDE_NAMES:
        return "lat"
    if normalized in _LONGITUDE_NAMES:
        return "lon"
    return None


def _coordinate_float(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _schema_columns(schema: Any) -> Iterable[Any]:
    if isinstance(schema, Mapping):
        return schema.get("columns", [])
    columns = getattr(schema, "columns", None)
    if columns is not None:
        return columns
    if isinstance(schema, Sequence) and not isinstance(schema, (str, bytes, bytearray)):
        return schema
    raise TypeError("schema must be a SchemaInference, column sequence, or mapping")


def _field(value: Any, name: str, default: Any) -> Any:
    if value is None:
        return default
    return value.get(name, default) if isinstance(value, Mapping) else getattr(value, name, default)
