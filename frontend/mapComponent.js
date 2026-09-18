/**
 * Phase F3: STEP 2B - BIS Laboratory Finder Reusable Map Component.
 *
 * Isolated, modular Leaflet + OpenStreetMap component designed for the future
 * BIS Laboratory Finder.
 *
 * Architectural Invariants:
 * 1. Independent: Decoupled from laboratory matching, ranking, and search algorithms.
 * 2. Privacy: Only standard /{z}/{x}/{y}.png tile requests are sent to tile servers.
 *    Laboratory names, addresses, search terms, and user PII are NEVER transmitted to tile servers.
 * 3. Configurable: Tile provider defaults to HTTPS OpenStreetMap with visible attribution,
 *    and can be swapped for other providers (e.g. Geoapify, CartoDB) without rewriting the component.
 * 4. Resilient: Respects browser caching policies and handles dynamic container resizing.
 */

// Default OpenStreetMap Tile Configuration (HTTPS + Mandated Visible Attribution)
export const DEFAULT_TILE_PROVIDER = {
    name: "OpenStreetMap",
    urlTemplate: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    options: {
        maxZoom: 19,
        minZoom: 3,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors'
    }
};

// Default geographic centroid (India)
export const DEFAULT_INDIA_CENTER = [20.5937, 78.9629];
export const DEFAULT_INITIAL_ZOOM = 5;

/**
 * Creates custom styled HTML pin marker for Leaflet
 */
export function createPinIcon(category = "DEFAULT") {
    if (typeof window.L === "undefined") return null;

    let color = "#8678F9"; // Default brand purple
    let border = "#6C63FF";
    let glyph = "•";

    switch (category) {
        case "BIS_OWNED":
            color = "#3B82F6"; // Blue
            border = "#2563EB";
            glyph = "B";
            break;
        case "BIS_RECOGNIZED":
            color = "#10B981"; // Emerald
            border = "#059669";
            glyph = "R";
            break;
        case "BIS_EMPANELLED":
            color = "#F59E0B"; // Amber
            border = "#D97706";
            glyph = "E";
            break;
    }

    return window.L.divIcon({
        className: `bis-map-pin bis-pin-${category.toLowerCase()}`,
        html: `<div class="pin-marker" style="background-color: ${color}; border-color: ${border};"><span>${glyph}</span></div>`,
        iconSize: [28, 28],
        iconAnchor: [14, 28],
        popupAnchor: [0, -28]
    });
}

/**
 * Creates custom styled HTML anchor beacon marker for Leaflet
 */
export function createAnchorIcon(label = "City Center") {
    if (typeof window.L === "undefined") return null;

    return window.L.divIcon({
        className: "bis-map-anchor-marker",
        html: `
            <div class="anchor-pin-beacon">
                <div class="anchor-pulse-halo"></div>
                <div class="anchor-pin-badge">
                    <span class="anchor-pin-icon">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                            <circle cx="12" cy="12" r="3"></circle>
                            <path d="M12 2v3m0 14v3M2 12h3m14 0h3"></path>
                        </svg>
                    </span>
                    <span class="anchor-pin-text">${label}</span>
                </div>
            </div>
        `,
        iconSize: [160, 36],
        iconAnchor: [80, 18],
        popupAnchor: [0, -20]
    });
}

export class BisMapComponent {
    /**
     * @param {HTMLElement|string} container - DOM element or ID
     * @param {Object} options - Configuration options
     * @param {Array<number>} [options.center] - Initial [latitude, longitude]
     * @param {number} [options.zoom] - Initial zoom level
     * @param {Object} [options.tileProvider] - Tile URL template and options
     */
    constructor(container, options = {}) {
        this.container = typeof container === "string" ? document.getElementById(container) : container;
        if (!this.container) {
            throw new Error(`BisMapComponent: Target container "${container}" not found in DOM.`);
        }

        this.center = options.center || DEFAULT_INDIA_CENTER;
        this.zoom = typeof options.zoom === "number" ? options.zoom : DEFAULT_INITIAL_ZOOM;
        this.tileProvider = options.tileProvider || DEFAULT_TILE_PROVIDER;

        this.map = null;
        this.tileLayer = null;
        this.markerLayerGroup = null;
        this.anchorLayerGroup = null;
        this.anchorData = null;
        this.anchorMarker = null;
        this.anchorCircle = null;
        this.markers = new Map();
        this._isInitialized = false;
    }

    /**
     * Initialize Leaflet map instance inside target container.
     */
    init() {
        if (this._isInitialized) return this;

        if (typeof window.L === "undefined") {
            console.error("BisMapComponent: Leaflet (L) is not loaded on window. Ensure leaflet.js is imported.");
            return this;
        }

        // Configure default image path for Leaflet marker assets
        if (window.L.Icon && window.L.Icon.Default) {
            window.L.Icon.Default.imagePath = "./vendor/leaflet/images/";
        }

        // Initialize Map
        this.map = window.L.map(this.container, {
            center: this.center,
            zoom: this.zoom,
            attributionControl: true,
            zoomControl: true,
            scrollWheelZoom: true
        });

        // Initialize Tile Layer (HTTPS + Attribution)
        this.tileLayer = window.L.tileLayer(this.tileProvider.urlTemplate, this.tileProvider.options);
        this.tileLayer.addTo(this.map);

        // Initialize Layer Group for Markers
        this.markerLayerGroup = window.L.layerGroup().addTo(this.map);
        // Initialize Layer Group for Anchor Reference
        this.anchorLayerGroup = window.L.layerGroup().addTo(this.map);

        this._isInitialized = true;
        return this;
    }

    /**
     * Re-center and adjust zoom on supplied coordinates.
     */
    setView(lat, lng, zoom = null) {
        if (!this.map) return this;
        const targetZoom = typeof zoom === "number" ? zoom : this.map.getZoom();
        this.map.setView([lat, lng], targetZoom);
        return this;
    }

    /**
     * Set or update reference proximity anchor (city center / GPS) and optional radius circle on the map.
     * @param {number} lat - Latitude
     * @param {number} lng - Longitude
     * @param {string} [label="City Center"] - Anchor display label
     * @param {number|null} [radiusKm=null] - Maximum radius in km
     */
    setAnchor(lat, lng, label = "City Center", radiusKm = null) {
        this.clearAnchor();

        if (typeof lat !== "number" || typeof lng !== "number" || isNaN(lat) || isNaN(lng)) {
            return this;
        }

        this.anchorData = { lat, lng, label, radiusKm };

        if (!this.map || !this.anchorLayerGroup) return this;

        // 1. Draw radius boundary circle if radius is active
        if (typeof radiusKm === "number" && radiusKm > 0 && typeof window.L.circle === "function") {
            try {
                this.anchorCircle = window.L.circle([lat, lng], {
                    radius: radiusKm * 1000,
                    color: '#8B5CF6',
                    weight: 1.5,
                    dashArray: '5, 5',
                    fillColor: '#8B5CF6',
                    fillOpacity: 0.05,
                    interactive: false
                });
                this.anchorCircle.addTo(this.anchorLayerGroup);
            } catch (e) {
                console.warn("BisMapComponent: Failed to render anchor radius circle", e);
            }
        }

        // 2. Add Anchor Marker with custom pulsing beacon and badge
        const icon = createAnchorIcon(label);
        const markerOptions = {
            zIndexOffset: 2000,
            title: `Proximity Anchor: ${label}`
        };
        if (icon) markerOptions.icon = icon;

        const marker = window.L.marker([lat, lng], markerOptions);

        const radiusStr = (typeof radiusKm === "number" && radiusKm > 0)
            ? `<div class="bis-popup-footer"><span class="popup-scope-tag">Radius Filter: ≤ ${radiusKm} km</span></div>`
            : '';

        const popupHtml = `
            <div class="bis-popup-card bis-anchor-popup">
                <div class="bis-popup-header">
                    <span class="bis-popup-badge anchor">Reference Anchor</span>
                    <span class="bis-popup-coords">${lat.toFixed(4)}° N, ${lng.toFixed(4)}° E</span>
                </div>
                <h4 class="bis-popup-title">📍 ${label}</h4>
                <p class="bis-popup-address">Center origin point for all laboratory distance measurements and proximity ranking.</p>
                ${radiusStr}
            </div>
        `;

        if (typeof marker.bindPopup === "function") {
            marker.bindPopup(popupHtml, {
                className: "bis-map-popup",
                maxWidth: 320
            });
        }

        marker.addTo(this.anchorLayerGroup);
        this.anchorMarker = marker;

        return this;
    }

    /**
     * Remove the reference proximity anchor and radius circle from the map.
     */
    clearAnchor() {
        if (this.anchorLayerGroup) {
            this.anchorLayerGroup.clearLayers();
        }
        this.anchorMarker = null;
        this.anchorCircle = null;
        this.anchorData = null;
        return this;
    }

    /**
     * Add a single marker to the map.
     * @param {Object} markerData
     * @param {number} markerData.lat - Latitude
     * @param {number} markerData.lng - Longitude
     * @param {string} [markerData.id] - Unique identifier
     * @param {string} [markerData.title] - Hover title
     * @param {string} [markerData.popupContent] - HTML content for popup
     * @param {string} [markerData.category] - "BIS_OWNED" | "BIS_RECOGNIZED" | "BIS_EMPANELLED"
     * @param {boolean} [markerData.autoOpen] - Whether to open popup immediately
     */
    addMarker(markerData) {
        if (!this.map || !this.markerLayerGroup) return null;
        const { lat, lng, id, title, popupContent, category = "DEFAULT", autoOpen = false } = markerData;

        if (typeof lat !== "number" || typeof lng !== "number" || isNaN(lat) || isNaN(lng)) {
            console.warn("BisMapComponent: Invalid coordinates for marker", markerData);
            return null;
        }

        const icon = createPinIcon(category);
        const markerOptions = { title: title || "" };
        if (icon) markerOptions.icon = icon;

        const marker = window.L.marker([lat, lng], markerOptions);

        if (popupContent) {
            marker.bindPopup(popupContent, {
                className: "bis-map-popup",
                maxWidth: 320
            });
        }

        marker.addTo(this.markerLayerGroup);

        const markerId = id || `marker_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
        this.markers.set(markerId, marker);

        if (autoOpen && popupContent) {
            marker.openPopup();
        }

        return marker;
    }

    /**
     * Set multiple markers and optionally auto-fit bounds.
     * @param {Array<Object>} markersList - List of marker configurations
     * @param {boolean} [autoFitBounds=true] - Automatically zoom/pan to encapsulate all markers
     */
    setMarkers(markersList = [], autoFitBounds = true) {
        this.clearMarkers();

        const bounds = [];
        // If an anchor is set, include anchor in the viewport bounds
        if (this.anchorData) {
            bounds.push([this.anchorData.lat, this.anchorData.lng]);
        }

        if (Array.isArray(markersList)) {
            for (const item of markersList) {
                const marker = this.addMarker(item);
                if (marker && typeof item.lat === "number" && typeof item.lng === "number") {
                    bounds.push([item.lat, item.lng]);
                }
            }
        }

        if (autoFitBounds && bounds.length > 0 && this.map) {
            if (bounds.length === 1) {
                this.setView(bounds[0][0], bounds[0][1], 11);
            } else {
                this.map.fitBounds(bounds, { padding: [50, 50], maxZoom: 13 });
            }
        } else if (markersList.length === 0 && this.anchorData && this.map) {
            this.setView(this.anchorData.lat, this.anchorData.lng, 10);
        }

        return this;
    }

    /**
     * Remove all markers from the map.
     */
    clearMarkers() {
        if (this.markerLayerGroup) {
            this.markerLayerGroup.clearLayers();
        }
        this.markers.clear();
        return this;
    }

    /**
     * Return count of active markers.
     */
    getMarkersCount() {
        return this.markers.size;
    }

    /**
     * Invalidate container size to ensure correct tile rendering after DOM visibility or resize changes.
     */
    invalidateSize() {
        if (this.map) {
            this.map.invalidateSize();
        }
        return this;
    }

    /**
     * Returns attribution HTML text for verification.
     */
    getAttributionText() {
        if (this.tileProvider && this.tileProvider.options) {
            return this.tileProvider.options.attribution || "";
        }
        return "";
    }

    /**
     * Cleanly destroy Leaflet instance and event listeners.
     */
    destroy() {
        if (this.map) {
            this.clearMarkers();
            this.clearAnchor();
            this.map.remove();
            this.map = null;
            this.tileLayer = null;
            this.markerLayerGroup = null;
            this.anchorLayerGroup = null;
            this._isInitialized = false;
        }
    }
}

export function createBisMap(container, options = {}) {
    const instance = new BisMapComponent(container, options);
    return instance.init();
}
