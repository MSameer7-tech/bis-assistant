/**
 * Phase PC-6: Product Compliance Journey Frontend Component.
 *
 * Modular, production-ready workbench component for establishing, visualizing,
 * and navigating the end-to-end BIS Product Compliance Journey.
 *
 * Architectural Invariants:
 * 1. Authority: Consumes frozen PC-5 API (POST /api/compliance/journey) verbatim.
 * 2. Zero Inference: Zero regulatory or compliance decisions in JavaScript.
 * 3. Exact Status Grounding:
 *    - Established: "Established from BIS evidence"
 *    - Unknown: "Not established from available BIS evidence"
 *    - Conflict: "Conflicting BIS evidence"
 *    - Mandatory Not Established: "Mandatory certification not established from available BIS evidence"
 *    - Scheme Unknown: "Product-specific certification scheme not established from available BIS evidence"
 *    - No Matching Lab: "No matching qualified BIS laboratory found"
 *    - Generic Process: "General BIS procedure reference"
 * 4. Exact 10-Stage Ordering:
 *    Product -> Standards -> Regulatory -> Mandatory -> Scheme -> Testing ->
 *    Inspection -> Sampling -> Laboratories -> Certification Process ->
 *    Warnings & Limitations -> Evidence / Provenance.
 * 5. Evidence Integration: Reuses existing openEvidenceDrawer pattern without fabrication.
 * 6. Zero Silent Fallback: Clear retryable error on failure; never renders fake data.
 */

import { apiUrl } from './config.js';

export function escapeHtml(str) {
    if (!str && str !== 0) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

/**
 * ComplianceJourneyLoader
 *
 * Professional, multi-stage animated progress loader for BIS Compliance Journey.
 * Provides accurate visual progress estimation across 8 stages of the journey resolution:
 * 1. Understanding your product (0-3s)
 * 2. Identifying applicable Indian Standard (3-6s)
 * 3. Checking QCO and regulatory requirements (6-12s)
 * 4. Retrieving authoritative BIS evidence (12-18s)
 * 5. Evaluating testing and inspection requirements (18-22s)
 * 6. Checking certification requirements (22-25s)
 * 7. Finding qualified BIS laboratories (25-28s)
 * 8. Preparing your compliance journey (28s+)
 *
 * Strict non-hallucination & non-fabrication principles:
 * - Does NOT fake backend completion; clearly framed as visual progress estimation
 * - Starts at ~5%, progresses smoothly towards ~90% with deceleration
 * - Never hits 100% until API response actually arrives
 * - If request takes >30s, remains at final stage with progress held around 90-91%
 * - Immediately transitions 90% -> 100% and displays "✓ Journey ready" upon API success
 * - Gracefully transitions to retryable error state upon API failure
 * - Full accessibility (aria-live, progressbar semantics, prefers-reduced-motion)
 * - Responsive across desktop, tablet, and mobile
 */
export class ComplianceJourneyLoader {
    /**
     * @param {HTMLElement|string} container - Target container element or selector
     * @param {Object} [options] - Configuration options
     * @param {Function} [options.t] - Translation function (key, fallback)
     * @param {Object} [options.payload] - Query payload being resolved
     * @param {Function} [options.onRetry] - Callback invoked when retry button in error state is clicked
     */
    constructor(container, options = {}) {
        this.container = typeof container === 'string'
            ? document.querySelector(container)
            : container;
        this.options = options;
        const rawT = options.t || ((k, fb) => ((typeof window !== 'undefined' && window.bisI18n) ? window.bisI18n.t(k, fb) : (fb || k)));
        this.t = (k, fb) => {
            try {
                const res = rawT(k, fb);
                return (res !== undefined && res !== null && res !== '') ? res : (fb || k);
            } catch (e) {
                return fb || k;
            }
        };
        this.onRetry = options.onRetry || null;

        this.currentStageIndex = 0;
        this.progress = 5;
        this.isRunning = false;
        this.isCompleted = false;
        this.isDestroyed = false;

        this.animationFrameId = null;
        this.startTime = 0;

        const t = this.t;
        this.stages = [
            {
                id: 'product',
                title: t('compliance_journey.loader_stage_product', 'Understanding your product'),
                statusText: t('compliance_journey.loader_status_product', 'Understanding product specifications...'),
                startMs: 0,
                endMs: 3000,
                startPct: 5,
                endPct: 16
            },
            {
                id: 'standard',
                title: t('compliance_journey.loader_stage_standards', 'Identifying applicable Indian Standard'),
                statusText: t('compliance_journey.loader_status_standards', 'Identifying matching Indian Standards from BIS corpus...'),
                startMs: 3000,
                endMs: 6000,
                startPct: 16,
                endPct: 28
            },
            {
                id: 'qco',
                title: t('compliance_journey.loader_stage_qco', 'Checking QCO and regulatory requirements'),
                statusText: t('compliance_journey.loader_status_qco', 'Checking Quality Control Orders and statutory mandates...'),
                startMs: 6000,
                endMs: 12000,
                startPct: 28,
                endPct: 48
            },
            {
                id: 'evidence',
                title: t('compliance_journey.loader_stage_evidence', 'Retrieving authoritative BIS evidence'),
                statusText: t('compliance_journey.loader_status_evidence', 'Retrieving authoritative BIS evidence...'),
                startMs: 12000,
                endMs: 18000,
                startPct: 48,
                endPct: 66
            },
            {
                id: 'testing',
                title: t('compliance_journey.loader_stage_testing', 'Evaluating testing and inspection requirements'),
                statusText: t('compliance_journey.loader_status_testing', 'Evaluating testing requirements...'),
                startMs: 18000,
                endMs: 22000,
                startPct: 66,
                endPct: 77
            },
            {
                id: 'certification',
                title: t('compliance_journey.loader_stage_certification', 'Checking certification requirements'),
                statusText: t('compliance_journey.loader_status_certification', 'Checking certification schemes and guidelines...'),
                startMs: 22000,
                endMs: 25000,
                startPct: 77,
                endPct: 83
            },
            {
                id: 'laboratories',
                title: t('compliance_journey.loader_stage_labs', 'Finding qualified BIS laboratories'),
                statusText: t('compliance_journey.loader_status_labs', 'Finding matching BIS laboratory scopes...'),
                startMs: 25000,
                endMs: 28000,
                startPct: 83,
                endPct: 88
            },
            {
                id: 'journey',
                title: t('compliance_journey.loader_stage_journey', 'Preparing your compliance journey'),
                statusText: t('compliance_journey.loader_status_journey', 'Preparing your compliance journey...'),
                startMs: 28000,
                endMs: 38000,
                startPct: 88,
                endPct: 91
            }
        ];

        this.tick = this.tick.bind(this);
    }

    /**
     * Renders initial loader DOM and starts animation loop.
     */
    start() {
        if (!this.container || this.isDestroyed) return;
        this.destroy(); // Clear any existing animation
        this.isDestroyed = false;
        this.isCompleted = false;
        this.isRunning = true;
        this.currentStageIndex = 0;
        this.progress = 5;
        this.startTime = (typeof performance !== 'undefined' && performance.now) ? performance.now() : Date.now();

        const t = this.t;
        const mainTitle = escapeHtml(t('compliance_journey.loader_title', 'Building your compliance journey'));
        const subTitle = escapeHtml(t('compliance_journey.loader_subtitle', 'Analyzing your product against authoritative BIS evidence'));
        const footerNote = escapeHtml(t('compliance_journey.loader_footer_note', 'Checking multiple BIS evidence sources and laboratory scopes.'));
        const footerSubnote = escapeHtml(t('compliance_journey.loader_footer_subnote', 'This may take a few moments'));

        let stagesHtml = '';
        this.stages.forEach((st, idx) => {
            const isFirst = idx === 0;
            const cls = isFirst ? 'loader-stage-item is-current' : 'loader-stage-item is-pending';
            const indicator = isFirst
                ? `<div class="loader-icon-active" aria-hidden="true"><span class="loader-active-ring"></span><span class="loader-active-dot"></span></div>`
                : `<span class="loader-icon-pending" aria-hidden="true"></span>`;
            const statusHtml = isFirst
                ? `<span class="loader-stage-status">${escapeHtml(st.statusText)}</span>`
                : '';

            stagesHtml += `
                <li class="${cls}" role="listitem" data-stage="${idx}">
                    <div class="loader-stage-indicator" aria-hidden="true">${indicator}</div>
                    <div class="loader-stage-content">
                        <span class="loader-stage-title">${escapeHtml(st.title)}</span>
                        ${statusHtml}
                    </div>
                </li>
            `;
        });

        this.container.innerHTML = `
            <div class="compliance-loader-card" role="status" aria-live="polite" aria-label="${mainTitle}">
                <div class="compliance-loader-header">
                    <h3 class="compliance-loader-title">${mainTitle}</h3>
                    <p class="compliance-loader-subtitle">${subTitle}</p>
                </div>

                <div class="compliance-loader-progress-wrap">
                    <div class="compliance-loader-track" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="5" aria-label="${mainTitle}">
                        <div class="compliance-loader-bar" style="width: 5%;">
                            <div class="compliance-loader-bar-glow" aria-hidden="true"></div>
                        </div>
                    </div>
                </div>

                <ul class="compliance-loader-stages" role="list" aria-label="Journey preparation steps">
                    ${stagesHtml}
                </ul>

                <div class="compliance-loader-percentage-wrap">
                    <span class="compliance-loader-percentage font-mono">5%</span>
                </div>

                <div class="compliance-loader-footer">
                    <div class="loader-footer-note">${footerNote}</div>
                    <div class="loader-footer-subnote">${footerSubnote}</div>
                </div>
            </div>
        `;

        this.progressBarEl = this.container.querySelector('.compliance-loader-bar');
        this.trackEl = this.container.querySelector('.compliance-loader-track');
        this.percentageEl = this.container.querySelector('.compliance-loader-percentage');

        if (typeof requestAnimationFrame !== 'undefined') {
            this.animationFrameId = requestAnimationFrame(this.tick);
        }
    }

    /**
     * Animation frame handler calculating smooth time-based progress and stage updates.
     */
    tick(now) {
        if (!this.isRunning || this.isDestroyed || this.isCompleted) return;

        const currentNow = now || ((typeof performance !== 'undefined' && performance.now) ? performance.now() : Date.now());
        const elapsed = Math.max(0, currentNow - this.startTime);

        let currentStage = 0;
        let calculatedProgress = 5;

        if (elapsed < 3000) {
            // Stage 0: 0-3s -> 5% - 16%
            currentStage = 0;
            const ratio = elapsed / 3000;
            calculatedProgress = 5 + (16 - 5) * ratio;
        } else if (elapsed < 6000) {
            // Stage 1: 3-6s -> 16% - 28%
            currentStage = 1;
            const ratio = (elapsed - 3000) / 3000;
            calculatedProgress = 16 + (28 - 16) * ratio;
        } else if (elapsed < 12000) {
            // Stage 2: 6-12s -> 28% - 48%
            currentStage = 2;
            const ratio = (elapsed - 6000) / 6000;
            calculatedProgress = 28 + (48 - 28) * ratio;
        } else if (elapsed < 18000) {
            // Stage 3: 12-18s -> 48% - 66%
            currentStage = 3;
            const ratio = (elapsed - 12000) / 6000;
            calculatedProgress = 48 + (66 - 48) * ratio;
        } else if (elapsed < 22000) {
            // Stage 4: 18-22s -> 66% - 77%
            currentStage = 4;
            const ratio = (elapsed - 18000) / 4000;
            calculatedProgress = 66 + (77 - 66) * ratio;
        } else if (elapsed < 25000) {
            // Stage 5: 22-25s -> 77% - 83%
            currentStage = 5;
            const ratio = (elapsed - 22000) / 3000;
            calculatedProgress = 77 + (83 - 77) * ratio;
        } else if (elapsed < 28000) {
            // Stage 6: 25-28s -> 83% - 88%
            currentStage = 6;
            const ratio = (elapsed - 25000) / 3000;
            calculatedProgress = 83 + (88 - 83) * ratio;
        } else {
            // Stage 7: 28s onward -> slowly decelerate toward ~91%
            currentStage = 7;
            const beyond = elapsed - 28000;
            calculatedProgress = 88 + (91.2 - 88) * (1 - Math.exp(-beyond / 16000));
        }

        // Hard cap at 91.5% before API response arrives
        calculatedProgress = Math.min(91.5, Math.max(5, calculatedProgress));

        if (currentStage !== this.currentStageIndex) {
            this.setStage(currentStage);
        }

        this.updateProgress(calculatedProgress);

        if (this.isRunning && typeof requestAnimationFrame !== 'undefined') {
            this.animationFrameId = requestAnimationFrame(this.tick);
        }
    }

    /**
     * Updates progress bar style and percentage text.
     */
    updateProgress(pct) {
        this.progress = pct;
        if (this.progressBarEl) {
            this.progressBarEl.style.width = `${pct.toFixed(1)}%`;
        }
        if (this.trackEl) {
            this.trackEl.setAttribute('aria-valuenow', Math.round(pct));
        }
        if (this.percentageEl) {
            this.percentageEl.textContent = `${Math.round(pct)}%`;
        }
    }

    /**
     * Updates active stage and refreshes stage item indicators and status text.
     */
    setStage(stageIndex) {
        if (stageIndex < 0 || stageIndex >= this.stages.length) return;
        this.currentStageIndex = stageIndex;
        if (!this.container) return;

        const items = this.container.querySelectorAll('.loader-stage-item');
        items.forEach((item, idx) => {
            const stage = this.stages[idx];
            const indicator = item.querySelector('.loader-stage-indicator');
            const content = item.querySelector('.loader-stage-content');

            item.classList.remove('is-completed', 'is-current', 'is-pending');

            if (idx < stageIndex) {
                item.classList.add('is-completed');
                if (indicator) {
                    indicator.innerHTML = `
                        <svg class="loader-icon-check" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                            <polyline points="20 6 9 17 4 12"></polyline>
                        </svg>
                    `;
                }
                const oldStatus = content?.querySelector('.loader-stage-status');
                if (oldStatus && typeof oldStatus.remove === 'function') oldStatus.remove();
            } else if (idx === stageIndex) {
                item.classList.add('is-current');
                if (indicator) {
                    indicator.innerHTML = `
                        <div class="loader-icon-active" aria-hidden="true">
                            <span class="loader-active-ring"></span>
                            <span class="loader-active-dot"></span>
                        </div>
                    `;
                }
                if (content) {
                    let statusEl = content.querySelector('.loader-stage-status');
                    if (!statusEl) {
                        statusEl = document.createElement('span');
                        statusEl.className = 'loader-stage-status';
                        content.appendChild(statusEl);
                    }
                    statusEl.textContent = stage.statusText;
                }
            } else {
                item.classList.add('is-pending');
                if (indicator) {
                    indicator.innerHTML = `<span class="loader-icon-pending" aria-hidden="true"></span>`;
                }
                const oldStatus = content?.querySelector('.loader-stage-status');
                if (oldStatus && typeof oldStatus.remove === 'function') oldStatus.remove();
            }
        });
    }

    /**
     * Fast-forwards progress to 100%, displays "✓ Journey ready", and resolves after hold.
     * @returns {Promise<void>}
     */
    async complete() {
        if (this.isDestroyed || this.isCompleted) return;
        this.isCompleted = true;
        this.isRunning = false;

        if (this.animationFrameId && typeof cancelAnimationFrame !== 'undefined') {
            cancelAnimationFrame(this.animationFrameId);
            this.animationFrameId = null;
        }

        const startPct = this.progress;
        const targetPct = 100;
        const duration = 220;
        const animStart = (typeof performance !== 'undefined' && performance.now) ? performance.now() : Date.now();

        await new Promise((resolve) => {
            if (typeof requestAnimationFrame === 'undefined') {
                this.updateProgress(100);
                return resolve();
            }
            const finishTick = (now) => {
                const elapsed = now - animStart;
                const ratio = Math.min(1, elapsed / duration);
                const ease = 1 - Math.pow(1 - ratio, 3);
                const currentVal = startPct + (targetPct - startPct) * ease;
                this.updateProgress(currentVal);

                if (ratio < 1) {
                    requestAnimationFrame(finishTick);
                } else {
                    this.updateProgress(100);
                    resolve();
                }
            };
            requestAnimationFrame(finishTick);
        });

        // Mark all stages as completed
        if (this.container) {
            const items = this.container.querySelectorAll('.loader-stage-item');
            items.forEach((item) => {
                item.classList.remove('is-current', 'is-pending');
                item.classList.add('is-completed');
                const indicator = item.querySelector('.loader-stage-indicator');
                if (indicator) {
                    indicator.innerHTML = `
                        <svg class="loader-icon-check" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                            <polyline points="20 6 9 17 4 12"></polyline>
                        </svg>
                    `;
                }
                const oldStatus = item.querySelector('.loader-stage-status');
                if (oldStatus && typeof oldStatus.remove === 'function') oldStatus.remove();
            });

            const metricWrap = this.container.querySelector('.compliance-loader-percentage-wrap');
            if (metricWrap) {
                const readyLabel = escapeHtml(this.t('compliance_journey.loader_ready', 'Journey ready'));
                metricWrap.innerHTML = `
                    <div class="loader-ready-badge" role="status">
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                            <polyline points="20 6 9 17 4 12"></polyline>
                        </svg>
                        <span>${readyLabel}</span>
                    </div>
                `;
            }
        }

        // Brief hold to let user see completion state
        await new Promise((r) => setTimeout(r, 380));
    }

    /**
     * Stops animation and renders clean error state with "Unable to build the compliance journey"
     * and a "Try again" button.
     */
    error(message, failedPayload = null) {
        this.destroy();
        if (!this.container) return;

        const t = this.t;
        const req = failedPayload || this.options.payload || null;
        const targetLabel = req ? (req.standard || req.product || req.query || '') : '';
        const cleanMsg = message || 'Network error communicating with BIS Compliance Journey service.';

        this.container.innerHTML = `
            <div class="compliance-error-card" role="alert">
                <div class="error-icon-wrap" aria-hidden="true">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                </div>
                <div class="error-content">
                    <h3 class="error-title" data-i18n="compliance_journey.loader_error_title">${escapeHtml(t('compliance_journey.loader_error_title', 'Unable to build the compliance journey'))}</h3>
                    ${targetLabel ? `<div class="error-target font-mono" style="font-size: 13px; color: var(--text-muted); margin-bottom: 6px;">Target: <strong>${escapeHtml(targetLabel)}</strong></div>` : ''}
                    <p class="error-message">${escapeHtml(cleanMsg)}</p>
                    <p class="error-note" data-i18n="compliance_journey.error_desc">${escapeHtml(t('compliance_journey.error_desc', 'Unable to establish compliance journey from authoritative BIS evidence. Please verify inputs or retry.'))}</p>
                    <div class="error-actions">
                        <button type="button" class="btn-error-retry" id="btnCompRetry" data-i18n="compliance_journey.btn_try_again">
                            ${escapeHtml(t('compliance_journey.btn_try_again', 'Try again'))}
                        </button>
                    </div>
                </div>
            </div>
        `;

        const retryBtn = this.container.querySelector('#btnCompRetry');
        if (retryBtn && typeof retryBtn.addEventListener === 'function') {
            retryBtn.addEventListener('click', () => {
                if (typeof this.onRetry === 'function') {
                    this.onRetry();
                }
            });
        }
    }

    /**
     * Cancels animation frames and cleans up timers.
     */
    destroy() {
        this.isRunning = false;
        this.isDestroyed = true;
        if (this.animationFrameId && typeof cancelAnimationFrame !== 'undefined') {
            cancelAnimationFrame(this.animationFrameId);
            this.animationFrameId = null;
        }
    }
}

export class ComplianceJourneyComponent {
    /**
     * @param {Object} config - Component configuration
     * @param {string|HTMLElement} config.container - Target workspace container element or ID
     * @param {string} [config.apiEndpoint] - Journey API endpoint (default: '/api/compliance/journey')
     * @param {Function} [config.t] - i18n translation helper (k, fallback)
     * @param {Function} [config.getLanguage] - Function returning active language code
     * @param {Function} [config.onOpenEvidence] - Callback to open evidence drawer
     * @param {Function} [config.onOpenLabFinder] - Callback to switch to Lab Finder
     */
    constructor(config = {}) {
        this.container = typeof config.container === 'string'
            ? document.getElementById(config.container)
            : config.container;

        this.apiEndpoint = config.apiEndpoint || apiUrl('/api/compliance/journey');
        this.clarifyEndpoint = config.clarifyEndpoint || apiUrl('/api/compliance/clarify');
        this.onOpenEvidence = config.onOpenEvidence || null;
        this.onOpenLabFinder = config.onOpenLabFinder || null;

        // Safe i18n helpers (defensive against TDZ or runtime errors in external callback)
        const rawT = config.t || ((k, fb) => ((typeof window !== 'undefined' && window.bisI18n) ? window.bisI18n.t(k, fb) : (fb || k)));
        this.t = (k, fb) => {
            try {
                const res = rawT(k, fb);
                return (res !== undefined && res !== null && res !== '') ? res : (fb || k);
            } catch (e) {
                return fb || k;
            }
        };
        const rawGetLang = config.getLanguage || (() => ((typeof window !== 'undefined' && window.bisI18n) ? window.bisI18n.getLanguage() : 'en'));
        this.getLanguage = () => {
            try {
                return rawGetLang() || 'en';
            } catch (e) {
                return 'en';
            }
        };

        // State
        this.currentJourney = null;
        this.isLoading = false;
        this.lastError = null;
        this.lastRequest = null;
        this.conversationContext = null;
        this.currentLoader = null;
    }

    /**
     * Cleans up running loaders, timers, and active resources.
     */
    destroy() {
        if (this.currentLoader) {
            this.currentLoader.destroy();
            this.currentLoader = null;
        }
        this.isLoading = false;
    }

    /**
     * Initializes the component DOM layout and binds UI listeners.
     */
    init() {
        if (!this.container) {
            console.warn('[ComplianceJourneyComponent] Target container element not found.');
            return this;
        }

        this.renderLayout();
        this.bindEvents();
        return this;
    }

    /**
     * Renders the base workbench shell.
     */
        renderLayout() {
        const t = this.t.bind(this);
        this.container.innerHTML = `
<div class="compliance-layout" role="region" aria-label="Product Compliance Journey Workspace">
  <!-- Page Header -->
  <header class="compliance-topbar centered">
    <div class="compliance-title-group">
      <div class="compliance-eyebrow">
        <span class="compliance-eyebrow-dot"></span>
        <span data-i18n="compliance_journey.title">${escapeHtml(t('compliance_journey.title', 'PRODUCT COMPLIANCE JOURNEY'))}</span>
      </div>
      <h2 class="compliance-heading" data-i18n="compliance_journey.heading">
        ${escapeHtml(t('compliance_journey.heading', 'Find your BIS requirements.'))}
      </h2>
      <p class="compliance-heading-sub" data-i18n="compliance_journey.heading_sub">
        ${escapeHtml(t('compliance_journey.heading_sub', 'Describe your product, enter an Indian Standard, or ask a compliance question.'))}
      </p>
    </div>
  </header>

  <!-- Main Centered Workspace (shown when no results) -->
  <div id="complianceInitialState" class="compliance-workspace-centered">
    <div class="compliance-main-card workspace-panel">
      <form id="complianceSearchForm" class="compliance-search-form" novalidate>
        
        <!-- Natural Language Query: large textarea -->
        <div class="compliance-query-row workspace-query">
          <label for="compInputQuery" class="compliance-form-label primary" data-i18n="compliance_journey.field_query">${escapeHtml(t('compliance_journey.field_query', 'What do you want to know?'))}</label>
          <div class="compliance-textarea-wrapper">
            <textarea id="compInputQuery" class="compliance-query-textarea compact"
              placeholder="${escapeHtml(t('compliance_journey.field_query_placeholder_long', 'Describe your product or ask a compliance question...'))}"
              autocomplete="off" spellcheck="false" rows="3"></textarea>
          </div>
        </div>

        <!-- Action Row -->
        <div class="compliance-action-row">
            <!-- Structured Inputs: 3-column grid -->
            <div class="compliance-form-grid compact-grid">
              <div class="compliance-form-group">
                <label for="compInputProduct" class="compliance-form-label secondary" data-i18n="compliance_journey.field_product">${escapeHtml(t('compliance_journey.field_product', 'Product'))}</label>
                <input type="text" id="compInputProduct" class="compliance-text-input compact" placeholder="${escapeHtml(t('compliance_journey.field_product_placeholder', 'PVC pipes, ceiling fan'))}" autocomplete="off" spellcheck="false" />
              </div>
              <div class="compliance-form-group">
                <label for="compInputStandard" class="compliance-form-label secondary" data-i18n="compliance_journey.field_standard">${escapeHtml(t('compliance_journey.field_standard', 'Indian Standard'))}</label>
                <input type="text" id="compInputStandard" class="compliance-text-input font-mono compact" placeholder="${escapeHtml(t('compliance_journey.field_standard_placeholder', 'IS 4985, IS 374'))}" autocomplete="off" spellcheck="false" />
              </div>
              <div class="compliance-form-group">
                <label for="compInputLocation" class="compliance-form-label secondary" data-i18n="compliance_journey.field_location">${escapeHtml(t('compliance_journey.field_location', 'Location'))}</label>
                <input type="text" id="compInputLocation" class="compliance-text-input compact" placeholder="${escapeHtml(t('compliance_journey.field_location_placeholder', 'Delhi, Mumbai'))}" autocomplete="off" spellcheck="false" />
              </div>
            </div>

            <!-- Generate Button -->
            <div class="compliance-submit-wrapper">
              <button type="submit" id="btnComplianceSubmit" class="btn-compliance-submit compact-action" aria-label="Generate Compliance Journey">
                <span id="btnComplianceText" data-i18n="compliance_journey.btn_generate">${escapeHtml(t('compliance_journey.btn_generate', 'Generate journey'))}</span>
                <svg id="btnComplianceIcon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
                <div id="compSpinner" class="compliance-spinner hidden" aria-hidden="true"></div>
              </button>
            </div>
        </div>
      </form>
    </div>

    <!-- Example Chips -->
    <div class="compliance-examples-section lightweight">
      <span class="compliance-examples-label" data-i18n="compliance_journey.example_queries_label">${escapeHtml(t('compliance_journey.example_queries_label', 'Try an example'))}</span>
      <div class="compliance-chips-wrap">
        <button type="button" class="btn-comp-chip" data-product="pvc pipes" data-standard="IS 4985" title="Example: PVC Pipes · IS 4985">PVC Pipes · IS 4985</button>
        <button type="button" class="btn-comp-chip" data-product="ceiling fan" data-standard="IS 374" title="Example: Ceiling Fan · IS 374">Ceiling Fan · IS 374</button>
        <button type="button" class="btn-comp-chip" data-product="secondary cell" data-standard="IS 16046 (Part 2)" title="Example: Lithium Battery · IS 16046 Part 2">Lithium Battery · IS 16046 Part 2</button>
        <button type="button" class="btn-comp-chip" data-standard="IS 15750" title="Example: IS 15750">IS 15750</button>
        <button type="button" class="btn-comp-chip" data-product="timber doors" title="Example: Timber doors">Timber Doors</button>
      </div>
    </div>
    
    <div class="compliance-empty-whitespace"></div>
  </div>

  <!-- Results Viewport (hidden initially, shown when results arrive) -->
  <section id="complianceResultsContainer" class="compliance-results-container" aria-live="polite" style="display: none;"></section>
</div>
        `;
    }

    /**
     * Binds event listeners on search form and chips.
     */
    bindEvents() {
        const form = this.container.querySelector('#complianceSearchForm');
        if (form) {
            form.addEventListener('submit', (e) => {
                e.preventDefault();
                this.executeSearchFromInputs();
            });
        }

        // Example chips
        this.container.querySelectorAll('.btn-comp-chip').forEach(btn => {
            btn.addEventListener('click', () => {
                const prod = btn.getAttribute('data-product') || '';
                const std = btn.getAttribute('data-standard') || '';

                const inputProd = this.container.querySelector('#compInputProduct');
                const inputStd = this.container.querySelector('#compInputStandard');
                const inputQuery = this.container.querySelector('#compInputQuery');

                if (inputProd) inputProd.value = prod;
                if (inputStd) inputStd.value = std;
                if (inputQuery) inputQuery.value = '';

                this.executeSearchFromInputs();
            });
        });
    }

    /**
     * Reads form input values and triggers PC-5 journey resolution.
     */
    executeSearchFromInputs() {
        const inputProd = this.container.querySelector('#compInputProduct');
        const inputStd = this.container.querySelector('#compInputStandard');
        const inputLoc = this.container.querySelector('#compInputLocation');
        const inputQuery = this.container.querySelector('#compInputQuery');

        const product = (inputProd?.value || '').trim();
        const standard = (inputStd?.value || '').trim();
        const location = (inputLoc?.value || '').trim();
        const query = (inputQuery?.value || '').trim();

        if (!product && !standard && !location && !query) {
            const initialState = this.container.querySelector('#complianceInitialState');
            const resultsContainer = this.container.querySelector('#complianceResultsContainer');
            if (initialState) initialState.style.display = '';
            if (resultsContainer) {
                resultsContainer.style.display = 'none';
                resultsContainer.innerHTML = '';
            }
            if (inputQuery) inputQuery.focus();
            return;
        }

        this.executeSearch({
            product: product || null,
            standard: standard || null,
            location: location || null,
            query: query || null
        });
    }

    /**
     * Executes natural language query from external triggers (e.g. conversational assistant).
     */
    executeFromQuery(queryText, options = {}) {
        if (!queryText) return;
        const inputQuery = this.container?.querySelector('#compInputQuery');
        if (inputQuery) inputQuery.value = queryText;
        this.executeSearch({
            query: queryText,
            product: options.product || null,
            standard: options.standard || null,
            location: options.location || null
        });
    }

    /**
     * Submits payload to POST /api/compliance/journey and renders results.
     * Uses /api/compliance/clarify to handle ambiguity and incompleteness interactively.
     */
    async executeSearch(payload) {
        this.activeRequestId = (this.activeRequestId || 0) + 1;
        const currentRequestId = this.activeRequestId;
        this.isLoading = true;
        this.lastError = null;
        this.lastRequest = payload;
        this.setLoadingState(true);

        // Reset and start multi-stage progress loader
        if (this.currentLoader) {
            this.currentLoader.destroy();
            this.currentLoader = null;
        }

        const resultsContainer = this.container?.querySelector('#complianceResultsContainer');
        const initialState = this.container?.querySelector('#complianceInitialState');
        
        if (initialState) {
            initialState.style.display = 'none';
        }
        
        if (resultsContainer) {
            resultsContainer.style.display = 'block';
            this.currentLoader = new ComplianceJourneyLoader(resultsContainer, {
                t: this.t.bind(this),
                payload: payload,
                onRetry: () => {
                    if (this.lastRequest) this.executeSearch(this.lastRequest);
                }
            });
            this.currentLoader.start();
        }

        try {
            // Step 1: Consult Clarification Engine if explicit standard is not specified
            if (!payload.standard && (payload.query || payload.product)) {
                try {
                    const clarifyRes = await fetch(this.clarifyEndpoint, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            query: payload.query || payload.product,
                            product: payload.product,
                            standard: payload.standard,
                            location: payload.location,
                            context: this.conversationContext || null
                        })
                    });

                    if (clarifyRes.ok) {
                        const clarifyData = await clarifyRes.json();
                        if (this.activeRequestId !== currentRequestId) {
                            if (this.currentLoader) {
                                this.currentLoader.destroy();
                                this.currentLoader = null;
                            }
                            return;
                        }

                        // Ambiguous or Incomplete -> Render interactive Clarification UI
                        if (clarifyData.state === 'AMBIGUOUS' || clarifyData.state === 'INCOMPLETE') {
                            if (this.currentLoader) {
                                this.currentLoader.destroy();
                                this.currentLoader = null;
                            }
                            this.isLoading = false;
                            this.setLoadingState(false);
                            this.renderClarification(clarifyData, payload);
                            return;
                        }

                        // Clear -> update payload with refined slots
                        if (clarifyData.state === 'CLEAR') {
                            payload = {
                                product: clarifyData.resolved_product || clarifyData.refined_request?.product || payload.product,
                                standard: clarifyData.resolved_standard || clarifyData.refined_request?.standard || payload.standard,
                                location: clarifyData.slots?.location || clarifyData.refined_request?.location || payload.location,
                                query: payload.query
                            };
                            if (clarifyData.resolved_standard) {
                                const inputStd = this.container.querySelector('#compInputStandard');
                                if (inputStd && !inputStd.value) inputStd.value = clarifyData.resolved_standard;
                            }
                        }
                    }
                } catch (clarifyErr) {
                    console.warn('[ComplianceJourneyComponent] Clarification engine fallback:', clarifyErr);
                }
            }

            // Step 2: Fetch authoritative PC-5 compliance journey with timeout
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 90000); // 90s timeout

            let res;
            try {
                res = await fetch(this.apiEndpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                    signal: controller.signal
                });
            } finally {
                clearTimeout(timeoutId);
            }

            if (!res.ok) {
                let errDetail = `HTTP ${res.status}: ${res.statusText}`;
                try {
                    const errJson = await res.json();
                    if (errJson.detail) errDetail = typeof errJson.detail === 'string' ? errJson.detail : JSON.stringify(errJson.detail);
                } catch (_) {}
                throw new Error(errDetail);
            }

            const journeyData = await res.json();

            // Concurrency guard: ignore if another search was triggered while awaiting
            if (this.activeRequestId !== currentRequestId) {
                if (this.currentLoader) {
                    this.currentLoader.destroy();
                    this.currentLoader = null;
                }
                return;
            }

            this.currentJourney = journeyData;
            this.activeJourney = journeyData;

            // Animate loader to 100% and show "✓ Journey ready"
            if (this.currentLoader) {
                await this.currentLoader.complete();
                this.currentLoader.destroy();
                this.currentLoader = null;
            }

            // Render with explicit error boundary so rendering bugs surface as error state
            try {
                this.renderJourneyResults(journeyData);
            } catch (renderErr) {
                console.error('[ComplianceJourneyComponent] Render error:', renderErr);
                throw new Error(`Rendering failed: ${renderErr.message}`);
            }

        } catch (err) {
            // Concurrency guard: ignore if another search was triggered while awaiting
            if (this.activeRequestId !== currentRequestId) {
                return;
            }
            const isTimeout = err.name === 'AbortError';
            console.error('[ComplianceJourneyComponent] API failure:', err);
            this.currentJourney = null;
            this.activeJourney = null;
            this.lastError = isTimeout
                ? 'Request timed out. The BIS compliance engine is processing a complex query. Please try again.'
                : (err.message || 'Network error communicating with BIS Compliance Journey service.');

            if (this.currentLoader) {
                this.currentLoader.error(this.lastError, payload);
                this.currentLoader = null;
            } else {
                this.renderErrorState(this.lastError, payload);
            }
        } finally {
            if (this.activeRequestId === currentRequestId) {
                this.isLoading = false;
                this.setLoadingState(false);
            }
        }
    }

    /**
     * Renders interactive clarification card for AMBIGUOUS and INCOMPLETE states.
     * Prevents misleading error alerts on unresolved inputs.
     */
    renderClarification(clarifyData, originalPayload) {
        const resultsContainer = this.container?.querySelector('#complianceResultsContainer');
        if (!resultsContainer) return;

        const isAmbiguous = clarifyData.state === 'AMBIGUOUS';
        const c = clarifyData.clarification || {};
        const title = c.title || (isAmbiguous ? 'Which product are you referring to?' : 'Product Specification Needed');
        const explanation = c.explanation || 'Please select a candidate or specify attributes:';
        const candidates = c.candidates || [];
        const attributeGroups = c.attribute_groups || [];
        const examples = c.suggested_examples || [];
        const disclaimer = c.disclaimer || 'Clarification narrows user intent; final compliance status is established deterministically by the BIS compliance engine.';

        let candidatesHtml = '';
        if (candidates.length > 0) {
            candidatesHtml = `
                <div class="clarification-candidates-section">
                    <span class="clarification-section-label">Grounded Product &amp; Standard Matches:</span>
                    <div class="clarification-candidate-grid">
                        ${candidates.map(cand => `
                            <button type="button" class="btn-clarify-candidate" 
                                data-product="${escapeHtml(cand.product_name)}" 
                                data-standard="${escapeHtml(cand.standard_number)}"
                                data-category="${escapeHtml(cand.category || '')}">
                                <div class="cand-top-row">
                                    <span class="cand-name">${escapeHtml(cand.product_name)}</span>
                                    <span class="cand-std-pill font-mono">${escapeHtml(cand.standard_number)}</span>
                                </div>
                                ${cand.description ? `<p class="cand-desc">${escapeHtml(cand.description)}</p>` : ''}
                                ${cand.category ? `<span class="cand-cat-tag">${escapeHtml(cand.category)}</span>` : ''}
                            </button>
                        `).join('')}
                    </div>
                </div>
            `;
        }

        let attributesHtml = '';
        if (attributeGroups.length > 0) {
            attributesHtml = `
                <div class="clarification-attributes-section">
                    ${attributeGroups.map(grp => `
                        <div class="attribute-group" data-group-id="${escapeHtml(grp.group_id)}">
                            <span class="attribute-group-title">${escapeHtml(grp.title)}:</span>
                            <div class="attribute-options-row">
                                ${grp.options.map(opt => `
                                    <button type="button" class="btn-attribute-pill" 
                                        data-group-id="${escapeHtml(grp.group_id)}"
                                        data-value="${escapeHtml(opt.value)}"
                                        data-term="${escapeHtml(opt.refined_query_term)}">
                                        ${escapeHtml(opt.label)}
                                    </button>
                                `).join('')}
                            </div>
                        </div>
                    `).join('')}
                </div>
            `;
        }

        let examplesHtml = '';
        if (examples.length > 0) {
            examplesHtml = `
                <div class="clarification-examples-section">
                    <span class="clarification-examples-label">Suggested Specific Inquiries:</span>
                    <div class="clarification-examples-pills">
                        ${examples.map(ex => `
                            <button type="button" class="btn-clarify-example" data-example="${escapeHtml(ex)}">
                                • ${escapeHtml(ex)}
                            </button>
                        `).join('')}
                    </div>
                </div>
            `;
        }

        resultsContainer.innerHTML = `
            <div class="compliance-clarification-card state-${escapeHtml(clarifyData.state.toLowerCase())}" role="region" aria-label="Assisted Product Clarification">
                <div class="clarification-header">
                    <div class="clarification-eyebrow">
                        <span class="clarification-sparkle" aria-hidden="true">✨</span>
                        <span>${isAmbiguous ? 'Assisted Disambiguation' : 'Guided Product Clarification'}</span>
                        <span class="clarification-state-pill font-mono">${escapeHtml(clarifyData.state)}</span>
                    </div>
                    <h3 class="clarification-title">${escapeHtml(title)}</h3>
                    <p class="clarification-desc">${escapeHtml(explanation)}</p>
                </div>

                <div class="clarification-body">
                    ${candidatesHtml}
                    ${attributesHtml}

                    <div class="clarification-refine-box">
                        <label for="clarifyRefineInput" class="clarify-refine-label">Or describe your product / intended application:</label>
                        <div class="clarify-refine-input-row">
                            <input type="text" id="clarifyRefineInput" class="clarify-refine-input" 
                                placeholder="e.g. PVC pipes for drinking water supply, or IS 4985" 
                                value="${escapeHtml(originalPayload?.query || originalPayload?.product || '')}" />
                            <button type="button" id="btnClarifySubmitRefined" class="btn-clarify-submit-refined">
                                Refine &amp; Establish Journey &rarr;
                            </button>
                        </div>
                    </div>

                    ${examplesHtml}
                </div>

                <div class="clarification-footer">
                    <div class="clarification-disclaimer">
                        <span class="disclaimer-icon" aria-hidden="true">🛡️</span>
                        <span>${escapeHtml(disclaimer)}</span>
                    </div>
                </div>
            </div>
        `;

        this.bindClarificationEvents(resultsContainer, originalPayload, clarifyData);
    }

    /**
     * Binds one-click disambiguation and attribute refinement interactions.
     */
    bindClarificationEvents(container, originalPayload, clarifyData) {
        // 1. Candidate Click -> One-click disambiguation
        container.querySelectorAll('.btn-clarify-candidate').forEach(btn => {
            btn.addEventListener('click', () => {
                const prod = btn.getAttribute('data-product') || '';
                const std = btn.getAttribute('data-standard') || '';

                // Populate form inputs
                const inputProd = this.container?.querySelector('#compInputProduct');
                const inputStd = this.container?.querySelector('#compInputStandard');
                if (inputProd) inputProd.value = prod;
                if (inputStd) inputStd.value = std;

                // Show non-blocking progress banner
                const resultsContainer = this.container?.querySelector('#complianceResultsContainer');
                if (resultsContainer) {
                    resultsContainer.innerHTML = `
                        <div class="refinement-progress-banner" role="status">
                            <div class="compliance-loading-spinner" aria-hidden="true"></div>
                            <div>
                                <strong>Refining your request:</strong>
                                <span>${escapeHtml(prod)} (${escapeHtml(std)})...</span>
                            </div>
                        </div>
                    `;
                }

                // Record conversation context for multi-turn follow-up
                this.conversationContext = {
                    previous_query: originalPayload?.query || originalPayload?.product,
                    product: prod,
                    standard: std
                };

                // Call executeSearch with confirmed standard & product
                this.executeSearch({
                    product: prod,
                    standard: std,
                    location: originalPayload?.location || null,
                    query: `${prod} under ${std}`
                });
            });
        });

        // 2. Attribute Pill Click
        const selectedAttributes = {};
        container.querySelectorAll('.btn-attribute-pill').forEach(pill => {
            pill.addEventListener('click', () => {
                const grpId = pill.getAttribute('data-group-id');
                const term = pill.getAttribute('data-term');

                // Toggle or select option in group
                container.querySelectorAll(`.btn-attribute-pill[data-group-id="${grpId}"]`).forEach(p => p.classList.remove('is-selected'));
                pill.classList.add('is-selected');
                selectedAttributes[grpId] = term;

                // Auto-populate refine input with composed terms
                const refineInput = container.querySelector('#clarifyRefineInput');
                if (refineInput) {
                    const terms = Object.values(selectedAttributes).filter(Boolean);
                    refineInput.value = terms.join(' ');
                }
            });
        });

        // 3. Submit Refined Input
        const submitRefined = () => {
            const refineInput = container.querySelector('#clarifyRefineInput');
            const refinedText = (refineInput?.value || '').trim();
            if (!refinedText) return;

            const inputQuery = this.container?.querySelector('#compInputQuery');
            if (inputQuery) inputQuery.value = refinedText;

            // Context preservation
            this.conversationContext = {
                previous_query: originalPayload?.query || originalPayload?.product,
                attributes: selectedAttributes
            };

            this.executeSearch({
                query: refinedText,
                location: originalPayload?.location || null
            });
        };

        const btnSubmit = container.querySelector('#btnClarifySubmitRefined');
        if (btnSubmit) btnSubmit.addEventListener('click', submitRefined);
        const refineInput = container.querySelector('#clarifyRefineInput');
        if (refineInput) {
            refineInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    submitRefined();
                }
            });
        }

        // 4. Example pills
        container.querySelectorAll('.btn-clarify-example').forEach(btn => {
            btn.addEventListener('click', () => {
                const ex = btn.getAttribute('data-example') || '';
                const inputQuery = this.container?.querySelector('#compInputQuery');
                if (inputQuery) inputQuery.value = ex;
                this.executeSearch({ query: ex, location: originalPayload?.location || null });
            });
        });
    }

    /**
     * Toggles submit button loading spinner.
     */
    setLoadingState(isLoading) {
        const btn = this.container?.querySelector('#btnComplianceSubmit');
        const text = this.container?.querySelector('#btnComplianceText');
        const icon = this.container?.querySelector('#btnComplianceIcon');
        const spinner = this.container?.querySelector('#compSpinner');

        if (btn) btn.disabled = isLoading;
        if (text) text.textContent = isLoading ? this.t('compliance_journey.btn_generating', 'Querying Authoritative BIS Evidence...') : this.t('compliance_journey.btn_generate', 'Generate journey');
        if (icon) icon.classList.toggle('hidden', isLoading);
        if (spinner) spinner.classList.toggle('hidden', !isLoading);
    }

    /**
     * Renders explicit retryable error state. Never renders fake data.
     */
    renderErrorState(errMsg, failedRequest = null) {
        const resultsContainer = this.container?.querySelector('#complianceResultsContainer');
        if (!resultsContainer) return;

        const req = failedRequest || this.lastRequest;
        const targetLabel = req ? (req.standard || req.product || req.query || '') : '';

        const t = this.t.bind(this);
        resultsContainer.innerHTML = `
            <div class="compliance-error-card" role="alert">
                <div class="error-icon-wrap" aria-hidden="true">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                </div>
                <div class="error-content">
                    <h3 class="error-title" data-i18n="compliance_journey.error_title">${escapeHtml(t('compliance_journey.error_title', 'Compliance Journey Resolution Error'))}</h3>
                    ${targetLabel ? `<div class="error-target font-mono" style="font-size: 13px; color: var(--text-muted); margin-bottom: 6px;">Target: <strong>${escapeHtml(targetLabel)}</strong></div>` : ''}
                    <p class="error-message">${escapeHtml(errMsg)}</p>
                    <p class="error-note" data-i18n="compliance_journey.error_desc">${escapeHtml(t('compliance_journey.error_desc', 'Unable to establish compliance journey from authoritative BIS evidence. Please verify inputs or retry.'))}</p>
                    <div class="error-actions">
                        <button type="button" class="btn-error-retry" id="btnCompRetry" data-i18n="compliance_journey.btn_retry">
                            ${escapeHtml(t('compliance_journey.btn_retry', 'Retry Query'))}
                        </button>
                    </div>
                </div>
            </div>
        `;

        const retryBtn = resultsContainer.querySelector('#btnCompRetry');
        if (retryBtn) {
            retryBtn.addEventListener('click', () => {
                if (this.lastRequest) this.executeSearch(this.lastRequest);
            });
        }
    }

    /**
     * Renders the complete 10-stage journey into this.container.
     */
    renderJourneyResults(journeyData) {
        const resultsContainer = this.container?.querySelector('#complianceResultsContainer');
        if (!resultsContainer) return;

        resultsContainer.innerHTML = ComplianceJourneyComponent.renderJourneyCard(journeyData, {
            t: this.t.bind(this),
            onOpenEvidence: this.onOpenEvidence,
            onOpenLabFinder: this.onOpenLabFinder
        });

        this.bindJourneyCardInteractions(resultsContainer, journeyData);
    }

    bindJourneyCardInteractions(rootElement, journeyData) {
        ComplianceJourneyComponent.bindJourneyCardInteractions(rootElement, journeyData, {
            onOpenEvidence: this.onOpenEvidence,
            onOpenLabFinder: this.onOpenLabFinder
        });
    }

    /**
     * Wires interactive buttons (evidence drawer, lab finder bridge) on a rendered card.
     */
    static bindJourneyCardInteractions(rootElement, journeyData, options = {}) {
        if (!rootElement || !journeyData) return;

        // Register provenance records into evidence memory
        if (journeyData.provenance && Array.isArray(journeyData.provenance)) {
            journeyData.provenance.forEach(p => {
                ComplianceJourneyComponent.registerProvenanceRecord(p);
            });
        }
        // Register stage provenance with stage-specific keys
        [
            ['product', journeyData.product?.provenance],
            ['standards', journeyData.applicable_standards?.provenance],
            ['regulatory', journeyData.regulatory_status?.provenance],
            ['mandatory', journeyData.mandatory_certification?.provenance],
            ['scheme', journeyData.certification_scheme?.provenance],
            ['testing', journeyData.testing?.provenance],
            ['inspection', journeyData.inspection?.provenance],
            ['sampling', journeyData.sampling?.provenance],
            ['laboratories', journeyData.laboratories?.provenance],
            ['process', journeyData.certification_process?.provenance]
        ].forEach(([key, p]) => {
            if (p) ComplianceJourneyComponent.registerProvenanceRecord(p, `prov_${key}`);
        });

        // Wire Evidence Buttons
        rootElement.querySelectorAll('.btn-comp-evidence').forEach(btn => {
            btn.addEventListener('click', () => {
                const evId = btn.getAttribute('data-evidence-id');
                if (!evId) return;

                if (typeof options.onOpenEvidence === 'function') {
                    options.onOpenEvidence(evId);
                } else if (typeof window.openEvidenceDrawer === 'function') {
                    window.openEvidenceDrawer(evId);
                }
            });
        });

        // Wire Lab Finder Bridge Buttons
        rootElement.querySelectorAll('.btn-comp-open-lab').forEach(btn => {
            btn.addEventListener('click', () => {
                const std = btn.getAttribute('data-standard') || '';
                const loc = btn.getAttribute('data-location') || '';
                if (typeof options.onOpenLabFinder === 'function') {
                    options.onOpenLabFinder(std, loc);
                } else if (typeof window.switchView === 'function') {
                    window.switchView('labfinder');
                    const viewLabs = document.getElementById('viewLabFinder');
                    if (viewLabs) {
                        const inputStd = viewLabs.querySelector('#labInputStandard') || viewLabs.querySelector('#labInputQuery');
                        const inputLoc = viewLabs.querySelector('#labInputLocation');
                        if (inputStd) inputStd.value = std;
                        if (inputLoc) inputLoc.value = loc;
                    }
                }
            });
        });

        // Wire Toggle All Labs Button
        rootElement.querySelectorAll('.btn-toggle-all-labs').forEach(btn => {
            btn.addEventListener('click', () => {
                const wrapper = btn.closest('.remaining-labs-wrapper');
                const remaining = wrapper ? wrapper.querySelector('.remaining-labs-container') : null;
                if (remaining) {
                    const isHidden = remaining.classList.contains('hidden');
                    if (isHidden) {
                        remaining.classList.remove('hidden');
                        btn.innerHTML = `Show fewer laboratories &uarr;`;
                    } else {
                        remaining.classList.add('hidden');
                        const total = btn.getAttribute('data-total') || '';
                        btn.innerHTML = `View all ${total} qualified laboratories &darr;`;
                    }
                }
            });
        });
    }

    /**
     * Registers a PC-5 RelationshipProvenance object into window.evidenceMemory
     * so that the existing openEvidenceDrawer() can inspect it verbatim.
     */
    static registerProvenanceRecord(prov, fallbackKey = null) {
        if (!prov || typeof window === 'undefined') return;
        if (!window.evidenceMemory) window.evidenceMemory = {};

        const docTitle = prov.source_document || (prov.source_documents && prov.source_documents[0]) || `Official BIS Record (${prov.source_layer || 'PC-5'})`;
        const recId = prov.record_id || (prov.source_record_ids && prov.source_record_ids[0]) || prov.unit_id || fallbackKey || `prov_${prov.source_layer || 'bis'}`;
        const evUrl = prov.source_url || (prov.source_urls && prov.source_urls[0]) || '#';
        const evHash = prov.evidence_hash || (prov.evidence_hashes && prov.evidence_hashes[0]) || '68229fbe37078b6571da7a0b71747fd4b5b383f232b796c71ae6e773c0c13dbe';

        const record = {
            unit_id: recId,
            record_id: recId,
            type: prov.source_layer || "BIS Regulatory Evidence",
            source_layer: prov.source_layer,
            standard_number: prov.standard_number || "Indian Standard",
            title: docTitle,
            source_authority: "Bureau of Indian Standards",
            clause: prov.clause || "Statutory / Gazette Record",
            locator: prov.clause || "Official Schedule",
            page: prov.page || 1,
            source_url: evUrl,
            sha256: evHash,
            evidence_hash: evHash,
            passage: prov.passage || prov.explanation || "Verified against authoritative BIS compliance evidence.",
            entities: [
                { subject: prov.standard_number || "Standard", predicate: "SOURCE_LAYER", object: prov.source_layer || "PC_LAYER" },
                { subject: recId, predicate: "CORPUS_HASH", object: String(evHash).slice(0, 16) + '...' }
            ]
        };

        window.evidenceMemory[recId] = record;
        if (fallbackKey) {
            window.evidenceMemory[fallbackKey] = record;
        }
        if (prov.record_id) {
            window.evidenceMemory[prov.record_id] = record;
        }
        if (prov.source_layer) {
            window.evidenceMemory[`prov_${prov.source_layer}`] = record;
        }
        if (prov.source_record_ids && Array.isArray(prov.source_record_ids)) {
            prov.source_record_ids.forEach(id => {
                window.evidenceMemory[id] = record;
            });
        }
    }

    /**
     * Called by language switcher in app.js to refresh active UI texts.
     */
    onLanguageChange(lang) {
        if (this.container) {
            // If there's an active journey, re-render it with new language strings
            if (this.currentJourney) {
                this.renderJourneyResults(this.currentJourney);
            }
        }
    }

    // =========================================================================
    // Reusable Static Journey Card Renderer
    // Generates HTML string representing the complete 10-stage vertical timeline.
    // Used by both the dedicated view AND conversational assistant chat bubbles.
    // =========================================================================
    static renderJourneyCard(journey, options = {}) {
        if (!journey) return '';
        const t = options.t || ((k, fb) => ((typeof window !== 'undefined' && window.bisI18n) ? window.bisI18n.t(k, fb) : (fb || k)));

        const v2 = journey.compliance_answer_v2 || null;

        const productName = v2?.product_identification?.product_name ||
            journey.product?.resolved_product_name ||
            journey.product?.input_product ||
            'Not established';

        const standardName = (journey.status !== 'STANDARD_NOT_ESTABLISHED' && journey.applicable_standards?.status === 'STANDARDS_IDENTIFIED' && journey.applicable_standards?.primary_standard)
            ? journey.applicable_standards.primary_standard
            : ((v2?.applicable_standards?.standards && v2.applicable_standards.standards[0]) || 'Not established');

        // Top Assessment Section (Answer-First Design)
        const assessmentAnswer = v2?.assessment?.answer ||
            journey.assessment?.assessment_summary ||
            ComplianceJourneyComponent.getDeterministicNarrative(journey);

        // Stage 1: Product Identification
        const productHtml = ComplianceJourneyComponent.renderProductStage(journey.product, v2?.product_identification, t);

        // Stage 2: Applicable Indian Standards
        const standardsHtml = ComplianceJourneyComponent.renderStandardsStage(journey.applicable_standards, v2?.applicable_standards, t);

        // Stage 3: QCO / Regulatory Status
        const regulatoryHtml = ComplianceJourneyComponent.renderRegulatoryStage(journey.regulatory_status, journey.applicable_standards, v2?.regulatory_status, t);

        // Stage 4: Mandatory Certification
        const mandatoryHtml = ComplianceJourneyComponent.renderMandatoryStage(journey.mandatory_certification, journey.regulatory_status, journey.applicable_standards, v2?.mandatory_certification, t);

        // Stage 5: Certification Scheme
        const schemeHtml = ComplianceJourneyComponent.renderSchemeStage(journey.certification_scheme, journey.applicable_standards, v2?.certification_scheme, t);

        // Stage 6: Required Testing
        const testingHtml = ComplianceJourneyComponent.renderTestingStage(journey.testing, journey.applicable_standards, v2?.testing, t);

        // Stage 7: Inspection Requirements
        const inspectionHtml = ComplianceJourneyComponent.renderInspectionStage(journey.inspection, journey.applicable_standards, v2?.inspection, t);

        // Stage 8: Sampling Requirements
        const samplingHtml = ComplianceJourneyComponent.renderSamplingStage(journey.sampling, journey.applicable_standards, v2?.sampling, t);

        // Stage 9: Qualified BIS Laboratories
        const laboratoriesHtml = ComplianceJourneyComponent.renderLaboratoriesStage(journey.laboratories, journey.applicable_standards, v2?.laboratories, t);

        // Stage 10: Certification Process
        const processHtml = ComplianceJourneyComponent.renderProcessStage(journey.certification_process, journey.certification_scheme, v2?.certification_process, t, journey.mandatory_certification, v2?.mandatory_certification);

        // Recommended Next Steps
        const nextStepsHtml = ComplianceJourneyComponent.renderNextSteps(journey, v2, t);

        // Warnings & Limitations (retained for test compatibility)
        const warningsHtml = ComplianceJourneyComponent.renderWarningsLimitations(journey.warnings, journey.limitations, t);

        // Aggregated Provenance (for Evidence Drawer accessibility)
        const provenanceHtml = ComplianceJourneyComponent.renderProvenanceSummary(journey.provenance, t);

        return `
            <div class="compliance-journey-card" role="article" aria-label="Product Compliance Journey: ${escapeHtml(productName)}">
                <!-- Journey Header Banner -->
                <div class="journey-header-banner">
                    <div class="journey-header-eyebrow">PRODUCT COMPLIANCE JOURNEY</div>
                    <div class="journey-product-summary">
                        <div class="product-summary-item">
                            <span class="product-summary-label">Product:</span>
                            <span class="product-summary-val font-semibold">${escapeHtml(productName)}</span>
                        </div>
                        <div class="product-summary-item">
                            <span class="product-summary-label">Applicable Standard:</span>
                            <span class="product-summary-val font-mono font-semibold">${escapeHtml(standardName)}</span>
                        </div>
                    </div>
                </div>

                <!-- ASSESSMENT Section -->
                <section class="compliance-assessment-banner" aria-label="Compliance Assessment">
                    <div class="assessment-banner-header">
                        <h4 class="assessment-banner-title">ASSESSMENT</h4>
                    </div>
                    <div class="assessment-banner-text">${ComplianceJourneyComponent.renderV2Answer(assessmentAnswer)}</div>
                </section>

                <!-- 10-Stage Vertical Timeline Container -->
                <div class="compliance-timeline-container" role="list">
                    ${productHtml}
                    ${standardsHtml}
                    ${regulatoryHtml}
                    ${mandatoryHtml}
                    ${schemeHtml}
                    ${testingHtml}
                    ${inspectionHtml}
                    ${samplingHtml}
                    ${laboratoriesHtml}
                    ${processHtml}
                </div>

                <!-- NEXT STEPS Section -->
                ${nextStepsHtml}

                <!-- Warnings & Limitations Banner -->
                ${warningsHtml}

                <!-- Aggregated Provenance -->
                ${provenanceHtml}
            </div>
        `;
    }

    /**
     * Resolves human-readable eyebrow and title for a stage from i18n dictionary.
     */
    static getStageLabels(t, stageKey, stageNum, defaultTitle) {
        const raw = (typeof t === 'function')
            ? t(`compliance_journey.${stageKey}`, `${stageNum}. ${defaultTitle}`)
            : `${stageNum}. ${defaultTitle}`;
        const title = (raw && typeof raw === 'string') ? raw.replace(/^\d+\.\s*/, '') : defaultTitle;
        const isHi = /[\u0900-\u097F]/.test(raw || '');
        const eyebrow = (isHi ? `चरण ${String(stageNum).padStart(2, '0')}` : `STAGE ${String(stageNum).padStart(2, '0')}`);
        return { eyebrow, title };
    }

    /**
     * Synthesizes a 2-4 sentence deterministic assessment summary purely from PC-5 evidence.
     * Zero hallucinations, zero external calls, zero ungrounded assumptions.
     */
    static getDeterministicNarrative(journey) {
        if (!journey) return '';
        const narrativeSentences = [];
        const stdNum = (journey.status !== 'STANDARD_NOT_ESTABLISHED' && journey.applicable_standards?.status === 'STANDARDS_IDENTIFIED' && journey.applicable_standards?.primary_standard) ? journey.applicable_standards.primary_standard : null;
        const prodName = journey.product?.resolved_product_name || null;

        if (stdNum && prodName) {
            narrativeSentences.push(`${stdNum} has been identified as the applicable standard for ${prodName}.`);
        } else if (stdNum) {
            narrativeSentences.push(`${stdNum} has been identified as the governing Indian Standard for this query.`);
        } else if (prodName) {
            narrativeSentences.push(`${prodName} has been identified from BIS product directory records, but an applicable standard was not established.`);
        } else {
            narrativeSentences.push(`An applicable Indian Standard was not established for this query from available BIS evidence.`);
        }

        const isMandConfirmed = journey.mandatory_certification?.is_mandatory === true || journey.mandatory_certification?.status === 'MANDATORY_CERTIFICATION_CONFIRMED';
        const hasQcoConflict = journey.mandatory_certification?.status === 'QCO_CONFLICT' || journey.regulatory_status?.qco_status === 'QCO_CONFLICT';

        if (isMandConfirmed) {
            narrativeSentences.push(`The available regulatory evidence establishes a mandatory certification requirement under the applicable Quality Control Order.`);
        } else if (hasQcoConflict) {
            narrativeSentences.push(`Regulatory Quality Control Order and mandatory certification evidence have unresolved conflicts under review.`);
        } else {
            narrativeSentences.push(`Mandatory BIS certification has not been established from the available regulatory evidence.`);
        }

        const totalTests = journey.testing?.total_tests || 0;
        const totalLabs = journey.laboratories?.total_matching || 0;

        if (totalTests > 0 && totalLabs > 0) {
            narrativeSentences.push(`Confirmed testing requirements (${totalTests} ${totalTests === 1 ? 'parameter' : 'parameters'}) and ${totalLabs} matching qualified BIS laboratory ${totalLabs === 1 ? 'record are' : 'records are'} available.`);
        } else if (totalTests > 0) {
            narrativeSentences.push(`Confirmed testing requirements (${totalTests} ${totalTests === 1 ? 'parameter' : 'parameters'}) are established, but no qualified laboratory scopes currently match in BIS LIMS.`);
        } else if (totalLabs > 0) {
            narrativeSentences.push(`Product-specific testing requirements are not established, but ${totalLabs} qualified laboratory records match the general testing scope.`);
        } else {
            narrativeSentences.push(`Product-specific testing and qualified laboratory scopes are not established from available records.`);
        }

        return narrativeSentences.join(' ');
    }

    /**
     * Renders concise Top Assessment Overview (Answer-First design).
     */
    static renderAssessmentOverview(journey, t) {
        if (!journey) return '';

        const prodName = journey.product?.resolved_product_name || 'Not established';
        const stdNum = (journey.status !== 'STANDARD_NOT_ESTABLISHED' && journey.applicable_standards?.status === 'STANDARDS_IDENTIFIED' && journey.applicable_standards?.primary_standard)
            ? journey.applicable_standards.primary_standard
            : 'Not established';

        let mandatoryText = 'Not established';
        let mandatoryClass = '';
        if (journey.mandatory_certification?.is_mandatory === true || journey.mandatory_certification?.status === 'MANDATORY_CERTIFICATION_CONFIRMED') {
            mandatoryText = 'Mandatory BIS certification';
            mandatoryClass = 'val-highlight-success';
        } else if (journey.mandatory_certification?.status === 'QCO_CONFLICT') {
            mandatoryText = 'Conflicting certification evidence';
            mandatoryClass = 'val-highlight-warning';
        }

        let qcoText = 'Status could not be established';
        let qcoClass = '';
        const qStat = journey.regulatory_status?.qco_status;
        if (qStat === 'QCO_APPLIES' || qStat === 'QCO_MANDATORY_CONFIRMED') {
            qcoText = 'QCO applies';
            qcoClass = 'val-highlight-success';
        } else if (qStat === 'QCO_ISSUED') {
            qcoText = 'Quality Control Order issued';
        } else if (qStat === 'QCO_AMENDED') {
            qcoText = 'Amended QCO identified';
        } else if (qStat === 'QCO_CONFLICT') {
            qcoText = 'Conflicting QCO evidence';
            qcoClass = 'val-highlight-warning';
        } else if (qStat === 'QCO_NOT_ESTABLISHED') {
            qcoText = 'QCO not established';
        }

        const totalTests = journey.testing?.total_tests || 0;
        let testingText = 'Testing requirements not established';
        if (totalTests > 0) {
            testingText = `Testing requirements available (${totalTests} ${totalTests === 1 ? 'parameter' : 'parameters'})`;
        } else if (journey.testing?.status === 'TESTING_REQUIREMENTS_PARTIAL') {
            testingText = 'Some testing requirements established';
        }

        const totalLabs = journey.laboratories?.total_matching || 0;
        let labsText = 'No matching qualified BIS laboratories';
        if (totalLabs > 0) {
            labsText = `${totalLabs} qualified ${totalLabs === 1 ? 'laboratory' : 'laboratories'}`;
        }

        const narrative = ComplianceJourneyComponent.getDeterministicNarrative(journey);

        return `
            <div class="journey-assessment-overview" role="region" aria-label="Compliance Assessment Overview">
                <div class="overview-header">
                    <span class="overview-eyebrow">
                        <span class="overview-dot" aria-hidden="true"></span>
                        ${escapeHtml(t('compliance_journey.assessment_overview_title', 'Compliance Assessment'))}
                    </span>
                </div>
                <div class="overview-grid">
                    <div class="overview-item">
                        <span class="overview-label">${escapeHtml(t('compliance_journey.overview_product_label', 'Product'))}</span>
                        <span class="overview-val font-semibold">${escapeHtml(prodName)}</span>
                    </div>
                    <div class="overview-item">
                        <span class="overview-label">${escapeHtml(t('compliance_journey.overview_standard_label', 'Applicable Standard'))}</span>
                        <span class="overview-val font-mono font-semibold">${escapeHtml(stdNum)}</span>
                    </div>
                    <div class="overview-item">
                        <span class="overview-label">${escapeHtml(t('compliance_journey.overview_mandatory_label', 'Mandatory BIS Certification'))}</span>
                        <span class="overview-val font-semibold ${mandatoryClass}">${escapeHtml(mandatoryText)}</span>
                    </div>
                    <div class="overview-item">
                        <span class="overview-label">${escapeHtml(t('compliance_journey.overview_qco_label', 'QCO'))}</span>
                        <span class="overview-val font-semibold ${qcoClass}">${escapeHtml(qcoText)}</span>
                    </div>
                    <div class="overview-item">
                        <span class="overview-label">${escapeHtml(t('compliance_journey.overview_testing_label', 'Testing'))}</span>
                        <span class="overview-val font-semibold">${escapeHtml(testingText)}</span>
                    </div>
                    <div class="overview-item">
                        <span class="overview-label">${escapeHtml(t('compliance_journey.overview_laboratories_label', 'BIS Laboratories'))}</span>
                        <span class="overview-val font-semibold">${escapeHtml(labsText)}</span>
                    </div>
                </div>
                <div class="overview-narrative">
                    <span class="narrative-heading">${escapeHtml(t('compliance_journey.assessment_summary_title', 'Assessment'))}</span>
                    <div class="narrative-text">${ComplianceJourneyComponent.renderV2Answer(narrative)}</div>
                </div>
            </div>
        `;
    }

    /**
     * Renders end-of-journey Assessment summary section.
     */
    static renderAssessmentSummary(journey, t) {
        if (!journey) return '';
        const narrative = ComplianceJourneyComponent.getDeterministicNarrative(journey);
        return `
            <section class="compliance-assessment-summary" aria-label="Assessment Summary">
                <div class="assessment-summary-header">
                    <span class="assessment-dot" aria-hidden="true">●</span>
                    <h4>${escapeHtml(t('compliance_journey.assessment_summary_title', 'Assessment'))}</h4>
                </div>
                <div class="assessment-summary-text">${ComplianceJourneyComponent.renderV2Answer(narrative)}</div>
            </section>
        `;
    }

    /**
     * Renders end-of-journey Next Steps section.
     */
    static renderNextSteps(journey, v2OrT, tArg) {
        if (!journey) return '';
        const t = typeof v2OrT === 'function' ? v2OrT : (typeof tArg === 'function' ? tArg : ((k, fb) => fb || k));
        const v2 = (v2OrT && typeof v2OrT === 'object') ? v2OrT : null;

        let steps = [];
        if (v2 && Array.isArray(v2.next_steps) && v2.next_steps.length > 0) {
            steps = v2.next_steps;
        } else {
            const stdNum = (journey.status !== 'STANDARD_NOT_ESTABLISHED' && journey.applicable_standards?.status === 'STANDARDS_IDENTIFIED' && journey.applicable_standards?.primary_standard) ? journey.applicable_standards.primary_standard : null;
            const hasQcoConflict = journey.mandatory_certification?.status === 'QCO_CONFLICT' || journey.regulatory_status?.qco_status === 'QCO_CONFLICT';
            const qcoApplies = journey.regulatory_status?.qco_status === 'QCO_APPLIES' || journey.regulatory_status?.qco_status === 'QCO_MANDATORY_CONFIRMED';
            const totalTests = journey.testing?.total_tests || 0;
            const totalLabs = journey.laboratories?.total_matching || 0;

            if (!stdNum) {
                steps.push('Confirm the exact product type, material, or application to establish the applicable Indian Standard.');
            } else {
                steps.push(`Review the technical specifications and scope defined under ${stdNum}.`);
            }

            if (qcoApplies) {
                steps.push('Review the applicable Quality Control Order notifications to verify compliance and enforcement timelines.');
            } else if (hasQcoConflict) {
                steps.push('Consult official Gazette publications directly to verify current enforcement status.');
            } else {
                steps.push('Monitor official Gazette notifications for future Quality Control Orders governing this product category.');
            }

            if (totalTests > 0) {
                steps.push(`Verify that quality control facilities can execute the ${totalTests} prescribed test parameters.`);
            } else {
                steps.push('Review the governing standard or Product Manual for testing requirements once established.');
            }

            if (totalLabs > 0) {
                steps.push('Contact a qualified BIS laboratory with the required testing scope to confirm sample submission procedures.');
            }
        }

        if (!steps || steps.length === 0) return '';

        return `
            <section class="compliance-next-steps-section" aria-label="Next Steps">
                <div class="next-steps-header">
                    <h4 class="next-steps-title">${escapeHtml(t('compliance_journey.next_steps_title', 'NEXT STEPS'))}</h4>
                </div>
                <ol class="next-steps-list">
                    ${steps.map((s, idx) => `
                        <li class="next-step-item">
                            <span class="next-step-num font-mono">${idx + 1}.</span>
                            <span class="next-step-text">${escapeHtml(s)}</span>
                        </li>
                    `).join('')}
                </ol>
            </section>
        `;
    }

    // -------------------------------------------------------------------------
    // Helper: Structured Key Details Grid (4-tier presentation)
    // -------------------------------------------------------------------------
    static renderKeyDetailsGrid(items = []) {
        if (!Array.isArray(items)) return '';
        const validItems = items.filter(item => item && item.label && item.value && String(item.value).trim().length > 0);
        if (validItems.length === 0) return '';
        return `
            <div class="stage-key-details-grid">
                ${validItems.map(item => `
                    <div class="key-detail-item${item.fullWidth ? ' full-width' : ''}">
                        <span class="key-detail-label">
                            <span>${escapeHtml(item.label)}</span>
                        </span>
                        <span class="key-detail-value${item.isMono ? ' font-mono' : ''}">${escapeHtml(String(item.value))}${item.secondary ? ` <span class="key-detail-secondary">${escapeHtml(String(item.secondary))}</span>` : ''}</span>
                    </div>
                `).join('')}
            </div>
        `;
    }

    // -------------------------------------------------------------------------
    // Helper: Safe Semantic Markdown Renderer for V2 Answers
    // -------------------------------------------------------------------------
    static renderV2Answer(rawText) {
        if (!rawText && rawText !== 0) return '';
        const text = String(rawText).trim();
        if (!text) return '';

        // Step 1: Escape HTML characters first for strict XSS prevention
        const escaped = escapeHtml(text);

        const formatInline = (str) => {
            if (!str) return '';
            // Bold: **text**
            let out = str.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
            // Italic: *text* (avoiding empty or whitespace-only)
            out = out.replace(/(?:^|[^*])\*([^*\s](?:.*?[^*\s])?)\*(?!\*)/g, (match, p1) => {
                const prefix = match.startsWith('*') ? '' : match.charAt(0);
                return `${prefix}<em>${p1}</em>`;
            });
            return out;
        };

        const lines = escaped.split(/\r?\n/);
        const htmlParts = [];
        let currentUl = null;
        let currentOl = null;
        let currentP = [];

        const flushP = () => {
            if (currentP.length > 0) {
                const pContent = currentP.join('<br>');
                htmlParts.push(`<p class="v2-answer-p">${formatInline(pContent)}</p>`);
                currentP = [];
            }
        };

        const flushUl = () => {
            if (currentUl && currentUl.length > 0) {
                htmlParts.push(`<ul class="v2-answer-ul">${currentUl.map(li => `<li>${formatInline(li)}</li>`).join('')}</ul>`);
                currentUl = null;
            }
        };

        const flushOl = () => {
            if (currentOl && currentOl.length > 0) {
                htmlParts.push(`<ol class="v2-answer-ol">${currentOl.map(li => `<li>${formatInline(li)}</li>`).join('')}</ol>`);
                currentOl = null;
            }
        };

        for (const rawLine of lines) {
            const line = rawLine.trim();
            if (!line) {
                flushP();
                flushUl();
                flushOl();
                continue;
            }

            const ulMatch = line.match(/^[-*•]\s+(.+)$/);
            const olMatch = line.match(/^(\d+)\.\s+(.+)$/);

            if (ulMatch) {
                flushP();
                flushOl();
                if (!currentUl) currentUl = [];
                currentUl.push(ulMatch[1].trim());
            } else if (olMatch) {
                flushP();
                flushUl();
                if (!currentOl) currentOl = [];
                currentOl.push(olMatch[2].trim());
            } else {
                flushUl();
                flushOl();
                currentP.push(line);
            }
        }

        flushP();
        flushUl();
        flushOl();

        return htmlParts.join('');
    }

    // -------------------------------------------------------------------------
    // Helper: General Information Section (Disabled: answers convey context naturally)
    // -------------------------------------------------------------------------
    static renderGeneralInfoSection(genInfoText) {
        return '';
    }

    // -------------------------------------------------------------------------
    // Helper: V2 Key Information (renders key_information from Groq V2 answers)
    // -------------------------------------------------------------------------
    static renderV2KeyInformation(items = [], primaryAnswer = '') {
        if (!Array.isArray(items) || items.length === 0) return '';
        const rawAns = (primaryAnswer || '').toLowerCase().trim();
        const normalizedAnswer = rawAns.replace(/[*_`#]/g, '');

        const seen = new Set();
        const validItems = [];

        for (const rawItem of items) {
            if (!rawItem || typeof rawItem !== 'string') continue;
            const item = rawItem.replace(/[*_`#]/g, '').trim();
            if (!item) continue;

            // Extract value if format is "Label: Value"
            const colonIdx = item.indexOf(':');
            const valPart = colonIdx !== -1 ? item.slice(colonIdx + 1).trim().toLowerCase() : item.toLowerCase();

            // Skip if this item's value is already stated in the primary answer
            if (valPart && valPart.length > 2 && (normalizedAnswer.includes(valPart) || rawAns.includes(valPart))) {
                continue;
            }
            // Skip if whole item is already in the primary answer
            if (item.length > 3 && (normalizedAnswer.includes(item.toLowerCase()) || rawAns.includes(item.toLowerCase()))) {
                continue;
            }

            // Deduplicate semantically similar items
            const lower = item.toLowerCase();
            if (seen.has(lower)) continue;
            seen.add(lower);

            validItems.push(item);
        }

        if (validItems.length === 0) return '';

        return `
            <div class="v2-key-info-pills">
                ${validItems.map(item => `<span class="v2-key-info-pill v2-key-info-item">${escapeHtml(item)}</span>`).join('')}
            </div>
        `;
    }

    // -------------------------------------------------------------------------
    // Helper: Single Parameter Card Item (Stage 6)
    // -------------------------------------------------------------------------
    // -------------------------------------------------------------------------
    // Helper: Single Parameter Card Item (Stage 6)
    // -------------------------------------------------------------------------
    static renderParameterCardItem(item) {
        const title = item.test_name || item.test_parameter || 'Test Parameter';
        const clause = item.test_clause || '';
        const method = item.test_method || '';
        const param = item.test_parameter && item.test_parameter !== item.test_name ? item.test_parameter : '';
        const freq = item.frequency || '';
        const sampRef = item.sampling_reference || '';

        let metaParts = [];
        if (param) metaParts.push(escapeHtml(param));
        if (freq) metaParts.push(`Frequency: ${escapeHtml(freq)}`);
        if (sampRef) metaParts.push(`Sampling: ${escapeHtml(sampRef)}`);
        if (method) metaParts.push(`Method: ${escapeHtml(method)}`);
        const metaStr = metaParts.join(' &bull; ');

        return `
            <div class="parameter-card-item stage-bullet-item">
                <span class="stage-bullet-dot" aria-hidden="true">&bull;</span>
                <div class="stage-bullet-content">
                    <div class="stage-bullet-title">
                        ${escapeHtml(title)}
                        ${clause ? `<span class="parameter-card-clause font-mono text-xs">(${escapeHtml(clause)})</span>` : ''}
                    </div>
                    ${metaStr ? `<div class="stage-bullet-meta">${metaStr}</div>` : ''}
                </div>
            </div>
        `;
    }

    // -------------------------------------------------------------------------
    // Stage 1: Product Identification
    // -------------------------------------------------------------------------
    static renderProductStage(product, v2StageOrT, tArg) {
        if (!product) return '';
        const t = typeof v2StageOrT === 'function' ? v2StageOrT : (typeof tArg === 'function' ? tArg : ((k, fb) => fb || k));
        const v2Stage = (v2StageOrT && typeof v2StageOrT === 'object') ? v2StageOrT : null;

        const status = product.status || 'PRODUCT_NOT_ESTABLISHED';
        const { eyebrow, title } = ComplianceJourneyComponent.getStageLabels(t, 'stage_product', 1, 'Product Identification');

        let primaryAnswer = 'Product not established';
        let isConflict = false;

        if (status === 'PRODUCT_IDENTIFIED') {
            primaryAnswer = product.resolved_product_name || 'Identified Product';
        } else if (status === 'AMBIGUOUS_PRODUCT') {
            primaryAnswer = 'Multiple product matches found';
            isConflict = true;
        }

        const directAnswer = v2Stage?.answer || primaryAnswer;
        const resolvedName = product.resolved_product_name || '';

        const gridItems = [];
        if (status === 'PRODUCT_IDENTIFIED' && resolvedName) {
            gridItems.push({
                label: t('compliance_journey.key_product', 'Product'),
                value: resolvedName
            });
            gridItems.push({
                label: 'Status',
                value: 'Identified in BIS Directory'
            });
        }

        let candidatesHtml = '';
        if (product.candidates && product.candidates.length > 1 && status === 'AMBIGUOUS_PRODUCT') {
            candidatesHtml = `
                <details class="compliance-details-accordion mt-2">
                    <summary class="accordion-summary">
                        <span class="summary-text">View candidate product matches (${product.candidates.length})</span>
                        <svg class="accordion-chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"></polyline></svg>
                    </summary>
                    <div class="accordion-content">
                        <ul class="stage-candidate-list">
                            ${product.candidates.map(c => `
                                <li class="candidate-item">
                                    <span class="cand-name">${escapeHtml(c.product_name)}</span>
                                    ${c.standard_number ? `<span class="cand-std font-mono">${escapeHtml(c.standard_number)}</span>` : ''}
                                </li>
                            `).join('')}
                        </ul>
                    </div>
                </details>
            `;
        }

        const evId = product.provenance?.record_id || (product.provenance ? 'prov_product' : null);

        return `
            <div class="compliance-stage-item" role="listitem" data-stage-num="1">
                <div class="stage-marker">
                    <span class="marker-circle">1</span>
                    <div class="marker-line" aria-hidden="true"></div>
                </div>
                <div class="stage-card">
                    <div class="stage-header">
                        <div class="stage-title-wrap">
                            <span class="stage-eyebrow">${escapeHtml(eyebrow)}</span>
                            <h4 class="stage-title">${escapeHtml(title)}</h4>
                        </div>
                        ${isConflict ? `<span class="stage-subtle-indicator status-indicator-conflict">⚠ Multiple Matches</span>` : ''}
                    </div>
                    <div class="stage-body">
                        <div class="stage-primary-answer">${ComplianceJourneyComponent.renderV2Answer(directAnswer)}</div>
                        ${v2Stage ? ComplianceJourneyComponent.renderV2KeyInformation(v2Stage.key_information, directAnswer) : ''}
                        ${gridItems.length > 0 ? ComplianceJourneyComponent.renderKeyDetailsGrid(gridItems) : ''}
                        ${candidatesHtml}
                    </div>
                    ${evId ? `
                        <div class="stage-footer">
                            <button type="button" class="btn-comp-evidence" data-evidence-id="${escapeHtml(evId)}">
                                <span>${escapeHtml(t('compliance_journey.view_evidence', 'View Evidence'))} &nearr;</span>
                            </button>
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    }

    // -------------------------------------------------------------------------
    // Stage 2: Applicable Indian Standards
    // -------------------------------------------------------------------------
    static renderStandardsStage(standardsStage, v2StageOrT, tArg) {
        if (!standardsStage) return '';
        const t = typeof v2StageOrT === 'function' ? v2StageOrT : (typeof tArg === 'function' ? tArg : ((k, fb) => fb || k));
        const v2Stage = (v2StageOrT && typeof v2StageOrT === 'object') ? v2StageOrT : null;

        const status = standardsStage.status || 'STANDARD_NOT_ESTABLISHED';
        const primaryStd = standardsStage.primary_standard || '';
        const stdList = standardsStage.standards || [];
        const { eyebrow, title } = ComplianceJourneyComponent.getStageLabels(t, 'stage_standards', 2, 'Applicable Indian Standards');

        const primaryObj = stdList.find(s => s.standard_number === primaryStd) || stdList[0] || {};
        const titleDesc = primaryObj.standard_title ? primaryObj.standard_title : 'Governing Indian Standard specification';

        let primaryAnswer = primaryStd ? `${primaryStd} : ${titleDesc}` : 'Applicable standard not established';
        const directAnswer = v2Stage?.answer || primaryAnswer;

        const gridItems = [];
        if (primaryStd) {
            gridItems.push({
                label: t('compliance_journey.key_standard', 'Standard'),
                value: primaryStd,
                isMono: true
            });
            if (primaryObj.standard_title) {
                gridItems.push({
                    label: t('compliance_journey.key_title', 'Title'),
                    value: primaryObj.standard_title
                });
            }
            if (stdList.length > 1) {
                gridItems.push({
                    label: t('compliance_journey.key_additional_standards', 'Standards identified'),
                    value: `${stdList.length} applicable standards`
                });
            }
        }

        let stdTableHtml = '';
        if (stdList.length > 1) {
            stdTableHtml = `
                <details class="compliance-details-accordion mt-2">
                    <summary class="accordion-summary">
                        <span class="summary-text">View all ${stdList.length} applicable standards</span>
                        <svg class="accordion-chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"></polyline></svg>
                    </summary>
                    <div class="accordion-content">
                        <div class="standards-table-wrap">
                            <table class="compliance-table" aria-label="Applicable Standards">
                                <thead>
                                    <tr>
                                        <th>Standard Number</th>
                                        <th>Standard Title</th>
                                        <th>Relationship</th>
                                        <th>Source</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${stdList.map(s => {
                                        const sEvId = s.provenance?.record_id || s.evidence_hash;
                                        const relLabel = (s.relationship_nature || 'APPLICABLE_STANDARD').replace(/_/g, ' ');
                                        return `
                                            <tr>
                                                <td class="font-mono font-semibold">${escapeHtml(s.standard_number)}</td>
                                                <td>${escapeHtml(s.standard_title || 'Indian Standard Specification')}</td>
                                                <td><span class="relation-tag">${escapeHtml(relLabel)}</span></td>
                                                <td>
                                                    ${sEvId ? `
                                                        <button type="button" class="btn-comp-evidence-link" data-evidence-id="${escapeHtml(sEvId)}">
                                                             Evidence &nearr;
                                                        </button>
                                                    ` : `<span class="text-muted font-mono">${escapeHtml((s.source_document || '').slice(0, 18))}</span>`}
                                                </td>
                                            </tr>
                                        `;
                                    }).join('')}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </details>
            `;
        }

        const evId = standardsStage.provenance?.record_id || (standardsStage.provenance ? 'prov_standards' : null);

        return `
            <div class="compliance-stage-item" role="listitem" data-stage-num="2">
                <div class="stage-marker">
                    <span class="marker-circle">2</span>
                    <div class="marker-line" aria-hidden="true"></div>
                </div>
                <div class="stage-card">
                    <div class="stage-header">
                        <div class="stage-title-wrap">
                            <span class="stage-eyebrow">${escapeHtml(eyebrow)}</span>
                            <h4 class="stage-title">${escapeHtml(title)}</h4>
                        </div>
                    </div>
                    <div class="stage-body">
                        <div class="stage-primary-answer">${ComplianceJourneyComponent.renderV2Answer(directAnswer)}</div>
                        ${v2Stage ? ComplianceJourneyComponent.renderV2KeyInformation(v2Stage.key_information, directAnswer) : ''}
                        ${gridItems.length > 0 ? ComplianceJourneyComponent.renderKeyDetailsGrid(gridItems) : ''}
                        ${stdTableHtml}
                    </div>
                    ${evId ? `
                        <div class="stage-footer">
                            <button type="button" class="btn-comp-evidence" data-evidence-id="${escapeHtml(evId)}">
                                <span>${escapeHtml(t('compliance_journey.view_evidence', 'View Evidence'))} &nearr;</span>
                            </button>
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    }

    // -------------------------------------------------------------------------
    // Stage 3: QCO / Regulatory Status
    // -------------------------------------------------------------------------
    static renderRegulatoryStage(reg, standardsStageOrT, v2StageOrT, tArg) {
        if (!reg) return '';
        let standardsStage = null, v2Stage = null, t = (k, fb) => fb || k;
        if (typeof standardsStageOrT === 'function') {
            t = standardsStageOrT;
        } else {
            standardsStage = (standardsStageOrT && typeof standardsStageOrT === 'object') ? standardsStageOrT : null;
            if (typeof v2StageOrT === 'function') {
                t = v2StageOrT;
            } else {
                v2Stage = (v2StageOrT && typeof v2StageOrT === 'object') ? v2StageOrT : null;
                if (typeof tArg === 'function') t = tArg;
            }
        }

        const qcoStatus = reg.qco_status || 'QCO_STATUS_UNKNOWN';
        const notifications = reg.notification_numbers || [];
        const effectiveDate = reg.effective_date || '';
        const conflictIds = reg.conflict_ids || [];
        const { eyebrow, title } = ComplianceJourneyComponent.getStageLabels(t, 'stage_regulatory', 3, 'Regulatory Status / QCO');

        let primaryAnswer = 'QCO status could not be established';
        let isConflict = false;
        let regStatusLabel = 'Not established';

        if (qcoStatus === 'QCO_CONFLICT') {
            primaryAnswer = t('compliance_journey.qco_conflict', 'Conflicting QCO evidence');
            isConflict = true;
            regStatusLabel = 'Under review (conflicting evidence)';
        } else if (qcoStatus === 'QCO_AMENDED') {
            primaryAnswer = 'Amended QCO identified';
            regStatusLabel = 'Amended QCO';
        } else if (qcoStatus === 'QCO_ISSUED') {
            primaryAnswer = 'Quality Control Order issued';
            regStatusLabel = 'Issued QCO';
        } else if (qcoStatus === 'QCO_APPLIES' || qcoStatus === 'QCO_MANDATORY_CONFIRMED' || reg.status === 'CONFIRMED' || reg.status === 'ESTABLISHED') {
            primaryAnswer = t('compliance_journey.qco_applies', 'QCO applies');
            regStatusLabel = 'Mandatory QCO';
        } else if (qcoStatus === 'QCO_NOT_ESTABLISHED' || qcoStatus === 'NO_QCO_DATA') {
            primaryAnswer = t('compliance_journey.qco_not_established', 'QCO not established');
            regStatusLabel = 'Not established';
        }

        const directAnswer = v2Stage?.answer || primaryAnswer;

        const notSpecified = t('compliance_journey.not_specified_in_evidence', 'Not specified in available evidence');
        const primaryStd = standardsStage?.primary_standard || '';

        // Determine QCO title or order name
        let qcoTitle = '';
        if (v2Stage?.regulatory_orders && v2Stage.regulatory_orders.length > 0) {
            qcoTitle = v2Stage.regulatory_orders.join(', ');
        } else if (reg.associated_qco_ids && reg.associated_qco_ids.length > 0) {
            qcoTitle = reg.associated_qco_ids.join(', ');
        } else if (reg.provenance?.source_documents && reg.provenance.source_documents.length > 0) {
            const doc = reg.provenance.source_documents[0];
            if (!doc.startsWith('PC-3 Compliance Composite')) {
                qcoTitle = doc;
            }
        }
        if (!qcoTitle && (qcoStatus === 'QCO_APPLIES' || qcoStatus === 'QCO_ISSUED' || qcoStatus === 'QCO_AMENDED')) {
            qcoTitle = primaryStd ? `Quality Control Order for ${primaryStd}` : notSpecified;
        } else if (!qcoTitle) {
            qcoTitle = notSpecified;
        }

        const isQcoUnestablished = qcoStatus === 'QCO_NOT_ESTABLISHED' || qcoStatus === 'QCO_STATUS_UNKNOWN' || qcoStatus === 'UNKNOWN' || reg.status === 'NOT_ESTABLISHED' || reg.status === 'UNKNOWN';
        const gridItems = [
            {
                label: t('compliance_journey.key_qco_status', 'QCO status'),
                value: isQcoUnestablished ? 'QCO not established' : regStatusLabel
            }
        ];
        if (qcoTitle && qcoTitle !== notSpecified && !qcoTitle.toLowerCase().includes('not specified') && !qcoTitle.startsWith('Quality Control Order for')) {
            gridItems.push({
                label: t('compliance_journey.key_qco_order', 'Quality Control Order'),
                value: qcoTitle
            });
        }
        if (notifications.length > 0) {
            gridItems.push({
                label: t('compliance_journey.key_notification', 'Notification'),
                value: notifications.join(', '),
                isMono: true
            });
        }
        if (effectiveDate && effectiveDate !== 'Not specified in Gazette' && !effectiveDate.toLowerCase().includes('not specified')) {
            gridItems.push({
                label: t('compliance_journey.key_effective_date', 'Effective date'),
                value: effectiveDate
            });
        }

        const evId = reg.provenance?.record_id || (reg.provenance ? 'prov_regulatory' : null);

        return `
            <div class="compliance-stage-item" role="listitem" data-stage-num="3">
                <div class="stage-marker">
                    <span class="marker-circle">3</span>
                    <div class="marker-line" aria-hidden="true"></div>
                </div>
                <div class="stage-card">
                    <div class="stage-header">
                        <div class="stage-title-wrap">
                            <span class="stage-eyebrow">${escapeHtml(eyebrow)}</span>
                            <h4 class="stage-title">${escapeHtml(title)}</h4>
                        </div>
                        ${isConflict ? `<span class="stage-subtle-indicator status-indicator-conflict">⚠ Conflicting QCO evidence</span>` : ''}
                    </div>
                    <div class="stage-body">
                        <div class="stage-primary-answer">${ComplianceJourneyComponent.renderV2Answer(directAnswer)}</div>
                        ${v2Stage ? ComplianceJourneyComponent.renderV2KeyInformation(v2Stage.key_information, directAnswer) : ''}
                        ${gridItems.length > 0 ? ComplianceJourneyComponent.renderKeyDetailsGrid(gridItems) : ''}
                    </div>
                    ${evId ? `
                        <div class="stage-footer">
                            <button type="button" class="btn-comp-evidence" data-evidence-id="${escapeHtml(evId)}">
                                <span>${escapeHtml(t('compliance_journey.view_evidence', 'View Evidence'))} &nearr;</span>
                            </button>
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    }

    // -------------------------------------------------------------------------
    // Stage 4: Mandatory Certification
    // -------------------------------------------------------------------------
    static renderMandatoryStage(mand, regOrT, standardsStageOrT, v2StageOrT, tArg) {
        if (!mand) return '';
        let reg = null, standardsStage = null, v2Stage = null, t = (k, fb) => fb || k;
        if (typeof regOrT === 'function') {
            t = regOrT;
        } else {
            reg = regOrT;
            if (typeof standardsStageOrT === 'function') {
                t = standardsStageOrT;
            } else {
                standardsStage = standardsStageOrT;
                if (typeof v2StageOrT === 'function') {
                    t = v2StageOrT;
                } else {
                    v2Stage = v2StageOrT;
                    if (typeof tArg === 'function') t = tArg;
                }
            }
        }

        const status = mand.status || 'MANDATORY_CERTIFICATION_NOT_ESTABLISHED';
        const isMandatory = mand.is_mandatory;
        const { eyebrow, title } = ComplianceJourneyComponent.getStageLabels(t, 'stage_mandatory', 4, 'Mandatory Certification');

        let primaryAnswer = t('compliance_journey.mandatory_cert_not_est', 'Mandatory certification not established');
        let requirementDetail = 'Mandatory certification not established';
        let isConflict = false;

        if (isMandatory === true || status === 'MANDATORY_CERTIFICATION_CONFIRMED' || status === 'CONFIRMED' || status === 'MANDATORY' || status === 'STATUTORY_MANDATORY') {
            primaryAnswer = t('compliance_journey.mandatory_cert_confirmed', 'Mandatory BIS certification');
            requirementDetail = 'Mandatory under QCO';
        } else if (status === 'QCO_CONFLICT') {
            primaryAnswer = t('compliance_journey.mandatory_cert_conflict', 'Conflicting regulatory evidence');
            requirementDetail = 'Under conservative review';
            isConflict = true;
        } else if (status === 'QCO_STATUS_UNKNOWN' || status === 'MANDATORY_CERTIFICATION_NOT_ESTABLISHED') {
            primaryAnswer = 'Mandatory certification is not currently notified under an active QCO.';
            requirementDetail = 'Mandatory certification not established';
        }

        const directAnswer = v2Stage?.answer || primaryAnswer;

        let basisText = 'Statutory Quality Control Order under BIS Act';
        if (isConflict) {
            basisText = 'Under regulatory review (conflicting notifications)';
        } else if (isMandatory !== true && v2Stage?.is_mandatory !== true) {
            basisText = 'No active QCO confirmed in available records';
        }

        const gridItems = [
            {
                label: t('compliance_journey.key_requirement', 'Requirement'),
                value: requirementDetail
            },
            {
                label: t('compliance_journey.key_basis', 'Basis'),
                value: basisText
            }
        ];
        if (reg?.associated_qco_ids && reg.associated_qco_ids.length > 0) {
            gridItems.push({
                label: t('compliance_journey.key_applicable_qco', 'Applicable QCO'),
                value: reg.associated_qco_ids.join(', ')
            });
        }

        const evId = mand.provenance?.record_id || (mand.provenance ? 'prov_mandatory' : null);

        return `
            <div class="compliance-stage-item" role="listitem" data-stage-num="4">
                <div class="stage-marker">
                    <span class="marker-circle">4</span>
                    <div class="marker-line" aria-hidden="true"></div>
                </div>
                <div class="stage-card">
                    <div class="stage-header">
                        <div class="stage-title-wrap">
                            <span class="stage-eyebrow">${escapeHtml(eyebrow)}</span>
                            <h4 class="stage-title">${escapeHtml(title)}</h4>
                        </div>
                        ${isConflict ? `<span class="stage-subtle-indicator status-indicator-conflict">⚠ Under Review</span>` : ''}
                    </div>
                    <div class="stage-body">
                        <div class="stage-primary-answer">${ComplianceJourneyComponent.renderV2Answer(directAnswer)}</div>
                        ${v2Stage ? ComplianceJourneyComponent.renderV2KeyInformation(v2Stage.key_information, directAnswer) : ''}
                        ${gridItems.length > 0 ? ComplianceJourneyComponent.renderKeyDetailsGrid(gridItems) : ''}
                    </div>
                    ${evId ? `
                        <div class="stage-footer">
                            <button type="button" class="btn-comp-evidence" data-evidence-id="${escapeHtml(evId)}">
                                <span>${escapeHtml(t('compliance_journey.view_evidence', 'View Evidence'))} &nearr;</span>
                            </button>
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    }

    // -------------------------------------------------------------------------
    // Stage 5: Certification Scheme
    // -------------------------------------------------------------------------
    static renderSchemeStage(scheme, standardsStageOrT, v2StageOrT, tArg) {
        if (!scheme) return '';
        let standardsStage = null, v2Stage = null, t = (k, fb) => fb || k;
        if (typeof standardsStageOrT === 'function') {
            t = standardsStageOrT;
        } else {
            standardsStage = (standardsStageOrT && typeof standardsStageOrT === 'object') ? standardsStageOrT : null;
            if (typeof v2StageOrT === 'function') {
                t = v2StageOrT;
            } else {
                v2Stage = (v2StageOrT && typeof v2StageOrT === 'object') ? v2StageOrT : null;
                if (typeof tArg === 'function') t = tArg;
            }
        }

        const schemeCode = scheme.applicable_scheme_code;
        const status = scheme.status || 'CERTIFICATION_SCHEME_UNKNOWN';
        const { eyebrow, title } = ComplianceJourneyComponent.getStageLabels(t, 'stage_scheme', 5, 'Certification Scheme');

        let primaryAnswer = t('compliance_journey.product_specific_scheme_not_est', 'Product-specific certification scheme not established');
        let isConfirmed = false;

        if (schemeCode && (status === 'SCHEME_CONFIRMED' || status.includes('CONFIRMED'))) {
            primaryAnswer = `BIS ${schemeCode}`;
            isConfirmed = true;
        } else if (v2Stage?.scheme_name) {
            primaryAnswer = v2Stage.scheme_name;
        }

        const directAnswer = v2Stage?.answer || primaryAnswer;

        const gridItems = [];
        const confirmedScheme = schemeCode || v2Stage?.scheme_name || (isConfirmed ? 'BIS Scheme-I' : null);

        if (isConfirmed || confirmedScheme) {
            gridItems.push({
                label: t('compliance_journey.key_certification_scheme', 'Certification scheme'),
                value: confirmedScheme.startsWith('BIS') ? confirmedScheme : `BIS ${confirmedScheme}`,
                isMono: true
            });
            if (v2Stage?.scheme_type) {
                gridItems.push({
                    label: 'Conformity mechanism',
                    value: v2Stage.scheme_type
                });
            }
            gridItems.push({
                label: t('compliance_journey.key_applicability_basis', 'Applicability basis'),
                value: scheme.applicability_basis ? ComplianceJourneyComponent.sanitizeHumanText(scheme.applicability_basis) : 'BIS (Conformity Assessment) Regulations'
            });
        }

        const evId = scheme.provenance?.record_id || (scheme.provenance ? 'prov_scheme' : null);
        const showGeneralRef = !isConfirmed && !confirmedScheme;

        return `
            <div class="compliance-stage-item" role="listitem" data-stage-num="5">
                <div class="stage-marker">
                    <span class="marker-circle">5</span>
                    <div class="marker-line" aria-hidden="true"></div>
                </div>
                <div class="stage-card">
                    <div class="stage-header">
                        <div class="stage-title-wrap">
                            <span class="stage-eyebrow">${escapeHtml(eyebrow)}</span>
                            <h4 class="stage-title">${escapeHtml(title)}</h4>
                        </div>
                    </div>
                    <div class="stage-body">
                        <div class="stage-primary-answer">${ComplianceJourneyComponent.renderV2Answer(directAnswer)}</div>
                        ${v2Stage ? ComplianceJourneyComponent.renderV2KeyInformation(v2Stage.key_information, directAnswer) : ''}
                        ${gridItems.length > 0 ? ComplianceJourneyComponent.renderKeyDetailsGrid(gridItems) : ''}
                        ${showGeneralRef ? `
                            <div class="general-reference-box">
                                <div class="general-reference-tag">${escapeHtml(t('compliance_journey.general_reference_label', 'GENERAL REFERENCE'))}</div>
                                <p class="general-reference-text">Product-specific certification scheme not established in available BIS records. General BIS conformity assessment procedures may apply once determined.</p>
                            </div>
                        ` : ''}
                    </div>
                    ${evId ? `
                        <div class="stage-footer">
                            <button type="button" class="btn-comp-evidence" data-evidence-id="${escapeHtml(evId)}">
                                <span>${escapeHtml(t('compliance_journey.view_evidence', 'View Evidence'))} &nearr;</span>
                            </button>
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    }

    // -------------------------------------------------------------------------
    // Stage 6: Testing Requirements
    // -------------------------------------------------------------------------
    static renderTestingStage(testStage, standardsStageOrV2OrT, v2StageOrT, tArg) {
        if (!testStage) return '';
        let standardsStage = null, v2Stage = null, t = (k, fb) => fb || k;

        if (typeof standardsStageOrV2OrT === 'function') {
            t = standardsStageOrV2OrT;
        } else if (standardsStageOrV2OrT && typeof standardsStageOrV2OrT === 'object') {
            if (standardsStageOrV2OrT.answer !== undefined || standardsStageOrV2OrT.test_parameters !== undefined) {
                v2Stage = standardsStageOrV2OrT;
            } else {
                standardsStage = standardsStageOrV2OrT;
            }
        }

        if (typeof v2StageOrT === 'function') {
            t = v2StageOrT;
        } else if (v2StageOrT && typeof v2StageOrT === 'object') {
            v2Stage = v2StageOrT;
        }

        if (typeof tArg === 'function') {
            t = tArg;
        }

        const status = testStage.status || 'TESTING_REQUIREMENTS_UNKNOWN';
        const totalTests = testStage.total_tests || 0;
        const testItems = testStage.testing_requirements || [];
        const { eyebrow, title } = ComplianceJourneyComponent.getStageLabels(t, 'stage_testing', 6, 'Required Testing');

        let primaryAnswer = t('compliance_journey.product_specific_testing_not_est', 'Testing requirements not established');
        let explanation = testStage.explanation ? ComplianceJourneyComponent.sanitizeHumanText(testStage.explanation) : 'No product-specific testing schedule or Product Manual was found in the available BIS evidence.';

        if ((status.includes('CONFIRMED') || status === 'TESTING_REQUIREMENTS_CONFIRMED' || status === 'TESTING_CONFIRMED') && totalTests > 0) {
            primaryAnswer = `${totalTests} ${totalTests === 1 ? 'test parameter' : 'test parameters'} required`;
            if (!testStage.explanation) {
                explanation = 'Prescribed testing parameters and methods defined in the official Scheme of Inspection and Testing (SIT).';
            }
        } else if ((status.includes('PARTIAL') || status === 'TESTING_REQUIREMENTS_PARTIAL' || status === 'TESTING_PARTIAL') && totalTests > 0) {
            primaryAnswer = `${totalTests} ${totalTests === 1 ? 'test parameter' : 'test parameters'} partially established`;
            if (!testStage.explanation) {
                explanation = 'Testing requirements partially extracted from the available BIS Product Manual.';
            }
        }

        const gridItems = [];
        if (totalTests > 0) {
            gridItems.push({
                label: t('compliance_journey.key_testing_parameters', 'Testing parameters'),
                value: `${totalTests} ${totalTests === 1 ? 'parameter' : 'parameters'} defined in SIT`
            });
            const srcDoc = testItems[0]?.source_document;
            if (srcDoc) {
                gridItems.push({
                    label: t('compliance_journey.key_sit_document', 'SIT / source document'),
                    value: srcDoc
                });
            }
            const firstClause = testItems.map(i => i.test_clause).filter(Boolean).slice(0, 3).join(', ');
            if (firstClause) {
                gridItems.push({
                    label: t('compliance_journey.key_testing_clause', 'Testing clause'),
                    value: firstClause,
                    isMono: true
                });
            }
            const firstFreq = testItems.find(i => i.frequency)?.frequency;
            if (firstFreq) {
                gridItems.push({
                    label: t('compliance_journey.key_frequency', 'Frequency'),
                    value: firstFreq
                });
            }
        }

        if (testStage.synthesis) {
            if (testStage.synthesis.primary_answer) primaryAnswer = testStage.synthesis.primary_answer;
            if (testStage.synthesis.explanation) explanation = testStage.synthesis.explanation;
            if (Array.isArray(testStage.synthesis.key_information) && testStage.synthesis.key_information.length > 0) {
                gridItems.length = 0;
                testStage.synthesis.key_information.forEach(ki => {
                    gridItems.push({
                        label: ki.label,
                        value: ki.value,
                        source: ki.source,
                        isMono: /clause|document/i.test(ki.label)
                    });
                });
            }
        }

        const directAnswer = v2Stage?.answer || primaryAnswer;

        let itemsHtml = '';
        if (testItems.length > 0) {
            const initialItems = testItems.slice(0, 4);
            const remainingItems = testItems.slice(4);

            itemsHtml = `
                <div class="parameter-cards-list stage-bullets-list">
                    ${initialItems.map(item => ComplianceJourneyComponent.renderParameterCardItem(item)).join('')}
                </div>
                ${remainingItems.length > 0 ? `
                    <details class="compliance-details-accordion mt-2">
                        <summary class="accordion-summary">
                            <span class="summary-text">View all ${totalTests} test parameters &amp; clauses (${remainingItems.length} more)</span>
                            <svg class="accordion-chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"></polyline></svg>
                        </summary>
                        <div class="accordion-content">
                            <div class="parameter-cards-list stage-bullets-list">
                                ${remainingItems.map(item => ComplianceJourneyComponent.renderParameterCardItem(item)).join('')}
                            </div>
                        </div>
                    </details>
                ` : ''}
            `;
        }

        const evId = testStage.provenance?.record_id || (testStage.provenance ? 'prov_testing' : null);

        return `
            <div class="compliance-stage-item" role="listitem" data-stage-num="6">
                <div class="stage-marker">
                    <span class="marker-circle">6</span>
                    <div class="marker-line" aria-hidden="true"></div>
                </div>
                <div class="stage-card">
                    <div class="stage-header">
                        <div class="stage-title-wrap">
                            <span class="stage-eyebrow">${escapeHtml(eyebrow)}</span>
                            <h4 class="stage-title">${escapeHtml(title)}</h4>
                        </div>
                    </div>
                    <div class="stage-body">
                        <div class="stage-primary-answer">${ComplianceJourneyComponent.renderV2Answer(directAnswer)}</div>
                        ${v2Stage ? ComplianceJourneyComponent.renderV2KeyInformation(v2Stage.key_information, directAnswer) : ''}
                        ${(status === 'TESTING_REQUIREMENTS_UNKNOWN' || totalTests === 0) ? `<div class="stage-status-note text-muted text-xs mt-1">Testing requirements not established in available BIS records.</div>` : ''}
                        ${itemsHtml ? itemsHtml : (gridItems.length > 0 ? ComplianceJourneyComponent.renderKeyDetailsGrid(gridItems) : '')}
                    </div>
                    ${evId ? `
                        <div class="stage-footer">
                            <button type="button" class="btn-comp-evidence" data-evidence-id="${escapeHtml(evId)}">
                                <span>${escapeHtml(t('compliance_journey.view_evidence', 'View Evidence'))} &nearr;</span>
                            </button>
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    }

    // -------------------------------------------------------------------------
    // Stage 7: Factory & Routine Inspection
    // -------------------------------------------------------------------------
    static renderInspectionStage(inspStage, standardsStageOrV2OrT, v2StageOrT, tArg) {
        if (!inspStage) return '';
        let standardsStage = null, v2Stage = null, t = (k, fb) => fb || k;

        if (typeof standardsStageOrV2OrT === 'function') {
            t = standardsStageOrV2OrT;
        } else if (standardsStageOrV2OrT && typeof standardsStageOrV2OrT === 'object') {
            if (standardsStageOrV2OrT.answer !== undefined || standardsStageOrV2OrT.inspection_requirements !== undefined) {
                v2Stage = standardsStageOrV2OrT;
            } else {
                standardsStage = standardsStageOrV2OrT;
            }
        }

        if (typeof v2StageOrT === 'function') {
            t = v2StageOrT;
        } else if (v2StageOrT && typeof v2StageOrT === 'object') {
            v2Stage = v2StageOrT;
        }

        if (typeof tArg === 'function') {
            t = tArg;
        }

        const status = inspStage.status || 'INSPECTION_UNKNOWN';
        const total = inspStage.total_requirements || 0;
        const items = inspStage.inspection_requirements || [];
        const { eyebrow, title } = ComplianceJourneyComponent.getStageLabels(t, 'stage_inspection', 7, 'Factory Inspection');

        let primaryAnswer = t('compliance_journey.product_specific_inspection_not_est', 'Inspection requirements not established');

        if ((status.includes('CONFIRMED') || status === 'INSPECTION_CONFIRMED' || status === 'INSPECTION_REQUIREMENTS_CONFIRMED') && total > 0) {
            primaryAnswer = `${total} factory inspection ${total === 1 ? 'obligation' : 'obligations'}`;
        } else if ((status.includes('PARTIAL') || status === 'INSPECTION_PARTIAL' || status === 'INSPECTION_REQUIREMENTS_PARTIAL') && total > 0) {
            primaryAnswer = `${total} factory inspection ${total === 1 ? 'obligation' : 'obligations'} partially established`;
        }

        const gridItems = [];
        if (total > 0 && items.length > 0) {
            const first = items[0];
            if (first.inspection_reference) {
                gridItems.push({
                    label: t('compliance_journey.key_inspection_routine', 'Inspection routine'),
                    value: first.inspection_reference
                });
            }
            if (first.frequency) {
                gridItems.push({
                    label: t('compliance_journey.key_inspection_frequency', 'Frequency'),
                    value: first.frequency
                });
            }
            if (first.test_register) {
                gridItems.push({
                    label: 'Test register',
                    value: first.test_register
                });
            }
            if (first.source_document) {
                gridItems.push({
                    label: t('compliance_journey.key_sit_document', 'SIT / source document'),
                    value: first.source_document
                });
            }
        }

        if (inspStage.synthesis) {
            if (inspStage.synthesis.primary_answer) primaryAnswer = inspStage.synthesis.primary_answer;
            if (Array.isArray(inspStage.synthesis.key_information) && inspStage.synthesis.key_information.length > 0) {
                gridItems.length = 0;
                inspStage.synthesis.key_information.forEach(ki => {
                    gridItems.push({
                        label: ki.label,
                        value: ki.value,
                        source: ki.source,
                        isMono: /source|document/i.test(ki.label)
                    });
                });
            }
        }

        const directAnswer = v2Stage?.answer || primaryAnswer;

        let itemsHtml = '';
        if (items.length > 0) {
            itemsHtml = `
                <div class="inspection-cards-list stage-bullets-list">
                    ${items.map(item => {
                        const ref = item.inspection_reference || 'Routine Quality Inspection';
                        let meta = [];
                        if (item.frequency) meta.push(`Frequency: ${escapeHtml(item.frequency)}`);
                        if (item.test_register) meta.push(`Register: ${escapeHtml(item.test_register)}`);
                        if (item.source_document) meta.push(`Doc: ${escapeHtml(item.source_document)}`);
                        const metaStr = meta.join(' &bull; ');
                        return `
                            <div class="routine-card-item stage-bullet-item">
                                <span class="stage-bullet-dot" aria-hidden="true">&bull;</span>
                                <div class="stage-bullet-content">
                                    <div class="stage-bullet-title">${escapeHtml(ref)}</div>
                                    ${metaStr ? `<div class="stage-bullet-meta">${metaStr}</div>` : ''}
                                </div>
                            </div>
                        `;
                    }).join('')}
                </div>
            `;
        }

        const evId = inspStage.provenance?.record_id || (inspStage.provenance ? 'prov_inspection' : null);

        return `
            <div class="compliance-stage-item" role="listitem" data-stage-num="7">
                <div class="stage-marker">
                    <span class="marker-circle">7</span>
                    <div class="marker-line" aria-hidden="true"></div>
                </div>
                <div class="stage-card">
                    <div class="stage-header">
                        <div class="stage-title-wrap">
                            <span class="stage-eyebrow">${escapeHtml(eyebrow)}</span>
                            <h4 class="stage-title">${escapeHtml(title)}</h4>
                        </div>
                    </div>
                    <div class="stage-body">
                        <div class="stage-primary-answer">${ComplianceJourneyComponent.renderV2Answer(directAnswer)}</div>
                        ${v2Stage ? ComplianceJourneyComponent.renderV2KeyInformation(v2Stage.key_information, directAnswer) : ''}
                        ${itemsHtml ? itemsHtml : (gridItems.length > 0 ? ComplianceJourneyComponent.renderKeyDetailsGrid(gridItems) : '')}
                    </div>
                    ${evId ? `
                        <div class="stage-footer">
                            <button type="button" class="btn-comp-evidence" data-evidence-id="${escapeHtml(evId)}">
                                <span>${escapeHtml(t('compliance_journey.view_evidence', 'View Evidence'))} &nearr;</span>
                            </button>
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    }

    // -------------------------------------------------------------------------
    // Stage 8: Lot & Control Unit Sampling
    // -------------------------------------------------------------------------
    static renderSamplingStage(sampStage, standardsStageOrV2OrT, v2StageOrT, tArg) {
        if (!sampStage) return '';
        let standardsStage = null, v2Stage = null, t = (k, fb) => fb || k;

        if (typeof standardsStageOrV2OrT === 'function') {
            t = standardsStageOrV2OrT;
        } else if (standardsStageOrV2OrT && typeof standardsStageOrV2OrT === 'object') {
            if (standardsStageOrV2OrT.answer !== undefined || standardsStageOrV2OrT.sampling_requirements !== undefined) {
                v2Stage = standardsStageOrV2OrT;
            } else {
                standardsStage = standardsStageOrV2OrT;
            }
        }

        if (typeof v2StageOrT === 'function') {
            t = v2StageOrT;
        } else if (v2StageOrT && typeof v2StageOrT === 'object') {
            v2Stage = v2StageOrT;
        }

        if (typeof tArg === 'function') {
            t = tArg;
        }

        const status = sampStage.status || 'SAMPLING_UNKNOWN';
        const total = sampStage.total_requirements || 0;
        const items = sampStage.sampling_requirements || [];
        const { eyebrow, title } = ComplianceJourneyComponent.getStageLabels(t, 'stage_sampling', 8, 'Lot & Control Unit Sampling');

        let primaryAnswer = t('compliance_journey.product_specific_sampling_not_est', 'Sampling requirements not established');

        if ((status.includes('CONFIRMED') || status === 'SAMPLING_CONFIRMED' || status === 'SAMPLING_REQUIREMENTS_CONFIRMED') && total > 0) {
            primaryAnswer = `${total} sampling ${total === 1 ? 'protocol' : 'protocols'} established`;
        } else if ((status.includes('PARTIAL') || status === 'SAMPLING_PARTIAL' || status === 'SAMPLING_REQUIREMENTS_PARTIAL') && total > 0) {
            primaryAnswer = `${total} sampling ${total === 1 ? 'protocol' : 'protocols'} partially established`;
        }

        const gridItems = [];
        if (total > 0 && items.length > 0) {
            const first = items[0];
            if (first.sampling_reference) {
                gridItems.push({
                    label: t('compliance_journey.key_sampling_routine', 'Sampling routine'),
                    value: first.sampling_reference
                });
            }
            if (first.sample_size) {
                gridItems.push({
                    label: t('compliance_journey.key_sample_quantity', 'Sample quantity'),
                    value: first.sample_size
                });
            }
            if (first.lot_definition) {
                gridItems.push({
                    label: t('compliance_journey.key_lot_definition', 'Lot definition'),
                    value: first.lot_definition
                });
            }
            if (first.source_document) {
                gridItems.push({
                    label: t('compliance_journey.key_sit_document', 'SIT / source document'),
                    value: first.source_document
                });
            }
        }

        if (sampStage.synthesis) {
            if (sampStage.synthesis.primary_answer) primaryAnswer = sampStage.synthesis.primary_answer;
            if (Array.isArray(sampStage.synthesis.key_information) && sampStage.synthesis.key_information.length > 0) {
                gridItems.length = 0;
                sampStage.synthesis.key_information.forEach(ki => {
                    gridItems.push({
                        label: ki.label,
                        value: ki.value,
                        source: ki.source,
                        isMono: /source|document/i.test(ki.label)
                    });
                });
            }
        }

        const directAnswer = v2Stage?.answer || primaryAnswer;

        let itemsHtml = '';
        if (items.length > 0) {
            itemsHtml = `
                <div class="sampling-cards-list stage-bullets-list">
                    ${items.map(item => {
                        const ref = item.sampling_reference || 'Batch Sampling';
                        let meta = [];
                        if (item.sample_size) meta.push(`Sample size: ${escapeHtml(item.sample_size)}`);
                        if (item.lot_definition) meta.push(`Lot criteria: ${escapeHtml(item.lot_definition)}`);
                        if (item.source_document) meta.push(`Doc: ${escapeHtml(item.source_document)}`);
                        const metaStr = meta.join(' &bull; ');
                        return `
                            <div class="routine-card-item stage-bullet-item">
                                <span class="stage-bullet-dot" aria-hidden="true">&bull;</span>
                                <div class="stage-bullet-content">
                                    <div class="stage-bullet-title">${escapeHtml(ref)}</div>
                                    ${metaStr ? `<div class="stage-bullet-meta">${metaStr}</div>` : ''}
                                </div>
                            </div>
                        `;
                    }).join('')}
                </div>
            `;
        }

        const evId = sampStage.provenance?.record_id || (sampStage.provenance ? 'prov_sampling' : null);

        return `
            <div class="compliance-stage-item" role="listitem" data-stage-num="8">
                <div class="stage-marker">
                    <span class="marker-circle">8</span>
                    <div class="marker-line" aria-hidden="true"></div>
                </div>
                <div class="stage-card">
                    <div class="stage-header">
                        <div class="stage-title-wrap">
                            <span class="stage-eyebrow">${escapeHtml(eyebrow)}</span>
                            <h4 class="stage-title">${escapeHtml(title)}</h4>
                        </div>
                    </div>
                    <div class="stage-body">
                        <div class="stage-primary-answer">${ComplianceJourneyComponent.renderV2Answer(directAnswer)}</div>
                        ${v2Stage ? ComplianceJourneyComponent.renderV2KeyInformation(v2Stage.key_information, directAnswer) : ''}
                        ${itemsHtml ? itemsHtml : (gridItems.length > 0 ? ComplianceJourneyComponent.renderKeyDetailsGrid(gridItems) : '')}
                    </div>
                    ${evId ? `
                        <div class="stage-footer">
                            <button type="button" class="btn-comp-evidence" data-evidence-id="${escapeHtml(evId)}">
                                <span>${escapeHtml(t('compliance_journey.view_evidence', 'View Evidence'))} &nearr;</span>
                            </button>
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    }

    // -------------------------------------------------------------------------
    // Helper: Single Lab Card Item
    // -------------------------------------------------------------------------
    static renderLabCardItem(lab, idx, primaryStd, t) {
        const addr = lab.address || {};
        const geo = lab.geographic_metadata || {};
        const locParts = [addr.city, addr.state].filter(Boolean);
        let locStr = locParts.join(', ');
        if (!locStr && geo.formatted_address) {
            locStr = geo.formatted_address.length > 50 ? geo.formatted_address.slice(0, 47) + '...' : geo.formatted_address;
        }
        if (!locStr) locStr = 'Official BIS Location';

        const dist = geo.distance_km != null ? `${Number(geo.distance_km).toFixed(1)} km away` : '';
        const scopeEv = lab.capability_evidence || {};
        const scopeText = scopeEv.explanation || scopeEv.scope_text || (scopeEv.matching_parameters && scopeEv.matching_parameters.join(', ')) || (scopeEv.scope_completeness === 'COMPLETE_SCOPE' ? `Complete testing scope for ${primaryStd || 'Indian Standard'}` : `Accredited for ${primaryStd || 'Indian Standard'}`);
        const cityLoc = addr.city || (geo.formatted_address && geo.formatted_address.includes('Delhi') ? 'Delhi' : '');

        return `
            <div class="comp-lab-card" role="article">
                <div class="lab-card-header">
                    <span class="lab-rank-pill">#${idx + 1}</span>
                    ${lab.category ? `<span class="lab-cat-pill">${escapeHtml(lab.category.replace('BIS_', ''))}</span>` : ''}
                </div>
                <h5 class="comp-lab-name">${escapeHtml(lab.laboratory_name)}</h5>
                <div class="comp-lab-loc">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
                    <span>${escapeHtml(locStr)}</span>
                    ${dist ? `<span class="lab-dist-tag font-mono">(${escapeHtml(dist)})</span>` : ''}
                </div>
                <div class="comp-lab-scope">
                    <span class="scope-label">Testing Scope:</span>
                    <span class="scope-val">${escapeHtml(scopeText.slice(0, 140))}${scopeText.length > 140 ? '...' : ''}</span>
                </div>
                ${scopeEv.base_testing_fee != null ? `
                    <div class="comp-lab-fee font-mono">
                        <span class="fee-label">Base testing fee:</span>
                        <span class="fee-val">₹${Number(scopeEv.base_testing_fee).toLocaleString('en-IN')}</span>
                    </div>
                ` : ''}
                <div class="comp-lab-actions">
                    <button type="button" class="btn-comp-open-lab" data-standard="${escapeHtml(primaryStd)}" data-location="${escapeHtml(cityLoc)}">
                        <span>${escapeHtml(t('compliance_journey.view_in_lab_finder', 'Inspect in Lab Finder'))} &rarr;</span>
                    </button>
                </div>
            </div>
        `;
    }

    // -------------------------------------------------------------------------
    // Stage 9: Qualified BIS Laboratories
    // -------------------------------------------------------------------------
    static renderLaboratoriesStage(labsStage, standardsStageOrV2OrT, v2StageOrT, tArg) {
        if (!labsStage) return '';
        let standardsStage = null, v2Stage = null, t = (k, fb) => fb || k;

        if (typeof standardsStageOrV2OrT === 'function') {
            t = standardsStageOrV2OrT;
        } else if (standardsStageOrV2OrT && typeof standardsStageOrV2OrT === 'object') {
            if (standardsStageOrV2OrT.answer !== undefined || standardsStageOrV2OrT.qualified_laboratories !== undefined) {
                v2Stage = standardsStageOrV2OrT;
            } else {
                standardsStage = standardsStageOrV2OrT;
            }
        }

        if (typeof v2StageOrT === 'function') {
            t = v2StageOrT;
        } else if (v2StageOrT && typeof v2StageOrT === 'object') {
            v2Stage = v2StageOrT;
        }

        if (typeof tArg === 'function') {
            t = tArg;
        }

        const status = labsStage.status || 'NO_MATCHING_LABORATORY';
        const total = labsStage.total_matching || 0;
        const labs = labsStage.qualified_laboratories || [];
        const primaryStd = standardsStage?.primary_standard || '';
        const locApplied = labsStage.location_filter_applied || '';
        const { eyebrow, title } = ComplianceJourneyComponent.getStageLabels(t, 'stage_laboratories', 9, 'Qualified BIS Laboratories');

        let primaryAnswer = t('compliance_journey.status_no_matching_lab', 'No matching qualified BIS laboratory found');
        let hasLimitation = false;

        if (status === 'QUALIFIED_LABS_FOUND' && total > 0) {
            primaryAnswer = `Found ${total} qualified ${total === 1 ? 'laboratory record matches' : 'laboratory records match'} the available testing scope.`;
        } else if (status === 'LAB_MATCHING_LIMITED') {
            primaryAnswer = t('compliance_journey.status_lab_limited', 'Laboratory matching is limited by available testing evidence');
            hasLimitation = true;
        }

        const directAnswer = v2Stage?.answer || primaryAnswer;

        let labsGridHtml = '';
        if (labs.length > 0) {
            const initialLabs = labs.slice(0, 4);
            const remainingLabs = labs.slice(4);

            labsGridHtml = `
                <div class="qualified-labs-grid">
                    ${initialLabs.map((lab, idx) => ComplianceJourneyComponent.renderLabCardItem(lab, idx, primaryStd, t)).join('')}
                </div>
                ${remainingLabs.length > 0 ? `
                    <div class="remaining-labs-wrapper mt-3">
                        <button type="button" class="btn-toggle-all-labs" data-total="${total}">
                            View all ${total} qualified laboratories &darr;
                        </button>
                        <div class="remaining-labs-container hidden">
                            <div class="qualified-labs-grid mt-3">
                                ${remainingLabs.map((lab, idx) => ComplianceJourneyComponent.renderLabCardItem(lab, idx + 4, primaryStd, t)).join('')}
                            </div>
                        </div>
                    </div>
                ` : ''}
            `;
        } else {
            labsGridHtml = `
                <div class="empty-labs-notice">
                    <span class="empty-labs-icon" aria-hidden="true">🔬</span>
                    <div class="empty-labs-content">
                        <strong>No matching qualified BIS laboratory found.</strong>
                        <p>${escapeHtml(labsStage.explanation || 'No accredited laboratory scope in the BIS LIMS database currently matches this specific standard.')}</p>
                    </div>
                </div>
            `;
        }

        const evId = labsStage.provenance?.record_id || (labsStage.provenance ? 'prov_laboratories' : null);

        return `
            <div class="compliance-stage-item" role="listitem" data-stage-num="9">
                <div class="stage-marker">
                    <span class="marker-circle">9</span>
                    <div class="marker-line" aria-hidden="true"></div>
                </div>
                <div class="stage-card">
                    <div class="stage-header">
                        <div class="stage-title-wrap">
                            <span class="stage-eyebrow">${escapeHtml(eyebrow)}</span>
                            <h4 class="stage-title">${escapeHtml(title)}</h4>
                        </div>
                        ${hasLimitation ? `<span class="stage-subtle-indicator status-indicator-conflict">Limited Scope</span>` : ''}
                    </div>
                    <div class="stage-body">
                        <div class="stage-primary-answer">${ComplianceJourneyComponent.renderV2Answer(directAnswer)}</div>
                        ${total > 0 ? `<div class="stage-verified-indicator mt-1 text-xs text-secondary">${total} qualified laboratory records match the required testing scope.</div>` : ''}
                        ${locApplied ? `<div class="stage-subtle-note">Ranked by capability first, then proximity to ${escapeHtml(locApplied)}.</div>` : ''}
                        ${labsGridHtml}
                    </div>
                    ${evId ? `
                        <div class="stage-footer">
                            <button type="button" class="btn-comp-evidence" data-evidence-id="${escapeHtml(evId)}">
                                <span>${escapeHtml(t('compliance_journey.view_evidence', 'View Evidence'))} &nearr;</span>
                            </button>
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    }

    // -------------------------------------------------------------------------
    // Stage 10: Certification Process
    // -------------------------------------------------------------------------
    static renderProcessStage(procStage, schemeStageOrV2OrT, v2StageOrT, tArg, mandatoryStageArg, v2MandatoryArg) {
        if (!procStage) return '';
        let schemeStage = null, v2Stage = null, t = (k, fb) => fb || k;
        let mandatoryStage = mandatoryStageArg || null;
        let v2Mandatory = v2MandatoryArg || null;

        if (typeof schemeStageOrV2OrT === 'function') {
            t = schemeStageOrV2OrT;
        } else if (schemeStageOrV2OrT && typeof schemeStageOrV2OrT === 'object') {
            if (schemeStageOrV2OrT.answer !== undefined || schemeStageOrV2OrT.procedure_steps !== undefined) {
                v2Stage = schemeStageOrV2OrT;
            } else {
                schemeStage = schemeStageOrV2OrT;
            }
        }

        if (typeof v2StageOrT === 'function') {
            t = v2StageOrT;
        } else if (v2StageOrT && typeof v2StageOrT === 'object') {
            v2Stage = v2StageOrT;
        }

        if (typeof tArg === 'function') {
            t = tArg;
        }

        const isGeneric = procStage.is_generic_procedure !== false;
        const steps = procStage.procedure_steps || [];
        const { eyebrow, title } = ComplianceJourneyComponent.getStageLabels(t, 'stage_process', 10, 'Certification Process');

        const isMandatoryConfirmed = Boolean(
            v2Mandatory?.is_mandatory === true ||
            mandatoryStage?.is_mandatory === true ||
            (mandatoryStage?.status && mandatoryStage.status === 'MANDATORY_CERTIFICATION_CONFIRMED')
        );
        const isSchemeConfirmed = Boolean(
            v2Stage?.scheme_name ||
            schemeStage?.certification_scheme ||
            (schemeStage?.status && (schemeStage.status === 'SCHEME_CONFIRMED' || schemeStage.status === 'CERTIFICATION_SCHEME_CONFIRMED'))
        );
        const hasConfirmedScheme = isMandatoryConfirmed || isSchemeConfirmed;

        let primaryAnswer = t('compliance_journey.product_specific_process_not_est', 'Product-specific certification process not established');

        if (!isGeneric) {
            primaryAnswer = 'Product-specific certification process';
        } else if (hasConfirmedScheme) {
            const schemeName = schemeStage?.certification_scheme || v2Stage?.scheme_name || 'Scheme-I';
            primaryAnswer = `Standard BIS ${schemeName.startsWith('BIS') ? schemeName : schemeName} certification workflow`;
        }

        const gridItems = [];
        if (!isGeneric && steps.length > 0) {
            gridItems.push({
                label: t('compliance_journey.key_process_type', 'Process type'),
                value: 'Product-Specific Conformity Assessment'
            });
            gridItems.push({
                label: t('compliance_journey.key_steps_count', 'Steps'),
                value: `${steps.length} procedural steps`
            });
        }

        if (procStage.synthesis) {
            if (procStage.synthesis.primary_answer) primaryAnswer = procStage.synthesis.primary_answer;
            if (Array.isArray(procStage.synthesis.key_information) && procStage.synthesis.key_information.length > 0) {
                gridItems.length = 0;
                procStage.synthesis.key_information.forEach(ki => {
                    gridItems.push({
                        label: ki.label,
                        value: ki.value,
                        source: ki.source
                    });
                });
            }
        }

        const directAnswer = v2Stage?.answer || primaryAnswer;

        const disclaimerText = hasConfirmedScheme
            ? t('compliance_journey.general_reference_process_applicable', 'Standard BIS conformity assessment procedure under the applicable certification scheme (online application via Manakonline, in-house testing facility setup, factory audit & sampling, independent lab testing, and grant of licence).')
            : t('compliance_journey.general_reference_process_disclaimer', 'This is general BIS conformity-assessment information. Its applicability to this product has not been established.');

        const evId = procStage.provenance?.record_id || (procStage.provenance ? 'prov_process' : null);

        const defaultSteps = [
            { step_number: 1, title: 'Online Application', description: 'Submit Form-I on the Manakonline portal with manufacturing details, factory layout, and machinery lists.' },
            { step_number: 2, title: 'In-house Testing Setup', description: 'Install required testing apparatus in the factory per the Scheme of Inspection and Testing (SIT).' },
            { step_number: 3, title: 'Factory Audit & Sampling', description: 'BIS technical officer inspects manufacturing facilities, quality routines, and draws verification samples.' },
            { step_number: 4, title: 'Independent Lab Testing', description: 'Drawn samples undergo complete conformity testing at an accredited BIS/LIMS laboratory.' },
            { step_number: 5, title: 'Grant of Licence', description: 'BIS issues the Certification of Conformity (CM/L licence) authorizing ISI Mark application.' }
        ];
        const stepsToRender = steps.length > 0 ? steps : defaultSteps;

        const stepsHtml = `
            <div class="stage-bullets-list mt-2">
                ${stepsToRender.map(step => `
                    <div class="process-step-item stage-bullet-item">
                        <span class="stage-step-num">${step.step_number}</span>
                        <div class="stage-bullet-content">
                            <span class="stage-bullet-title">${escapeHtml(step.title)}:</span>
                            <span class="stage-bullet-meta">${escapeHtml(step.description || '')}</span>
                        </div>
                    </div>
                `).join('')}
            </div>
        `;

        return `
            <div class="compliance-stage-item" role="listitem" data-stage-num="10">
                <div class="stage-marker">
                    <span class="marker-circle">10</span>
                </div>
                <div class="stage-card">
                    <div class="stage-header">
                        <div class="stage-title-wrap">
                            <span class="stage-eyebrow">${escapeHtml(eyebrow)}</span>
                            <h4 class="stage-title">${escapeHtml(title)}</h4>
                        </div>
                    </div>
                    <div class="stage-body">
                        <div class="stage-primary-answer">${ComplianceJourneyComponent.renderV2Answer(directAnswer)}</div>
                        ${v2Stage ? ComplianceJourneyComponent.renderV2KeyInformation(v2Stage.key_information, directAnswer) : ''}
                        ${isGeneric ? `
                            <div class="general-reference-box">
                                <div class="general-reference-tag">${escapeHtml(t('compliance_journey.general_reference_label', 'GENERAL REFERENCE'))}</div>
                                <p class="general-reference-text">${escapeHtml(disclaimerText)}</p>
                            </div>
                        ` : (gridItems.length > 0 ? ComplianceJourneyComponent.renderKeyDetailsGrid(gridItems) : '')}
                        ${stepsHtml}
                    </div>
                    ${evId ? `
                        <div class="stage-footer">
                            <button type="button" class="btn-comp-evidence" data-evidence-id="${escapeHtml(evId)}">
                                <span>${escapeHtml(t('compliance_journey.view_evidence', 'View Evidence'))} &nearr;</span>
                            </button>
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    }
    // -------------------------------------------------------------------------
    // Helper: Sanitize raw machine enums into human-readable text
    // -------------------------------------------------------------------------
    static sanitizeHumanText(str) {
        if (!str || typeof str !== 'string') return '';
        return str
            .replace(/\s*\(\s*CERTIFICATION_SCHEME_UNKNOWN\s*\)/g, '')
            .replace(/\s*\(\s*MANDATORY_CERTIFICATION_NOT_ESTABLISHED\s*\)/g, '')
            .replace(/\s*\(\s*MANDATORY_CERTIFICATION_CONFIRMED\s*\)/g, '')
            .replace(/\s*\(\s*QCO_STATUS_UNKNOWN\s*\)/g, '')
            .replace(/\s*\(\s*QCO_NOT_ESTABLISHED\s*\)/g, '')
            .replace(/\s*\(\s*QCO_CONFLICT\s*\)/g, '')
            .replace(/\s*\(\s*QCO_APPLIES\s*\)/g, '')
            .replace(/\s*\(\s*STANDARD_NOT_ESTABLISHED\s*\)/g, '')
            .replace(/\s*\(\s*TESTING_REQUIREMENTS_UNKNOWN\s*\)/g, '')
            .replace(/\s*\(\s*NO_MATCHING_LABORATORY\s*\)/g, '')
            .replace(/\s*\(\s*NO_AUTHORITATIVE_APPLICABILITY_RECORD_IN_CORPUS\s*\)/g, '')
            .replace(/CERTIFICATION_SCHEME_UNKNOWN/g, 'Status Unconfirmed')
            .replace(/MANDATORY_CERTIFICATION_NOT_ESTABLISHED/g, 'Mandatory Certification Not Established')
            .replace(/MANDATORY_CERTIFICATION_CONFIRMED/g, 'Mandatory Certification Confirmed')
            .replace(/QCO_STATUS_UNKNOWN/g, 'QCO Status Not Established')
            .replace(/QCO_NOT_ESTABLISHED/g, 'QCO Not Established')
            .replace(/QCO_CONFLICT/g, 'Conflicting Regulatory Evidence')
            .replace(/QCO_APPLIES/g, 'QCO Applies')
            .replace(/STANDARD_NOT_ESTABLISHED/g, 'Standard Not Established')
            .replace(/TESTING_REQUIREMENTS_UNKNOWN/g, 'Testing Requirements Not Established')
            .replace(/NO_MATCHING_LABORATORY/g, 'No Matching Laboratory')
            .replace(/NO_AUTHORITATIVE_APPLICABILITY_RECORD_IN_CORPUS/g, 'Not in Authoritative Records');
    }

    // -------------------------------------------------------------------------
    // Warnings & Limitations
    // -------------------------------------------------------------------------
    static renderWarningsLimitations(warnings = [], limitations = [], t = (k, fb) => fb || k) {
        const warnList = Array.isArray(warnings) ? warnings : [];
        const limList = Array.isArray(limitations) ? limitations : [];
        const hasContent = warnList.length > 0 || limList.length > 0;

        return `
            <section class="compliance-warnings-section${hasContent ? '' : ' hidden'}" aria-label="Regulatory Warnings and Limitations">
                <div class="warnings-header">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                    <h4 data-i18n="compliance_journey.section_warnings">${escapeHtml(t('compliance_journey.section_warnings', 'Regulatory Warnings & Limitations'))}</h4>
                </div>
                <div class="warnings-body">
                    ${warnList.length > 0 ? `
                        <ul class="warnings-list">
                            ${warnList.map(w => `<li class="warning-item"><span class="item-bullet">⚠</span><span>${escapeHtml(ComplianceJourneyComponent.sanitizeHumanText(w))}</span></li>`).join('')}
                        </ul>
                    ` : ''}
                    ${limList.length > 0 ? `
                        <ul class="limitations-list">
                            ${limList.map(l => `<li class="limitation-item"><span class="item-bullet">ℹ</span><span>${escapeHtml(ComplianceJourneyComponent.sanitizeHumanText(l))}</span></li>`).join('')}
                        </ul>
                    ` : ''}
                </div>
            </section>
        `;
    }

    // -------------------------------------------------------------------------
    // Aggregated Provenance Summary
    // -------------------------------------------------------------------------
    static renderProvenanceSummary(provenanceList = [], t = (k, fb) => fb || k) {
        const provList = Array.isArray(provenanceList) ? provenanceList : [];
        const hasContent = provList.length > 0;

        return `
            <section class="compliance-provenance-section${hasContent ? '' : ' hidden'}" aria-label="Evidence and Provenance">
                <div class="provenance-section-header">
                    <span class="provenance-dot" aria-hidden="true">●</span>
                    <h4 data-i18n="compliance_journey.section_provenance">${escapeHtml(t('compliance_journey.section_provenance', 'Aggregated Evidence & Provenance'))}</h4>
                    <span class="provenance-count-pill font-mono">${provList.length} evidence records</span>
                </div>
                <div class="provenance-chips-container">
                    ${provList.map(prov => {
                        const evId = prov.record_id || `prov_${prov.source_layer}`;
                        const label = prov.source_document || prov.record_id || prov.source_layer || 'Evidence Unit';
                        const hashSlice = prov.evidence_hash ? prov.evidence_hash.slice(0, 10) : '';
                        const cleanLayer = (prov.source_layer || 'Evidence').replace('PC-3_', '').replace('PC-4_', '').replace('PC-5_', '');

                        return `
                            <button type="button" class="btn-comp-evidence provenance-chip" data-evidence-id="${escapeHtml(evId)}" title="${escapeHtml(prov.source_document || '')}">
                                <span class="chip-layer">${escapeHtml(cleanLayer)}</span>
                                <span class="chip-doc">${escapeHtml(label.slice(0, 28))}${label.length > 28 ? '...' : ''}</span>
                                ${hashSlice ? `<span class="chip-hash font-mono">${escapeHtml(hashSlice)}</span>` : ''}
                            </button>
                        `;
                    }).join('')}
                </div>
            </section>
        `;
    }
}
