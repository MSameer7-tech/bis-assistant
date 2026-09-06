"""
Unit & Component tests for Phase F3 Step 2B: Leaflet + OpenStreetMap Map Foundation.

Covers:
1. Vendor asset presence & integrity (leaflet.js, leaflet.css, icons)
2. mapComponent.js module structure & exports
3. OpenStreetMap tile configuration (HTTPS + required visible attribution)
4. map_test.html test harness structure
5. styles.css map, pin, popup, and attribution rules
6. Node.js headless lifecycle validation (init, setView, markers, clear, destroy)
7. Security & Privacy: No Google Maps dependencies, no PII/search leakage to tile server
"""

import json
import subprocess
import shutil
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"


class TestMapFoundation:
    """Automated test suite for Phase F3 Step 2B Map Foundation."""

    def test_01_leaflet_vendor_assets_exist(self):
        vendor_dir = FRONTEND_DIR / "vendor" / "leaflet"
        assert vendor_dir.exists(), "frontend/vendor/leaflet directory must exist"

        js_file = vendor_dir / "leaflet.js"
        css_file = vendor_dir / "leaflet.css"
        icon_file = vendor_dir / "images" / "marker-icon.png"

        assert js_file.exists() and js_file.stat().st_size > 50000, "leaflet.js must be present and valid"
        assert css_file.exists() and css_file.stat().st_size > 5000, "leaflet.css must be present and valid"
        assert icon_file.exists(), "Leaflet marker icon image must exist"

    def test_02_map_component_structure_and_exports(self):
        map_comp_file = FRONTEND_DIR / "mapComponent.js"
        assert map_comp_file.exists(), "frontend/mapComponent.js must exist"

        content = map_comp_file.read_text(encoding="utf-8")
        assert "export class BisMapComponent" in content
        assert "export const DEFAULT_TILE_PROVIDER" in content
        assert "export function createBisMap" in content
        assert "export function createPinIcon" in content

    def test_03_tile_provider_uses_https_and_visible_osm_attribution(self):
        map_comp_file = FRONTEND_DIR / "mapComponent.js"
        content = map_comp_file.read_text(encoding="utf-8")

        assert "https://tile.openstreetmap.org/{z}/{x}/{y}.png" in content, "Tile URL must use HTTPS OpenStreetMap"
        assert "OpenStreetMap" in content, "OpenStreetMap attribution must be defined"
        assert "openstreetmap.org/copyright" in content, "OpenStreetMap copyright link must be defined"

    def test_04_map_test_html_structure(self):
        test_html_file = FRONTEND_DIR / "map_test.html"
        assert test_html_file.exists(), "frontend/map_test.html must exist"

        content = test_html_file.read_text(encoding="utf-8")
        assert "id=\"testMap\"" in content or "id='testMap'" in content, "Must contain #testMap container"
        assert "leaflet.js" in content, "Must include leaflet.js"
        assert "leaflet.css" in content, "Must include leaflet.css"
        assert "mapComponent.js" in content, "Must import mapComponent.js"
        assert "OpenStreetMap Attribution" in content
        assert "btnCenterDelhi" in content
        assert "btnAddSample4" in content

    def test_05_styles_contain_map_rules(self):
        styles_file = FRONTEND_DIR / "styles.css"
        content = styles_file.read_text(encoding="utf-8")

        assert ".bis-map-container" in content, "Must define .bis-map-container"
        assert ".bis-map-pin" in content, "Must define .bis-map-pin marker style"
        assert ".bis-map-popup" in content, "Must define .bis-map-popup"
        assert ".leaflet-control-attribution" in content, "Must style .leaflet-control-attribution"

    def test_06_no_google_maps_dependencies(self):
        """Ensure no Google Maps APIs or scripts are introduced."""
        for path in [FRONTEND_DIR / "mapComponent.js", FRONTEND_DIR / "map_test.html"]:
            content = path.read_text(encoding="utf-8").lower()
            assert "maps.googleapis.com" not in content, f"Found Google Maps script in {path}"
            assert "google.maps" not in content, f"Found google.maps reference in {path}"

    def test_07_privacy_no_pii_in_tile_requests(self):
        """Verify tile URLs are strictly coordinate-based templates without query leaks."""
        map_comp_file = FRONTEND_DIR / "mapComponent.js"
        content = map_comp_file.read_text(encoding="utf-8")

        # Tile URL template should only contain {z}/{x}/{y} parameters
        assert "{z}/{x}/{y}" in content
        # Ensure no search parameters or address parameters are appended to tile URL
        assert "{address}" not in content
        assert "{query}" not in content
        assert "{lab}" not in content

    def test_08_nodejs_lifecycle_execution(self):
        """Executes full BisMapComponent lifecycle test in Node.js."""
        node_bin = shutil.which("node")
        if not node_bin:
            pytest.skip("Node.js not installed on system")

        script = """
        global.window = global;
        global.document = { getElementById: (id) => ({ id, style: {} }) };
        const markersInGroup = new Set();
        const mockLayerGroup = {
            addTo: function() { return this; },
            clearLayers: function() { markersInGroup.clear(); }
        };
        const mockMap = {
            setView: function(center, zoom) { this.center = center; this.zoom = zoom; return this; },
            getZoom: function() { return this.zoom || 5; },
            fitBounds: function(bounds, opts) { this.bounds = bounds; return this; },
            invalidateSize: function() { this.invalidated = true; },
            remove: function() { this.removed = true; }
        };
        window.L = {
            map: function() { return mockMap; },
            tileLayer: function() { return { addTo: function() { return this; } }; },
            layerGroup: function() { return mockLayerGroup; },
            divIcon: function(opts) { return opts; },
            marker: function(coords, opts) {
                return {
                    coords, opts,
                    bindPopup: function(c) { this.popup = c; return this; },
                    addTo: function() { markersInGroup.add(this); return this; },
                    openPopup: function() { this.popupOpened = true; }
                };
            }
        };

        import("./frontend/mapComponent.js").then(mod => {
            const { createBisMap } = mod;
            const comp = createBisMap("testMap", { center: [20.59, 78.96], zoom: 5 });
            if (!comp._isInitialized) throw new Error("Init failed");

            comp.setView(28.61, 77.20, 11);
            if (mockMap.center[0] !== 28.61) throw new Error("setView failed");

            comp.setMarkers([
                { lat: 28.68, lng: 77.43, title: "Lab 1", category: "BIS_OWNED" },
                { lat: 28.69, lng: 77.21, title: "Lab 2", category: "BIS_RECOGNIZED" }
            ]);
            if (comp.getMarkersCount() !== 2) throw new Error("setMarkers failed");

            comp.clearMarkers();
            if (comp.getMarkersCount() !== 0) throw new Error("clearMarkers failed");

            comp.invalidateSize();
            if (!mockMap.invalidated) throw new Error("invalidateSize failed");

            comp.destroy();
            if (!mockMap.removed) throw new Error("destroy failed");

            process.exit(0);
        }).catch(err => {
            console.error(err);
            process.exit(1);
        });
        """

        result = subprocess.run(
            [node_bin, "-e", script],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True
        )

        assert result.returncode == 0, f"Node.js test failed: {result.stderr}"
