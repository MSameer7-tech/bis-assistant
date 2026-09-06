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

        if (!Array.isArray(markersList) || markersList.length === 0) {
            return this;
        }

        const bounds = [];
        for (const item of markersList) {
            const marker = this.addMarker(item);
            if (marker && typeof item.lat === "number" && typeof item.lng === "number") {
                bounds.push([item.lat, item.lng]);
            }
        }

        if (autoFitBounds && bounds.length > 0 && this.map) {
            if (bounds.length === 1) {
                this.setView(bounds[0][0], bounds[0][1], 12);
            } else {
                this.map.fitBounds(bounds, { padding: [40, 40], maxZoom: 14 });
            }
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
            this.map.remove();
            this.map = null;
            this.tileLayer = null;
            this.markerLayerGroup = null;
            this._isInitialized = false;
        }
    }
}

export function createBisMap(container, options = {}) {
    const instance = new BisMapComponent(container, options);
    return instance.init();
}
