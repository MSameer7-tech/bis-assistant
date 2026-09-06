"""
Phase F3: STEP 2A - Geoapify Backend Geocoding Service.

Provides isolated, server-side geographic coordinate resolution for authoritative
Bureau of Indian Standards (BIS) laboratory addresses using the Geoapify Geocoding API.

Architectural Invariants:
1. Server-Side Only: The Geoapify API key is read strictly from GEOAPIFY_API_KEY and NEVER
   exposed to frontend clients or browser JavaScript.
2. Immutability & Provenance: The original BIS LIMS address is preserved 100% verbatim.
   Geoapify outputs are isolated under separate geographic metadata keys.
3. Authority Boundary: Geocoder outputs are strictly spatial supplementary metadata. They do
   NOT constitute normative evidence of BIS recognition, laboratory authorization, or testing capability.
4. Zero Coordinate Synthesis: If geocoding fails, returns zero results, or times out, coordinates
   are strictly set to None. Fake or fallback coordinates are NEVER fabricated.
5. Error Resilience: Handles missing keys, empty inputs, HTTP 429 rate limits, HTTP 4xx/5xx API errors,
   and network disconnects deterministically without throwing uncaught exceptions.
"""

import os
import re
import sys
import json
import logging
import urllib.request
import urllib.parse
import urllib.error
import ssl
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, Union

logger = logging.getLogger("geocoding_service")

# Resolve repository root to discover local .env if not yet loaded in os.environ
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def load_env_if_missing():
    """Load environment variables from project .env if GEOAPIFY_API_KEY is unset."""
    if os.getenv("GEOAPIFY_API_KEY"):
        return
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'\"")
                        if k not in os.environ:
                            os.environ[k] = v
        except Exception as e:
            logger.debug("Could not read .env file: %s", e)


load_env_if_missing()


@dataclass
class GeocodingResult:
    """Structured geographic metadata produced by the Geocoding Service."""
    status: str  # "SUCCESS" | "ZERO_RESULTS" | "MISSING_ADDRESS" | "MISSING_API_KEY" | "RATE_LIMITED" | "API_ERROR" | "NETWORK_ERROR"
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    place_id: Optional[str] = None
    formatted_address: Optional[str] = None
    confidence: Optional[float] = None
    match_type: Optional[str] = None
    provider: str = "GEOAPIFY"
    original_address: str = ""
    error_message: Optional[str] = None
    raw_result: Optional[Dict[str, Any]] = None
    provenance: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class GeoapifyGeocodingService:
    """
    Isolated backend client for Geoapify Geocoding API v1.
    """
    GEOAPIFY_BASE_URL = "https://api.geoapify.com/v1/geocode/search"
    DEFAULT_TIMEOUT_SEC = 10.0

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT_SEC,
        country_filter: Optional[str] = "in"
    ):
        if api_key is None:
            load_env_if_missing()
            self._api_key = os.getenv("GEOAPIFY_API_KEY")
        else:
            self._api_key = api_key
        self.timeout = timeout
        self.country_filter = country_filter

    @property
    def has_api_key(self) -> bool:
        return bool(self._api_key and self._api_key.strip())

    def _build_provenance(self) -> Dict[str, Any]:
        return {
            "provider": "Geoapify",
            "service": "Geoapify Geocoding API (v1)",
            "endpoint": self.GEOAPIFY_BASE_URL,
            "authority_boundary": "GEOGRAPHIC_METADATA_ONLY",
            "disclaimer": (
                "Geocoded spatial coordinates are supplementary geographic metadata only. "
                "They do not constitute normative evidence of BIS recognition, laboratory "
                "authorization, or product testing capability."
            ),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    @staticmethod
    def clean_address_query(raw_address: str) -> str:
        """
        Cleans multi-line or redundantly formatted BIS LIMS address strings for search queries,
        while strictly preserving the original verbatim string for output provenance.
        """
        if not raw_address:
            return ""
        # Replace newlines, carriage returns, and excessive punctuation
        cleaned = re.sub(r"[\r\n]+", ", ", raw_address)
        # Collapse multi-spaces
        cleaned = re.sub(r"\s+", " ", cleaned)
        # Clean trailing / leading whitespace and redundant commas
        cleaned = re.sub(r",\s*,+", ", ", cleaned).strip(" ,-")
        return cleaned

    def geocode(self, address: Union[str, Dict[str, Any]]) -> GeocodingResult:
        """
        Geocode a BIS laboratory address.

        Args:
            address: Either an address string verbatim from BIS LIMS, or a dictionary containing
                     an "address" key along with optional "lab_name", "pincode", "city", "state".

        Returns:
            GeocodingResult with coordinates, place identifier, status, and provenance.
        """
        # Extract raw address string
        if isinstance(address, dict):
            raw_address = address.get("address") or address.get("raw_address") or ""
        else:
            raw_address = str(address or "")

        provenance = self._build_provenance()

        # Guard: Missing or empty address
        if not raw_address or not raw_address.strip():
            return GeocodingResult(
                status="MISSING_ADDRESS",
                original_address=raw_address,
                error_message="Laboratory address was empty or not provided.",
                provenance=provenance
            )

        # Guard: Missing API key
        if not self.has_api_key:
            return GeocodingResult(
                status="MISSING_API_KEY",
                original_address=raw_address,
                error_message="GEOAPIFY_API_KEY environment variable is not configured.",
                provenance=provenance
            )

        cleaned_query = self.clean_address_query(raw_address)
        if not cleaned_query:
            return GeocodingResult(
                status="MISSING_ADDRESS",
                original_address=raw_address,
                error_message="Laboratory address contained no searchable content after cleaning.",
                provenance=provenance
            )

        # Prepare request parameters
        params = {
            "text": cleaned_query,
            "apiKey": self._api_key,
            "format": "json",
            "limit": 1
        }
        if self.country_filter:
            params["filter"] = f"countrycode:{self.country_filter}"

        query_str = urllib.parse.urlencode(params)
        request_url = f"{self.GEOAPIFY_BASE_URL}?{query_str}"

        # Execute HTTP GET
        ctx = ssl.create_default_context()
        req = urllib.request.Request(
            request_url,
            headers={
                "User-Agent": "BIS-AI-Assistant/1.0 (Phase F3 Geocoder)",
                "Accept": "application/json"
            }
        )

        try:
            with urllib.request.urlopen(req, context=ctx, timeout=self.timeout) as resp:
                status_code = resp.status
                payload_bytes = resp.read()
                data = json.loads(payload_bytes.decode("utf-8", errors="ignore"))

                results = data.get("results", [])
                if not results:
                    return GeocodingResult(
                        status="ZERO_RESULTS",
                        original_address=raw_address,
                        error_message="Geoapify returned zero matching coordinate results for this address.",
                        provenance=provenance
                    )

                top = results[0]
                lat = top.get("lat")
                lon = top.get("lon")
                place_id = top.get("place_id")
                formatted = top.get("formatted")
                rank = top.get("rank", {})
                confidence = rank.get("confidence")
                match_type = rank.get("match_type")

                # Safe float conversion
                lat_val = float(lat) if lat is not None else None
                lon_val = float(lon) if lon is not None else None

                # Clean raw result subset (omitting redundant nested geometry blobs)
                raw_summary = {
                    "country": top.get("country"),
                    "state": top.get("state"),
                    "city": top.get("city"),
                    "postcode": top.get("postcode"),
                    "result_type": top.get("result_type"),
                    "confidence": confidence,
                    "match_type": match_type
                }

                return GeocodingResult(
                    status="SUCCESS",
                    latitude=lat_val,
                    longitude=lon_val,
                    place_id=place_id,
                    formatted_address=formatted,
                    confidence=confidence,
                    match_type=match_type,
                    original_address=raw_address,
                    raw_result=raw_summary,
                    provenance=provenance
                )

        except urllib.error.HTTPError as e:
            if e.code == 429:
                logger.warning("Geoapify rate limit exceeded (HTTP 429)")
                return GeocodingResult(
                    status="RATE_LIMITED",
                    original_address=raw_address,
                    error_message=f"Geoapify rate limit or quota exceeded (HTTP 429): {e.reason}",
                    provenance=provenance
                )
            elif e.code in (401, 403):
                logger.error("Geoapify authentication failed (HTTP %d)", e.code)
                return GeocodingResult(
                    status="API_ERROR",
                    original_address=raw_address,
                    error_message=f"Geoapify authentication/authorization failure (HTTP {e.code}): {e.reason}",
                    provenance=provenance
                )
            else:
                logger.error("Geoapify API HTTP error %d: %s", e.code, e.reason)
                return GeocodingResult(
                    status="API_ERROR",
                    original_address=raw_address,
                    error_message=f"Geoapify API returned HTTP {e.code}: {e.reason}",
                    provenance=provenance
                )

        except (urllib.error.URLError, TimeoutError, OSError) as e:
            logger.warning("Geoapify network connectivity error: %s", e)
            return GeocodingResult(
                status="NETWORK_ERROR",
                original_address=raw_address,
                error_message=f"Network error communicating with Geoapify: {str(e)}",
                provenance=provenance
            )
        except json.JSONDecodeError as e:
            logger.error("Geoapify payload decode failure: %s", e)
            return GeocodingResult(
                status="API_ERROR",
                original_address=raw_address,
                error_message="Invalid non-JSON response returned by Geoapify.",
                provenance=provenance
            )
        except Exception as e:
            logger.error("Unexpected geocoding failure: %s", e, exc_info=True)
            return GeocodingResult(
                status="API_ERROR",
                original_address=raw_address,
                error_message=f"Unexpected error during geocoding: {str(e)}",
                provenance=provenance
            )


# Default singleton instance
_default_service: Optional[GeoapifyGeocodingService] = None


def get_geocoding_service() -> GeoapifyGeocodingService:
    """Returns the default configured GeoapifyGeocodingService singleton."""
    global _default_service
    if _default_service is None:
        _default_service = GeoapifyGeocodingService()
    return _default_service


def geocode_laboratory_address(address: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Convenience function to geocode a BIS LIMS laboratory address.

    Returns a dictionary representation of GeocodingResult.
    """
    service = get_geocoding_service()
    return service.geocode(address).to_dict()
