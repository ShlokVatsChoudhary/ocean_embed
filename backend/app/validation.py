"""Validation helpers for API query parameters.

These helpers keep obvious domain checks separate from service logic and are intended to
support a future real backend without introducing database or ML-specific rules.
"""

from __future__ import annotations


def validate_latitude(value: float, field_name: str = "latitude") -> float:
    """Validate latitude values using obvious geospatial bounds."""
    if value < -90.0 or value > 90.0:
        raise ValueError(f"{field_name} must be between -90 and 90.")
    return value


def validate_longitude(value: float, field_name: str = "longitude") -> float:
    """Validate longitude values using obvious geospatial bounds."""
    if value < -180.0 or value > 180.0:
        raise ValueError(f"{field_name} must be between -180 and 180.")
    return value


def validate_depth(value: float, field_name: str = "depth") -> float:
    """Validate depth as a non-negative ocean depth in meters."""
    if value < 0.0:
        raise ValueError(f"{field_name} must be greater than or equal to 0.")
    return value


def validate_geographic_bounds(
    min_value: float | None,
    max_value: float | None,
    min_name: str,
    max_name: str,
) -> tuple[float | None, float | None]:
    """Validate paired geographic bounds where both values are present."""
    if min_value is not None and max_value is not None and min_value > max_value:
        raise ValueError(f"{min_name} cannot be greater than {max_name}.")
    return min_value, max_value
