# Phase PC-3: Product → Standard → QCO → Certification Scheme Relationship Engine Report

## Executive Summary

Phase PC-3 of the BIS AI Assistant Product Compliance Journey has been successfully implemented as an **offline, deterministic, provenance-preserving relationship engine**. It links products, standards, QCOs, regulatory requirements, Product Manuals, and certification schemes using exclusively the authoritative evidence established in PC-1 (`data/compliance/raw/`) and normalized in PC-2 (`data/compliance/normalized/`).

### Core Invariants Enforced Without Exception:
1. **Standard ≠ Mandatory Certification**:
   - The existence of an Indian Standard does **not** establish mandatory certification.
   - Products with an identified standard but no authoritative QCO are marked `MANDATORY_CERTIFICATION_NOT_ESTABLISHED` (never "NO", never "VOLUNTARY").
2. **Missing Evidence ≠ Negative Evidence**:
   - Missing QCOs, missing effective dates, unlinked product manuals, and unestablished certification schemes remain explicitly unknown or unestablished. No negative claims are manufactured.
3. **Amended QCO Safety**:
   - `QCO_AMENDED` orders only establish mandatory certification when authoritative evidence confirms the order is operative and in force as of the evaluation reference time.
4. **Scheme Applicability Honesty**:
   - While 12 statutory certification schemes are defined in PC-2, zero product-specific scheme applicability mappings existed in authoritative evidence. Exactly **665 of 665 (100%)** composite records maintain `CERTIFICATION_SCHEME_UNKNOWN` with zero synthetic defaults to Scheme I or ISI Mark.
5. **Deterministic Conflict Disclosure**:
   - All 105 normalized conflicts (1 notification, 6 QCO status, 98 Product Manual version) are preserved with `UNRESOLVED_DISCLOSED` policy. Conflicted QCOs propagate directly into `QCO_CONFLICT` status without silent synthetic resolution.
6. **Byte-Reproducible Execution**:
   - Two consecutive rebuilds produce bit-identical files with 100% matching SHA-256 digests.
7. **Strict Phase Boundary & Subsystem Immutability**:
   - PC-4 (testing/process interpretation), PC-5 (API/orchestrator), PC-6 (UI), and PC-7 (validation) remain strictly untouched.
   - Phase 12 RAG, Phase 13 corpus, ClaimValidator, F3 Laboratory Engine/data, Phase 14/15 orchestrator/fallback, Supabase, Groq, and frontend assets remain 100% frozen.

---

## 1. Relationship Datasets Accounting

All five relationship datasets and their associated manifests are written in JSON Lines format under `data/compliance/relationships/`:

| Dataset Filename | Description | Records | Unique Keys | Source Layer | Provenance Coverage |
| :--- | :--- | :---: | :---: | :---: | :---: |
| `product_standard_relationships.jsonl` | Product → Indian Standard pairs | **665** | 665 unique `(product_name, standard_number)` | `PC-2_NORMALIZED` | 100.0% |
| `standard_qco_relationships.jsonl` | Standard → QCO regulatory links | **431** | 431 unique `standard_normalized` | `PC-2_NORMALIZED` | 100.0% |
| `qco_requirement_relationships.jsonl` | QCO → Statutory Requirements | **313** | 313 unique `qco_id` | `PC-2_NORMALIZED` | 100.0% |
| `certification_scheme_relationships.jsonl` | Standard / Product → Scheme links | **665** | 665 unique `relationship_id` | `PC-2_NORMALIZED` | 100.0% |
| `compliance_relationships.jsonl` | Unified Composite Compliance records | **665** | 665 unique `(product_name, standard_normalized)` | `PC-2_NORMALIZED` | 100.0% |
| **TOTAL RELATIONSHIP RECORDS** | — | **2,739** | — | — | **100.0% (0 orphans)** |

---

## 2. Empirical Verification & Quality Audit Breakdown

The quality audit generated dynamically in `relationship_quality_audit.json` records the exact state across all dimensions:

### A. Mandatory Certification Requirement Breakdown (665 Composite Relationships)
- **`MANDATORY_CERTIFICATION_NOT_ESTABLISHED`**: **398 records (59.8%)**
  - Products where an Indian Standard is identified, but no authoritative QCO exists in the corpus.
- **`MANDATORY_CERTIFICATION_CONFIRMED`**: **222 records (33.4%)**
  - 95 records backed by active in-force QCOs (`QCO_APPLIES`)
  - 127 records backed by operative amended QCOs (`QCO_AMENDED`)
- **`QCO_CONFLICT`**: **37 records (5.6%)**
  - Standards affected by contradictory regulatory orders in `conflicts.jsonl` (e.g. `IS 374`, `IS 15298`, `IS 4246`, `IS 1293`, `IS 15644`, `IS 4151`).
- **`QCO_STATUS_UNKNOWN`**: **8 records (1.2%)**
  - Products whose QCO regulatory status or commencement date remains unverified in authoritative records (e.g. `IS 15750` for refrigerators).
- **Total**: **665 records**

### B. Standard-to-QCO Status Breakdown (431 Unique Standards)
Across all 431 unique standards present in the compliance universe:
- `QCO_STATUS_UNKNOWN`: **190 standards** (standards in QCO records whose operative status is unverified)
- `QCO_NOT_ESTABLISHED`: **181 standards** (standards identified from product lists or PMs with no QCO record)
- `QCO_APPLIES`: **31 standards** (active in-force QCOs)
- `QCO_AMENDED`: **23 standards** (operative amended QCOs)
- `QCO_CONFLICT`: **6 standards** (`IS 374`, `IS 15298`, `IS 4246`, `IS 1293`, `IS 15644`, `IS 4151`)
- **Total**: **431 unique standards**

### C. Product Manual Availability Breakdown (665 Composite Relationships)
- **`PRODUCT_MANUAL_NOT_FOUND`**: **340 records (51.1%)**
  - No BIS Product Manual available for the product's standard in the corpus.
- **`PRODUCT_MANUAL_CONFLICT`**: **187 records (28.1%)**
  - Standards with multiple divergent Product Manual versions recorded in `conflicts.jsonl`.
- **`PRODUCT_MANUAL_AVAILABLE`**: **138 records (20.8%)**
  - Exactly one authoritative Product Manual archived and verified.
- **Critical Proof Case**: 86 records have `PRODUCT_MANUAL_AVAILABLE` but `QCO_NOT_ESTABLISHED` (e.g., `electrical conduit` / `IS 1653`). This confirms that the engine never falsely infers mandatory certification from the mere presence of an official Product Manual.

### D. Certification Scheme Applicability Breakdown
- **`CERTIFICATION_SCHEME_UNKNOWN`**: **665 records (100.0%)**
  - `applicable_scheme_code`: `null`
  - `applicability_basis`: `NO_AUTHORITATIVE_APPLICABILITY_RECORD_IN_CORPUS`
  - Zero fabricated mappings to Scheme I, Scheme II, or ISI Mark.

---

## 3. Artifact Hashes & Bitwise Integrity

All relationship datasets have their SHA-256 digests cryptographically sealed in `relationship_manifest.json`:

- `product_standard_relationships.jsonl`: `2bc3142c47d8b058ec36a2e925b3664a4c070c4ec6bf7ed39274b05b7e1bc555`
- `standard_qco_relationships.jsonl`: `dbb7484df6f295b931cb91494548e658cb0a8f828a2a7aa15c7e0c96c568ae70`
- `qco_requirement_relationships.jsonl`: `d7c09f480ff65b6e88afb8bfa3bbb8b6a9b17f32a89aa3374dc8a7b0ad383355`
- `certification_scheme_relationships.jsonl`: `21a7648ff37ee022960bbad8cf78605c03d35d170d65edea5944817dcd323ee2`
- `compliance_relationships.jsonl`: `7e56c96c4aec96a54a160bf5b1a7ea38979fd382cb8d790c25d8108b38776d1a`

---

## 4. Test Verification Suite Results

The Phase PC-3 test suite `tests/compliance/test_pc3_relationship_engine.py` covers all 15 adversarial test scenarios:

- `test_01_product_with_verified_standard`: PASSED
- `test_02_product_with_standard_but_no_qco`: PASSED
- `test_03_product_with_qco_confirmed`: PASSED
- `test_04_product_with_qco_status_unknown`: PASSED
- `test_05_product_affected_by_conflicting_qcos`: PASSED
- `test_06_qco_with_missing_effective_date`: PASSED
- `test_07_standard_with_multiple_pm_versions`: PASSED
- `test_08_product_with_no_established_scheme`: PASSED
- `test_09_no_false_inference_standard_implies_mandatory`: PASSED
- `test_10_no_false_inference_pm_implies_mandatory`: PASSED
- `test_11_no_false_inference_scheme_definition_implies_applicability`: PASSED
- `test_12_provenance_and_lineage_completeness`: PASSED
- `test_13_deterministic_deduplication`: PASSED
- `test_14_byte_deterministic_rebuild`: PASSED
- `test_15_frozen_system_immutability`: PASSED

### Full Multi-Phase Regression Results
- **All Compliance Tests (PC-1, PC-2, PC-3)**: **43 passed** in 0.54s
- **Phase 15 Remediation & F3 Lab Finder Suite**: **248 passed** in 37.19s
- **Grand Total**: **291 passed**, 0 regressions.

---

## 5. Phase Boundary & Freeze Notice

Phase PC-3 is **100% complete and frozen**. 
- Relationship models in `ai/compliance/relationship_models.py` are sealed.
- Builder pipeline in `scripts/compliance/build_pc3_relationships.py` is sealed.
- All datasets in `data/compliance/relationships/` are sealed.
- **Do NOT begin Phase PC-4 (Testing + Certification Process Engine) without explicit user authorization.**
