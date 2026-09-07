"""
Phase F3 Step 6: Deterministic Haversine Distance Calculation Module.

Provides exact, deterministic great-circle distance calculations between geographic
coordinate pairs on the Earth's spherical approximation.

Invariants:
1. Determinism: Identical coordinate pairs produce bitwise identical distance floats.
2. Coordinate Bounds: Latitude must be in [-90.0, 90.0], Longitude in [-180.0, 180.0].
3. Zero Distance: Identical coordinates yield exactly 0.0 km.
4. Null Safety: Missing/null coordinates return None without raising uncaught errors.
5. Standard Radius: Uses the IUGG mean Earth radius R = 6371.0088 km.
"""

import math
from typing import Optional, Tuple, Union

# International Union of Geodesy and Geophysics (IUGG) mean Earth radius in kilometers
EARTH_RADIUS_KM: float = 6371.0088


def validate_coordinates(lat: Union[float, int], lon: Union[float, int]) -> bool:
    """
    Validates that latitude and longitude are valid numeric values within global bounds.
    """
    if lat is None or lon is None:
        return False
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        return False
    if math.isnan(lat) or math.isnan(lon) or math.isinf(lat) or math.isinf(lon):
        return False
    if not (-90.0 <= lat <= 90.0):
        return False
    if not (-180.0 <= lon <= 180.0):
        return False
    return True


def haversine_distance_km(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    radius_km: float = EARTH_RADIUS_KM
) -> float:
    """
    Computes great-circle distance between two coordinate pairs using the Haversine formula.

    Args:
        lat1: Latitude of first point in decimal degrees [-90.0, 90.0]
        lon1: Longitude of first point in decimal degrees [-180.0, 180.0]
        lat2: Latitude of second point in decimal degrees [-90.0, 90.0]
        lon2: Longitude of second point in decimal degrees [-180.0, 180.0]
        radius_km: Earth radius in kilometers (default: 6371.0088 km)

    Returns:
        Great-circle distance in kilometers as a float.

    Raises:
        ValueError: If any coordinate is invalid or out of bounds.
    """
    if not validate_coordinates(lat1, lon1):
        raise ValueError(f"Invalid coordinate pair (lat1={lat1}, lon1={lon1})")
    if not validate_coordinates(lat2, lon2):
        raise ValueError(f"Invalid coordinate pair (lat2={lat2}, lon2={lon2})")

    # Identical coordinate optimization
    if lat1 == lat2 and lon1 == lon2:
        return 0.0

    # Convert decimal degrees to radians
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    # Haversine formula
    sin_half_dphi = math.sin(delta_phi / 2.0)
    sin_half_dlambda = math.sin(delta_lambda / 2.0)

    a = (
        sin_half_dphi * sin_half_dphi
        + math.cos(phi1) * math.cos(phi2) * sin_half_dlambda * sin_half_dlambda
    )

    # Clamp a to [0.0, 1.0] to prevent floating point domain errors in math.sqrt
    a_clamped = min(1.0, max(0.0, a))

    c = 2.0 * math.atan2(math.sqrt(a_clamped), math.sqrt(1.0 - a_clamped))

    return radius_km * c


def safe_haversine_distance_km(
    lat1: Optional[float],
    lon1: Optional[float],
    lat2: Optional[float],
    lon2: Optional[float],
    radius_km: float = EARTH_RADIUS_KM
) -> Optional[float]:
    """
    Computes Haversine distance safely, returning None if any coordinate is missing or invalid.
    Never throws an exception on null or malformed coordinates.
    """
    if not validate_coordinates(lat1, lon1) or not validate_coordinates(lat2, lon2):
        return None
    try:
        return haversine_distance_km(lat1, lon1, lat2, lon2, radius_km=radius_km)
    except ValueError:
        return None
