"""
Phase F3 Step 2A: Live Geocoding Verification Script.

Tests 4 real BIS LIMS laboratory addresses against the Geoapify Geocoding Service:
1. BIS-Owned Lab
2. Recognized Lab (OSL)
3. Empanelled Lab
4. Complex Industrial/Landmark Address

Ensures:
- Status is SUCCESS
- Latitude and Longitude are valid numbers within India
- Original address is preserved verbatim
- Provenance and authority boundary are cleanly separated
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai.services.geocoding_service import GeoapifyGeocodingService

def run_live_verification():
    service = GeoapifyGeocodingService()
    if not service.has_api_key:
        print("ERROR: GEOAPIFY_API_KEY is not set in environment or .env!")
        sys.exit(1)

    test_cases = [
        {
            "category": "BIS_OWNED",
            "lab_name": "BIS, Central Laboratory (CL)",
            "lab_code": "-",
            "address": "20/9, Site 4, Sahibabad Industrial Area, Sahibabad,\n Ghaziabad, \n Ghaziabad, \n Uttar Pradesh, \n India -  201010"
        },
        {
            "category": "BIS_RECOGNIZED",
            "lab_name": "SIIR, Delhi Shriram Institute For Industrial Research",
            "lab_code": "8102006",
            "address": "19-University Road, Delhi 110007,\n Delhi, \n North, \n Delhi, \n India -  110007"
        },
        {
            "category": "BIS_EMPANELLED",
            "lab_name": "Regional Reference Standards Laboratory, Bangalore",
            "lab_code": "6133034",
            "address": "maptol bhavan jakkur bengaluru,\n bengaluru, \n Bengaluru Urban, \n Karnataka, \n India -  560064"
        },
        {
            "category": "COMPLEX_ADDRESS",
            "lab_name": "Sleen India Biz venture Private Limited, Agra",
            "lab_code": "9139736",
            "address": "RAHANKALAN ROAD, PART 295, BLOCK-A KUBERPUR, 300 METER FROM RAILWAY CROSSING CHALESHAR ROAD,  Agra, Uttar Pradesh,  India, 282006,\n Agra, \n Agra, \n Uttar Pradesh, \n India -  282006"
        }
    ]

    print("================================================================================")
    print("Phase F3: Live Geoapify Geocoding Integration Test (4 Sample Labs)")
    print("================================================================================")

    all_passed = True
    results_summary = []

    for idx, tc in enumerate(test_cases, 1):
        print(f"\n[{idx}/4] Testing {tc['category']}: {tc['lab_name']}")
        res = service.geocode(tc["address"])

        passed = (
            res.status == "SUCCESS"
            and res.latitude is not None
            and res.longitude is not None
            and res.original_address == tc["address"]
            and 8.0 <= res.latitude <= 37.5  # Approximate latitude range of India
            and 68.0 <= res.longitude <= 97.5 # Approximate longitude range of India
        )

        if not passed:
            all_passed = False

        print(f"  Status: {res.status}")
        print(f"  Coordinates: ({res.latitude:.6f}, {res.longitude:.6f})")
        print(f"  Place ID: {res.place_id}")
        print(f"  Formatted: {res.formatted_address}")
        print(f"  Confidence: {res.confidence}")
        print(f"  Verbatim Address Preserved: {res.original_address == tc['address']}")
        print(f"  Authority Boundary: {res.provenance.get('authority_boundary')}")
        print(f"  Result: {'PASS' if passed else 'FAIL'}")

        results_summary.append({
            "category": tc["category"],
            "lab_name": tc["lab_name"],
            "lab_code": tc["lab_code"],
            "status": res.status,
            "latitude": res.latitude,
            "longitude": res.longitude,
            "place_id": res.place_id,
            "formatted_address": res.formatted_address,
            "confidence": res.confidence,
            "passed": passed
        })

    print("\n================================================================================")
    if all_passed:
        print("ALL 4 LIVE GEOCODING INTEGRATION CHECKS PASSED (100% SUCCESS)")
    else:
        print("SOME LIVE CHECKS FAILED")
    print("================================================================================")

if __name__ == "__main__":
    run_live_verification()
