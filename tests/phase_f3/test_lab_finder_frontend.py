"""
Phase F3 Step 8: BIS AI Assistant Laboratory Finder Frontend Integration Tests.

Validates:
1. File existence & module exports (labFinderComponent.js, index.html, styles.css)
2. Zero external dependencies: No Google Maps, no un-vendored external CDNs
3. Zero secrets / API keys exposed in frontend code
4. Complete CSS design system and responsive layout rules in styles.css
5. Index.html integration: nav link, view section, and vendored Leaflet assets
6. App.js integration: component initialization, switchView routing, and chat bridge
7. Node.js headless DOM: component initialization & layout generation
8. Node.js headless DOM: search request payload construction
9. Node.js headless DOM: API response parsing & laboratory card rendering
10. Node.js headless DOM: map marker creation exclusively for valid coordinates
11. Node.js headless DOM: null-coordinate handling ("Location unavailable", 0 map markers, no coordinate fabrication)
12. Node.js headless DOM: card and map marker bidirectional synchronization
13. Node.js headless DOM: empty states (no capability match, radius exhausted) & error states (invalid request, network error)
14. Node.js headless DOM: detail inspector with strict separation of BIS authoritative evidence and geographic metadata
"""

import shutil
import subprocess
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"


class TestLabFinderFrontend:
    """Automated test suite for Phase F3 Step 8 Lab Finder Frontend Integration."""

    def test_01_frontend_files_and_exports_exist(self):
        """Verifies that the modular frontend component and assets exist."""
        component_file = FRONTEND_DIR / "labFinderComponent.js"
        assert component_file.exists(), "frontend/labFinderComponent.js must exist"

        content = component_file.read_text(encoding="utf-8")
        assert "export class LabFinderComponent" in content
        assert "init(" in content
        assert "search(" in content
        assert "renderResults(" in content
        assert "updateMapMarkers(" in content
        assert "selectCandidate(" in content
        assert "openDetailInspector(" in content
        assert "renderEmptyState(" in content
        assert "renderErrorState(" in content

    def test_02_no_google_maps_or_external_cdns(self):
        """Ensures complete absence of Google Maps and external non-vendored map CDNs."""
        for path in [
            FRONTEND_DIR / "labFinderComponent.js",
            FRONTEND_DIR / "index.html",
            FRONTEND_DIR / "app.js",
            FRONTEND_DIR / "styles.css"
        ]:
            content = path.read_text(encoding="utf-8").lower()
            assert "maps.googleapis.com" not in content, f"Found Google Maps script in {path.name}"
            assert "google.maps" not in content, f"Found google.maps reference in {path.name}"
            assert "unpkg.com/leaflet" not in content, f"Found external Leaflet CDN in {path.name}"
            assert "cdnjs.cloudflare.com/ajax/libs/leaflet" not in content, f"Found external Leaflet CDN in {path.name}"

    def test_03_no_api_keys_or_secrets_exposed(self):
        """Verifies no private API keys or Geoapify credentials are hardcoded into frontend files."""
        for path in [
            FRONTEND_DIR / "labFinderComponent.js",
            FRONTEND_DIR / "index.html",
            FRONTEND_DIR / "app.js"
        ]:
            content = path.read_text(encoding="utf-8")
            assert "apiKey=" not in content, f"Potential API key parameter found in {path.name}"
            assert "geoapify_key" not in content.lower(), f"Potential Geoapify key reference in {path.name}"

    def test_04_styles_css_lab_finder_rules(self):
        """Verifies styles.css defines all required Lab Finder UI components and badges."""
        styles_file = FRONTEND_DIR / "styles.css"
        content = styles_file.read_text(encoding="utf-8")

        required_classes = [
            ".lab-finder-workspace",
            ".lab-finder-layout",
            ".lab-finder-topbar",
            ".lab-search-form",
            ".lab-finder-body",
            ".lab-results-panel",
            ".lab-candidate-card",
            ".card-distance-badge",
            ".card-distance-badge.unavailable",
            ".lab-map-panel",
            ".map-deck-header",
            ".results-empty-state",
            ".results-error-state",
            ".lab-detail-drawer",
            ".drawer-authority-header",
            ".geo-disclaimer-quote",
            ".chat-lab-finder-card"
        ]
        for cls in required_classes:
            assert cls in content, f"CSS rule {cls} missing from styles.css"

    def test_05_responsive_layout_css_rules(self):
        """Verifies desktop grid and mobile/tablet responsive breakpoints exist."""
        styles_file = FRONTEND_DIR / "styles.css"
        content = styles_file.read_text(encoding="utf-8")

        assert "grid-template-columns: 460px 1fr;" in content
        assert "@media (max-width: 960px)" in content
        assert "@media (max-width: 640px)" in content

    def test_06_index_html_integration(self):
        """Verifies index.html contains the Lab Finder navigation link, view section, and Leaflet bundle."""
        index_file = FRONTEND_DIR / "index.html"
        content = index_file.read_text(encoding="utf-8")

        assert 'id="navLabFinder"' in content, "index.html must contain #navLabFinder nav link"
        assert 'id="viewLabFinder"' in content, "index.html must contain #viewLabFinder view section"
        assert 'href="./vendor/leaflet/leaflet.css"' in content, "index.html must link local leaflet.css"
        assert 'src="./vendor/leaflet/leaflet.js"' in content, "index.html must load local leaflet.js"

    def test_07_app_js_integration(self):
        """Verifies app.js imports LabFinderComponent, wires view switching, and includes chat bridge."""
        app_file = FRONTEND_DIR / "app.js"
        content = app_file.read_text(encoding="utf-8")

        assert "import { LabFinderComponent } from './labFinderComponent.js'" in content
        assert "new LabFinderComponent(" in content
        assert "viewLabFinder" in content
        assert "navLabFinder" in content
        assert "'labfinder'" in content
        assert "chat-lab-finder-card" in content

    def test_08_node_headless_component_init_and_layout(self):
        """Tests that LabFinderComponent renders its DOM structure in a headless environment."""
        node_bin = shutil.which("node")
        if not node_bin:
            pytest.skip("Node.js not installed")

        script = """
        const elements = new Map();
        function createMockElement(tag, id = null) {
            const el = {
                tagName: tag.toUpperCase(),
                id: id,
                className: '',
                classList: {
                    add: function(c) { el.className += ' ' + c; },
                    remove: function(c) { el.className = el.className.replace(c, '').trim(); },
                    contains: function(c) { return el.className.includes(c); }
                },
                attributes: {},
                children: [],
                innerHTML: '',
                value: '',
                checked: false,
                setAttribute: function(k, v) { this.attributes[k] = v; },
                getAttribute: function(k) { return this.attributes[k] || null; },
                appendChild: function(c) { this.children.push(c); return c; },
                querySelector: function(sel) {
                    if (sel.startsWith('#')) return elements.get(sel.slice(1)) || null;
                    return null;
                },
                querySelectorAll: function() { return []; },
                addEventListener: function(evt, fn) { this['on' + evt] = fn; },
                focus: function() {}
            };
            if (id) elements.set(id, el);
            return el;
        }

        global.window = global;
        global.document = {
            getElementById: (id) => elements.get(id) || createMockElement('div', id),
            createElement: (tag) => createMockElement(tag)
        };

        const container = createMockElement('div', 'viewLabFinder');
        import('./frontend/labFinderComponent.js').then(mod => {
            const { LabFinderComponent } = mod;
            const comp = new LabFinderComponent({
                container: container,
                mapContainer: 'labFinderMap'
            });
            comp.renderLayout();

            // Verify rendered layout elements
            if (!container.innerHTML.includes('id="labSearchForm"')) throw new Error("Missing #labSearchForm");
            if (!container.innerHTML.includes('id="labInputStandard"')) throw new Error("Missing #labInputStandard");
            if (!container.innerHTML.includes('id="labFinderMap"')) throw new Error("Missing #labFinderMap");
            if (!container.innerHTML.includes('id="labDetailDrawer"')) throw new Error("Missing #labDetailDrawer");

            process.exit(0);
        }).catch(err => {
            console.error(err);
            process.exit(1);
        });
        """
        result = subprocess.run([node_bin, "-e", script], cwd=str(PROJECT_ROOT), capture_output=True, text=True)
        assert result.returncode == 0, f"Node.js layout test failed: {result.stderr}"

    def test_09_node_headless_request_construction(self):
        """Tests that executeSearchFromInputs constructs correct request payloads."""
        node_bin = shutil.which("node")
        if not node_bin:
            pytest.skip("Node.js not installed")

        script = """
        const elements = new Map();
        function createMockElement(tag, id = null) {
            let _inner = '';
            const el = {
                tagName: tag.toUpperCase(),
                id: id,
                className: '',
                value: '',
                checked: false,
                classList: {
                    add: function(c) { el.className += ' ' + c; },
                    remove: function(c) { el.className = el.className.replace(c, '').trim(); },
                    contains: function(c) { return el.className.includes(c); }
                },
                attributes: {},
                children: [],
                setAttribute: function(k, v) { this.attributes[k] = v; },
                getAttribute: function(k) { return this.attributes[k] || null; },
                appendChild: function(c) { this.children.push(c); return c; },
                querySelector: function(sel) {
                    if (sel.startsWith('#')) return elements.get(sel.slice(1)) || null;
                    return null;
                },
                querySelectorAll: function() { return []; },
                addEventListener: function(evt, fn) { this['on' + evt] = fn; },
                focus: function() {}
            };
            Object.defineProperty(el, 'innerHTML', {
                get() { return _inner; },
                set(val) {
                    _inner = String(val);
                    const matches = _inner.matchAll(/id="([^"]+)"/g);
                    for (const m of matches) {
                        const elemId = m[1];
                        if (!elements.has(elemId)) {
                            elements.set(elemId, createMockElement('div', elemId));
                        }
                    }
                }
            });
            if (id) elements.set(id, el);
            return el;
        }

        global.window = global;
        global.document = {
            getElementById: (id) => elements.get(id) || createMockElement('div', id),
            createElement: (tag) => createMockElement(tag)
        };

        const container = createMockElement('div', 'viewLabFinder');
        import('./frontend/labFinderComponent.js').then(mod => {
            const { LabFinderComponent } = mod;
            const comp = new LabFinderComponent({ container });
            comp.renderLayout();

            // Set inputs
            elements.get('labInputStandard').value = 'IS 4985';
            elements.get('labFilterCategory').value = 'BIS_RECOGNIZED';
            elements.get('labFilterCompleteScope').checked = true;
            elements.get('labFilterLimit').value = '25';

            let capturedOptions = null;
            comp.search = (opts) => { capturedOptions = opts; };

            comp.executeSearchFromInputs();

            if (!capturedOptions) throw new Error("Search not called");
            if (capturedOptions.standard !== 'IS 4985') throw new Error("Standard mismatch");
            if (capturedOptions.category !== 'BIS_RECOGNIZED') throw new Error("Category mismatch");
            if (capturedOptions.require_complete_scope !== true) throw new Error("require_complete_scope mismatch");
            if (capturedOptions.limit !== 25) throw new Error("limit mismatch");

            // Now test with coordinates
            comp.setUserLocation(28.6139, 77.2090, 'Delhi');
            elements.get('labFilterRadius').value = '50';
            comp.executeSearchFromInputs();

            if (capturedOptions.latitude !== 28.6139) throw new Error("Latitude missing");
            if (capturedOptions.longitude !== 77.2090) throw new Error("Longitude missing");
            if (capturedOptions.max_distance_km !== 50) throw new Error("Max distance missing");

            process.exit(0);
        }).catch(err => {
            console.error(err);
            process.exit(1);
        });
        """
        result = subprocess.run([node_bin, "-e", script], cwd=str(PROJECT_ROOT), capture_output=True, text=True)
        assert result.returncode == 0, f"Node.js request construction test failed: {result.stderr}"

    def test_10_node_headless_response_parsing_and_card_rendering(self):
        """Tests that renderResults parses API candidate records into styled cards."""
        node_bin = shutil.which("node")
        if not node_bin:
            pytest.skip("Node.js not installed")

        script = """
        const elements = new Map();
        function createMockElement(tag, id = null) {
            const el = {
                tagName: tag.toUpperCase(),
                id: id,
                className: '',
                classList: {
                    add: function(c) { el.className += ' ' + c; },
                    remove: function(c) { el.className = el.className.replace(c, '').trim(); },
                    contains: function(c) { return el.className.includes(c); }
                },
                attributes: {},
                children: [],
                innerHTML: '',
                setAttribute: function(k, v) { this.attributes[k] = v; },
                getAttribute: function(k) { return this.attributes[k] || null; },
                appendChild: function(c) { this.children.push(c); return c; },
                querySelector: function(sel) {
                    if (sel.startsWith('#')) return elements.get(sel.slice(1)) || null;
                    if (sel === '.btn-card-detail') return createMockElement('button');
                    return null;
                },
                querySelectorAll: function() { return []; },
                addEventListener: function(evt, fn) { this['on' + evt] = fn; }
            };
            if (id) elements.set(id, el);
            return el;
        }

        global.window = global;
        global.document = {
            getElementById: (id) => elements.get(id) || createMockElement('div', id),
            createElement: (tag) => createMockElement(tag)
        };

        const mockResponse = {
            status: 'MATCH',
            match_status: 'EXACT_MATCH',
            standard: 'IS 4985',
            total_matching: 1,
            returned_candidates: 1,
            query_criteria: { standard: 'IS 4985' },
            candidates: [{
                rank: 1,
                internal_id: 87,
                public_lab_code: '8113506',
                laboratory_name: 'SIIR Delhi Shriram Institute',
                category: 'BIS_RECOGNIZED',
                address: { original_address: '19 University Road Delhi' },
                capability_evidence: {
                    matching_standard: 'IS 4985',
                    scope_completeness: 'COMPLETE_SCOPE',
                    base_testing_fee: 15000.0,
                    matched_clauses: ['5.1', '6.2']
                },
                geographic_metadata: {
                    has_coordinates: true,
                    latitude: 28.6923,
                    longitude: 77.2144,
                    distance_km: 8.70
                }
            }]
        };

        const container = createMockElement('div', 'viewLabFinder');
        import('./frontend/labFinderComponent.js').then(mod => {
            const { LabFinderComponent } = mod;
            const comp = new LabFinderComponent({ container });
            comp.renderLayout();
            comp.updateMapMarkers = () => {}; // Mock map
            comp.renderResults(mockResponse);

            const card = comp.createCandidateCard(mockResponse.candidates[0], 0);
            if (!card.innerHTML.includes('#1')) throw new Error("Rank missing");
            if (!card.innerHTML.includes('SIIR Delhi Shriram Institute')) throw new Error("Lab name missing");
            if (!card.innerHTML.includes('8.7 km')) throw new Error("Distance display missing");
            if (!card.innerHTML.includes('Complete Scope')) throw new Error("Scope badge missing");
            if (!card.innerHTML.includes('₹15,000')) throw new Error("Fee missing");

            process.exit(0);
        }).catch(err => {
            console.error(err);
            process.exit(1);
        });
        """
        result = subprocess.run([node_bin, "-e", script], cwd=str(PROJECT_ROOT), capture_output=True, text=True)
        assert result.returncode == 0, f"Node.js card rendering test failed: {result.stderr}"

    def test_11_node_headless_map_marker_creation_only_valid_coords(self):
        """Verifies that Leaflet map markers are added exclusively for laboratories with valid coordinates."""
        node_bin = shutil.which("node")
        if not node_bin:
            pytest.skip("Node.js not installed")

        script = """
        const elements = new Map();
        function createMockElement(tag, id = null) {
            const el = {
                tagName: tag.toUpperCase(),
                id: id,
                className: '',
                classList: {
                    add: function(c) { el.className += ' ' + c; },
                    remove: function(c) { el.className = el.className.replace(c, '').trim(); },
                    contains: function(c) { return el.className.includes(c); }
                },
                attributes: {},
                children: [],
                innerHTML: '',
                setAttribute: function(k, v) { this.attributes[k] = v; },
                getAttribute: function(k) { return this.attributes[k] || null; },
                appendChild: function(c) { this.children.push(c); return c; },
                querySelector: function(sel) {
                    if (sel.startsWith('#')) return elements.get(sel.slice(1)) || null;
                    return null;
                },
                querySelectorAll: function() { return []; },
                addEventListener: function(evt, fn) { this['on' + evt] = fn; }
            };
            if (id) elements.set(id, el);
            return el;
        }

        global.window = global;
        global.document = {
            getElementById: (id) => elements.get(id) || createMockElement('div', id),
            createElement: (tag) => createMockElement(tag)
        };

        // Mock candidates: 2 with valid coordinates, 1 ZERO_RESULTS
        const candidates = [
            {
                internal_id: 1, rank: 1, category: 'BIS_OWNED',
                laboratory_name: 'Lab 1', address: { original_address: 'Addr 1' },
                capability_evidence: { scope_completeness: 'COMPLETE_SCOPE' },
                geographic_metadata: { has_coordinates: true, latitude: 28.5, longitude: 77.2, distance_km: 5.0 }
            },
            {
                internal_id: 2, rank: 2, category: 'BIS_RECOGNIZED',
                laboratory_name: 'Lab 2', address: { original_address: 'Addr 2' },
                capability_evidence: { scope_completeness: 'COMPLETE_SCOPE' },
                geographic_metadata: { has_coordinates: true, latitude: 28.6, longitude: 77.3, distance_km: 15.0 }
            },
            {
                internal_id: 3, rank: 3, category: 'BIS_EMPANELLED',
                laboratory_name: 'Lab 3 (ZERO_RESULTS)', address: { original_address: 'Addr 3' },
                capability_evidence: { scope_completeness: 'PARTIAL_SCOPE' },
                geographic_metadata: { has_coordinates: false, latitude: null, longitude: null, distance_km: null, geocoding_status: 'ZERO_RESULTS' }
            }
        ];

        let receivedMarkers = [];
        const mockMapComp = {
            _isInitialized: true,
            clearMarkers: () => { receivedMarkers = []; },
            setMarkers: (list) => { receivedMarkers = list; },
            markers: new Map(),
            invalidateSize: () => {}
        };

        const container = createMockElement('div', 'viewLabFinder');
        import('./frontend/labFinderComponent.js').then(mod => {
            const { LabFinderComponent } = mod;
            const comp = new LabFinderComponent({ container });
            comp.mapComponent = mockMapComp;
            comp.renderLayout();

            comp.updateMapMarkers(candidates);

            // Invariant: Exactly 2 markers added, candidate 3 received 0 markers
            if (receivedMarkers.length !== 2) {
                throw new Error("Expected 2 markers, got " + receivedMarkers.length);
            }
            if (receivedMarkers.some(m => m.id === 'lab_3')) {
                throw new Error("Candidate 3 with null coordinates was illegally mapped!");
            }

            process.exit(0);
        }).catch(err => {
            console.error(err);
            process.exit(1);
        });
        """
        result = subprocess.run([node_bin, "-e", script], cwd=str(PROJECT_ROOT), capture_output=True, text=True)
        assert result.returncode == 0, f"Node.js marker creation test failed: {result.stderr}"

    def test_12_node_headless_null_coordinate_handling(self):
        """Verifies that laboratories without coordinates show 'Location unavailable' and no fabricated coords."""
        node_bin = shutil.which("node")
        if not node_bin:
            pytest.skip("Node.js not installed")

        script = """
        const elements = new Map();
        function createMockElement(tag, id = null) {
            const el = {
                tagName: tag.toUpperCase(),
                id: id,
                className: '',
                classList: {
                    add: function(c) { el.className += ' ' + c; },
                    remove: function(c) { el.className = el.className.replace(c, '').trim(); },
                    contains: function(c) { return el.className.includes(c); }
                },
                attributes: {},
                children: [],
                innerHTML: '',
                setAttribute: function(k, v) { this.attributes[k] = v; },
                getAttribute: function(k) { return this.attributes[k] || null; },
                appendChild: function(c) { this.children.push(c); return c; },
                querySelector: function(sel) {
                    if (sel.startsWith('#')) return elements.get(sel.slice(1)) || null;
                    if (sel === '.btn-card-detail') return createMockElement('button');
                    return null;
                },
                querySelectorAll: function() { return []; },
                addEventListener: function(evt, fn) { this['on' + evt] = fn; }
            };
            if (id) elements.set(id, el);
            return el;
        }

        global.window = global;
        global.document = {
            getElementById: (id) => elements.get(id) || createMockElement('div', id),
            createElement: (tag) => createMockElement(tag)
        };

        const zeroCandidate = {
            rank: 4,
            internal_id: 1610,
            public_lab_code: '8114901',
            laboratory_name: 'Arakonam Testing Laboratory',
            category: 'BIS_RECOGNIZED',
            address: { original_address: 'No.17 Winterpet Post Arakonam Vellore' },
            capability_evidence: {
                matching_standard: 'IS 269',
                scope_completeness: 'COMPLETE_SCOPE'
            },
            geographic_metadata: {
                has_coordinates: false,
                latitude: null,
                longitude: null,
                distance_km: null,
                geocoding_status: 'ZERO_RESULTS'
            }
        };

        const container = createMockElement('div', 'viewLabFinder');
        import('./frontend/labFinderComponent.js').then(mod => {
            const { LabFinderComponent } = mod;
            const comp = new LabFinderComponent({ container });
            const card = comp.createCandidateCard(zeroCandidate, 0);

            if (!card.innerHTML.includes('Location unavailable')) {
                throw new Error("Missing 'Location unavailable' label on zero-result card");
            }
            if (!card.innerHTML.includes('card-distance-badge unavailable')) {
                throw new Error("Missing unavailable styling class");
            }

            process.exit(0);
        }).catch(err => {
            console.error(err);
            process.exit(1);
        });
        """
        result = subprocess.run([node_bin, "-e", script], cwd=str(PROJECT_ROOT), capture_output=True, text=True)
        assert result.returncode == 0, f"Node.js null-coordinate test failed: {result.stderr}"

    def test_13_node_headless_card_and_marker_synchronization(self):
        """Verifies that card selection pans the map and triggers marker popup."""
        node_bin = shutil.which("node")
        if not node_bin:
            pytest.skip("Node.js not installed")

        script = """
        const elements = new Map();
        function createMockElement(tag, id = null) {
            const el = {
                tagName: tag.toUpperCase(),
                id: id,
                className: '',
                classList: {
                    add: function(c) { el.className += ' ' + c; },
                    remove: function(c) { el.className = el.className.replace(c, '').trim(); },
                    contains: function(c) { return el.className.includes(c); }
                },
                attributes: {},
                children: [],
                innerHTML: '',
                scrollIntoView: function() { this.scrolled = true; },
                setAttribute: function(k, v) { this.attributes[k] = v; },
                getAttribute: function(k) { return this.attributes[k] || null; },
                appendChild: function(c) { this.children.push(c); return c; },
                querySelector: function(sel) {
                    if (sel.startsWith('#')) return elements.get(sel.slice(1)) || null;
                    if (sel.includes('data-id="87"')) return targetCard;
                    return null;
                },
                querySelectorAll: function() { return [targetCard]; },
                addEventListener: function(evt, fn) { this['on' + evt] = fn; }
            };
            if (id) elements.set(id, el);
            return el;
        }

        const targetCard = createMockElement('div');
        targetCard.setAttribute('data-id', '87');

        global.window = global;
        global.document = {
            getElementById: (id) => elements.get(id) || createMockElement('div', id),
            createElement: (tag) => createMockElement(tag)
        };

        const mockMarker = {
            openPopup: function() { this.popupOpened = true; }
        };

        let mapPannedTo = null;
        const mockMapComp = {
            setView: function(lat, lng, zoom) { mapPannedTo = { lat, lng, zoom }; },
            markers: new Map([['lab_87', mockMarker]])
        };

        const candidate = {
            internal_id: 87,
            rank: 1,
            laboratory_name: 'SIIR Delhi',
            geographic_metadata: { has_coordinates: true, latitude: 28.6923, longitude: 77.2144 }
        };

        const container = createMockElement('div', 'viewLabFinder');
        import('./frontend/labFinderComponent.js').then(mod => {
            const { LabFinderComponent } = mod;
            const comp = new LabFinderComponent({ container });
            comp.mapComponent = mockMapComp;

            comp.selectCandidate(candidate, true);

            if (!mapPannedTo || mapPannedTo.lat !== 28.6923) throw new Error("Map not panned to candidate coordinates");
            if (!mockMarker.popupOpened) throw new Error("Marker popup not opened");
            if (!targetCard.classList.contains('selected')) throw new Error("Card not marked as selected");

            process.exit(0);
        }).catch(err => {
            console.error(err);
            process.exit(1);
        });
        """
        result = subprocess.run([node_bin, "-e", script], cwd=str(PROJECT_ROOT), capture_output=True, text=True)
        assert result.returncode == 0, f"Node.js synchronization test failed: {result.stderr}"

    def test_14_node_headless_empty_and_error_states(self):
        """Verifies clear rendering of empty and error states without inventing data."""
        node_bin = shutil.which("node")
        if not node_bin:
            pytest.skip("Node.js not installed")

        script = """
        const elements = new Map();
        function createMockElement(tag, id = null) {
            let _inner = '';
            const el = {
                tagName: tag.toUpperCase(),
                id: id,
                className: '',
                classList: {
                    add: function(c) { el.className += ' ' + c; },
                    remove: function(c) { el.className = el.className.replace(c, '').trim(); }
                },
                attributes: {},
                children: [],
                setAttribute: function(k, v) { this.attributes[k] = v; },
                getAttribute: function(k) { return this.attributes[k] || null; },
                appendChild: function(c) { this.children.push(c); return c; },
                querySelector: function(sel) {
                    if (sel.startsWith('#')) return elements.get(sel.slice(1)) || null;
                    return null;
                },
                querySelectorAll: function() { return []; },
                addEventListener: function(evt, fn) { this['on' + evt] = fn; }
            };
            Object.defineProperty(el, 'innerHTML', {
                get() { return _inner; },
                set(val) {
                    _inner = String(val);
                    const matches = _inner.matchAll(/id="([^"]+)"/g);
                    for (const m of matches) {
                        const elemId = m[1];
                        if (!elements.has(elemId)) {
                            elements.set(elemId, createMockElement('div', elemId));
                        }
                    }
                }
            });
            if (id) elements.set(id, el);
            return el;
        }

        global.window = global;
        global.document = {
            getElementById: (id) => elements.get(id) || createMockElement('div', id),
            createElement: (tag) => createMockElement(tag)
        };

        const container = createMockElement('div', 'viewLabFinder');
        import('./frontend/labFinderComponent.js').then(mod => {
            const { LabFinderComponent } = mod;
            const comp = new LabFinderComponent({ container });
            comp.renderLayout();

            // 1. NO_CAPABILITY_MATCH
            comp.renderEmptyState('NO_CAPABILITY_MATCH', { standard: 'IS 999999' });
            const listCont = elements.get('resultsListContainer');
            if (!listCont.innerHTML.includes('No Capability Scope for IS 999999')) {
                throw new Error("NO_CAPABILITY_MATCH title missing");
            }

            // 2. RADIUS_EXHAUSTED
            comp.renderEmptyState('RADIUS_EXHAUSTED', { standard: 'IS 4985', radius: 25 });
            if (!listCont.innerHTML.includes('No Laboratories Within 25 km')) {
                throw new Error("RADIUS_EXHAUSTED title missing");
            }

            // 3. Error state
            comp.renderErrorState('Invalid Indian Standard number format', 'INVALID_REQUEST');
            if (!listCont.innerHTML.includes('INVALID_REQUEST')) {
                throw new Error("Error badge missing");
            }
            if (!listCont.innerHTML.includes('Invalid Indian Standard number format')) {
                throw new Error("Error description missing");
            }

            process.exit(0);
        }).catch(err => {
            console.error(err);
            process.exit(1);
        });
        """
        result = subprocess.run([node_bin, "-e", script], cwd=str(PROJECT_ROOT), capture_output=True, text=True)
        assert result.returncode == 0, f"Node.js empty/error states test failed: {result.stderr}"

    def test_15_node_headless_detail_inspector_authority_separation(self):
        """Verifies detail inspector strictly separates BIS evidence from geographic metadata with disclaimer."""
        node_bin = shutil.which("node")
        if not node_bin:
            pytest.skip("Node.js not installed")

        script = """
        const elements = new Map();
        function createMockElement(tag, id = null) {
            let _inner = '';
            const el = {
                tagName: tag.toUpperCase(),
                id: id,
                className: '',
                classList: {
                    add: function(c) { el.className += ' ' + c; },
                    remove: function(c) { el.className = el.className.replace(c, '').trim(); }
                },
                attributes: {},
                children: [],
                setAttribute: function(k, v) { this.attributes[k] = v; },
                getAttribute: function(k) { return this.attributes[k] || null; },
                appendChild: function(c) { this.children.push(c); return c; },
                querySelector: function(sel) {
                    if (sel.startsWith('#')) return elements.get(sel.slice(1)) || null;
                    return null;
                },
                querySelectorAll: function() { return []; },
                addEventListener: function(evt, fn) { this['on' + evt] = fn; }
            };
            Object.defineProperty(el, 'innerHTML', {
                get() { return _inner; },
                set(val) {
                    _inner = String(val);
                    const matches = _inner.matchAll(/id="([^"]+)"/g);
                    for (const m of matches) {
                        const elemId = m[1];
                        if (!elements.has(elemId)) {
                            elements.set(elemId, createMockElement('div', elemId));
                        }
                    }
                }
            });
            if (id) elements.set(id, el);
            return el;
        }

        global.window = global;
        global.document = {
            getElementById: (id) => elements.get(id) || createMockElement('div', id),
            createElement: (tag) => createMockElement(tag)
        };

        const sampleCand = {
            internal_id: 87,
            public_lab_code: '8113506',
            laboratory_name: 'SIIR Delhi Shriram Institute',
            category: 'BIS_RECOGNIZED',
            address: { original_address: '19 University Road Delhi 110007', state: 'DELHI' },
            capability_evidence: {
                matching_standard: 'IS 4985',
                matching_scope_id: '87_IS_4985',
                scope_completeness: 'COMPLETE_SCOPE',
                matched_clauses: ['5.1', '6.2'],
                match_score: 135.0,
                base_testing_fee: 15000.0,
                provenance_sha256: '4b971bbfa60183187260538a792556b6b7d6ff6f4e66c6b4fc3ea970f5e7f0b8',
                provenance_url: 'https://lims.bis.gov.in/test_scope'
            },
            geographic_metadata: {
                has_coordinates: true,
                latitude: 28.6923,
                longitude: 77.2144,
                distance_km: 8.70,
                geocoding_status: 'SUCCESS',
                authority_disclaimer: 'Geographic distance is supplementary spatial metadata. It does not constitute normative evidence of BIS recognition.'
            }
        };

        const container = createMockElement('div', 'viewLabFinder');
        import('./frontend/labFinderComponent.js').then(mod => {
            const { LabFinderComponent } = mod;
            const comp = new LabFinderComponent({ container });
            comp.renderLayout();

            comp.openDetailInspector(sampleCand);

            const bodyHtml = elements.get('labDrawerBody').innerHTML;

            // SECTION 1: Authoritative BIS evidence checks
            if (!bodyHtml.includes('Authoritative BIS LIMS Capability Evidence')) {
                throw new Error("Missing BIS Authority Header");
            }
            if (!bodyHtml.includes('4b971bbfa60183187260538a792556b6b7d6ff6f4e66c6b4fc3ea970f5e7f0b8')) {
                throw new Error("Missing SHA256 checksum");
            }
            if (!bodyHtml.includes('87_IS_4985')) {
                throw new Error("Missing Scope ID");
            }

            // SECTION 2: Supplementary Geographic metadata checks
            if (!bodyHtml.includes('Supplementary Geographic Metadata')) {
                throw new Error("Missing Geographic Section Header");
            }
            if (!bodyHtml.includes('Geographic distance is supplementary spatial metadata')) {
                throw new Error("Missing Geographic Authority Disclaimer");
            }

            process.exit(0);
        }).catch(err => {
            console.error(err);
            process.exit(1);
        });
        """
        result = subprocess.run([node_bin, "-e", script], cwd=str(PROJECT_ROOT), capture_output=True, text=True)
        assert result.returncode == 0, f"Node.js authority separation test failed: {result.stderr}"
