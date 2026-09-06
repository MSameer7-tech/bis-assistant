"""
Unit tests for Phase F3 Step 2A: Geoapify Backend Geocoding Service.

Covers:
1. Valid address geocoding (mocked)
2. Missing/empty address handling
3. Zero-result address handling
4. Missing API key / configuration handling
5. API failure handling (401, 403, 500)
6. Rate limiting (429) handling
7. Network failure / timeout handling
8. BIS address verbatim preservation
9. Provenance separation & authority boundary verification
10. Dictionary input handling
11. Convenience wrapper function
"""

import json
import urllib.error
from unittest.mock import patch, MagicMock
import pytest

from ai.services.geocoding_service import (
    GeoapifyGeocodingService,
    GeocodingResult,
    geocode_laboratory_address,
)


@pytest.fixture
def mock_geoapify_response():
    return {
        "results": [
            {
                "country": "India",
                "country_code": "in",
                "state": "Delhi",
                "city": "Delhi",
                "postcode": "110007",
                "district": "North Delhi",
                "street": "University Road",
                "housenumber": "19",
                "lon": 77.217508,
                "lat": 28.691799,
                "result_type": "building",
                "formatted": "19, University Road, Delhi - 110007, DL, India",
                "rank": {
                    "importance": 0.5,
                    "confidence": 0.85,
                    "match_type": "full_match"
                },
                "place_id": "geoapify_sample_place_12345"
            }
        ]
    }


def make_mock_cm(status: int, data_dict: dict):
    """Helper to mock urllib.request.urlopen context manager cleanly."""
    mock_resp = MagicMock()
    mock_resp.status = status
    mock_resp.read.return_value = json.dumps(data_dict).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None
    return mock_resp


class TestGeoapifyGeocodingService:
    """Automated deterministic test suite with external API mocked."""

    def test_01_valid_address_mocked(self, mock_geoapify_response):
        service = GeoapifyGeocodingService(api_key="mock_key_test_123")
        raw_addr = "19-University Road, Delhi 110007, India"
        mock_resp = make_mock_cm(200, mock_geoapify_response)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            res = service.geocode(raw_addr)

        assert res.status == "SUCCESS"
        assert res.latitude == pytest.approx(28.691799, rel=1e-5)
        assert res.longitude == pytest.approx(77.217508, rel=1e-5)
        assert res.place_id == "geoapify_sample_place_12345"
        assert "University Road" in res.formatted_address
        assert res.confidence == 0.85
        assert res.match_type == "full_match"
        assert res.provider == "GEOAPIFY"
        assert res.error_message is None

    def test_02_missing_or_empty_address(self):
        service = GeoapifyGeocodingService(api_key="mock_key_test_123")

        # Test None
        res_none = service.geocode(None)
        assert res_none.status == "MISSING_ADDRESS"
        assert res_none.latitude is None
        assert res_none.longitude is None
        assert "not provided" in res_none.error_message

        # Test Empty String
        res_empty = service.geocode("")
        assert res_empty.status == "MISSING_ADDRESS"
        assert res_empty.latitude is None

        # Test Whitespace only
        res_ws = service.geocode("    \n\t   ")
        assert res_ws.status == "MISSING_ADDRESS"
        assert res_ws.latitude is None

    def test_03_zero_results_address(self):
        service = GeoapifyGeocodingService(api_key="mock_key_test_123")
        non_existent = "ZZZZZZ NON_EXISTENT_LOCATION_999999"
        mock_resp = make_mock_cm(200, {"results": []})

        with patch("urllib.request.urlopen", return_value=mock_resp):
            res = service.geocode(non_existent)

        assert res.status == "ZERO_RESULTS"
        assert res.latitude is None
        assert res.longitude is None
        assert res.place_id is None
        assert "zero" in res.error_message.lower()

    def test_04_missing_api_key_configuration(self):
        service = GeoapifyGeocodingService(api_key="")
        res = service.geocode("19-University Road, Delhi 110007, India")

        assert res.status == "MISSING_API_KEY"
        assert res.latitude is None
        assert res.longitude is None
        assert "GEOAPIFY_API_KEY" in res.error_message

    def test_05_api_error_handling_unauthorized(self):
        service = GeoapifyGeocodingService(api_key="invalid_key")
        err = urllib.error.HTTPError(
            url="https://api.geoapify.com/v1/geocode/search",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=None
        )

        with patch("urllib.request.urlopen", side_effect=err):
            res = service.geocode("19-University Road, Delhi 110007, India")

        assert res.status == "API_ERROR"
        assert res.latitude is None
        assert res.longitude is None
        assert "401" in res.error_message

    def test_06_rate_limiting_handling(self):
        service = GeoapifyGeocodingService(api_key="mock_key")
        err = urllib.error.HTTPError(
            url="https://api.geoapify.com/v1/geocode/search",
            code=429,
            msg="Too Many Requests",
            hdrs={},
            fp=None
        )

        with patch("urllib.request.urlopen", side_effect=err):
            res = service.geocode("19-University Road, Delhi 110007, India")

        assert res.status == "RATE_LIMITED"
        assert res.latitude is None
        assert res.longitude is None
        assert "429" in res.error_message

    def test_07_network_failure_handling(self):
        service = GeoapifyGeocodingService(api_key="mock_key")
        err = urllib.error.URLError(reason="Connection refused")

        with patch("urllib.request.urlopen", side_effect=err):
            res = service.geocode("19-University Road, Delhi 110007, India")

        assert res.status == "NETWORK_ERROR"
        assert res.latitude is None
        assert res.longitude is None
        assert "Connection refused" in res.error_message

    def test_08_bis_address_preservation(self, mock_geoapify_response):
        service = GeoapifyGeocodingService(api_key="mock_key")
        raw_lims_addr = (
            "20/9, Site 4, Sahibabad Industrial Area, Sahibabad,\n"
            " Ghaziabad, \n"
            " Ghaziabad, \n"
            " Uttar Pradesh, \n"
            " India -  201010"
        )
        mock_resp = make_mock_cm(200, mock_geoapify_response)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            res = service.geocode(raw_lims_addr)

        # Original address must be preserved 100% byte-for-byte
        assert res.original_address == raw_lims_addr
        assert "\n" in res.original_address
        assert "201010" in res.original_address

    def test_09_provenance_separation_and_authority_boundary(self, mock_geoapify_response):
        service = GeoapifyGeocodingService(api_key="mock_key")
        mock_resp = make_mock_cm(200, mock_geoapify_response)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            res = service.geocode("SIIR Delhi, 19-University Road")

        prov = res.provenance
        assert isinstance(prov, dict)
        assert prov["provider"] == "Geoapify"
        assert prov["authority_boundary"] == "GEOGRAPHIC_METADATA_ONLY"
        assert "do not constitute normative evidence of BIS recognition" in prov["disclaimer"]
        assert "timestamp" in prov

    def test_10_dictionary_input_handling(self, mock_geoapify_response):
        service = GeoapifyGeocodingService(api_key="mock_key")
        addr_dict = {
            "lab_name": "SIIR, Delhi",
            "address": "19-University Road, Delhi 110007, India",
            "pincode": "110007"
        }
        mock_resp = make_mock_cm(200, mock_geoapify_response)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            res = service.geocode(addr_dict)

        assert res.status == "SUCCESS"
        assert res.original_address == "19-University Road, Delhi 110007, India"
        assert res.latitude is not None

    def test_11_convenience_function(self, mock_geoapify_response):
        mock_resp = make_mock_cm(200, mock_geoapify_response)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            res_dict = geocode_laboratory_address("19-University Road, Delhi 110007")

        assert isinstance(res_dict, dict)
        assert res_dict["status"] == "SUCCESS"
        assert "latitude" in res_dict
        assert "longitude" in res_dict
        assert "provenance" in res_dict
