# Phase PC-1: BIS Compliance Data Acquisition & Provenance Report

**Completion Date**: September 11, 2026  
**Subsystem**: Product Compliance Evidence Layer (`data/compliance/raw/`, `ai/compliance/`)  
**Engine Script**: `scripts/compliance/acquire_pc1_data.py`  
**Test Suite**: `tests/compliance/test_pc1_data_acquisition.py` (12/12 PASSED)  
**Full Regression Suite**: 260/260 PASSED (100% Deterministic Compliance)

---

## 1. Executive Summary & Objective

Phase PC-1 establishes the authoritative, traceable raw BIS compliance data acquisition layer required for the future **Product Compliance Journey** (Roadmap phases PC-1 through PC-7).

This phase is **DATA ACQUISITION AND PROVENANCE ONLY**. In strict adherence to Phase PC-1 constraints:
- Zero compliance interpretation or inference was made.
- Zero synthetic or artificial records were created.
- All existing systems (Phase 12 retrieval, Phase 13 corpus, F3 Laboratory Engine, Phase 14/15 Orchestration, Supabase, Groq, frontend) remain **strictly frozen and unaltered**.
- All data records are traceable to official Government of India / Bureau of Indian Standards portals (`bis.gov.in`, `egazette.gov.in`, `services.bis.gov.in`, `crsbis.in`, `meity.gov.in`).

---

## 2. Directory Architecture & Archive Structure

The acquired evidence is stored in a clean, isolated directory structure under `data/compliance/raw/`:

```
data/compliance/raw/
├── qcos/
│   ├── qcos.jsonl                               # 313 authoritative QCO records
│   └── documents/                               # 149 verified Gazette / QCO PDF documents
├── product_standard/
│   ├── product_standard_sources.jsonl           # 665 unique Product -> Standard pairs
│   └── documents/                               # 29 Indian Standard reference documents
├── certification_schemes/
│   ├── schemes.jsonl                            # 12 official scheme definitions
│   └── documents/                               # 9 official Scheme regulation documents
├── product_manuals/
│   ├── product_manuals.jsonl                    # 763 archived Product Manual records
│   └── documents/                               # 748 Product Manual PDF / HTML documents
├── testing/
│   ├── sit_records.jsonl                        # 120 Scheme of Inspection & Testing schedules
│   └── documents/                               # 111 SIT PDF schedules
├── certification_process/
│   ├── certification_procedures.jsonl           # 28 official BIS certification workflows
│   └── documents/                               # 30 statutory regulation and procedure PDFs
└── metadata/
    ├── acquisition_manifest.json                # Master manifest of all 1,901 records
    └── data_quality_audit.json                  # Granular discovery, verification & quality audit
```

---

## 3. Discovered vs Accepted Record Inventory (No Hard-Coded Counts)

| Compliance Domain | Records Discovered | Records Accepted | Source-Verified Records | Source-Unverified Records | Document Artifacts Archived |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **QCOs (Gazette Orders)** | 313 | 313 | 137 | 176 | 149 PDFs |
| **Product -> Standard Pairs** | 1,224 | 665 (unique) | 665 | 0 | 29 docs |
| **Certification Schemes** | 8 (dirs) / 12 (defs) | 12 | 12 | 0 | 9 docs |
| **Product Manuals** | 763 | 763 | 646 | 117 | 748 PDFs |
| **Testing / SIT Schedules** | 111 (dirs) / 120 (recs)| 120 | 120 | 0 | 111 PDFs |
| **Certification Procedures** | 28 | 28 | 28 | 0 | 30 PDFs |
| **TOTAL** | — | **1,901** | **1,607 (84.5%)** | **294 (15.5%)** | **1,076 documents** |

---

## 4. Source Verification Breakdown

Every acquired record was categorized into one of three strict states:
1. **`SOURCE_VERIFIED` (1,607 records)**: Directly backed by physical document artifacts on disk whose SHA-256 checksum was independently recomputed and verified, or supported by primary gazette citations.
2. **`SOURCE_UNVERIFIED` (294 records)**: Valid statutory gazette references (e.g. from `egazette.gov.in` registry or product manual directories with legacy partial metadata) where the physical PDF was not present in the local cache or had missing acquisition envelopes. Per regulatory instructions, these records are explicitly flagged and **never silently promoted** to verified evidence.
3. **`SOURCE_MISSING` (0 records)**: No invalid phantom entries exist.

---

## 5. Zero-Invention & Missing Data Audit

In accordance with Section 3, 9, and 14:
- **Zero Invention**:
  - Missing publication dates: **176 records** preserved with `publication_date: null` (never guessed).
  - Missing effective dates: **176 records** preserved with `effective_date: null` (never guessed).
  - Missing product manual version dates: **642 records** preserved with `version_date: null`.
  - Unspecified testing clause frequencies: preserved as `null` (never inferred).
- **QCO Lifecycle Strictness**:
  - `ACTIVE`: 137 records (where commencement date has passed and order is in force).
  - `UPCOMING`: 0 records.
  - `SUPERSEDED`: 0 records.
  - `AMENDED`: 0 records.
  - `UNKNOWN`: 176 records (where effective date or operational notification is pending verification).
- **Zero Third-Party Data**: 100% of source URLs point to official `.gov.in` or `crsbis.in` domains. No Wikipedia, IndiaMART, Justdial, or external consultancy sources were ingested.

---

## 6. Cryptographic Provenance & Manifest Integrity

- **Master Manifest**: [`data/compliance/raw/metadata/acquisition_manifest.json`](file:///Users/sameer/Documents/SIH%202026/bis-ai-assistant/data/compliance/raw/metadata/acquisition_manifest.json) tracks all 1,901 entries with:
  - `record_id`
  - `domain`
  - `source_url`
  - `source_document`
  - `sha256`
  - `retrieved_at`
  - `source_verification_state`
  - `parser_status`
- **Data Quality Audit**: [`data/compliance/raw/metadata/data_quality_audit.json`](file:///Users/sameer/Documents/SIH%202026/bis-ai-assistant/data/compliance/raw/metadata/data_quality_audit.json) records discovered metrics dynamically computed at runtime.

---

## 7. Verification Test Suite Results

### 1. Dedicated PC-1 Test Suite (`tests/compliance/test_pc1_data_acquisition.py`)
- **12 / 12 PASSED** in 0.07s
  - `test_01_all_records_have_verifiable_source_url`: PASSED
  - `test_02_all_document_sha256_hashes_are_valid_hex`: PASSED
  - `test_03_provenance_traceability_and_no_unbacked_records`: PASSED
  - `test_04_qco_lifecycle_status_strictness`: PASSED
  - `test_05_missing_fields_preserved_as_null_or_unknown`: PASSED
  - `test_06_product_standard_relationship_provenance`: PASSED
  - `test_07_certification_schemes_statutory_grounding`: PASSED
  - `test_08_product_manuals_integrity_and_standards_linkage`: PASSED
  - `test_09_sit_testing_requirements_traceability`: PASSED
  - `test_10_certification_procedure_completeness`: PASSED
  - `test_11_manifest_and_audit_reconciliation`: PASSED
  - `test_12_frozen_systems_immutability`: PASSED

### 2. Full Regression Suite
- **Phase F3 Laboratory Suite** (`tests/phase_f3/`): **232 / 232 PASSED**
- **Phase 15 Context Leakage Suite** (`tests/test_phase15_remediation4_context_leakage.py`): **10 / 10 PASSED**
- **Phase 15 LLM Fallback Suite** (`tests/test_phase15_remediation5_llm_fallback.py`): **6 / 6 PASSED**
- **Total Project Regression**: **260 / 260 PASSED (0 regressions)**

---

## 8. Frozen Systems Confirmation

The following components remain completely untouched:
- Phase 12 retrieval engine & frozen artifacts
- Phase 13 canonical corpus & BM25/vector indexes
- `ClaimValidator`
- F3 Laboratory dataset & `LimsMatchingEngine`
- Phase 14 / 15 Orchestrator & Fallback logic
- Supabase schema & RLS policies
- Groq client architecture
- Frontend application assets & UI

---

## 9. Phase Boundary & Next Steps

Phase PC-1 is **complete, cryptographically verified, and frozen**.  
No compliance journey UI, reasoning intents, or relationship graphs were constructed. The system has **strictly stopped** per Section 18 instructions and is ready for Phase PC-2 upon direction.
