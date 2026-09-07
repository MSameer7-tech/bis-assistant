"""
Geographic metadata and coordinate caching module for Phase F3 Step 5.
"""

from ai.geo.models import (
    LabGeographicMetadata,
    compute_address_hash,
    generate_cache_key,
)
from ai.geo.cache import (
    LabGeographicCache,
    DEFAULT_CACHE_DIR,
    DEFAULT_CACHE_FILE,
    DEFAULT_MANIFEST_FILE,
    DEFAULT_CHECKPOINT_FILE,
)
from ai.geo.bulk_geocoder import (
    ControlledBulkGeocoder,
    BatchAccountingSummary,
    GeocodingCheckpointManager,
)
from ai.geo.audit import (
    GeographicCacheAuditor,
    GeographicCacheAuditReport,
    QualityClassificationCounts,
    classify_record,
)
from ai.geo.distance import (
    haversine_distance_km,
    safe_haversine_distance_km,
    validate_coordinates,
    EARTH_RADIUS_KM,
)
from ai.geo.ranking import (
    GeographicDistanceMetadata,
    GeographicRankingEngine,
)

__all__ = [
    "LabGeographicMetadata",
    "compute_address_hash",
    "generate_cache_key",
    "LabGeographicCache",
    "DEFAULT_CACHE_DIR",
    "DEFAULT_CACHE_FILE",
    "DEFAULT_MANIFEST_FILE",
    "DEFAULT_CHECKPOINT_FILE",
    "ControlledBulkGeocoder",
    "BatchAccountingSummary",
    "GeocodingCheckpointManager",
    "GeographicCacheAuditor",
    "GeographicCacheAuditReport",
    "QualityClassificationCounts",
    "classify_record",
    "haversine_distance_km",
    "safe_haversine_distance_km",
    "validate_coordinates",
    "EARTH_RADIUS_KM",
    "GeographicDistanceMetadata",
    "GeographicRankingEngine",
]
