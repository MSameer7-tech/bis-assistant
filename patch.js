const fs = require('fs');
const file = 'frontend/complianceJourneyComponent.js';
let content = fs.readFileSync(file, 'utf8');

const newRenderLayout = `    renderLayout() {
        const t = this.t.bind(this);
        this.container.innerHTML = \`
<div class="compliance-layout" role="region" aria-label="Product Compliance Journey Workspace">
  <!-- Page Header -->
  <header class="compliance-topbar centered">
    <div class="compliance-title-group">
      <div class="compliance-eyebrow">
        <span class="compliance-eyebrow-dot"></span>
        <span data-i18n="compliance_journey.title">\${escapeHtml(t('compliance_journey.title', 'PRODUCT COMPLIANCE JOURNEY'))}</span>
      </div>
      <h2 class="compliance-heading" data-i18n="compliance_journey.heading">
        \${escapeHtml(t('compliance_journey.heading', 'Find your BIS requirements.'))}
      </h2>
      <p class="compliance-heading-sub" data-i18n="compliance_journey.heading_sub">
        \${escapeHtml(t('compliance_journey.heading_sub', 'Describe your product, enter an Indian Standard, or ask a compliance question.'))}
      </p>
    </div>
  </header>

  <!-- Main Centered Workspace (shown when no results) -->
  <div id="complianceInitialState" class="compliance-workspace-centered">
    <div class="compliance-main-card workspace-panel">
      <form id="complianceSearchForm" class="compliance-search-form" novalidate>
        
        <!-- Natural Language Query: large textarea -->
        <div class="compliance-query-row workspace-query">
          <label for="compInputQuery" class="compliance-form-label primary" data-i18n="compliance_journey.field_query">\${escapeHtml(t('compliance_journey.field_query', 'What do you want to know?'))}</label>
          <div class="compliance-textarea-wrapper">
            <textarea id="compInputQuery" class="compliance-query-textarea compact"
              placeholder="\${escapeHtml(t('compliance_journey.field_query_placeholder_long', 'Describe your product or ask a compliance question...'))}"
              autocomplete="off" spellcheck="false" rows="3"></textarea>
          </div>
        </div>

        <!-- Action Row -->
        <div class="compliance-action-row">
            <!-- Structured Inputs: 3-column grid -->
            <div class="compliance-form-grid compact-grid">
              <div class="compliance-form-group">
                <label for="compInputProduct" class="compliance-form-label secondary" data-i18n="compliance_journey.field_product">\${escapeHtml(t('compliance_journey.field_product', 'Product'))}</label>
                <input type="text" id="compInputProduct" class="compliance-text-input compact" placeholder="\${escapeHtml(t('compliance_journey.field_product_placeholder', 'PVC pipes, ceiling fan'))}" autocomplete="off" spellcheck="false" />
              </div>
              <div class="compliance-form-group">
                <label for="compInputStandard" class="compliance-form-label secondary" data-i18n="compliance_journey.field_standard">\${escapeHtml(t('compliance_journey.field_standard', 'Indian Standard'))}</label>
                <input type="text" id="compInputStandard" class="compliance-text-input font-mono compact" placeholder="\${escapeHtml(t('compliance_journey.field_standard_placeholder', 'IS 4985, IS 374'))}" autocomplete="off" spellcheck="false" />
              </div>
              <div class="compliance-form-group">
                <label for="compInputLocation" class="compliance-form-label secondary" data-i18n="compliance_journey.field_location">\${escapeHtml(t('compliance_journey.field_location', 'Location'))}</label>
                <input type="text" id="compInputLocation" class="compliance-text-input compact" placeholder="\${escapeHtml(t('compliance_journey.field_location_placeholder', 'Delhi, Mumbai'))}" autocomplete="off" spellcheck="false" />
              </div>
            </div>

            <!-- Generate Button -->
            <div class="compliance-submit-wrapper">
              <button type="submit" id="btnComplianceSubmit" class="btn-compliance-submit compact-action" aria-label="Generate Compliance Journey">
                <span id="btnComplianceText" data-i18n="compliance_journey.btn_generate">\${escapeHtml(t('compliance_journey.btn_generate', 'Generate journey →'))}</span>
                <div id="compSpinner" class="compliance-spinner hidden" aria-hidden="true"></div>
              </button>
            </div>
        </div>
      </form>
    </div>

    <!-- Example Chips -->
    <div class="compliance-examples-section lightweight">
      <span class="compliance-examples-label" data-i18n="compliance_journey.example_queries_label">\${escapeHtml(t('compliance_journey.example_queries_label', 'Try an example'))}</span>
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
        \`;
    }`;

// Replace the renderLayout block
const regex = /renderLayout\(\)\s*\{[\s\S]*?\n    \}\n/m;
content = content.replace(regex, newRenderLayout + '\n');
fs.writeFileSync(file, content, 'utf8');
