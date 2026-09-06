"""
Phase F3 Step 5A: Geographic Metadata Cache Foundation.

Manages persistent, deterministic geographic coordinate caching for BIS laboratories.
Preserves the strict authority boundary:
- BIS LIMS remains authoritative for identity, addresses, and testing competence.
- Geoapify coordinates are isolated supplementary metadata.
- Changed addresses trigger cache misses (stale coordinates are never reused).
- Zero coordinate synthesis or interpolation on geocoding failures.
"""

import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Union

from ai.geo.models import (
    LabGeographicMetadata,
    compute_address_hash,
    generate_cache_key,
)
from ai.lims.models import NormalizedLimsLab
from ai.services.geocoding_service import (
    GeoapifyGeocodingService,
    GeocodingResult,
    get_geocoding_service,
)

DEFAULT_CACHE_DIR = Path("data/cache/geographic")
DEFAULT_CACHE_FILE = DEFAULT_CACHE_DIR / "lab_coordinates_cache.jsonl"
DEFAULT_MANIFEST_FILE = DEFAULT_CACHE_DIR / "cache_manifest.json"
DEFAULT_CHECKPOINT_FILE = DEFAULT_CACHE_DIR / "geocoding_checkpoint.json"


class LabGeographicCache:
    """
    Deterministic cache for laboratory geographic coordinates.
    References BIS laboratories without duplicating statutory scope records.
    """

    def __init__(self, cache_file: Optional[Path] = None):
        self.cache_file = cache_file or DEFAULT_CACHE_FILE
        self._by_id: Dict[int, LabGeographicMetadata] = {}
        self._by_key: Dict[str, LabGeographicMetadata] = {}

        if self.cache_file.exists():
            self.load_from_disk(self.cache_file)

    def __len__(self) -> int:
        return len(self._by_id)

    def get_by_id(self, internal_id: int) -> Optional[LabGeographicMetadata]:
        """Retrieves cached metadata by internal laboratory ID."""
        return self._by_id.get(internal_id)

    def get_by_key(self, cache_key: str) -> Optional[LabGeographicMetadata]:
        """Retrieves cached metadata by deterministic cache key."""
        return self._by_key.get(cache_key)

    def get_for_laboratory(
        self, internal_id: int, original_address: str
    ) -> Optional[LabGeographicMetadata]:
        """
        Retrieves cached geographic metadata for a laboratory, verifying that
        the cached result matches the exact address input.
        If the laboratory's address has changed, returns None (cache miss).
        """
        entry = self._by_id.get(internal_id)
        if not entry:
            return None

        current_hash = compute_address_hash(original_address)
        if entry.address_hash != current_hash:
            # Address changed: do NOT reuse coordinates for a different address!
            return None

        return entry

    def is_stale(self, internal_id: int, current_address: str) -> bool:
        """
        Returns True if a cached entry exists for internal_id, but the address
        hash does not match current_address.
        """
        entry = self._by_id.get(internal_id)
        if not entry:
            return False
        return entry.address_hash != compute_address_hash(current_address)

    def put(self, metadata: LabGeographicMetadata) -> None:
        """Stores or updates a geographic metadata entry in the cache."""
        self._by_id[metadata.internal_id] = metadata
        self._by_key[metadata.cache_key] = metadata

    def record_geocoding_result(
        self,
        internal_id: int,
        public_lab_code: Optional[str],
        original_address: str,
        result: GeocodingResult
    ) -> LabGeographicMetadata:
        """
        Converts a Step 2A GeocodingResult into a LabGeographicMetadata record
        and stores it deterministically in the cache.
        """
        addr_hash = compute_address_hash(original_address)
        cache_key = generate_cache_key(internal_id, original_address)

        meta = LabGeographicMetadata(
            internal_id=internal_id,
            public_lab_code=public_lab_code,
            original_address=original_address,
            address_hash=addr_hash,
            cache_key=cache_key,
            status=result.status,
            provider="GEOAPIFY",
            latitude=result.latitude if result.status == "SUCCESS" else None,
            longitude=result.longitude if result.status == "SUCCESS" else None,
            place_id=result.place_id,
            formatted_address=result.formatted_address,
            confidence=result.confidence,
            match_type=result.match_type,
            error_message=result.error_message,
            provider_metadata=result.raw_result or {},
            retrieved_at=datetime.now(timezone.utc).isoformat()
        )
        self.put(meta)
        return meta

    def geocode_laboratory(
        self,
        lab: Union[NormalizedLimsLab, Dict[str, Any]],
        service: Optional[GeoapifyGeocodingService] = None,
        force_refresh: bool = False
    ) -> LabGeographicMetadata:
        """
        Resolves coordinates for a BIS laboratory with caching.
        Preserves lab immutability (does not modify the input lab record).
        """
        if isinstance(lab, dict):
            internal_id = lab["internal_id"]
            lab_code = lab.get("lab_code")
            original_address = lab["original_address"]
        else:
            internal_id = lab.internal_id
            lab_code = lab.lab_code
            original_address = lab.original_address

        if not force_refresh:
            cached = self.get_for_laboratory(internal_id, original_address)
            if cached is not None:
                return cached

        geocoder = service or get_geocoding_service()
        res = geocoder.geocode(original_address)
        return self.record_geocoding_result(
            internal_id=internal_id,
            public_lab_code=lab_code,
            original_address=original_address,
            result=res
        )

    def save_to_disk(self, cache_file: Optional[Path] = None) -> None:
        """
        Persists cached geographic metadata to disk in deterministic JSONL format.
        Also writes an accompanying cache manifest with accounting statistics.
        """
        target_file = cache_file or self.cache_file
        target_dir = target_file.parent
        target_dir.mkdir(parents=True, exist_ok=True)

        sorted_entries = sorted(self._by_id.values(), key=lambda m: m.internal_id)

        with open(target_file, "w", encoding="utf-8") as f:
            for entry in sorted_entries:
                f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")

        manifest_file = target_dir / "cache_manifest.json"
        manifest_data = {
            "cache_version": "Phase F3 Step 5A",
            "total_cached_records": len(sorted_entries),
            "successful_coordinates_count": sum(1 for m in sorted_entries if m.has_valid_coordinates()),
            "zero_results_count": sum(1 for m in sorted_entries if m.status == "ZERO_RESULTS"),
            "failed_count": sum(1 for m in sorted_entries if m.status not in ("SUCCESS", "ZERO_RESULTS")),
            "provider": "GEOAPIFY",
            "authority_boundary": (
                "Geoapify provides supplementary geographic metadata only. "
                "BIS LIMS remains the sole authority for laboratory identity and capability."
            ),
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
        manifest_file.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

    def load_from_disk(self, cache_file: Optional[Path] = None) -> int:
        """Loads cached records from disk into memory."""
        target_file = cache_file or self.cache_file
        if not target_file.exists():
            return 0

        count = 0
        with open(target_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    d = json.loads(line)
                    meta = LabGeographicMetadata.from_dict(d)
                    self.put(meta)
                    count += 1
        return count

    def get_statistics(self) -> Dict[str, Any]:
        """Returns in-memory cache statistics."""
        entries = list(self._by_id.values())
        return {
            "total_cached_records": len(entries),
            "successful_coordinates_count": sum(1 for m in entries if m.has_valid_coordinates()),
            "zero_results_count": sum(1 for m in entries if m.status == "ZERO_RESULTS"),
            "failed_count": sum(1 for m in entries if m.status not in ("SUCCESS", "ZERO_RESULTS")),
            "provider": "GEOAPIFY"
        }
