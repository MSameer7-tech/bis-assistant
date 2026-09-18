# Phase PC-5: Product Compliance Journey Orchestrator + API Report

## Executive Summary

Phase PC-5 of the BIS AI Assistant Product Compliance Journey implements the **unified backend orchestration layer and API** (`POST /api/compliance/journey`). It combines:
1. **Frozen PC-3**: Product -> Indian Standard -> QCO -> Mandatory Certification -> Certification Scheme relationships
2. **Frozen PC-4**: Testing -> Inspection -> Sampling -> Certification Process relationships
3. **Frozen F3**: BIS Laboratory Finder (via approved Python interface `execute_search`)

into a single, deterministic, provenance-preserving Product Compliance Journey.

### Target Flow
$$\text{Product} \longrightarrow \text{Indian Standard} \longrightarrow \text{QCO Status} \longrightarrow \text{Mandatory Certification} \longrightarrow \text{Scheme} \longrightarrow \text{Testing} \longrightarrow \text{Inspection} \longrightarrow \text{Sampling} \longrightarrow \text{Qualified BIS Lab} \longrightarrow \text{Process}$$

### Non-Negotiable Compliance Invariants Enforced Without Exception:
1. **Standard != Mandatory Certification**:
   - The existence of an Indian Standard does not establish mandatory certification. Products without an authoritative QCO remain `MANDATORY_CERTIFICATION_NOT_ESTABLISHED` (never "NO", never "VOLUNTARY").
2. **Testing Evidence != Mandatory Certification**:
   - The existence of confirmed testing specifications (SIT) does not alter or upgrade regulatory status. Products with confirmed tests but active QCO conflicts (e.g. `IS 374` ceiling fans, `IS 1293` plugs) strictly retain `mandatory_certification_status == QCO_CONFLICT`.
3. **Missing Evidence != Negative Evidence**:
   - Absent QCOs, missing dates, unestablished schemes, or missing testing records are marked `UNKNOWN` or `NOT_ESTABLISHED`. No negative claims are manufactured.
4. **Scheme Applicability Honesty**:
   - Exactly 100% of products maintain `CERTIFICATION_SCHEME_UNKNOWN` with zero synthetic defaults to Scheme I or ISI Mark.
5. **Generic Process != Product Process**:
   - Generic Scheme I certification procedures (28 records in PC-2) are never stamped onto individual products as confirmed processes. `CERTIFICATION_PROCESS_CONFIRMED` is strictly 0 across all products; reference procedures are clearly labeled as generic material.
6. **Capability Precedes Proximity**:
   - F3 laboratory qualification strictly evaluates BIS testing capability and scope before applying geographic proximity ranking. An unqualified nearby lab is never returned.
7. **Never Empty Journey**:
   - The API returns all 10 compliance stages with explicit statuses (`UNKNOWN`, `NOT_ESTABLISHED`, `NO_MATCHING_LABORATORY`). It never collapses unknown into false and never omits stages.
8. **Standard Precedence**:
   - When an explicit Indian Standard designation (e.g. `IS 4985`) is provided in the request or query, it strictly takes precedence over ambiguous product keywords.
9. **Zero LLM / Groq Regulatory Decisions**:
   - 100% deterministic execution. Zero LLM calls are made for standard, QCO, scheme, testing, lab, or process decisions.
10. **Strict Subsystem Immutability**:
    - PC-1, PC-2, PC-3, PC-4 datasets, manifests, and hashes remain 100% byte-identical.
    - F3 Laboratory Finder qualification engine and catalog data remain 100% frozen.
    - Phase 12-15 pipelines, Groq, Supabase, and frontend remain 100% untouched.

---

## 1. API Contracts & Endpoints

The compliance router is mounted at prefix `/api/compliance` in `backend/app.py`:

| Endpoint | Method | Purpose | Input Model | Response Model |
| :--- | :---: | :--- | :--- | :--- |
| `/api/compliance/journey` | `POST` | Primary compliance journey query | `ComplianceJourneyRequest` | `ComplianceJourneyResponse` |
| `/api/compliance/health` | `GET` | Health check & dataset accounting | None | JSON Health Object |
| `/api/compliance/metadata` | `GET` | PC-3/PC-4/F3 integration metadata & hashes | None | JSON Metadata Object |

### Request Model (`ComplianceJourneyRequest`):
```json
{
  "product": "ceiling fan",
  "standard": "IS 374",
  "location": "Delhi",
  "query": "I manufacture ceiling fans in Delhi"
}
```
*All fields are optional, but at least one must provide usable input. An empty request cleanly returns `INVALID_REQUEST` without crashing.*

---

## 2. Ten Structured Compliance Stages

Every response from `POST /api/compliance/journey` provides the complete 10-stage structured journey:

### Stage 1: Product Identification (`product`)
- **Statuses**: `PRODUCT_IDENTIFIED`, `AMBIGUOUS_PRODUCT`, `PRODUCT_NOT_ESTABLISHED`
- Resolves colloquial product phrases ("I manufacture timber doors", "we manufacture PVC pipes", "my product is a ceiling fan") deterministically using prefix stripping, singular/plural stemming, and controlled synonym expansion.
- Discloses all candidate matches when ambiguous (e.g. `PVC pipes` matching `IS 4985` and `IS 13592`).

### Stage 2: Applicable Indian Standards (`applicable_standards`)
- **Statuses**: `STANDARDS_IDENTIFIED`, `STANDARD_NOT_ESTABLISHED`
- Explicit IS designations take strict precedence over ambiguous product text.
- Preserves all applicable standards when a product maps to multiple standards (e.g. `automotive vehicles` preserving both `IS 15633` and `IS 15636`).

### Stage 3: QCO / Regulatory Status (`regulatory_status`)
- **Statuses**: `QCO_APPLIES`, `QCO_AMENDED`, `QCO_STATUS_UNKNOWN`, `QCO_CONFLICT`, `QCO_NOT_ESTABLISHED`
- Consumes PC-3 relationship states verbatim without re-interpretation.
- Exposes gazette notification numbers, effective dates, QCO IDs, and conflict IDs.

### Stage 4: Mandatory Certification Status (`mandatory_certification`)
- **Statuses**: `MANDATORY_CERTIFICATION_CONFIRMED`, `MANDATORY_CERTIFICATION_NOT_ESTABLISHED`, `QCO_STATUS_UNKNOWN`, `QCO_CONFLICT`
- Explicitly distinguishes "mandatory certification not established" from voluntary certification.

### Stage 5: Certification Scheme Applicability (`certification_scheme`)
- **Status**: `CERTIFICATION_SCHEME_UNKNOWN` (100% baseline)
- Discloses that while statutory schemes exist, no product-specific scheme mapping is established in authoritative records.

### Stage 6: Required Testing (`testing`)
- **Statuses**: `TESTING_REQUIREMENTS_CONFIRMED`, `TESTING_REQUIREMENTS_PARTIAL`, `TESTING_REQUIREMENTS_UNKNOWN`
- Consumes PC-4 testing records. Exposes individual test parameters, test methods, explicit clause numbers (e.g. `Clause 10.4`), frequencies, sampling references, and source documents.

### Stage 7: Factory & Routine Inspection (`inspection`)
- **Statuses**: `INSPECTION_REQUIREMENTS_CONFIRMED`, `INSPECTION_REQUIREMENTS_PARTIAL`, `INSPECTION_REQUIREMENTS_UNKNOWN`
- Consumes PC-4 inspection records. Exposes test registers, calibration routines, and inspection schedules.

### Stage 8: Lot & Control Unit Sampling (`sampling`)
- **Statuses**: `SAMPLING_REQUIREMENTS_CONFIRMED`, `SAMPLING_REQUIREMENTS_PARTIAL`, `SAMPLING_REQUIREMENTS_UNKNOWN`
- Consumes PC-4 sampling records. Exposes sample sizes, lot definitions, and sampling methods.

### Stage 9: Qualified BIS Laboratories (`laboratories`)
- **Statuses**: `QUALIFIED_LABS_FOUND`, `NO_MATCHING_LABORATORY`, `LAB_MATCHING_LIMITED`, `LAB_MATCHING_UNAVAILABLE`
- Integrates directly with the frozen F3 Laboratory Finder via `execute_search(...)`.
- **Capability evaluated before proximity**: Unqualified laboratories in the requested city are never recommended.
- Marks `LAB_MATCHING_LIMITED` when testing specifications are unestablished for the standard.
- Cleanly returns `NO_MATCHING_LABORATORY` with total_matching: 0 when no recognized lab exists for a standard.

### Stage 10: Certification Process Requirements (`certification_process`)
- **Statuses**: `CERTIFICATION_PROCESS_PARTIAL`, `CERTIFICATION_PROCESS_UNKNOWN`
- Never promotes generic Scheme I guidelines into confirmed product-specific processes (`CERTIFICATION_PROCESS_CONFIRMED` remains 0).

### Cross-Cutting Sections:
- **`provenance`**: Aggregates `RelationshipProvenance` objects across all stages, linking source layers (`PC-2_NORMALIZED`, `PC-3_RELATIONSHIPS`, `F3_LAB_FINDER`), record IDs, documents, URLs, and evidence hashes.
- **`warnings`** & **`limitations`**: Explicitly discloses regulatory caveats, QCO conflicts, unestablished schemes, and missing evidence.

---

## 3. Adversarial Test Suite Verification

The Phase PC-5 test suite (`tests/compliance/test_pc5_compliance_journey.py`) implements all 32 required adversarial scenarios:

- `test_01_product_with_confirmed_standard`: PASSED
- `test_02_explicit_is_number_overrides_ambiguous_product`: PASSED
- `test_03_multiple_applicable_standards_preserved`: PASSED
- `test_04_no_standard_established`: PASSED
- `test_05_confirmed_qco`: PASSED
- `test_06_qco_unknown`: PASSED
- `test_07_qco_conflict`: PASSED
- `test_08_mandatory_certification_not_established`: PASSED
- `test_09_scheme_applicability_unknown`: PASSED
- `test_10_testing_confirmed`: PASSED
- `test_11_testing_partial`: PASSED
- `test_12_testing_unknown`: PASSED
- `test_13_inspection_status_preserved`: PASSED
- `test_14_sampling_status_preserved`: PASSED
- `test_15_certification_process_partial`: PASSED
- `test_16_certification_process_unknown`: PASSED
- `test_17_generic_process_not_promoted_to_product_specific`: PASSED
- `test_18_testing_does_not_imply_mandatory_certification`: PASSED
- `test_19_pc3_regulatory_states_remain_unchanged`: PASSED
- `test_20_pc4_testing_states_remain_unchanged`: PASSED
- `test_21_f3_qualification_is_actually_used`: PASSED
- `test_22_f3_capability_precedes_proximity`: PASSED
- `test_23_nearby_but_unqualified_lab_is_not_recommended`: PASSED
- `test_24_no_qualified_laboratory_handled_cleanly`: PASSED
- `test_25_provenance_completeness`: PASSED
- `test_26_unknown_stages_remain_explicit`: PASSED
- `test_27_no_empty_journey`: PASSED
- `test_28_deterministic_repeated_request`: PASSED
- `test_29_pc3_files_remain_byte_identical`: PASSED
- `test_30_pc4_files_remain_byte_identical`: PASSED
- `test_31_frozen_f3_files_remain_unchanged`: PASSED
- `test_32_zero_llm_groq_regulatory_decisions`: PASSED

---

## 4. Full Regression Verification & System Integrity

1. **Full Compliance Test Suite (PC-1 through PC-5)**:
   - **93 passed**, 0 failed in 4.62s.
2. **Frozen Subsystem Immutability**:
   - PC-3 manifest hashes verified 100% bitwise identical.
   - PC-4 manifest hashes verified 100% bitwise identical.
   - F3 catalog manifest and lab data verified 100% intact.
   - Phase 12-15 regression suites verified passing.
   - Zero LLM / Groq calls executed during compliance journey resolution.

---

## 5. Phase Boundary & Freeze Notice

Phase PC-5 is **100% complete and frozen**.
- Do NOT begin Phase PC-6 (Compliance Journey UI) without explicit user authorization.
- Do NOT modify the existing BIS AI Assistant frontend.
- Do NOT begin PC-7.