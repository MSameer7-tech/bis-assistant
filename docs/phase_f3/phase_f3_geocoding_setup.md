# Phase F3: STEP 2A & 2B - Geocoding & Leaflet Map Foundation Report
**Isolated Server-Side Geocoding & Reusable Frontend Map Component**

---

## 1. Overview & Objective

Phase F3 established the core location and mapping infrastructure for the upcoming **BIS Laboratory Finder** while strictly protecting the boundaries of the existing AI Hub 2.0 assistant:

* **STEP 2A (Backend Geocoding)**: Built an isolated server-side geocoding service via Geoapify Geocoding API v1 to resolve authoritative BIS LIMS addresses to spatial coordinates without client exposure of API keys or coordinate hallucination.
* **STEP 2B (Frontend Map Foundation)**: Created a reusable, decoupled Leaflet map component powered by HTTPS OpenStreetMap tiles with visible attribution, zero bulk downloading, and complete privacy isolation from laboratory data.

---

## 2. Environment Configuration & Backend Security (Step 2A)

### Environment Variable
- **Key Name**: `GEOAPIFY_API_KEY`
- **Location**: `.env` (Local backend environment only).
- **Template**: `.env.example` contains only `GEOAPIFY_API_KEY=` (unpopulated placeholder).

### Security Invariants
1. **Git Isolation**: Verified via `git check-ignore -v .env` and `git ls-files --error-unmatch .env` that `.env` is ignored at line 11 of `.gitignore` and has never been committed or tracked in Git history.
2. **Server-Side Exclusivity**: All calls to Geoapify originate from the Python backend service (`GeoapifyGeocodingService`). No frontend script, HTML template, or client-side JavaScript receives or transmits the API key.
3. **No Secret Recording**: The actual key is omitted from all committed source files, logs, artifacts, and documentation.

---

## 3. Backend Geocoding Architecture & Service Design

The service is implemented in `ai/services/geocoding_service.py` with zero third-party library dependencies (built directly on Python standard library `urllib.request`, `json`, and `dataclasses`).

### Request & Response Flow

```
Authoritative BIS LIMS Record (Address, Pincode, Lab Code)
                            ↓
     GeoapifyGeocodingService.geocode(address)
                            ↓
     Sanitize Query Text (Normalize Whitespace & Delimiters)
     [Original Address String Preserved Verbatim]
                            ↓
     HTTP GET api.geoapify.com/v1/geocode/search
     [apiKey via GEOAPIFY_API_KEY | filter=countrycode:in | format=json]
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ GeocodingResult                                             │
├─────────────────────────────────────────────────────────────┤
│ status: "SUCCESS" | "ZERO_RESULTS" | "MISSING_ADDRESS" ...  │
│ latitude: float | None                                      │
│ longitude: float | None                                     │
│ place_id: str | None                                        │
│ formatted_address: str | None                               │
│ confidence: float | None                                    │
│ original_address: str (Verbatim unchanged)                  │
│ provider: "GEOAPIFY"                                        │
│ provenance: {...}                                           │
└─────────────────────────────────────────────────────────────┘
```

### Provenance Model & Authority Boundary
- `original_address`: Contains the unaltered text exactly as scraped from BIS LIMS.
- `formatted_address`, `latitude`, `longitude`, `place_id`: Tagged under `provider: "GEOAPIFY"`.
- `provenance.authority_boundary = "GEOGRAPHIC_METADATA_ONLY"`.
- **Disclaimer**: Coordinates do not constitute normative evidence of BIS recognition or testing capability.
- **Zero Coordinate Fabrication**: If geocoding fails or returns zero results, `latitude` and `longitude` are strictly `None`. Fake or interpolated coordinates are never invented.

---

## 4. Frontend Leaflet Map Foundation (Step 2B)

### Reusable Map Component: `frontend/mapComponent.js`
The map component (`BisMapComponent` / `createBisMap`) is an isolated, reusable ESM module:
- **Container Mounting**: Mounts cleanly to any DOM element or ID (e.g. `createBisMap("testMap")`).
- **Configurable Tile Provider**: Defaults to HTTPS OpenStreetMap with visible attribution, allowing zero-rewrite replacement with other tile providers (e.g., Geoapify tiles, CartoDB) in future iterations.
- **Dynamic Views**: `setView(lat, lng, zoom)` allows smooth re-centering and zooming on coordinates.
- **Marker Management**:
  - `addMarker({ lat, lng, title, popupContent, category, autoOpen })` supports custom styled pins for `BIS_OWNED` (blue), `BIS_RECOGNIZED` (emerald), `BIS_EMPANELLED` (amber), and `DEFAULT` (purple).
  - `setMarkers(list, autoFitBounds = true)` manages collections of markers with automatic bounding box fitting.
  - `clearMarkers()` removes all active pins.
  - `invalidateSize()` recalculates dimensions when map panels resize or become visible.
  - `destroy()` cleans up Leaflet instances and event listeners to prevent memory leaks.

### OpenStreetMap Tile Configuration & Compliance
```javascript
export const DEFAULT_TILE_PROVIDER = {
    name: "OpenStreetMap",
    urlTemplate: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    options: {
        maxZoom: 19,
        minZoom: 3,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors'
    }
};
```
- **HTTPS Only**: All tile requests use secure `https://tile.openstreetmap.org/`.
- **Visible Attribution**: Leaflet's built-in attribution control is styled and visible at the bottom-right of the map container (`© OpenStreetMap contributors` linking to copyright).
- **No Scraping / Bulk Downloading**: No prefetching, crawling, or offline caching of tile images. Standard browser HTTP caching headers (`Cache-Control`, `ETag`) are respected.
- **Privacy Guarantee**: Tile requests follow `{z}/{x}/{y}.png`. Zero laboratory names, addresses, search terms, or user PII are sent to the tile server.

### Local Vendor Assets
To ensure deterministic, offline-capable rendering without external CDN downtime:
- `frontend/vendor/leaflet/leaflet.js` (Leaflet 1.9.4 runtime)
- `frontend/vendor/leaflet/leaflet.css` (Leaflet styles)
- `frontend/vendor/leaflet/images/` (Standard marker icons and shadows)

---

## 5. Development & Test Workbench (`frontend/map_test.html`)

An isolated test harness served at `http://127.0.0.1:3000/map_test.html` verifies:
1. Leaflet runtime loads without errors.
2. Map renders inside `.bis-map-container`.
3. OpenStreetMap attribution is prominently displayed.
4. Single markers and popups display correctly (SIIR Delhi).
5. Multiple markers (4 Step 2A sample labs across all categories) render with category badges and auto-fit bounds.
6. Zero browser console errors occur during map operations.

---

## 6. Verification & Test Results

### A. Geocoding Automated Tests (`tests/phase_f3/test_geocoding_service.py`)
All 11 tests pass deterministically with mocked HTTP layers:
- Valid address geocoding: **PASS**
- Missing / empty address handling: **PASS**
- Zero-results handling: **PASS**
- Missing API key configuration handling: **PASS**
- HTTP 401/403/500 API error handling: **PASS**
- HTTP 429 rate limit handling: **PASS**
- Network failure & timeout handling: **PASS**
- Verbatim BIS address preservation: **PASS**
- Provenance separation & authority boundary: **PASS**
- Dictionary input handling: **PASS**
- Convenience wrapper function: **PASS**

### B. Map Foundation Automated Tests (`tests/phase_f3/test_map_component.py`)
All 8 map foundation tests pass:
- Leaflet vendor assets exist locally: **PASS**
- `mapComponent.js` exports and structure: **PASS**
- OpenStreetMap HTTPS tile configuration & attribution: **PASS**
- `map_test.html` test harness DOM structure: **PASS**
- `styles.css` map container, pin, and popup rules: **PASS**
- No Google Maps dependencies (`maps.googleapis.com` / `google.maps` = 0): **PASS**
- Privacy: No PII or search terms in tile requests: **PASS**
- Node.js headless lifecycle execution (init, setView, markers, clear, destroy): **PASS**

**Full Phase F3 Test Suite**: **19/19 PASSED in 0.11s** (`pytest tests/phase_f3/ -v`).

### C. Live Integration Test (`scripts/test_live_geocoding.py`)
Tested against 4 real BIS LIMS laboratories (no bulk geocoding performed):
- **BIS Owned**: BIS Central Laboratory (CL), Sahibabad -> `(28.686014, 77.432251)` [PASS]
- **Recognized**: SIIR Delhi Shriram Institute -> `(28.691799, 77.217508)` [PASS]
- **Empanelled**: RRSL Bangalore -> `(13.140169, 77.572251)` [PASS]
- **Complex Address**: Sleen India Biz venture, Agra -> `(27.191807, 77.994967)` [PASS]

**Live Test Summary**: **4/4 passed (100% SUCCESS)**.

### D. Phase 12 / F2 Regression Check
- `pytest tests/phase12/test_phase12_f2_orchestrator.py`: **12/12 PASSED**. Zero regressions introduced to existing RAG or orchestrator systems.

---

## 7. Files Changed & Files Untouched

### Files Created or Modified
1. `ai/services/geocoding_service.py` [NEW]: Core Geoapify geocoding service module.
2. `ai/services/__init__.py` [MODIFIED]: Exported geocoding service symbols.
3. `tests/phase_f3/test_geocoding_service.py` [NEW]: 11 automated unit tests for geocoder.
4. `scripts/test_live_geocoding.py` [NEW]: Live 4-sample geocoding verification script.
5. `frontend/vendor/leaflet/` [NEW]: Local Leaflet 1.9.4 CSS, JS, and image assets.
6. `frontend/mapComponent.js` [NEW]: Reusable Leaflet map component module.
7. `frontend/map_test.html` [NEW]: Isolated test workbench view for map component.
8. `frontend/styles.css` [MODIFIED]: Added `.bis-map-container`, marker pin, popup, and attribution CSS.
9. `tests/phase_f3/test_map_component.py` [NEW]: 8 automated unit & lifecycle tests for map.
10. `.env` [MODIFIED, UNTRACKED]: Added `GEOAPIFY_API_KEY`.
11. `.env.example` [MODIFIED]: Added `GEOAPIFY_API_KEY=`.
12. `docs/phase_f3/phase_f3_geocoding_setup.md` [UPDATED]: Comprehensive technical report.

### Files Intentionally Untouched
- All Phase 12.B, 12.C, 12.CA, 12.CB, 12.D, 12.DA, 12.DB, 12.E baselines.
- Frozen RAG datasets, vector stores, BM25 indices, and claim validators.
- Conversation frontend code: `frontend/app.js` and `frontend/index.html` (AI Hub conversation view preserved untouched).
- Complete BIS lab datasets (no bulk geocoding performed).

---

## 8. Remaining Work (Upcoming Steps)

- **Step 3**: Build BIS laboratory data/retrieval layer (structured storage for 581 labs and scope relationships).
- **Step 4**: Build lab matching engine (filtering by standard, capability, and distance ranking).
- **Step 5**: Build Lab Finder backend APIs (`GET /api/labs/search`).
- **Step 6**: Build Lab Finder frontend workspace and integrate interactive map view.
- **Step 7 & 8**: Real-world verification and final F3 audit/freeze.

---

## 9. Step 2B Stop Point

**STOP POINT OBSERVED**: All Step 2B requirements were completed:
- Leaflet is installed locally and cleanly encapsulated.
- Reusable map component is implemented and verified.
- OpenStreetMap HTTPS tiles with visible attribution are configured.
- Automated tests pass (19/19).
- No bulk geocoding or matching engine code written.

---

## 10. Phase F3: STEP 5A - Geographic Metadata / Coordinate Cache Foundation

### 10.1 Overview & Architecture

Step 5A establishes the persistent, deterministic spatial metadata cache layer that binds Geoapify coordinate resolutions to authoritative BIS LIMS laboratory profiles (`data/catalog/phase_f3_lims/laboratories.jsonl`).

```
Authoritative BIS LIMS Laboratory
(internal_id, original_address, lab_name, category)
                       │
                       ▼
            compute_address_hash()
        sha256(clean_address.lower())
                       │
                       ▼
         generate_cache_key()
     "{internal_id}:{address_hash}"
                       │
          ┌────────────┴────────────┐
          │                         │
     Cache Hit                 Cache Miss / Stale
 (Metadata Returned)           (Geocode via Step 2A)
                                    │
                                    ▼
                         GeoapifyGeocodingService
                                    │
                                    ▼
                        LabGeographicMetadata
                     (Recorded in Cache Store)
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
     lab_coordinates_cache.jsonl           cache_manifest.json
```

### 10.2 Authority Boundary & Non-Negotiable Invariants

1. **Strict Authority Hierarchy**:
   - **BIS LIMS** is the sole authority for laboratory identity, statutory address, category, and testing scope.
   - **Geoapify** coordinates are external, supplementary spatial metadata. They never constitute evidence of BIS recognition, compliance, or testing capabilities.
2. **Immutable Original Address**:
   - `original_address` is strictly preserved verbatim from BIS LIMS.
   - `formatted_address` returned by Geoapify is stored separately and never overwrites or alters the statutory address.
3. **Address Hash Binding & Invalidation**:
   - Cache entries are keyed by `f"{internal_id}:{address_hash}"`, where `address_hash = sha256(clean_address.lower())`.
   - If an address is updated in BIS LIMS, any existing entry for that `internal_id` with a different address hash is flagged as `is_stale = True`. Lookup via `get_for_laboratory(lab_dict)` returns `None`, preventing stale or incorrect coordinates from being served.
4. **Coordinate Null Rule**:
   - If geocoding encounters `ZERO_RESULTS`, `API_ERROR`, `RATE_LIMITED`, `NETWORK_FAILURE`, `MISSING_ADDRESS`, or `MISSING_API_KEY`, `latitude` and `longitude` are strictly `None`.
   - Zero coordinate fabrication, interpolation, default centering, or fuzzy guessing.
5. **Separation of Data Concerns**:
   - The cache references BIS laboratories strictly by `internal_id` and `lab_code`.
   - It does NOT duplicate testing scope records, clauses, fees, or categories.
   - Distance calculation and geographic ranking logic are explicitly excluded from Step 5A.

### 10.3 Schema Specification (`LabGeographicMetadata`)

```json
{
  "cache_key": "12:a81f...",
  "internal_id": 12,
  "lab_code": "CL01",
  "lab_name": "CENTRAL LABORATORY",
  "original_address": "PLOT NO. 20/9, SITE IV, SAHIBABAD...",
  "address_hash": "a81fe34...",
  "status": "SUCCESS",
  "latitude": 28.686014,
  "longitude": 77.432251,
  "formatted_address": "Sahibabad Industrial Area Site 4, Ghaziabad - 201010, Uttar Pradesh, India",
  "place_id": "5123...",
  "confidence": 0.95,
  "match_type": "full_match",
  "provider": "GEOAPIFY",
  "geocoded_at": "2026-09-06T08:00:00.000000Z",
  "error_message": null,
  "is_stale": false,
  "provenance": {
    "authority_boundary": "GEOGRAPHIC_METADATA_ONLY",
    "disclaimer": "Coordinates and geocoded metadata are supplementary and do not constitute normative evidence of BIS recognition or testing capability.",
    "source_catalog": "data/catalog/phase_f3_lims/laboratories.jsonl"
  }
}
```

### 10.4 Persistence & Cache Manifest (`cache_manifest.json`)

The cache writes append-ready JSONL files and a synchronizing manifest:
- **Cache File**: `data/catalog/phase_f3_lims/lab_coordinates_cache.jsonl`
- **Manifest File**: `data/catalog/phase_f3_lims/cache_manifest.json`
  - Tracks total entries, successes, failures, null coordinates, provider, and timestamp.

### 10.5 Automated Verification (`tests/phase_f3/test_geographic_cache.py`)

All 18 unit tests passed deterministically:
1. `test_01_successful_geocode`: Valid coordinates and metadata recorded.
2. `test_02_zero_result`: Handled cleanly with `latitude=None`, `longitude=None`.
3. `test_03_api_error`: Handled cleanly with `latitude=None`, `longitude=None`.
4. `test_04_rate_limiting`: Handled cleanly with `RATE_LIMITED` status.
5. `test_05_network_failure`: Handled cleanly with `NETWORK_FAILURE` status.
6. `test_06_missing_address`: Empty/whitespace address rejected without network call.
7. `test_07_missing_api_key`: Handled cleanly with `MISSING_API_KEY` status.
8. `test_08_missing_coordinates`: Response missing coordinates stored as `ZERO_RESULTS`.
9. `test_09_original_bis_address_preservation`: Verbatim address unchanged across lifecycle.
10. `test_10_formatted_address_separation`: Provider address isolated from original.
11. `test_11_provider_metadata_separation`: Provenance and provider metadata isolated.
12. `test_12_cache_key_determinism`: Deterministic `internal_id:sha256` keys.
13. `test_13_changed_address_detection`: Changed address triggers stale detection & cache miss.
14. `test_14_stable_bis_laboratory_identity`: Re-keyed lookups respect BIS `internal_id`.
15. `test_15_no_coordinate_fabrication`: Failure statuses guarantee `None` coordinates.
16. `test_16_repeated_identical_input_produces_identical_cache`: 100% deterministic output.
17. `test_17_save_and_load_disk_persistence`: JSONL + manifest roundtrip fidelity.
18. `test_18_catalog_immutability`: Verifies catalog files in `data/catalog/phase_f3_lims/` are untouched.

**Test Suite Results**: **149/149 PASSED across all phases** (0 failures, 0 regressions).

