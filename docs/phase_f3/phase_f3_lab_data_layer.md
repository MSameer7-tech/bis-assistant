# Phase F3: STEP 3 — BIS Laboratory Data & Retrieval Layer Report

**Authoritative Normative Intelligence & Deterministic Retrieval Specification**

---

## Executive Summary

Phase F3 Step 3 implements the **deterministic BIS LIMS Laboratory Data and Retrieval Layer**. 

Following the Phase F3 Step 1 live investigation and preserving all frozen baselines (Phases 12.B–12.E, F1, F2, F3 Step 2A, F3 Step 2B), this layer extracts, validates, normalizes, deduplicates, catalogs, and indexes authoritative BIS testing laboratory data directly from production BIS LIMS structures without LLMs, without external geocoding calls, and with zero synthetic assumptions.

> [!NOTE]
> **Dataset Evolution (Initial Subset vs Complete Expanded Catalog)**:
> The initial catalog built in Phase F3 Step 3 represented an initial validated subset of 24 laboratories, 149 scope records, and 133 Indian Standards.
> Under **Phase F3 Step 3E**, this dataset was fully expanded across all 30 directory pages to encompass all discoverable BIS facilities: **581 directory records discovered, 580 unique validated laboratories (10 BIS Owned, 431 Recognized, 140 Empanelled), 541 laboratories with active scopes, 39 laboratories with empty scopes, 6,327 normalized scope records, and 430,026 clause records across 1,264 Indian Standards**. Full details are documented in [`docs/phase_f3/phase_f3_lims_catalog_expansion.md`](phase_f3_lims_catalog_expansion.md).

---

## 1. BIS LIMS Source Endpoints & Architecture

The Bureau of Indian Standards operates the Laboratory Information Management System (**BIS LIMS**) at `https://lims.bis.gov.in`. The authoritative endpoints supported by this data layer include:

1. **Recognized Laboratories Directory**:
   - URL: `https://lims.bis.gov.in/home/labs/?page=1..22`
   - Scope: 431 commercial and industrial testing facilities accredited under the BIS Laboratory Recognition Scheme (LRS 2020).
   - Columns: `S.NO.`, `LAB CODE` (7-digit OSL code), `LAB NAME`, `ADDRESS`, `CONTACT PERSON`, `CONTACT NUMBER`, `EMAIL`, `VALIDITY DATE`, `VIEW SCOPE` (`/home_lab_scope/<internal_id>/`).
2. **BIS Owned Laboratories Directory**:
   - URL: `https://lims.bis.gov.in/home/bis_labs/`
   - Scope: 10 statutory central, regional, and branch laboratories owned directly by BIS (Central Lab Sahibabad, NRL Mohali, WRL Mumbai, SRL Chennai, ERL Kolkata, etc.).
   - Columns: `S.NO.`, `LAB CODE` (`-`), `LAB NAME`, `ADDRESS`, `CONTACT PERSON`, `CONTACT NUMBER`, `EMAIL`, `VIEW SCOPE`.
3. **Empanelled Laboratories Directory**:
   - URL: `https://lims.bis.gov.in/home/empaneled_labs/?page=1..7`
   - Scope: 140 autonomous, CSIR, and governmental laboratories recognized for specific testing needs (CIMFR, NPL, BARC, IITs, etc.).
4. **Laboratory Scope & Fee Schedule**:
   - URL: `https://lims.bis.gov.in/home_lab_scope/<internal_id>/`
   - Header Container: `<div class="ml-2">` holding exact registered lab name (`<h3>`), full address (`<h5 class="mb-0">`), phone, and email.
   - Master Table: `#review_lab_list` / `table.customTable.table-bordered` listing accredited Indian Standards, product titles, grades, base testing fees, and validity dates.
   - Clause Modal Table: Nested `#assign_audit_list_table` within `#testingChargesModal<row_id>` detailing clause-by-clause testing charges, clause exclusions, and effective dates.

---

## 2. Existing Components Reused & Engineering Rationale

In accordance with Step 2 instructions, existing project components were thoroughly inspected and reused:

| Component | Location | Reused Logic | Rationale |
| :--- | :--- | :--- | :--- |
| `normalize_standard` | `ai/acquisition/lims_scope/scope_parser.py` | Regex normalization of standard strings, part, section, and year | Preserves consistent IS normalization across project phases. |
| `parse_testing_charge` | `ai/acquisition/lims_scope/scope_parser.py` | Numeric extraction of base INR amounts and tax inclusion detection | Tested regex extraction of currency strings (e.g. `₹ 14,000`, `1210`). |
| `hash_row` | `ai/acquisition/lims_scope/scope_parser.py` | Deterministic row hashing via SHA-256 | Reliable collision-resistant row identification. |
| Immutable Scope Cache | `data/raw/immutable/lims_scope/` | 26 cached production HTML scope files with SHA-256 manifests | Enables 100% offline, deterministic testing and verification without internet dependencies. |

### Bug Corrections & New Architecture
- **Phase 11.1 Column Alignment**: Phase 11.1 crawler had a column off-by-one bug where `cells[1]` (the public numeric lab code e.g. `8102006`) was mapped to `lab_name`, leaving addresses null. `LimsExtractor` dynamically maps headers (`LAB CODE`, `LAB NAME`, `ADDRESS`, `VALIDITY DATE`) to prevent column misalignments across different LIMS page layouts.
- **Nested Modal Isolation**: Phase 11.1 dumped modal table text into the outer table's test method field. `LimsExtractor` parses the outer table row first, extracts the modal DOM separately, and creates structured `ClauseRecord` entries.

---

## 3. Data Schemas: Raw vs Normalized Layers

### A. Raw Layer (`ai/lims/models.py`)

Preserves the exact server-side rendered HTML and cell text verbatim:
- `RawLimsLabRecord`: `raw_id`, `internal_id`, `lab_code`, `lab_name`, `category`, `raw_address`, `contact_person`, `phone`, `email`, `validity_date`, `source_url`, `retrieved_at`, `raw_html_sha256`, `extraction_metadata`.
- `RawLimsScopeRecord`: `raw_scope_id`, `internal_lab_id`, `raw_standard`, `raw_product`, `raw_grade_type_size`, `raw_fee_text`, `raw_validity_date`, `raw_remark`, `raw_modal_html`, `source_url`, `source_sha256`, `retrieved_at`.

### B. Normalized Search Layer (`ai/lims/models.py`)

Immutable, strictly typed, validated records for downstream search and matching:
- `NormalizedLimsLab`: `internal_id` (int), `lab_code` (str), `lab_name` (str), `category` (`LabCategory`), `original_address` (EXACT, UNTOUCHED verbatim address), `normalized_state`, `normalized_district`, `normalized_city`, `pincode`, `contact_person`, `phone`, `email`, `recognition_status`, `validity_date`, `source_url`, `retrieved_at`, `provenance_sha256`.
- `NormalizedLimsScope`: `scope_id`, `internal_lab_id`, `lab_code`, `standard_number`, `standard_title`, `edition_year`, `product`, `grade_type_size`, `base_testing_fee`, `currency` ("INR"), `is_complete_scope` (bool), `clauses` (`List[ClauseRecord]`), `excluded_clauses` (`List[str]`), `validity_date`, `remark`, `source_url`, `source_sha256`.
- `ClauseRecord`: `clause_number`, `is_excluded`, `fee_amount`, `effective_date`, `remark`, `raw_text`.

---

## 4. Validation, Deduplication & Immutability Rules

### Deterministic Validation (`ai/lims/validator.py`)
No records are ever silently discarded. Every rejected record is logged with an explicit, traceable reason:
- `MISSING_LAB_NAME`: Laboratory name is empty or `< 3` characters.
- `MALFORMED_CATEGORY`: Category does not match `LabCategory` enum.
- `MISSING_ADDRESS`: Address is empty or `< 4` characters.
- `MISSING_LAB_IDENTIFIERS`: Both `internal_id` and `lab_code` are missing.
- `INCONSISTENT_SOURCE_REFERENCE`: Missing `source_url`.
- `UNBOUND_LABORATORY_IDENTITY`: Scope record references an unknown `internal_lab_id`.
- `MISSING_STANDARD_IDENTIFIER`: Scope standard string is empty.
- `INVALID_STANDARD_IDENTIFIER`: Scope string cannot be resolved to a standard number.

### Deduplication Engine (`LimsDeduplicationEngine`)
- **Laboratories**: Keyed primarily by `internal_id`. If the same `internal_id` is encountered across multiple pages:
  - If name and category are identical: Grouped as a `CLEAN_DUPLICATE` with references preserved.
  - If name or category conflicts: Retained and flagged as `FLAGGED_FOR_REVIEW_CONFLICT` (NEVER merged with fuzzy guesses).
- **Scope Records**: Keyed by `(internal_lab_id, standard_number, grade_type_size)`. Duplicate standard scopes are identified and logged.

### Address & Geographic Boundaries
- `original_address` is treated as **authoritative statutory evidence** and is **NEVER modified, overwritten, or substituted with geocoded addresses**.
- Geocoded coordinates (Geoapify from Step 2A) remain strictly in a separate geographic metadata layer and are NOT treated as BIS statutory evidence.
- Zero bulk geocoding was executed during Step 3.

---

## 5. Deterministic Retrieval Interface (`ai/lims/retrieval_layer.py`)

`LimsRetrievalLayer` provides in-memory, index-backed deterministic queries:
- `get_laboratory_by_id(internal_id: int) -> Optional[NormalizedLimsLab]`
- `get_laboratory_by_code(lab_code: str) -> Optional[NormalizedLimsLab]`
- `search_laboratories(name, lab_code, category, state, city, standard_number, limit=50) -> List[NormalizedLimsLab]`
- `get_laboratories_for_standard(standard_number, category=None, state=None) -> List[Dict[str, Any]]`
- `get_scope_for_laboratory(internal_lab_id: int) -> List[NormalizedLimsScope]`
- `get_statistics() -> Dict[str, Any]`

---

## 6. Actual Record Counts & Catalog Artifacts

From the authoritative raw inputs processed:

| Metric | Actual Count | Source / Provenance |
| :--- | :---: | :--- |
| **Total Raw Laboratories Discovered** | **28** | Scope page headers + Step 2A authoritative labs |
| **Total Unique Validated Laboratories** | **24** | Deduplicated via `LimsDeduplicationEngine` |
| • *BIS-Owned Laboratories* | **1** | BIS Central Laboratory Sahibabad (`BIS_CL`) |
| • *BIS-Recognized Laboratories* | **19** | Private & commercial accredited facilities |
| • *BIS-Empanelled Laboratories* | **4** | CSIR-CIMFR, CSIR-NPL, CIFT, CIHT |
| **Total Raw Scope Records Extracted** | **165** | Parsed from 26 cached scope pages |
| **Total Unique Validated Scope Records** | **149** | Clean unique scopes (16 duplicate rows deduplicated) |
| **Total Unique Indian Standards Associated** | **133** | Unique normative standards accredited |
| **Total Clause Breakdown Records Extracted** | **5,879** | Modal clause rows (`#assign_audit_list_table`) |
| **Records Rejected / Incomplete** | **0** | 100% validation pass rate |

### Catalog Outputs (`data/catalog/phase_f3_lims/`)
- `laboratories_raw.jsonl`: 28 raw laboratory JSONL records.
- `laboratories_normalized.jsonl`: 24 normalized laboratory records.
- `scope_raw.jsonl`: 165 raw scope records.
- `scope_normalized.jsonl`: 149 normalized scope records with full clause breakups.
- `validation_report.json`: Rejection report, conflict logs, and catalog manifest.
- `catalog_manifest.json`: Ingestion summary and category breakdown.

---

## 7. Verification & Automated Test Results

The test suite in `tests/phase_f3/test_lims_data_layer.py` was executed with 100% pass rate:
- `test_01_directory_html_parsing`: PASSED
- `test_02_category_preservation`: PASSED
- `test_03_identifier_preservation`: PASSED
- `test_04_original_address_preservation`: PASSED
- `test_05_scope_parsing_and_standard_association`: PASSED
- `test_06_modal_clause_preservation`: PASSED
- `test_07_validation_missing_fields`: PASSED
- `test_08_validation_invalid_standards`: PASSED
- `test_09_deduplication_clean_and_conflict`: PASSED
- `test_10_retrieval_layer_name_and_code_search`: PASSED
- `test_11_retrieval_layer_category_and_state_filtering`: PASSED
- `test_12_retrieval_layer_standard_filtering`: PASSED
- `test_13_provenance_integrity`: PASSED
- `test_14_no_llm_or_geocoding_dependency`: PASSED
- `test_15_catalog_persistence_and_loading`: PASSED

### Cumulative Test Suite Pass
- **Phase F3 Suite** (`tests/phase_f3/`): **34/34 passing in 0.25s** (Geocoding Service 11/11, Map Component 8/8, LIMS Data Layer 15/15).
- **Phase 12 Baselines** (`tests/phase12/`): **19/19 passing in 3.39s** (Phase 12.E Production 7/7, F2 Orchestrator 12/12).

---

## 8. Files Changed & Files Intentionally Untouched

### New Files Created (Step 3)
- `ai/lims/__init__.py`: Package export definitions.
- `ai/lims/models.py`: Authoritative BIS LIMS data models.
- `ai/lims/extractor.py`: HTML table & modal clause extractor.
- `ai/lims/validator.py`: Deterministic validation & deduplication engine.
- `ai/lims/retrieval_layer.py`: Deterministic indexed retrieval layer.
- `scripts/phase_f3_lims_data_layer.py`: Catalog builder and verification runner.
- `tests/phase_f3/test_lims_data_layer.py`: 15-test automated validation suite.
- `data/catalog/phase_f3_lims/`: Output catalogs (`laboratories_raw.jsonl`, `laboratories_normalized.jsonl`, `scope_raw.jsonl`, `scope_normalized.jsonl`, `validation_report.json`, `catalog_manifest.json`).
- `docs/phase_f3/phase_f3_lab_data_layer.md`: This comprehensive specification report.

### Files Intentionally Untouched
- `ai/services/geocoding_service.py` (Phase F3 Step 2A - preserved)
- `frontend/mapComponent.js` (Phase F3 Step 2B - preserved)
- `frontend/map_test.html` (Phase F3 Step 2B - preserved)
- `scripts/phase12_e_production_rag.py` (Phase 12.E - preserved, serving port 3000)
- `scripts/phase12_f2_orchestrator.py` (Phase F2 - preserved)
- `data/corpus_versions/v2.0/` & all Phase 12 RAG vector/BM25 indices (100% frozen)
- `tests/phase12/` test suites (100% frozen & passing)

---

## 9. Strict STOP Boundary Compliance

As mandated by project constraints:
- **NO** product-to-lab semantic matching was implemented.
- **NO** standard-to-lab distance ranking was implemented.
- **NO** bulk Geoapify geocoding was triggered.
- **NO** Lab Finder API or frontend UI was modified.
- **NO** changes were made to Phase 12 RAG, F1, or F2.
- Antigravity execution stops completely after Step 3.
