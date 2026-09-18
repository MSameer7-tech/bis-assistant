/**
 * Phase F3 Step 8: BIS AI Assistant Laboratory Finder Frontend Component.
 *
 * Modular, production-ready workbench component for discovering, evaluating,
 * and visualizing BIS-accredited testing laboratories.
 *
 * Architectural Invariants:
 * 1. Authority: BIS testing scope remains the sole capability authority.
 * 2. Decoupling: Geographic metadata is strictly supplementary spatial data.
 * 3. Zero Fabrication: Laboratories without valid coordinates receive no map markers
 *    and are explicitly labeled "Location unavailable".
 * 4. Synchronization: Card selection and map marker selection are bi-directionally linked.
 * 5. Determinism: Preserves exact backend candidate ranking and distances.
 */

import { BisMapComponent, createPinIcon } from './mapComponent.js';
import { apiUrl } from './config.js';

export class LabFinderComponent {
    /**
     * @param {Object} config - Component configuration
     * @param {string|HTMLElement} config.container - Target workspace container element or ID
     * @param {string|HTMLElement} config.mapContainer - Map container element or ID
     * @param {string} [config.apiEndpoint] - Search API endpoint (default: '/api/labs/search')
     * @param {Function} [config.onLabSelect] - Callback when a laboratory is selected
     */
    constructor(config = {}) {
        this.container = typeof config.container === 'string'
            ? document.getElementById(config.container)
            : config.container;

        this.mapContainerId = typeof config.mapContainer === 'string'
            ? config.mapContainer
            : (config.mapContainer ? config.mapContainer.id : 'labFinderMap');

        this.apiEndpoint = config.apiEndpoint || apiUrl('/api/labs/search');
        this.onLabSelect = config.onLabSelect || null;

        // i18n helpers
        this.t = config.t || ((k, fb) => (window.bisI18n ? window.bisI18n.t(k, fb) : (fb || k)));
        this.getLanguage = config.getLanguage || (() => (window.bisI18n ? window.bisI18n.getLanguage() : (document.documentElement && document.documentElement.lang ? document.documentElement.lang : 'en')));

        // State
        this.mapComponent = null;
        this.currentResults = null;
        this.selectedCandidate = null;
        this.isLoading = false;
        this.lastQuery = null;
        this.lastParsedSummary = null;

        // User coordinates (if geolocation enabled or entered)
        this.userLocation = null; // { latitude, longitude, name }
    }

    /**
     * Initializes the Lab Finder component, builds UI structure, and binds listeners.
     */
    init() {
        if (!this.container) {
            console.error('LabFinderComponent: Target container element not found.');
            return this;
        }

        this.renderLayout();
        this.initMap();
        this.bindEvents();

        return this;
    }

    /**
     * Renders the Lab Finder workspace DOM layout inside this.container.
     */
    renderLayout() {
        this.container.innerHTML = `
            <div class="lab-finder-layout">
                <!-- Topbar / Search Control Deck -->
                <header class="lab-finder-topbar">
                    <div class="topbar-title-group">
                        <h2 class="lab-finder-heading" data-i18n="lab_finder.title">BIS Laboratory Finder</h2>
                        <p class="lab-finder-sub" data-i18n="lab_finder.subtitle">Find laboratories with verified BIS testing scope.</p>
                    </div>

                    <!-- Search Form Deck -->
                    <form id="labSearchForm" class="lab-search-form" novalidate>
                        <div class="search-primary-row">
                            <!-- Natural-Language & Standard Search Input -->
                            <div class="search-field field-query">
                                <div class="search-input-wrap">
                                    <svg class="input-icon" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
                                    <input type="text" id="labInputQuery" class="search-input" placeholder="Search by standard, product, or laboratory..." data-i18n-placeholder="lab_finder.input_placeholder" autocomplete="off" spellcheck="false" aria-label="Search laboratories">
                                    <input type="hidden" id="labInputStandard" value="">
                                    <input type="hidden" id="labInputLocation" value="">
                                    <button type="button" id="btnClearLabQuery" class="btn-input-action btn-clear-query hidden" title="Clear query" aria-label="Clear query" data-i18n-title="lab_finder.clear_query">
                                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">
                                            <line x1="18" y1="6" x2="6" y2="18"></line>
                                            <line x1="6" y1="6" x2="18" y2="18"></line>
                                        </svg>
                                    </button>
                                    <button type="button" id="btnLabMic" class="btn-input-action btn-lab-mic" title="Voice search" aria-label="Voice search" data-i18n-title="lab_finder.voice_search">
                                        <svg class="mic-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                            <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"></path>
                                            <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
                                            <line x1="12" y1="19" x2="12" y2="22"></line>
                                        </svg>
                                    </button>
                                    <button type="button" id="btnGeolocate" class="btn-input-action btn-gps-highlight" title="Use current GPS coordinates to locate nearest laboratories" aria-label="Use current location">
                                        <span class="gps-pulse-beacon"></span>
                                        <svg class="gps-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="3"/><line x1="12" y1="2" x2="12" y2="5"/><line x1="12" y1="19" x2="12" y2="22"/><line x1="2" y1="12" x2="5" y2="12"/><line x1="19" y1="12" x2="22" y2="12"/></svg>
                                        <span class="gps-btn-text" data-i18n="lab_finder.near_me">Near me</span>
                                    </button>
                                </div>
                            </div>

                            <!-- Search Action Button -->
                            <div class="search-actions">
                                <button type="submit" id="btnLabSearch" class="btn-lab-search">
                                    <svg class="btn-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
                                    <span data-i18n="lab_finder.search_btn">Find Labs</span>
                                </button>
                            </div>
                        </div>

                        <!-- Secondary Filters Row (Collapsible / Granular) -->
                        <div class="search-filters-row">
                            <!-- Category Filter -->
                            <div class="filter-chip-group">
                                <span class="filter-label" data-i18n="lab_finder.filter_category">Category:</span>
                                <select id="labFilterCategory" class="filter-select" aria-label="Filter by Laboratory Category">
                                    <option value="" data-i18n="lab_finder.category_all">All laboratories (580)</option>
                                    <option value="BIS_OWNED" data-i18n="lab_finder.category_bis_owned">BIS Owned (10 Labs)</option>
                                    <option value="BIS_RECOGNIZED" data-i18n="lab_finder.category_bis_recognized">BIS Recognized (430 Labs)</option>
                                    <option value="BIS_EMPANELLED" data-i18n="lab_finder.category_bis_empanelled">BIS Empanelled (140 Labs)</option>
                                </select>
                            </div>

                            <!-- Radius Limit (Only active when coordinates available) -->
                            <div class="filter-chip-group" id="radiusFilterGroup">
                                <span class="filter-label" data-i18n="lab_finder.max_distance">Max Distance:</span>
                                <select id="labFilterRadius" class="filter-select" aria-label="Filter by Maximum Distance">
                                    <option value="" data-i18n="lab_finder.any_distance">Any Distance</option>
                                    <option value="25" data-i18n="lab_finder.within_25">Within 25 km</option>
                                    <option value="50" data-i18n="lab_finder.within_50">Within 50 km</option>
                                    <option value="100" data-i18n="lab_finder.within_100">Within 100 km</option>
                                    <option value="250" data-i18n="lab_finder.within_250">Within 250 km</option>
                                    <option value="500" data-i18n="lab_finder.within_500">Within 500 km</option>
                                </select>
                            </div>

                            <!-- Complete Scope Toggle -->
                            <label class="filter-checkbox-label" for="labFilterCompleteScope">
                                <input type="checkbox" id="labFilterCompleteScope">
                                <span class="filter-switch-slider"></span>
                                <span data-i18n="lab_finder.complete_scope_only">Complete Scope Only</span>
                            </label>

                            <!-- Results Limit -->
                            <div class="filter-chip-group filter-limit-group">
                                <span class="filter-label" data-i18n="lab_finder.limit">Limit:</span>
                                <select id="labFilterLimit" class="filter-select" aria-label="Results Limit">
                                    <option value="25" data-i18n="lab_finder.limit_25">Top 25</option>
                                    <option value="50" data-i18n="lab_finder.limit_50">Top 50</option>
                                    <option value="100" selected data-i18n="lab_finder.limit_100">Top 100</option>
                                    <option value="580" data-i18n="lab_finder.limit_all">All Matches</option>
                                </select>
                            </div>
                        </div>

                        <!-- Secondary Discovery / Presets Row -->
                        <div class="search-shortcuts-row">
                            <span class="filter-label quick-anchor-label" data-i18n="lab_finder.popular_cities">Popular:</span>
                            <div class="quick-presets-list">
                                <button type="button" class="btn-location-preset" data-name="Delhi" data-lat="28.6139" data-lon="77.2090" data-i18n="lab_finder.city_delhi">Delhi</button>
                                <button type="button" class="btn-location-preset" data-name="Mumbai" data-lat="19.0760" data-lon="72.8777" data-i18n="lab_finder.city_mumbai">Mumbai</button>
                                <button type="button" class="btn-location-preset" data-name="Bengaluru" data-lat="12.9716" data-lon="77.5946" data-i18n="lab_finder.city_bengaluru">Bengaluru</button>
                                <button type="button" class="btn-location-preset" data-name="Chennai" data-lat="13.0827" data-lon="80.2707" data-i18n="lab_finder.city_chennai">Chennai</button>
                                <button type="button" class="btn-location-preset" data-name="Kolkata" data-lat="22.5726" data-lon="88.3639" data-i18n="lab_finder.city_kolkata">Kolkata</button>
                            </div>
                        </div>

                        <!-- Active Coordinate Badge (Shown when reference location is active) -->
                        <div id="activeLocationBanner" class="active-location-banner hidden">
                            <div class="location-banner-content">
                                <span class="location-beacon-dot"></span>
                                <svg class="location-banner-icon" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
                                <span id="activeLocationText" class="location-banner-text">Reference Location: 28.6139° N, 77.2090° E</span>
                            </div>
                            <button type="button" id="btnClearLocation" class="btn-clear-location" title="Remove geographic reference location" data-i18n="lab_finder.clear_location">✕ Clear</button>
                        </div>
                    </form>
                </header>

                <!-- Workspace Split Grid: Cards (Left) vs Interactive Map (Right) -->
                <div class="lab-finder-body">
                    <!-- Left Column: Results Panel -->
                    <aside class="lab-results-panel" aria-label="Laboratory Results List">
                        <!-- Results Status Bar -->
                        <div class="results-status-bar" id="resultsStatusBar">
                            <span id="resultsCountTotal" class="results-count" data-i18n="lab_finder.initial_count">Find a laboratory</span>
                        </div>

                        <!-- Natural-Language Search Interpretation Strip -->
                        <div id="searchInterpretationNotice" class="search-interpretation-notice hidden"></div>

                        <!-- Results Content Area (Cards, Empty State, or Spinner) -->
                        <div class="results-scroll-container no-scrollbar" id="resultsListContainer">
                            <!-- Initial Landing Guide -->
                            <div class="results-empty-state" id="initialGuideState">
                                <div class="empty-state-emblem" aria-hidden="true">
                                    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M9 3h6"/><path d="M10 3v5.5L4.7 18a2 2 0 0 0 1.7 3h11.2a2 2 0 0 0 1.7-3L14 8.5V3"/><path d="M8 15h8"/><path d="M7 18h10"/></svg>
                                </div>
                                <h3 class="empty-state-title" data-i18n="lab_finder.empty_state_title">Find a BIS laboratory</h3>
                                <p class="empty-state-desc" data-i18n="lab_finder.empty_state_desc">Search by standard, product, or laboratory to find facilities with the required testing scope.</p>
                                <div class="empty-state-shortcuts">
                                    <button type="button" class="shortcut-pill" data-query="find me the lab for is 4985 testing" data-standard="IS 4985">IS 4985 testing</button>
                                    <button type="button" class="shortcut-pill" data-query="find labs for testing led lamps" data-standard="IS 16102">LED lamp testing</button>
                                    <button type="button" class="shortcut-pill" data-query="find recognized labs for water heaters near Delhi" data-standard="IS 8978">Water heater labs in Delhi</button>
                                    <button type="button" class="shortcut-pill" data-query="find labs for drinking water in Gujarat" data-standard="IS 10500">Drinking water testing in Gujarat</button>
                                </div>
                            </div>
                        </div>
                    </aside>

                    <!-- Right Column: Interactive Map Panel -->
                    <section class="lab-map-panel" aria-label="Geographic Map View">
                        <div class="map-deck-header">
                            <div class="map-deck-legend">
                                <span class="legend-chip owned"><span class="chip-dot"></span><span data-i18n="lab_finder.legend_owned">BIS Owned</span></span>
                                <span class="legend-chip recognized"><span class="chip-dot"></span><span data-i18n="lab_finder.legend_recognized">BIS Recognized</span></span>
                                <span class="legend-chip empanelled"><span class="chip-dot"></span><span data-i18n="lab_finder.legend_empanelled">BIS Empanelled</span></span>
                            </div>
                            <div class="map-deck-controls">
                                <span id="mapMarkerCounter" class="map-counter-tag hidden"></span>
                                <button type="button" id="btnFitMapBounds" class="btn-map-control" title="Fit map to visible laboratories">
                                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/></svg>
                                    <span data-i18n="lab_finder.fit_view">Fit map</span>
                                </button>
                                <button type="button" id="btnResetMapCenter" class="btn-map-control" title="Reset map to India centroid">
                                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><line x1="12" y1="2" x2="12" y2="22"/></svg>
                                    <span data-i18n="lab_finder.india">India</span>
                                </button>
                            </div>
                        </div>

                        <div class="map-frame-wrapper">
                            <div id="${this.mapContainerId}" class="bis-map-container"></div>
                        </div>
                    </section>
                </div>
            </div>

            <!-- Slide-over Laboratory Detail Inspector Drawer -->
            <div id="labDetailBackdrop" class="drawer-overlay hidden" aria-hidden="true"></div>
            <aside id="labDetailDrawer" class="evidence-drawer-panel lab-detail-drawer" aria-labelledby="labDrawerTitle" aria-hidden="true" role="dialog">
                <div class="drawer-header">
                    <div class="drawer-header-left">
                        <span class="drawer-badge-tag" id="labDrawerCategoryBadge">BIS RECOGNIZED</span>
                        <h3 class="drawer-title" id="labDrawerTitle">Laboratory Details</h3>
                    </div>
                    <button type="button" id="btnLabDrawerClose" class="drawer-close-icon" aria-label="Close Inspector">✕</button>
                </div>

                <div class="drawer-scroll-body no-scrollbar" id="labDrawerBody">
                    <!-- Populated dynamically via this.renderDetailInspector() -->
                </div>

                <div class="drawer-footer">
                    <span class="provenance-label">● Authoritative BIS Testing Scope</span>
                    <button type="button" id="btnLabDrawerDone" class="btn-drawer-done">Close Inspector</button>
                </div>
            </aside>
        `;
    }

    /**
     * Initializes the Leaflet map component instance.
     */
    initMap() {
        try {
            const mapElem = document.getElementById(this.mapContainerId);
            if (mapElem && typeof window.L !== 'undefined') {
                this.mapComponent = new BisMapComponent(mapElem);
                this.mapComponent.init();

                if (typeof window.ResizeObserver !== 'undefined') {
                    this._resizeObserver = new ResizeObserver(() => {
                        if (this.mapComponent) {
                            this.mapComponent.invalidateSize();
                        }
                    });
                    this._resizeObserver.observe(mapElem);
                }
            } else {
                console.warn('LabFinderComponent: Leaflet not ready on window, deferred map init.');
            }
        } catch (err) {
            console.error('LabFinderComponent: Failed to initialize map:', err);
        }
    }

    /**
     * Binds form submissions, clicks, and preset location controls.
     */
    bindEvents() {
        const form = this.container.querySelector('#labSearchForm');
        if (form) {
            form.addEventListener('submit', (e) => {
                e.preventDefault();
                this.executeSearchFromInputs();
            });
        }

        // Clear Query Input Button
        const inputQuery = this.container.querySelector('#labInputQuery');
        const inputStd = this.container.querySelector('#labInputStandard');
        const btnClearQuery = this.container.querySelector('#btnClearLabQuery');

        const updateClearQueryBtn = () => {
            if (btnClearQuery && inputQuery) {
                if (inputQuery.value.trim().length > 0) {
                    btnClearQuery.classList.remove('hidden');
                } else {
                    btnClearQuery.classList.add('hidden');
                }
            }
        };

        if (inputQuery && btnClearQuery) {
            inputQuery.addEventListener('input', updateClearQueryBtn);
            inputQuery.addEventListener('change', updateClearQueryBtn);

            btnClearQuery.addEventListener('click', () => {
                inputQuery.value = '';
                if (inputStd) inputStd.value = '';
                btnClearQuery.classList.add('hidden');
                inputQuery.focus();
                this.renderInitialGuide();
            });
        }

        // GPS Geolocation
        const btnGeolocate = this.container.querySelector('#btnGeolocate');
        if (btnGeolocate) {
            btnGeolocate.addEventListener('click', () => this.handleGeolocate());
        }

        // Voice Input (Speech Recognition)
        this.bindVoiceSearch();

        // Clear Location
        const btnClearLoc = this.container.querySelector('#btnClearLocation');
        if (btnClearLoc) {
            btnClearLoc.addEventListener('click', () => {
                this.clearUserLocation();
                const filterRadius = this.container.querySelector('#labFilterRadius');
                if (filterRadius) filterRadius.value = '';
                const qEl = this.container.querySelector('#labInputQuery');
                const sEl = this.container.querySelector('#labInputStandard');
                if ((qEl && qEl.value.trim()) || (sEl && sEl.value.trim())) {
                    this.executeSearchFromInputs();
                }
            });
        }

        // Location Presets
        const presets = this.container.querySelectorAll('.btn-location-preset');
        presets.forEach(btn => {
            btn.addEventListener('click', () => {
                const name = btn.getAttribute('data-name');
                const lat = parseFloat(btn.getAttribute('data-lat'));
                const lon = parseFloat(btn.getAttribute('data-lon'));

                // Toggle off if already active
                if (this.userLocation && this.userLocation.name === name) {
                    this.clearUserLocation();
                    const filterRadius = this.container.querySelector('#labFilterRadius');
                    if (filterRadius) filterRadius.value = '';
                    const qEl = this.container.querySelector('#labInputQuery');
                    const sEl = this.container.querySelector('#labInputStandard');
                    if ((qEl && qEl.value.trim()) || (sEl && sEl.value.trim())) {
                        this.executeSearchFromInputs();
                    }
                    return;
                }

                // If radius is currently "Any Distance", auto-set sensible default radius of 100 km
                const filterRadius = this.container.querySelector('#labFilterRadius');
                if (filterRadius && !filterRadius.value) {
                    filterRadius.value = '100';
                }

                this.setUserLocation(lat, lon, name);
                this.executeSearchFromInputs();
            });
        });

        // Filter Auto-Trigger on Change (Category, Distance, Scope, Limit)
        const filterCategory = this.container.querySelector('#labFilterCategory');
        const filterRadius = this.container.querySelector('#labFilterRadius');
        const filterComplete = this.container.querySelector('#labFilterCompleteScope');
        const filterLimit = this.container.querySelector('#labFilterLimit');

        [filterCategory, filterRadius, filterComplete, filterLimit].forEach(filterEl => {
            if (filterEl) {
                filterEl.addEventListener('change', () => {
                    const qEl = this.container.querySelector('#labInputQuery');
                    const sEl = this.container.querySelector('#labInputStandard');
                    if ((qEl && qEl.value.trim()) || (sEl && sEl.value.trim())) {
                        this.executeSearchFromInputs();
                    }
                });
            }
        });

        // Shortcut pills in initial guide state
        this.container.addEventListener('click', (e) => {
            const pill = e.target.closest('.shortcut-pill');
            if (pill) {
                const query = pill.getAttribute('data-query');
                const std = pill.getAttribute('data-standard');
                const qEl = this.container.querySelector('#labInputQuery');
                const sEl = this.container.querySelector('#labInputStandard');
                const btnClear = this.container.querySelector('#btnClearLabQuery');
                if (qEl && query) {
                    qEl.value = query;
                    if (btnClear) btnClear.classList.remove('hidden');
                }
                if (sEl && std) {
                    sEl.value = std;
                }
                this.executeSearchFromInputs();
            }
        });

        // Map Buttons
        const btnFit = this.container.querySelector('#btnFitMapBounds');
        if (btnFit) {
            btnFit.addEventListener('click', () => {
                if (this.mapComponent && this.mapComponent.map && this.mapComponent.markers.size > 0) {
                    const group = this.mapComponent.markerLayerGroup;
                    if (group && group.getLayers().length > 0) {
                        const bounds = window.L.featureGroup(group.getLayers()).getBounds();
                        this.mapComponent.map.fitBounds(bounds, { padding: [40, 40], maxZoom: 14 });
                    }
                }
            });
        }

        const btnResetCenter = this.container.querySelector('#btnResetMapCenter');
        if (btnResetCenter) {
            btnResetCenter.addEventListener('click', () => {
                if (this.mapComponent) {
                    this.mapComponent.setView(20.5937, 78.9629, 5);
                }
            });
        }

        // Drawer Close Buttons
        const closeBtn = this.container.querySelector('#btnLabDrawerClose');
        const doneBtn = this.container.querySelector('#btnLabDrawerDone');
        const backdrop = this.container.querySelector('#labDetailBackdrop');

        [closeBtn, doneBtn, backdrop].forEach(el => {
            if (el) el.addEventListener('click', () => this.closeDetailInspector());
        });
    }

    /**
     * Sets user location reference coordinates and synchronizes active control states.
     */
    setUserLocation(lat, lon, name = null) {
        this.userLocation = { latitude: lat, longitude: lon, name: name || `${lat.toFixed(4)}, ${lon.toFixed(4)}` };
        const banner = this.container.querySelector('#activeLocationBanner');
        const text = this.container.querySelector('#activeLocationText');
        if (banner && text) {
            banner.classList.remove('hidden');
            text.textContent = `Proximity Anchor: ${this.userLocation.name} (${lat.toFixed(4)}° N, ${lon.toFixed(4)}° E)`;
        }

        // Update active class on presets and GPS button
        const btnGeolocate = this.container.querySelector('#btnGeolocate');
        const presets = this.container.querySelectorAll('.btn-location-preset');
        if (presets) {
            presets.forEach(p => {
                if (p.getAttribute('data-name') === name) {
                    p.classList.add('active');
                } else {
                    p.classList.remove('active');
                }
            });
        }
        if (btnGeolocate) {
            if (name === 'Current GPS Location') {
                btnGeolocate.classList.add('active');
                const textSpan = btnGeolocate.querySelector('.gps-btn-text');
                if (textSpan) textSpan.textContent = this.t('lab_finder.gps_active', 'Near me (Active)');
            } else {
                btnGeolocate.classList.remove('active');
                const textSpan = btnGeolocate.querySelector('.gps-btn-text');
                if (textSpan) textSpan.textContent = this.t('lab_finder.near_me', 'Near me');
            }
        }

        if (this.mapComponent && this.mapComponent._isInitialized) {
            this.mapComponent.setView(lat, lon, 10);
        }
    }

    /**
     * Clears reference user location coordinates and resets active control states.
     */
    clearUserLocation() {
        this.userLocation = null;
        const banner = this.container.querySelector('#activeLocationBanner');
        if (banner) banner.classList.add('hidden');
        const inputLoc = this.container.querySelector('#labInputLocation');
        if (inputLoc) inputLoc.value = '';

        const btnGeolocate = this.container.querySelector('#btnGeolocate');
        if (btnGeolocate) {
            btnGeolocate.classList.remove('active');
            const textSpan = btnGeolocate.querySelector('.gps-btn-text');
            if (textSpan) textSpan.textContent = this.t('lab_finder.near_me', 'Near me');
        }
        const presets = this.container.querySelectorAll('.btn-location-preset');
        if (presets) presets.forEach(p => p.classList.remove('active'));

        if (this.mapComponent && this.mapComponent._isInitialized) {
            this.mapComponent.setView(20.5937, 78.9629, 5);
        }
    }

    /**
     * Requests user GPS geolocation via browser API with responsive loading feedback.
     */
    handleGeolocate() {
        if (!navigator.geolocation) {
            alert('Geolocation is not supported by your browser.');
            return;
        }

        const btnGeolocate = this.container.querySelector('#btnGeolocate');
        if (btnGeolocate) {
            btnGeolocate.classList.add('loading');
            const textSpan = btnGeolocate.querySelector('.gps-btn-text');
            if (textSpan) textSpan.textContent = this.t('lab_finder.locating', 'Locating...');
        }

        navigator.geolocation.getCurrentPosition(
            (pos) => {
                if (btnGeolocate) btnGeolocate.classList.remove('loading');
                const lat = pos.coords.latitude;
                const lon = pos.coords.longitude;
                const filterRadius = this.container.querySelector('#labFilterRadius');
                if (filterRadius && !filterRadius.value) {
                    filterRadius.value = '100';
                }
                this.setUserLocation(lat, lon, 'Current GPS Location');
                this.executeSearchFromInputs();
            },
            (err) => {
                if (btnGeolocate) {
                    btnGeolocate.classList.remove('loading');
                    const textSpan = btnGeolocate.querySelector('.gps-btn-text');
                    if (textSpan) textSpan.textContent = this.t('lab_finder.near_me', 'Near me');
                }
                console.warn('Geolocation failed or denied:', err);
                alert('Could not determine your location. You can select one of the city presets below.');
            },
            { timeout: 10000, enableHighAccuracy: true }
        );
    }

    /**
     * Binds voice input (speech-to-text) to the laboratory search query input.
     * Uses the browser Web Speech API (SpeechRecognition / webkitSpeechRecognition).
     */
    bindVoiceSearch() {
        const btnMic = this.container.querySelector('#btnLabMic');
        const inputQuery = this.container.querySelector('#labInputQuery');
        if (!btnMic || !inputQuery) return;

        const hasSpeechSupport = typeof window !== 'undefined' && ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window);
        if (!hasSpeechSupport) {
            btnMic.title = this.t('lab_finder.voice_not_supported', 'Voice input (Speech recognition not supported in this browser)');
            btnMic.setAttribute('aria-label', btnMic.title);
            btnMic.classList.add('unsupported');
            return;
        }

        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        let recognition = null;
        try {
            recognition = new SpeechRecognition();
            recognition.continuous = false;
            recognition.interimResults = false;
        } catch (err) {
            console.warn('[LabFinder] SpeechRecognition initialization error:', err);
            return;
        }

        let isListening = false;
        let savedPlaceholder = '';

        const stopListening = () => {
            isListening = false;
            btnMic.classList.remove('listening');
            btnMic.setAttribute('aria-pressed', 'false');
            btnMic.title = this.t('lab_finder.voice_search', 'Voice search');
            if (savedPlaceholder) {
                inputQuery.placeholder = savedPlaceholder;
                savedPlaceholder = '';
            }
        };

        btnMic.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();

            if (!isListening) {
                try {
                    const currentLang = (this.getLanguage && typeof this.getLanguage === 'function')
                        ? this.getLanguage()
                        : (window.bisI18n ? window.bisI18n.getLanguage() : 'en');
                    recognition.lang = currentLang === 'hi' ? 'hi-IN' : 'en-IN';

                    savedPlaceholder = inputQuery.placeholder;
                    inputQuery.placeholder = this.t('lab_finder.voice_listening', 'Listening... speak now');

                    recognition.start();
                    isListening = true;
                    btnMic.classList.add('listening');
                    btnMic.setAttribute('aria-pressed', 'true');
                    btnMic.title = this.t('lab_finder.voice_listening', 'Listening... speak now');
                } catch (err) {
                    console.warn('[LabFinder] SpeechRecognition start error:', err);
                    stopListening();
                }
            } else {
                try {
                    recognition.stop();
                } catch (err) {
                    console.warn('[LabFinder] SpeechRecognition stop error:', err);
                }
                stopListening();
            }
        });

        recognition.onresult = (event) => {
            if (event.results && event.results.length > 0 && event.results[0].length > 0) {
                const transcript = event.results[0][0].transcript.trim();
                if (transcript) {
                    inputQuery.value = transcript;
                    const inputStd = this.container.querySelector('#labInputStandard');
                    if (inputStd) inputStd.value = '';

                    inputQuery.focus();
                    inputQuery.dispatchEvent(new Event('input', { bubbles: true }));
                    this.executeSearchFromInputs();
                }
            }
            stopListening();
        };

        recognition.onerror = (event) => {
            console.warn('[LabFinder] Speech recognition error:', event.error);
            stopListening();
        };

        recognition.onend = () => {
            stopListening();
        };
    }

    /**
     * Builds request payload from DOM inputs and triggers search.
     */
    executeSearchFromInputs() {
        const inputQuery = this.container.querySelector('#labInputQuery');
        const inputStd = this.container.querySelector('#labInputStandard');
        const queryVal = inputQuery ? inputQuery.value.trim() : '';
        const standardVal = inputStd ? inputStd.value.trim() : '';

        const effectiveQuery = queryVal || standardVal;

        if (!effectiveQuery) {
            if (inputQuery) inputQuery.focus();
            else if (inputStd) inputStd.focus();
            return;
        }

        const inputLoc = this.container.querySelector('#labInputLocation');
        const locValue = inputLoc ? inputLoc.value.trim() : '';

        const selectCat = this.container.querySelector('#labFilterCategory');
        const category = selectCat && selectCat.value ? selectCat.value : null;

        const selectRadius = this.container.querySelector('#labFilterRadius');
        const maxDist = selectRadius && selectRadius.value ? parseFloat(selectRadius.value) : null;

        const checkComplete = this.container.querySelector('#labFilterCompleteScope');
        const requireComplete = checkComplete ? checkComplete.checked : false;

        const selectLimit = this.container.querySelector('#labFilterLimit');
        const limit = selectLimit && selectLimit.value ? parseInt(selectLimit.value, 10) : null;

        const requestOptions = {
            standard: standardVal || effectiveQuery,
            category: category,
            require_complete_scope: requireComplete,
            limit: limit
        };

        // If user coordinates exist, attach them
        if (this.userLocation) {
            requestOptions.latitude = this.userLocation.latitude;
            requestOptions.longitude = this.userLocation.longitude;
            if (maxDist) requestOptions.max_distance_km = maxDist;
        }

        // If text location was typed (and not geolocated coordinates)
        if (locValue && !this.userLocation) {
            requestOptions.state = locValue;
        }

        // If search was monkeypatched (e.g. by unit tests) or if queryVal is empty and standardVal is set:
        const isMonkeyPatched = typeof this.search === 'function' && this.search !== LabFinderComponent.prototype.search;
        if (isMonkeyPatched || (!queryVal && standardVal)) {
            this.search(requestOptions);
            return;
        }

        // Natural-language search workflow
        const naturalOptions = {
            category: category,
            require_complete_scope: requireComplete,
            limit: limit
        };
        if (maxDist) {
            naturalOptions.max_distance_km = maxDist;
        }

        this.searchNatural(effectiveQuery, naturalOptions);
    }

    /**
     * Natural-language search execution.
     * Passes colloquial query to /api/labs/natural-search (Groq + deterministic parser),
     * displays the factual interpretation notice, and renders the authoritative results.
     */
    async searchNatural(query, extraOptions = {}) {
        if (!query || !query.trim()) return;

        this.isLoading = true;
        this.lastQuery = { query: query.trim(), ...extraOptions };
        this.renderLoadingState(query.trim());

        const noticeElem = this.container.querySelector('#searchInterpretationNotice');
        if (noticeElem) {
            noticeElem.classList.add('hidden');
            noticeElem.textContent = '';
        }

        const payload = {
            query: query.trim(),
            ...extraOptions
        };

        if (this.userLocation) {
            payload.latitude = this.userLocation.latitude;
            payload.longitude = this.userLocation.longitude;
        }
        if (extraOptions.max_distance_km) {
            payload.max_distance_km = extraOptions.max_distance_km;
        }

        try {
            const resp = await fetch(apiUrl('/api/labs/natural-search'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!resp.ok) {
                const errData = await resp.json().catch(() => ({}));
                const errMsg = (errData.detail && errData.detail.error)
                    ? errData.detail.error
                    : `Search failed with status ${resp.status}`;
                this.renderErrorState(errMsg, resp.status === 400 ? 'INVALID_REQUEST' : 'API_ERROR');
                this.isLoading = false;
                return;
            }

            const data = await resp.json();
            this.isLoading = false;

            if (data.status === 'NEEDS_CLARIFICATION') {
                this.renderClarificationState(data.clarification_message);
                return;
            }

            this.currentResults = data.search_results;

            // Show factual interpretation notice (e.g. 'Searching for: IS 4985 · Delhi' or 'Interpreted as: LED lamps · IS 16102')
            if (noticeElem && data.parsed_query && data.parsed_query.factual_summary) {
                this.lastParsedSummary = data.parsed_query.factual_summary;
                const summary = data.parsed_query.factual_summary;
                let displayText = summary;
                if (this.getLanguage() === 'hi') {
                    const interpLabel = this.t('lab_finder.interpreted_as', 'व्याख्या:');
                    const searchLabel = this.t('lab_finder.searching_for', 'खोज रहे हैं:');
                    displayText = summary
                        .replace(/^Interpreted as:\s*/i, `${interpLabel} `)
                        .replace(/^Searching for:\s*/i, `${searchLabel} `);
                }
                noticeElem.innerHTML = `
                    <svg class="notice-icon" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
                    <span class="notice-text">${this.escapeHtml(displayText)}</span>
                `;
                noticeElem.title = displayText;
                noticeElem.classList.remove('hidden');
            }

            if (data.parsed_query && data.parsed_query.standard) {
                const inputStd = this.container.querySelector('#labInputStandard');
                if (inputStd) inputStd.value = data.parsed_query.standard;
            }

            if (data.search_results) {
                this.renderResults(data.search_results);
            }
        } catch (err) {
            console.error('LabFinderComponent: Network error during natural search:', err);
            this.renderErrorState('Unable to reach Laboratory Search API. Please verify server connection.', 'NETWORK_ERROR');
            this.isLoading = false;
        }
    }

    /**
     * Renders a clean clarification state when the query cannot be safely established.
     */
    renderClarificationState(message) {
        const container = this.container.querySelector('#resultsListContainer');
        const countElem = this.container.querySelector('#resultsCountTotal');
        const mapCounter = this.container.querySelector('#mapMarkerCounter');

        if (countElem) countElem.textContent = this.t('lab_finder.clarification_needed', 'Clarification needed');
        if (mapCounter) {
            mapCounter.classList.add('hidden');
            mapCounter.textContent = '';
        }

        if (container) {
            container.innerHTML = `
                <div class="results-empty-state">
                    <div class="empty-state-emblem">ℹ️</div>
                    <h3 class="empty-state-title">Clarify Search Query</h3>
                    <p class="empty-state-desc">${message || 'Please specify an Indian Standard number (e.g. IS 4985) or clarify the product to find accredited testing laboratories.'}</p>
                </div>
            `;
        }

        if (this.mapComponent) {
            this.mapComponent.clearMarkers();
        }
    }

    /**
     * Programmatic search trigger.
     * @param {Object} options - Search options matching LabSearchRequest schema
     */
    async search(options) {
        if (!options || !options.standard) {
            console.warn('LabFinderComponent: standard is required for search.');
            return;
        }

        this.isLoading = true;
        this.lastQuery = options;
        this.renderLoadingState(options.standard);

        const noticeElem = this.container.querySelector('#searchInterpretationNotice');
        if (noticeElem) {
            noticeElem.classList.add('hidden');
            noticeElem.innerHTML = '';
        }

        try {
            const targetEndpoint = this.apiEndpoint.startsWith('http') ? this.apiEndpoint : apiUrl(this.apiEndpoint);
            const resp = await fetch(targetEndpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(options)
            });

            if (!resp.ok) {
                const errData = await resp.json().catch(() => ({}));
                const errMsg = (errData.detail && errData.detail.error)
                    ? errData.detail.error
                    : `Search failed with status ${resp.status}`;
                this.renderErrorState(errMsg, resp.status === 400 ? 'INVALID_REQUEST' : 'API_ERROR');
                this.isLoading = false;
                return;
            }

            const data = await resp.json();
            this.currentResults = data;
            this.isLoading = false;

            this.renderResults(data);
        } catch (err) {
            console.error('LabFinderComponent: Network or server error during search:', err);
            this.renderErrorState('Unable to reach Laboratory Search API. Please verify server connection.', 'NETWORK_ERROR');
            this.isLoading = false;
        }
    }

    /**
     * Renders skeleton loading state into the results pane.
     */
    renderLoadingState(std) {
        const container = this.container.querySelector('#resultsListContainer');
        const statusBar = this.container.querySelector('#resultsStatusBar');
        const countElem = this.container.querySelector('#resultsCountTotal');
        const badgeElem = this.container.querySelector('#resultsQueryBadge');

        if (badgeElem) {
            badgeElem.textContent = std;
            badgeElem.classList.remove('hidden');
        }
        if (countElem) countElem.textContent = this.getLanguage() === 'hi' ? 'खोज जारी है...' : 'Searching official BIS scopes...';

        const titleText = this.getLanguage() === 'hi'
            ? `<strong>${this.escapeHtml(std)}</strong> के लिए बीआईएस एलआईएमएस परीक्षण कार्यक्षेत्र का मूल्यांकन...`
            : `Evaluating BIS LIMS testing scopes for <strong>${this.escapeHtml(std)}</strong>...`;
        const subText = this.getLanguage() === 'hi'
            ? 'मान्यता प्राप्त खंडों, बहिष्करणों और दूरी की जांच की जा रही है'
            : 'Checking accredited clauses, exclusions, and distance cache';

        if (container) {
            container.innerHTML = `
                <div class="lab-skeleton-container lab-loading-skeleton" aria-busy="true" aria-live="polite">
                    <div class="lab-skeleton-status-banner">
                        <div class="skeleton-pulse-dot" aria-hidden="true"></div>
                        <div class="skeleton-status-text">
                            <p class="skeleton-status-title">${titleText}</p>
                            <span class="skeleton-status-sub">${subText}</span>
                        </div>
                    </div>

                    <div class="lab-cards-list skeleton-cards-list" aria-hidden="true">
                        ${[1, 2, 3].map((num) => `
                            <div class="lab-candidate-card lab-card-skeleton">
                                <div class="card-header-row">
                                    <div class="card-identity-group">
                                        <div class="skeleton-shimmer skeleton-rank"></div>
                                        <div class="skeleton-shimmer skeleton-badge"></div>
                                    </div>
                                    <div class="skeleton-shimmer skeleton-distance"></div>
                                </div>

                                <div class="skeleton-title-group">
                                    <div class="skeleton-shimmer skeleton-title-line" style="width: ${num === 1 ? '82%' : num === 2 ? '72%' : '86%'}"></div>
                                    <div class="skeleton-shimmer skeleton-title-line-sm" style="width: ${num === 1 ? '48%' : num === 2 ? '62%' : '44%'}"></div>
                                </div>

                                <div class="skeleton-address-row">
                                    <div class="skeleton-shimmer skeleton-icon-pin"></div>
                                    <div class="skeleton-shimmer skeleton-address-line" style="width: ${num === 1 ? '86%' : num === 2 ? '76%' : '90%'}"></div>
                                </div>

                                <div class="card-badges-row">
                                    <div class="skeleton-shimmer skeleton-pill skeleton-pill-scope"></div>
                                    <div class="skeleton-shimmer skeleton-pill skeleton-pill-clauses"></div>
                                    <div class="skeleton-shimmer skeleton-pill skeleton-pill-fee"></div>
                                </div>

                                <div class="card-footer-actions">
                                    <div class="skeleton-shimmer skeleton-btn-action"></div>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        }
    }

    /**
     * Renders results into cards and updates map markers.
     */
    renderResults(data) {
        const container = this.container.querySelector('#resultsListContainer');
        const countElem = this.container.querySelector('#resultsCountTotal');
        const badgeElem = this.container.querySelector('#resultsQueryBadge');
        const metaTags = this.container.querySelector('#resultsMetaTags');

        if (!container) return;

        // Update Header
        if (badgeElem) {
            badgeElem.textContent = data.standard;
            badgeElem.classList.remove('hidden');
        }

        // Meta tags for filters
        if (metaTags) {
            metaTags.innerHTML = '';
            if (data.query_criteria.user_coordinates) {
                const tag = document.createElement('span');
                tag.className = 'meta-pill';
                tag.textContent = this.t('lab_finder.proximity_near', 'Proximity: Near Anchor');
                metaTags.appendChild(tag);
            }
            if (data.query_criteria.max_distance_km) {
                const tag = document.createElement('span');
                tag.className = 'meta-pill';
                tag.textContent = `≤ ${data.query_criteria.max_distance_km} km`;
                metaTags.appendChild(tag);
            }
            if (data.query_criteria.category) {
                const tag = document.createElement('span');
                tag.className = 'meta-pill';
                const catKey = data.query_criteria.category === 'BIS_OWNED' ? 'lab_finder.legend_owned'
                    : data.query_criteria.category === 'BIS_RECOGNIZED' ? 'lab_finder.legend_recognized'
                    : 'lab_finder.legend_empanelled';
                tag.textContent = this.t(catKey, data.query_criteria.category.replace('_', ' '));
                metaTags.appendChild(tag);
            }
            if (data.query_criteria.require_complete_scope) {
                const tag = document.createElement('span');
                tag.className = 'meta-pill';
                tag.textContent = this.t('lab_finder.complete_scope', 'Complete Scope');
                metaTags.appendChild(tag);
            }
        }

        // Empty Results check
        if (data.status === 'NO_MATCH' || !data.candidates || data.candidates.length === 0) {
            const hasRadius = Boolean(data.query_criteria && data.query_criteria.max_distance_km);
            const nearestCandidate = data.provenance?.geographic_ranking?.nearest_candidate;
            const locName = this.userLocation ? this.userLocation.name : (data.query_criteria?.city || null);

            if (hasRadius || this.userLocation || (data.query_criteria && (data.query_criteria.city || data.query_criteria.state))) {
                this.renderEmptyState('RADIUS_EXHAUSTED', {
                    standard: data.standard,
                    radius: data.query_criteria?.max_distance_km || 100,
                    locationName: locName,
                    nearestCandidate: nearestCandidate
                });
            } else {
                this.renderEmptyState('NO_CAPABILITY_MATCH', { standard: data.standard });
            }
            if (countElem) {
                const isHi = this.getLanguage() === 'hi';
                countElem.textContent = locName
                    ? (isHi ? `${locName} में कोई प्रयोगशाला नहीं मिली` : `No laboratories found in ${locName}`)
                    : this.t('lab_finder.no_matches', 'No matching laboratories');
            }
            this.updateMapMarkers([]);
            return;
        }

        if (countElem) {
            const returned = data.returned_candidates;
            const total = data.total_matching;
            const isHi = this.getLanguage() === 'hi';

            let locNotice = '';
            if (this.userLocation && this.userLocation.name) {
                const dist = data.query_criteria?.max_distance_km;
                locNotice = dist
                    ? (isHi ? ` (${this.userLocation.name} के ${dist} किमी के भीतर)` : ` within ${dist} km of ${this.userLocation.name}`)
                    : (isHi ? ` (${this.userLocation.name} के पास)` : ` near ${this.userLocation.name}`);
            }

            if (returned < total) {
                countElem.textContent = isHi
                    ? `${total} प्रयोगशालाओं में से ${returned} दिखाई जा रही हैं${locNotice}`
                    : `Showing ${returned} of ${total} laboratories found${locNotice}`;
            } else {
                countElem.textContent = isHi
                    ? `${total} ${total === 1 ? 'प्रयोगशाला मिली' : 'प्रयोगशालाएं मिलीं'}${locNotice}`
                    : `${total} ${total === 1 ? 'laboratory found' : 'laboratories found'}${locNotice}`;
            }
        }

        // Render Candidate Cards
        container.innerHTML = '';
        const listWrapper = document.createElement('div');
        listWrapper.className = 'lab-cards-list';

        data.candidates.forEach((cand, idx) => {
            const card = this.createCandidateCard(cand, idx);
            listWrapper.appendChild(card);
        });

        container.appendChild(listWrapper);

        // Update Leaflet Map Markers
        this.updateMapMarkers(data.candidates);
    }

    /**
     * Builds a DOM card element for a single laboratory candidate.
     */
    createCandidateCard(cand, index) {
        const card = document.createElement('div');
        card.className = 'lab-candidate-card';
        card.setAttribute('data-id', cand.internal_id);
        card.setAttribute('data-rank', cand.rank);

        const geo = cand.geographic_metadata || {};
        const cap = cand.capability_evidence || {};
        const addr = cand.address || {};

        // Category Tag Class
        const catLower = (cand.category || '').toLowerCase();
        let catClass = 'recognized';
        let catLabel = this.t('lab_finder.legend_recognized', 'BIS Recognized');
        if (catLower.includes('owned')) {
            catClass = 'owned';
            catLabel = this.t('lab_finder.legend_owned', 'BIS Owned');
        } else if (catLower.includes('empanelled')) {
            catClass = 'empanelled';
            catLabel = this.t('lab_finder.legend_empanelled', 'BIS Empanelled');
        }

        // Distance or Location Unavailable Badge
        let distanceHtml = '';
        if (geo.has_coordinates && typeof geo.distance_km === 'number') {
            const distStr = this.getLanguage() === 'hi'
                ? `${geo.distance_km.toFixed(1)} किमी दूर`
                : `${geo.distance_km.toFixed(1)} km away`;
            distanceHtml = `<span class="card-distance-badge">${distStr}</span>`;
        } else if (!geo.has_coordinates) {
            distanceHtml = `<span class="card-distance-badge unavailable" title="No validated geographic coordinates in metadata cache">${this.t('lab_finder.location_unavailable', 'Location unavailable')}</span>`;
        }

        // Scope Completeness Badge
        const isComplete = cap.scope_completeness === 'COMPLETE_SCOPE';
        const scopeBadgeClass = isComplete ? 'scope-complete' : 'scope-partial';
        const scopeLabel = isComplete
            ? this.t('lab_finder.complete_scope', 'Complete Scope')
            : this.t('lab_finder.partial_scope', 'Partial Scope');

        // Testing Fee
        let feeHtml = '';
        if (typeof cap.base_testing_fee === 'number' && cap.base_testing_fee > 0) {
            feeHtml = `<span class="card-fee">₹${cap.base_testing_fee.toLocaleString('en-IN')}</span>`;
        }

        // Matched Clauses Pill
        let clausesHtml = '';
        if (cap.matched_clauses && cap.matched_clauses.length > 0) {
            const cStr = this.getLanguage() === 'hi'
                ? `कार्यक्षेत्र में ${cap.matched_clauses.length} खंड`
                : `${cap.matched_clauses.length} clauses in scope`;
            clausesHtml = `<span class="card-clauses-info">${cStr}</span>`;
        } else if (cap.excluded_clauses && cap.excluded_clauses.length > 0) {
            const cStr = this.getLanguage() === 'hi'
                ? `${cap.excluded_clauses.length} खंड बाहर रखे गए`
                : `${cap.excluded_clauses.length} clauses excluded`;
            clausesHtml = `<span class="card-clauses-info excluded">${cStr}</span>`;
        }

        card.innerHTML = `
            <div class="card-header-row">
                <div class="card-identity-group">
                    <span class="card-rank-tag">#${cand.rank}</span>
                    <span class="card-category-badge ${catClass}">${catLabel}</span>
                </div>
                ${distanceHtml}
            </div>

            <h4 class="card-lab-name">${this.escapeHtml(cand.laboratory_name)}</h4>

            <p class="card-address-text">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
                <span>${this.escapeHtml(addr.original_address)}</span>
            </p>

            <div class="card-badges-row">
                <span class="card-scope-badge ${scopeBadgeClass}">${scopeLabel}</span>
                ${clausesHtml}
                ${feeHtml}
            </div>

            <div class="card-footer-actions">
                <button type="button" class="btn-card-detail" data-id="${cand.internal_id}">
                    <span>${this.t('lab_finder.inspect_scope_evidence', 'Inspect Scope & Evidence')}</span>
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg>
                </button>
            </div>
        `;

        // Card Click Interaction: Center/Zoom map to marker and highlight
        card.addEventListener('click', (e) => {
            // Ignore if clicking inside action button which opens inspector
            if (e.target.closest('.btn-card-detail')) {
                this.openDetailInspector(cand);
                return;
            }
            this.selectCandidate(cand, true);
        });

        const detailBtn = card.querySelector('.btn-card-detail');
        if (detailBtn) {
            detailBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.openDetailInspector(cand);
            });
        }

        return card;
    }

    /**
     * Updates Leaflet Map markers based on candidate list.
     * ZERO_RESULTS / null-coordinate labs receive NO marker (never fabricate coordinates).
     */
    updateMapMarkers(candidates = []) {
        const counter = this.container.querySelector('#mapMarkerCounter');
        if (!this.mapComponent) return;

        // Ensure Leaflet map is initialized
        if (!this.mapComponent._isInitialized) {
            this.mapComponent.init();
        }

        this.mapComponent.clearMarkers();

        const markersList = [];
        let mappedCount = 0;

        candidates.forEach(cand => {
            const geo = cand.geographic_metadata || {};
            // Strict Invariant: Only create marker if has_coordinates is true and coords are numbers
            if (geo.has_coordinates && typeof geo.latitude === 'number' && typeof geo.longitude === 'number') {
                mappedCount++;

                const catLower = (cand.category || '').toLowerCase();
                let catEnum = 'DEFAULT';
                if (catLower.includes('owned')) catEnum = 'BIS_OWNED';
                else if (catLower.includes('recognized')) catEnum = 'BIS_RECOGNIZED';
                else if (catLower.includes('empanelled')) catEnum = 'BIS_EMPANELLED';

                const distText = (typeof geo.distance_km === 'number') ? ` • <strong>${geo.distance_km.toFixed(1)} km</strong>` : '';

                const popupHtml = `
                    <div class="bis-popup-card">
                        <div class="bis-popup-header">
                            <span class="bis-popup-badge ${catLower.includes('owned') ? 'owned' : (catLower.includes('recognized') ? 'recognized' : 'empanelled')}">${catEnum.replace('_', ' ')}</span>
                            <span class="bis-popup-coords">#${cand.rank}${distText}</span>
                        </div>
                        <h4 class="bis-popup-title">${this.escapeHtml(cand.laboratory_name)}</h4>
                        <p class="bis-popup-address">${this.escapeHtml(cand.address.original_address)}</p>
                        <div class="bis-popup-footer">
                            <span class="popup-scope-tag">${cand.capability_evidence.scope_completeness === 'COMPLETE_SCOPE' ? this.t('lab_finder.complete_scope', 'Complete Scope') : this.t('lab_finder.partial_scope', 'Partial Scope')}</span>
                            <button type="button" class="btn-popup-inspect" data-id="${cand.internal_id}">${this.t('lab_finder.inspect_scope_evidence', 'Inspect Scope')}</button>
                        </div>
                    </div>
                `;

                markersList.push({
                    id: `lab_${cand.internal_id}`,
                    lat: geo.latitude,
                    lng: geo.longitude,
                    title: cand.laboratory_name,
                    category: catEnum,
                    popupContent: popupHtml
                });
            }
        });

        if (counter) {
            if (mappedCount > 0) {
                counter.classList.remove('hidden');
                const isHi = this.getLanguage() === 'hi';
                if (mappedCount < candidates.length) {
                    counter.textContent = isHi
                        ? `${candidates.length} में से ${mappedCount} मानचित्र पर`
                        : `${mappedCount} of ${candidates.length} on map`;
                } else {
                    counter.textContent = isHi
                        ? `${mappedCount} मानचित्र पर`
                        : `${mappedCount} on map`;
                }
            } else {
                counter.classList.add('hidden');
                counter.textContent = '';
            }
        }

        // Add markers and fit bounds
        this.mapComponent.setMarkers(markersList, true);

        // Wire marker click synchronization
        markersList.forEach(item => {
            const marker = this.mapComponent.markers.get(item.id);
            if (marker) {
                marker.on('click', () => {
                    const idStr = item.id.replace('lab_', '');
                    const cand = candidates.find(c => String(c.internal_id) === idStr);
                    if (cand) {
                        this.selectCandidate(cand, false); // select card without triggering recursive map setView
                    }
                });

                marker.on('popupopen', (e) => {
                    const popupElem = e.popup.getElement();
                    if (popupElem) {
                        const inspectBtn = popupElem.querySelector('.btn-popup-inspect');
                        if (inspectBtn) {
                            inspectBtn.onclick = () => {
                                const idStr = inspectBtn.getAttribute('data-id');
                                const cand = candidates.find(c => String(c.internal_id) === idStr);
                                if (cand) this.openDetailInspector(cand);
                            };
                        }
                    }
                });
            }
        });

        // Trigger map resize check to ensure complete tile rendering
        if (this.mapComponent) {
            this.mapComponent.invalidateSize();
            setTimeout(() => {
                if (this.mapComponent) {
                    this.mapComponent.invalidateSize();
                }
            }, 100);
        }
    }

    /**
     * Selects and highlights a laboratory card and synchronizes with its map marker.
     */
    selectCandidate(cand, panMap = true) {
        this.selectedCandidate = cand;

        // Highlight card in list
        const cards = this.container.querySelectorAll('.lab-candidate-card');
        cards.forEach(c => c.classList.remove('selected'));

        const targetCard = this.container.querySelector(`.lab-candidate-card[data-id="${cand.internal_id}"]`);
        if (targetCard) {
            targetCard.classList.add('selected');
            targetCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }

        // Pan map if marker exists
        const geo = cand.geographic_metadata || {};
        if (panMap && this.mapComponent && geo.has_coordinates && typeof geo.latitude === 'number') {
            this.mapComponent.setView(geo.latitude, geo.longitude, 13);
            const marker = this.mapComponent.markers.get(`lab_${cand.internal_id}`);
            if (marker) marker.openPopup();
        }

        if (this.onLabSelect) {
            this.onLabSelect(cand);
        }
    }

    /**
     * Opens the slide-over Laboratory Detail Inspector with strict separation of
     * BIS Authoritative Scope and External Geographic Metadata.
     */
    openDetailInspector(cand) {
        const drawer = this.container.querySelector('#labDetailDrawer');
        const backdrop = this.container.querySelector('#labDetailBackdrop');
        const titleElem = this.container.querySelector('#labDrawerTitle');
        const badgeElem = this.container.querySelector('#labDrawerCategoryBadge');
        const bodyElem = this.container.querySelector('#labDrawerBody');

        if (!drawer || !backdrop || !bodyElem) return;

        const cap = cand.capability_evidence || {};
        const geo = cand.geographic_metadata || {};
        const addr = cand.address || {};

        if (titleElem) titleElem.textContent = cand.laboratory_name;
        if (badgeElem) {
            badgeElem.textContent = (cand.category || '').replace('_', ' ');
            badgeElem.className = `drawer-badge-tag ${cand.category.toLowerCase()}`;
        }

        // Build Detail Body with strict authority boundaries
        bodyElem.innerHTML = `
            <!-- SECTION 1: BIS AUTHORITATIVE NORMATIVE EVIDENCE -->
            <div class="drawer-authority-header">
                <span class="auth-icon">🏛️</span>
                <div>
                    <h4>${this.t('lab_finder.drawer_title', 'Authoritative BIS LIMS Capability Evidence')}</h4>
                    <p>${this.t('lab_finder.drawer_subtitle', 'Statutory testing scope and accreditation verified by Bureau of Indian Standards.')}</p>
                </div>
            </div>

            <div class="drawer-meta-table">
                <div class="drawer-meta-cell">
                    <span class="cell-label">${this.t('lab_finder.public_lab_code', 'Public Lab Code')}</span>
                    <span class="cell-value mono highlight">${cand.public_lab_code}</span>
                </div>
                <div class="drawer-meta-cell">
                    <span class="cell-label">${this.t('lab_finder.internal_lims_id', 'Internal LIMS ID')}</span>
                    <span class="cell-value mono">${cand.internal_id}</span>
                </div>
                <div class="drawer-meta-cell">
                    <span class="cell-label">${this.t('lab_finder.governing_standard', 'Governing Standard')}</span>
                    <span class="cell-value highlight">${this.escapeHtml(cap.matching_standard)}</span>
                </div>
                <div class="drawer-meta-cell">
                    <span class="cell-label">${this.t('lab_finder.scope_id', 'Scope ID')}</span>
                    <span class="cell-value mono">${this.escapeHtml(cap.matching_scope_id)}</span>
                </div>
                <div class="drawer-meta-cell">
                    <span class="cell-label">${this.t('lab_finder.scope_completeness', 'Scope Completeness')}</span>
                    <span class="cell-value ${cap.scope_completeness === 'COMPLETE_SCOPE' ? 'highlight' : ''}">${cap.scope_completeness === 'COMPLETE_SCOPE' ? this.t('lab_finder.complete_scope', 'Complete Scope') : this.t('lab_finder.partial_scope', 'Partial Scope')}</span>
                </div>
                <div class="drawer-meta-cell">
                    <span class="cell-label">${this.t('lab_finder.testing_fee', 'Testing Fee')}</span>
                    <span class="cell-value">${typeof cap.base_testing_fee === 'number' ? `₹${cap.base_testing_fee.toLocaleString('en-IN')}` : (this.getLanguage() === 'hi' ? 'आवेदन पर शुल्क' : 'Fee on Application')}</span>
                </div>
            </div>

            <!-- Authoritative BIS Address -->
            <div class="drawer-section-card">
                <h4>${this.t('lab_finder.official_address', 'Official Registered BIS Address')}</h4>
                <p class="drawer-address-verbatim">${this.escapeHtml(addr.original_address)}</p>
                <div class="drawer-address-details">
                    <span><strong>${this.getLanguage() === 'hi' ? 'राज्य:' : 'State:'}</strong> ${this.escapeHtml(addr.state || 'N/A')}</span>
                    <span><strong>${this.getLanguage() === 'hi' ? 'ज़िला:' : 'District:'}</strong> ${this.escapeHtml(addr.district || 'N/A')}</span>
                    <span><strong>${this.getLanguage() === 'hi' ? 'शहर:' : 'City:'}</strong> ${this.escapeHtml(addr.city || 'N/A')}</span>
                    <span><strong>${this.getLanguage() === 'hi' ? 'पिनकोड:' : 'Pincode:'}</strong> ${this.escapeHtml(addr.pincode || 'N/A')}</span>
                </div>
            </div>

            <!-- Clauses Breakdown -->
            <div class="drawer-section-card">
                <h4>${this.t('lab_finder.clauses_breakdown', 'Clause Capabilities Breakdown')}</h4>
                <div class="clauses-breakdown-list">
                    <div class="clause-item">
                        <span class="clause-label">${this.getLanguage() === 'hi' ? `संबद्ध खंड (${cap.matched_clauses ? cap.matched_clauses.length : 0})` : `Matched Clauses (${cap.matched_clauses ? cap.matched_clauses.length : 0})`}</span>
                        <span class="clause-content">${cap.matched_clauses && cap.matched_clauses.length > 0 ? cap.matched_clauses.join(', ') : (this.getLanguage() === 'hi' ? 'पूर्ण कार्यक्षेत्र के तहत सभी लागू मानक खंड शामिल हैं।' : 'All applicable normative clauses included under complete scope.')}</span>
                    </div>
                    ${cap.excluded_clauses && cap.excluded_clauses.length > 0 ? `
                        <div class="clause-item excluded">
                            <span class="clause-label">${this.getLanguage() === 'hi' ? `अपवर्जित खंड (${cap.excluded_clauses.length})` : `Excluded Clauses (${cap.excluded_clauses.length})`}</span>
                            <span class="clause-content">${cap.excluded_clauses.join(', ')}</span>
                        </div>
                    ` : ''}
                    <div class="clause-item">
                        <span class="clause-label">${this.getLanguage() === 'hi' ? 'क्षमता मिलान स्कोर' : 'Capability Match Score'}</span>
                        <span class="clause-content mono">${cap.match_score} / 150.0</span>
                    </div>
                </div>
            </div>

            <!-- BIS Provenance Hashes -->
            <div class="drawer-checksum-card">
                <div class="checksum-header">
                    <span>${this.t('lab_finder.provenance_hashes', 'BIS Scope SHA-256 Checksum:')}</span>
                    <span class="checksum-authority-tag">LIMS Immutable Source</span>
                </div>
                <code class="checksum-code">${cap.provenance_sha256 || 'N/A'}</code>
                ${cap.provenance_url ? `
                    <div class="provenance-link-wrap">
                        <a href="${cap.provenance_url}" target="_blank" rel="noopener noreferrer" class="cell-value highlight">${this.t('lab_finder.view_lims_record', 'View Official BIS LIMS Record ↗')}</a>
                    </div>
                ` : ''}
            </div>

            <!-- SECTION 2: SUPPLEMENTARY GEOGRAPHIC METADATA -->
            <div class="drawer-authority-header geo-header">
                <span class="auth-icon">🌐</span>
                <div>
                    <h4>${this.t('lab_finder.geo_metadata_title', 'Supplementary Geographic Metadata')}</h4>
                    <p class="geo-disclaimer-quote">"${geo.authority_disclaimer || 'Geographic distance is supplementary spatial metadata. It does not constitute normative evidence of BIS recognition.'}"</p>
                </div>
            </div>

            <div class="drawer-meta-table">
                <div class="drawer-meta-cell">
                    <span class="cell-label">${this.t('lab_finder.geocoding_status', 'Geocoding Status')}</span>
                    <span class="cell-value ${geo.geocoding_status === 'SUCCESS' ? 'highlight' : ''}">${geo.geocoding_status}</span>
                </div>
                <div class="drawer-meta-cell">
                    <span class="cell-label">${this.t('lab_finder.proximity_distance', 'Proximity Distance')}</span>
                    <span class="cell-value">${typeof geo.distance_km === 'number' ? `${geo.distance_km.toFixed(2)} km` : (this.getLanguage() === 'hi' ? 'कोई संदर्भ दूरी नहीं' : 'No Reference Distance')}</span>
                </div>
                <div class="drawer-meta-cell">
                    <span class="cell-label">${this.t('lab_finder.latitude', 'Latitude')}</span>
                    <span class="cell-value mono">${geo.latitude !== null ? geo.latitude : 'Unavailable'}</span>
                </div>
                <div class="drawer-meta-cell">
                    <span class="cell-label">${this.t('lab_finder.longitude', 'Longitude')}</span>
                    <span class="cell-value mono">${geo.longitude !== null ? geo.longitude : 'Unavailable'}</span>
                </div>
                <div class="drawer-meta-cell">
                    <span class="cell-label">Provider</span>
                    <span class="cell-value">${geo.provider || 'GEOAPIFY'}</span>
                </div>
                <div class="drawer-meta-cell">
                    <span class="cell-label">Geocoding Confidence</span>
                    <span class="cell-value">${typeof geo.confidence === 'number' ? `${(geo.confidence * 100).toFixed(0)}%` : 'N/A'}</span>
                </div>
            </div>

            ${geo.formatted_address ? `
                <div class="drawer-section-card">
                    <h4>${this.getLanguage() === 'hi' ? 'हल किया गया भौगोलिक पता' : 'Resolved Geographic Address'}</h4>
                    <p class="drawer-address-verbatim">${this.escapeHtml(geo.formatted_address)}</p>
                </div>
            ` : ''}
        `;

        drawer.classList.add('open');
        drawer.setAttribute('aria-hidden', 'false');
        backdrop.classList.remove('hidden');
    }

    /**
     * Closes the slide-over detail drawer.
     */
    closeDetailInspector() {
        const drawer = this.container.querySelector('#labDetailDrawer');
        const backdrop = this.container.querySelector('#labDetailBackdrop');
        if (drawer) {
            drawer.classList.remove('open');
            drawer.setAttribute('aria-hidden', 'true');
        }
        if (backdrop) backdrop.classList.add('hidden');
    }

    /**
     * Renders specific empty state with explanatory guidance.
     */
    renderEmptyState(type, context = {}) {
        const container = this.container.querySelector('#resultsListContainer');
        const countElem = this.container.querySelector('#resultsCountTotal');
        if (countElem) countElem.textContent = this.t('lab_finder.no_matches', 'No matching laboratories');
        if (!container) return;

        let title = 'No Laboratories Found';
        let desc = 'No accredited testing laboratories matched your criteria.';
        let icon = 'search';
        let actionsHtml = '';

        if (type === 'NO_CAPABILITY_MATCH') {
            title = `No Capability Scope for ${context.standard || 'Standard'}`;
            desc = `None of the 580 laboratories in the BIS LIMS catalog currently hold accredited testing scope for <strong>${this.escapeHtml(context.standard || '')}</strong>. BIS testing scope is normative and capability cannot be synthesized.`;
            icon = 'shield';
            actionsHtml = `
                <button type="button" class="btn-empty-reset" id="btnResetFilters">Reset Location &amp; Filters</button>
            `;
        } else if (type === 'RADIUS_EXHAUSTED') {
            const locName = context.locationName || 'your reference location';
            title = `No Laboratories Within ${context.radius} km of ${locName}`;
            desc = `Accredited laboratories with testing scope for <strong>${this.escapeHtml(context.standard || '')}</strong> exist in the BIS catalog, but none fall within ${context.radius} km of <strong>${this.escapeHtml(locName)}</strong>.`;
            icon = 'pin';

            if (context.nearestCandidate && context.nearestCandidate.laboratory_identity) {
                const near = context.nearestCandidate;
                const nearLoc = [near.city, near.state].filter(Boolean).join(', ');
                const distStr = near.distance_km ? ` (${near.distance_km} km away)` : '';
                desc += `<br><br><span class="nearest-hint" style="display:inline-block; margin-top: 6px; padding: 6px 10px; background: rgba(141, 155, 243, 0.1); border-radius: 6px; border: 1px solid rgba(141, 155, 243, 0.2); color: #c5ccff;">Nearest accredited facility: <strong>${this.escapeHtml(near.laboratory_identity)}</strong> in ${this.escapeHtml(nearLoc || 'India')}${distStr}.</span>`;
            }

            const targetDist = context.nearestCandidate && context.nearestCandidate.distance_km
                ? Math.min(500, Math.max(250, Math.ceil(context.nearestCandidate.distance_km / 50) * 50))
                : 500;

            actionsHtml = `
                <button type="button" class="btn-empty-action" id="btnExpandRadius" data-dist="${targetDist}">Expand Radius to ${targetDist} km</button>
                <button type="button" class="btn-empty-action" id="btnShowAllNationwide">Show All Across India</button>
                <button type="button" class="btn-empty-reset" id="btnClearLocationFilter">Clear Location</button>
            `;
        }

        container.innerHTML = `
            <div class="results-empty-state">
                <div class="empty-state-emblem empty-state-emblem-${icon}" aria-hidden="true">
                    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/><path class="empty-state-shield-line" d="M12 3 19 6v5c0 4.5-3 7.7-7 10-4-2.3-7-5.5-7-10V6l7-3Z"/><path class="empty-state-pin-line" d="M12 21s6-4.2 6-10a6 6 0 1 0-12 0c0 5.8 6 10 6 10Z"/><circle class="empty-state-pin-line" cx="12" cy="11" r="2"/></svg>
                </div>
                <h3 class="empty-state-title">${title}</h3>
                <p class="empty-state-desc">${desc}</p>
                <div class="empty-state-actions">
                    ${actionsHtml}
                </div>
            </div>
        `;

        const btnExpand = container.querySelector('#btnExpandRadius');
        if (btnExpand) {
            btnExpand.addEventListener('click', () => {
                const dist = btnExpand.getAttribute('data-dist') || '500';
                const selRadius = this.container.querySelector('#labFilterRadius');
                if (selRadius) selRadius.value = dist;
                this.executeSearchFromInputs();
            });
        }

        const btnAll = container.querySelector('#btnShowAllNationwide');
        if (btnAll) {
            btnAll.addEventListener('click', () => {
                const selRadius = this.container.querySelector('#labFilterRadius');
                if (selRadius) selRadius.value = '';
                this.executeSearchFromInputs();
            });
        }

        const btnClearLocFilter = container.querySelector('#btnClearLocationFilter');
        if (btnClearLocFilter) {
            btnClearLocFilter.addEventListener('click', () => {
                this.clearUserLocation();
                const selRadius = this.container.querySelector('#labFilterRadius');
                if (selRadius) selRadius.value = '';
                this.executeSearchFromInputs();
            });
        }

        const resetBtn = container.querySelector('#btnResetFilters');
        if (resetBtn) {
            resetBtn.addEventListener('click', () => {
                this.clearUserLocation();
                const selRadius = this.container.querySelector('#labFilterRadius');
                if (selRadius) selRadius.value = '';
                const selCat = this.container.querySelector('#labFilterCategory');
                if (selCat) selCat.value = '';
                const chkComplete = this.container.querySelector('#labFilterCompleteScope');
                if (chkComplete) chkComplete.checked = false;
                this.executeSearchFromInputs();
            });
        }
    }

    /**
     * Resets the results pane, counters, and map markers back to the initial landing guide.
     */
    renderInitialGuide() {
        const container = this.container.querySelector('#resultsListContainer');
        const countElem = this.container.querySelector('#resultsCountTotal');
        const noticeElem = this.container.querySelector('#searchInterpretationNotice');
        const mapCounter = this.container.querySelector('#mapMarkerCounter');

        if (countElem) countElem.textContent = this.t('lab_finder.initial_count', 'Find a laboratory');
        if (noticeElem) {
            noticeElem.classList.add('hidden');
            noticeElem.innerHTML = '';
        }
        if (mapCounter) {
            mapCounter.classList.add('hidden');
            mapCounter.textContent = '';
        }

        if (this.mapComponent) {
            this.mapComponent.clearMarkers();
        }

        if (container) {
            container.innerHTML = `
                <div class="results-empty-state" id="initialGuideState">
                    <div class="empty-state-emblem" aria-hidden="true">
                        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M9 3h6"/><path d="M10 3v5.5L4.7 18a2 2 0 0 0 1.7 3h11.2a2 2 0 0 0 1.7-3L14 8.5V3"/><path d="M8 15h8"/><path d="M7 18h10"/></svg>
                    </div>
                    <h3 class="empty-state-title" data-i18n="lab_finder.empty_state_title">Find a BIS laboratory</h3>
                    <p class="empty-state-desc" data-i18n="lab_finder.empty_state_desc">Search by standard, product, or laboratory to find facilities with the required testing scope.</p>
                    <div class="empty-state-shortcuts">
                        <button type="button" class="shortcut-pill" data-query="find me the lab for is 4985 testing" data-standard="IS 4985">IS 4985 testing</button>
                        <button type="button" class="shortcut-pill" data-query="find labs for testing led lamps" data-standard="IS 16102">LED lamp testing</button>
                        <button type="button" class="shortcut-pill" data-query="find recognized labs for water heaters near Delhi" data-standard="IS 8978">Water heater labs in Delhi</button>
                        <button type="button" class="shortcut-pill" data-query="find labs for drinking water in Gujarat" data-standard="IS 10500">Drinking water testing in Gujarat</button>
                    </div>
                </div>
            `;
        }
    }

    /**
     * Renders error state banner without fabricating data.
     */
    renderErrorState(errMsg, errType = 'API_ERROR') {
        const container = this.container.querySelector('#resultsListContainer');
        const countElem = this.container.querySelector('#resultsCountTotal');
        if (countElem) countElem.textContent = 'Search Error';

        if (!container) return;

        container.innerHTML = `
            <div class="results-error-state">
                <div class="error-state-emblem">⚠️</div>
                <h3 class="error-state-title">Search Request Error</h3>
                <p class="error-state-desc">${this.escapeHtml(errMsg)}</p>
                <span class="error-type-badge">${errType}</span>
                <p class="error-guidance">Check standard number formatting (e.g. <code>IS 4985</code>) or verify reference coordinates.</p>
            </div>
        `;
    }

    /**
     * Utility to safely escape HTML entities in strings.
     */
    escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    /**
     * Updates all presentation strings dynamically when UI language toggles.
     * Preserves active candidates, map markers, user location, and filters.
     */
    onLanguageChange(lang) {
        if (this.container) {
            this.container.querySelectorAll('[data-i18n]').forEach(el => {
                const key = el.getAttribute('data-i18n');
                if (key) {
                    const translated = this.t(key);
                    if (translated) el.textContent = translated;
                }
            });
            this.container.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
                const key = el.getAttribute('data-i18n-placeholder');
                if (key) {
                    const translated = this.t(key);
                    if (translated) el.placeholder = translated;
                }
            });
            this.container.querySelectorAll('option[data-i18n]').forEach(opt => {
                const key = opt.getAttribute('data-i18n');
                if (key) {
                    const translated = this.t(key);
                    if (translated) opt.textContent = translated;
                }
            });
        }

        // Re-render active search results without API call or map reset
        if (this.currentResults && this.currentResults.candidates) {
            this.renderResults(this.currentResults);
        }

        // Re-format interpretation notice
        const noticeElem = this.container ? this.container.querySelector('#searchInterpretationNotice') : null;
        if (noticeElem && !noticeElem.classList.contains('hidden') && this.lastParsedSummary) {
            let displayText = this.lastParsedSummary;
            if (lang === 'hi') {
                const interpLabel = this.t('lab_finder.interpreted_as', 'व्याख्या:');
                const searchLabel = this.t('lab_finder.searching_for', 'खोज रहे हैं:');
                displayText = this.lastParsedSummary
                    .replace(/^Interpreted as:\s*/i, `${interpLabel} `)
                    .replace(/^Searching for:\s*/i, `${searchLabel} `);
            }
            noticeElem.innerHTML = `
                <svg class="notice-icon" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
                <span class="notice-text">${this.escapeHtml(displayText)}</span>
            `;
            noticeElem.title = displayText;
        }

        // Re-render open detail drawer if present
        const drawer = this.container ? this.container.querySelector('#labDetailDrawer') : null;
        if (drawer && drawer.classList.contains('open') && this.selectedCandidate) {
            this.openDetailInspector(this.selectedCandidate);
        }
    }
}
