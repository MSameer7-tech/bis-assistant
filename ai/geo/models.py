"""
Phase F3 Step 5A: Geographic Metadata Models.

Defines the isolated geographic metadata structure binding Geoapify coordinate
resolutions to stable Bureau of Indian Standards (BIS) laboratory identities.

Invariants:
- Geoapify coordinates are strictly supplementary spatial metadata.
- They NEVER constitute evidence of BIS recognition, laboratory identity, or testing scope.
- original_address is preserved verbatim from statutory BIS records.
- Geoapify formatted_address is stored strictly in formatted_address and NEVER overwrites original_address.
- If geocoding fails or yields zero results, latitude and longitude are strictly None.
"""

import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional, Dict, Any


def compute_address_hash(address: str) -> str:
    """
    Computes a deterministic SHA-256 hash of a normalized address string.
    Normalizes whitespace and case to ensure deterministic cache keys.
    """
    clean_addr = " ".join((address or "").strip().lower().split())
    return hashlib.sha256(clean_addr.encode("utf-8")).hexdigest()


def generate_cache_key(internal_id: int, address: str) -> str:
    """
    Generates a deterministic cache key binding internal laboratory ID
    to the specific address text.
    """
    addr_hash = compute_address_hash(address)
    return f"GEO_LAB_{internal_id}_{addr_hash[:16]}"


@dataclass
class LabGeographicMetadata:
    """
    Supplementary geographic coordinate metadata for a BIS laboratory.
    Maintains strict separation between statutory BIS attributes and
    external spatial provider outputs.
    """
    internal_id: int
    public_lab_code: Optional[str]
    original_address: str
    address_hash: str
    cache_key: str
    status: str  # "SUCCESS" | "ZERO_RESULTS" | "MISSING_ADDRESS" | "MISSING_API_KEY" | "RATE_LIMITED" | "API_ERROR" | "NETWORK_ERROR"
    provider: str = "GEOAPIFY"
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    place_id: Optional[str] = None
    formatted_address: Optional[str] = None
    confidence: Optional[float] = None
    match_type: Optional[str] = None
    error_message: Optional[str] = None
    provider_metadata: Dict[str, Any] = field(default_factory=dict)
    retrieved_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    authority_boundary: str = (
        "Geoapify provides supplementary geographic metadata only. "
        "It does not constitute normative evidence of BIS recognition, "
        "laboratory capability, testing scope, or accreditation."
    )

    def has_valid_coordinates(self) -> bool:
        """Returns True only if status is SUCCESS with non-null float coordinates."""
        return (
            self.status == "SUCCESS"
            and self.latitude is not None
            and self.longitude is not None
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LabGeographicMetadata":
        return cls(
            internal_id=data["internal_id"],
            public_lab_code=data.get("public_lab_code"),
            original_address=data["original_address"],
            address_hash=data["address_hash"],
            cache_key=data["cache_key"],
            status=data["status"],
            provider=data.get("provider", "GEOAPIFY"),
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            place_id=data.get("place_id"),
            formatted_address=data.get("formatted_address"),
            confidence=data.get("confidence"),
            match_type=data.get("match_type"),
            error_message=data.get("error_message"),
            provider_metadata=data.get("provider_metadata", {}) or {},
            retrieved_at=data.get("retrieved_at", datetime.now(timezone.utc).isoformat()),
            authority_boundary=data.get(
                "authority_boundary",
                "Geoapify provides supplementary geographic metadata only."
            )
        )
