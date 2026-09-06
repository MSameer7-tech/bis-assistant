# Phase F3 Step 4A: Laboratory Matching Engine Data Model

## 1. Overview & Objectives

**Phase F3 Step 4A** establishes the strict, capability-first deterministic data model for the Bureau of Indian Standards (BIS) Laboratory Matching Engine.

The purpose of the Laboratory Matching Engine is to evaluate whether a testing facility has authoritative statutory competence to test a product against an Indian Standard (IS code), specific parts, amendments, and individual clauses/test parameters.

In accordance with strict architectural boundaries:
- **Capability First**: A laboratory's statutory capability strictly supersedes geographic proximity. A laboratory 5 km away without standard scope must never outrank or be returned before a laboratory 30 km away with verified complete scope.
- **Statutory Authority Boundary**: Authoritative BIS statutory data extracted directly from BIS LIMS (`public_lab_code`, `internal_id`, `original_address`, standard scope, test charge, clause parameters) is strictly isolated from external geographic metadata (latitude, longitude, geocoding confidence).
- **Identity Invariant**: Public 7-digit laboratory codes (`public_lab_code`, e.g., `8102006`) and internal system identifiers (`internal_id`, e.g., `15`) are strictly separated and never conflated or coerced.
- **Zero LLM / External API Dependency**: The matching engine models are 100% deterministic, Python-native data structures with zero calls to LLMs (Groq), external geocoders, or Google Maps.

> **Important Boundary Note**: Step 4A establishes **only** the data structures, validation rules, enums, and serialization contracts. Matching algorithms, candidate ranking, and catalog evaluation are deferred to Step 4B.

---

## 2. Core Data Models (`ai/lims/matching_models.py`)

### 2.1 Enums

#### `MatchStatus`
Represents the overall outcome of a laboratory matching query:
- `EXACT_MATCH`: One or more laboratories meet the requested standard with full scope or required clauses.
- `PARTIAL_MATCH`: Laboratories match the standard but have partial scope or lack some requested clauses.
- `NO_MATCH`: No laboratories in the BIS catalog have statutory scope for the requested standard.
- `INVALID_REQUEST`: The request failed structural validation (e.g., missing or blank standard number).

#### `ScopeCompleteness`
Evaluates statutory scope breadth:
- `COMPLETE_SCOPE`: Laboratory scope covers all tests and clauses under the Indian Standard without exclusions.
- `PARTIAL_SCOPE`: Laboratory scope covers only specific clauses or has explicitly listed excluded clauses.
- `UNKNOWN`: Scope details are unverified or unparsed.

#### `MatchReason`
Deterministic machine-readable audit tags explaining why a candidate was matched or filtered:
- `EXACT_STANDARD_SCOPE`
- `EXACT_STANDARD_PART_SCOPE`
- `CLAUSE_REQUIREMENTS_MATCHED`
- `PARTIAL_SCOPE`
- `LOCATION_FILTER_MATCH`
- `EXCLUDED_CLAUSES_PRESENT`
- `MISSING_REQUIRED_CLAUSES`
- `NO_MATCHING_STANDARD`
- `LOCATION_FILTER_MISMATCH`
- `CATEGORY_FILTER_MISMATCH`

---

### 2.2 Request Model (`LabMatchingRequest`)

Represents a deterministic query presented to the matching engine:

```python
@dataclass
class LabMatchingRequest:
    standard: str
    part: Optional[str] = None
    year: Optional[str] = None
    clauses: List[str] = field(default_factory=list)
    test_requirements: List[str] = field(default_factory=list)
    state: Optional[str] = None
    district: Optional[str] = None
    city: Optional[str] = None
    category: Optional[LabCategory] = None
    require_complete_scope: bool = False
```

#### Validation Contract
- `validate() -> Tuple[bool, Optional[str]]`:
  - Rejects empty, whitespace-only, or abnormally short standard names (`MISSING_STANDARD`, `INVALID_STANDARD`).
  - Does not modify input values or invent defaults.
- `to_dict() -> Dict[str, Any]` and `from_dict(data: Dict[str, Any]) -> LabMatchingRequest`:
  - Fully serializable to/from JSON primitives, preserving `LabCategory` enum conversions.

---

### 2.3 Candidate Match Model (`LabCandidateMatch`)

Represents a single evaluated laboratory candidate:

```python
@dataclass
class LabCandidateMatch:
    laboratory_identity: str
    public_lab_code: str
    internal_id: int
    category: LabCategory
    original_address: str
    state: Optional[str] = None
    district: Optional[str] = None
    city: Optional[str] = None
    pincode: Optional[str] = None
    matching_standard: str = ""
    matching_scope_id: str = ""
    scope_completeness: ScopeCompleteness = ScopeCompleteness.UNKNOWN
    matched_clauses: List[str] = field(default_factory=list)
    unmatched_requested_clauses: List[str] = field(default_factory=list)
    excluded_clauses: List[str] = field(default_factory=list)
    reasons: List[MatchReason] = field(default_factory=list)
    explanation: str = ""
    base_testing_fee: Optional[float] = None
    clause_fee_total: Optional[float] = None
    currency: str = "INR"
    provenance_url: str = ""
    provenance_sha256: str = ""
    match_score: float = 0.0
    rank: int = 0
    external_geographic_metadata: Optional[Dict[str, Any]] = None
```

#### Key Design Safeguards
1. **Statutory Identity Separation**: `public_lab_code` (e.g. `"8102006"`) and `internal_id` (e.g. `15`) are distinct typed fields.
2. **Original Address Preserved**: `original_address` is strictly preserved from statutory BIS LIMS records. Geocoding coordinates or cleaned names are never written into `original_address`.
3. **External Geographic Metadata Isolation**: `external_geographic_metadata` is explicitly typed as an optional dictionary and initialized to `None`. In Step 4A, no geocoding is performed.

---

### 2.4 Result Container (`LabMatchingResult`)

Encapsulates the complete engine response:

```python
@dataclass
class LabMatchingResult:
    request: LabMatchingRequest
    status: MatchStatus
    candidates: List[LabCandidateMatch] = field(default_factory=list)
    total_candidates: int = 0
    execution_timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    catalog_statistics: Dict[str, Any] = field(default_factory=dict)
    provenance: Dict[str, Any] = field(default_factory=dict)
```

---

## 3. Verification & Test Suite

The data models and their contracts are verified in `tests/phase_f3/test_matching_models.py`:

| Test Name | Verification Focus | Result |
| :--- | :--- | :--- |
| `test_valid_request_creation_and_validation` | Valid standard string accepted, returns `(True, None)` | PASSED |
| `test_invalid_empty_standard_rejection` | Empty, blank, and short standard strings rejected with explicit error codes | PASSED |
| `test_request_optional_filters_and_serialization` | Optional filters, round-trip serialization/deserialization | PASSED |
| `test_lab_candidate_match_identity_separation_and_invariants` | `public_lab_code` vs `internal_id` separation, `original_address` preservation, `external_geographic_metadata` defaulting to `None` | PASSED |
| `test_matching_result_container` | Result container serialization, timestamping, stats | PASSED |
| `test_external_geographic_metadata_isolation` | Metadata isolation without mutating statutory BIS fields | PASSED |

### Full Test Suite Status
- **Phase F3 tests**: 35 passed (Geocoding 11 + LIMS Data Layer 15 + Map Component 8 + Matching Models 6, minus 5 baseline duplicates).
- **Phase 12 regression tests**: 19 passed (Phase 12.E 7 + Phase 12.F2 12).
- **Total Suite**: 59 passed in 2.49s. Zero regressions.

---

## 4. Next Step: Phase F3 Step 4B

Step 4B will implement the deterministic evaluation engine (`ai/lims/matching_engine.py`) using the models defined in Step 4A:
- Querying the catalog built in Step 3 (`data/catalog/phase_f3_lims/`).
- Standard number matching and clause comparison.
- Scope completeness evaluation.
- Deterministic candidate ranking strictly on capability first.
