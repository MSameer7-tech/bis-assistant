"""
Phase F3 Step 3: Deterministic BIS LIMS Validation and Deduplication Engine.

Invariants:
- Never silently discard invalid or incomplete records (every rejection has an explicit reason).
- Do not merge two laboratories merely because names or addresses look similar.
- Authoritative BIS identifiers (internal_id, lab_code) are preferred.
- Unresolvable duplicates are retained and flagged for review rather than inventing merge decisions.
- original_address is preserved exactly.
"""

import re
import hashlib
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple, Any, Set

from ai.lims.models import (
    LabCategory,
    ClauseRecord,
    RawLimsLabRecord,
    RawLimsScopeRecord,
    NormalizedLimsLab,
    NormalizedLimsScope,
    RejectedRecord,
)
from ai.lims.extractor import (
    extract_state_from_address,
    extract_pincode,
    LimsExtractor,
    clean_text,
    sha256_text,
)
from ai.acquisition.lims_scope.scope_parser import (
    normalize_standard,
    parse_testing_charge,
)


class LimsValidator:
    """Deterministic validation and normalization engine for BIS LIMS records."""

    @staticmethod
    def validate_and_normalize_lab(
        raw_lab: RawLimsLabRecord
    ) -> Tuple[Optional[NormalizedLimsLab], Optional[RejectedRecord]]:
        now_ts = datetime.now(timezone.utc).isoformat()

        # 1. Missing lab name
        name = clean_text(raw_lab.lab_name)
        if not name or len(name) < 3:
            return None, RejectedRecord(
                record_type="LABORATORY",
                raw_identifier=raw_lab.raw_id,
                rejection_reason="MISSING_LAB_NAME: Laboratory name is empty or too short (<3 chars).",
                raw_data=raw_lab.to_dict(),
                timestamp=now_ts
            )

        # 2. Malformed category
        try:
            category_enum = LabCategory(raw_lab.category)
        except (ValueError, KeyError):
            return None, RejectedRecord(
                record_type="LABORATORY",
                raw_identifier=raw_lab.raw_id,
                rejection_reason=f"MALFORMED_CATEGORY: Category '{raw_lab.category}' is not a valid LabCategory.",
                raw_data=raw_lab.to_dict(),
                timestamp=now_ts
            )

        # 3. Missing address
        raw_address = clean_text(raw_lab.raw_address)
        if not raw_address or len(raw_address) < 4:
            return None, RejectedRecord(
                record_type="LABORATORY",
                raw_identifier=raw_lab.raw_id,
                rejection_reason="MISSING_ADDRESS: Address is empty or insufficient (<4 chars).",
                raw_data=raw_lab.to_dict(),
                timestamp=now_ts
            )

        # 4. Missing laboratory identifiers (must have at least internal_id or lab_code)
        internal_id = raw_lab.internal_id
        lab_code = clean_text(raw_lab.lab_code) if raw_lab.lab_code else None

        if internal_id is None and not lab_code:
            return None, RejectedRecord(
                record_type="LABORATORY",
                raw_identifier=raw_lab.raw_id,
                rejection_reason="MISSING_LAB_IDENTIFIERS: Both internal_id and lab_code are absent.",
                raw_data=raw_lab.to_dict(),
                timestamp=now_ts
            )

        # 5. Inconsistent source reference
        if not raw_lab.source_url:
            return None, RejectedRecord(
                record_type="LABORATORY",
                raw_identifier=raw_lab.raw_id,
                rejection_reason="INCONSISTENT_SOURCE_REFERENCE: source_url is missing.",
                raw_data=raw_lab.to_dict(),
                timestamp=now_ts
            )

        # If internal_id is missing, derive deterministic pseudo-id from lab_code
        if internal_id is None:
            # Deterministic integer hash
            internal_id = int(hashlib.md5(lab_code.encode()).hexdigest()[:7], 16)

        if not lab_code:
            lab_code = f"{category_enum.value}_{internal_id}"

        # Deterministic search normalization (DOES NOT ALTER original_address)
        state = extract_state_from_address(raw_address)
        pincode = extract_pincode(raw_address)

        # City extraction heuristic
        city = None
        addr_parts = [p.strip() for p in raw_address.split(",")]
        if len(addr_parts) >= 2:
            candidate = addr_parts[-2] if addr_parts[-1].strip().isdigit() else addr_parts[-1]
            if len(candidate) > 2 and not any(char.isdigit() for char in candidate):
                city = candidate

        # Provenance SHA-256
        provenance_payload = f"{internal_id}|{lab_code}|{name}|{raw_address}|{raw_lab.source_url}"
        prov_sha = sha256_text(provenance_payload)

        norm_lab = NormalizedLimsLab(
            internal_id=internal_id,
            lab_code=lab_code,
            lab_name=name,
            category=category_enum,
            original_address=raw_address,
            normalized_state=state,
            normalized_district=None,
            normalized_city=city,
            pincode=pincode,
            contact_person=raw_lab.contact_person,
            phone=raw_lab.phone,
            email=raw_lab.email,
            recognition_status="ACTIVE",
            validity_date=raw_lab.validity_date,
            source_url=raw_lab.source_url,
            retrieved_at=raw_lab.retrieved_at,
            provenance_sha256=prov_sha,
            scope_status=raw_lab.extraction_metadata.get("scope_status", "SCOPE_AVAILABLE")
        )
        return norm_lab, None

    @staticmethod
    def validate_and_normalize_scope(
        raw_scope: RawLimsScopeRecord,
        lab_lookup: Dict[int, NormalizedLimsLab]
    ) -> Tuple[Optional[NormalizedLimsScope], Optional[RejectedRecord]]:
        now_ts = datetime.now(timezone.utc).isoformat()

        # 1. Unbound lab identity
        if raw_scope.internal_lab_id not in lab_lookup:
            return None, RejectedRecord(
                record_type="SCOPE",
                raw_identifier=raw_scope.raw_scope_id,
                rejection_reason=f"UNBOUND_LABORATORY_IDENTITY: internal_lab_id {raw_scope.internal_lab_id} not found in validated laboratories.",
                raw_data=raw_scope.to_dict(),
                timestamp=now_ts
            )

        parent_lab = lab_lookup[raw_scope.internal_lab_id]

        # 2. Missing standard identifier
        raw_std = clean_text(raw_scope.raw_standard)
        if not raw_std:
            return None, RejectedRecord(
                record_type="SCOPE",
                raw_identifier=raw_scope.raw_scope_id,
                rejection_reason="MISSING_STANDARD_IDENTIFIER: raw_standard is empty.",
                raw_data=raw_scope.to_dict(),
                timestamp=now_ts
            )

        # 3. Invalid standard identifier
        base_std, part, sec, year = normalize_standard(raw_std)
        # Check parenthesized year e.g. IS 318 (1981)
        if not year:
            year_match = re.search(r'\((\d{4})\)', raw_std)
            if year_match:
                year = year_match.group(1)
                base_std = re.sub(r'\(\d{4}\)', '', base_std).strip()

        raw_std_upper = raw_std.upper()
        has_std_keyword = "IS" in raw_std_upper or "ISO" in raw_std_upper or "IEC" in raw_std_upper
        has_std_number = bool(re.search(r'\d{2,5}', raw_std))
        if not (has_std_keyword or has_std_number):
            return None, RejectedRecord(
                record_type="SCOPE",
                raw_identifier=raw_scope.raw_scope_id,
                rejection_reason=f"INVALID_STANDARD_IDENTIFIER: '{raw_std}' could not be resolved to a standard code.",
                raw_data=raw_scope.to_dict(),
                timestamp=now_ts
            )

        # Ensure "IS " prefix
        if not base_std.upper().startswith("IS") and not base_std.upper().startswith("ISO") and not base_std.upper().startswith("IEC"):
            base_std = f"IS {base_std}"

        # 4. Parse fee
        base_fee = None
        if raw_scope.raw_fee_text:
            parsed_chg = parse_testing_charge(raw_scope.raw_fee_text)
            if parsed_chg:
                base_fee = parsed_chg.amount

        # 5. Extract clauses from modal
        clauses, excluded_clauses = LimsExtractor.extract_clauses_from_modal_html(raw_scope.raw_modal_html)
        is_complete = len(excluded_clauses) == 0

        # Deterministic scope ID
        scope_key = f"{raw_scope.internal_lab_id}|{base_std}|{raw_scope.raw_grade_type_size or ''}"
        scope_id = f"SCOPE_{sha256_text(scope_key)[:16]}"

        norm_scope = NormalizedLimsScope(
            scope_id=scope_id,
            internal_lab_id=raw_scope.internal_lab_id,
            lab_code=parent_lab.lab_code,
            standard_number=base_std,
            standard_title=raw_scope.raw_product,
            edition_year=year,
            product=raw_scope.raw_product,
            grade_type_size=raw_scope.raw_grade_type_size,
            base_testing_fee=base_fee,
            currency="INR",
            is_complete_scope=is_complete,
            clauses=clauses,
            excluded_clauses=excluded_clauses,
            validity_date=raw_scope.raw_validity_date,
            remark=raw_scope.raw_remark,
            source_url=raw_scope.source_url,
            source_sha256=raw_scope.source_sha256
        )
        return norm_scope, None


class LimsDeduplicationEngine:
    """
    Deterministic deduplication and conflict detection.
    Never merges on fuzzy names. Relies on authoritative BIS internal_id and lab_code.
    """

    def __init__(self):
        self.validated_labs: Dict[int, NormalizedLimsLab] = {}
        self.lab_duplicates: List[Dict[str, Any]] = []
        self.flagged_lab_conflicts: List[Dict[str, Any]] = []

        self.validated_scopes: Dict[str, NormalizedLimsScope] = {}
        self.scope_duplicates: List[Dict[str, Any]] = []

    def process_laboratories(
        self, labs: List[NormalizedLimsLab]
    ) -> Tuple[List[NormalizedLimsLab], List[Dict[str, Any]]]:
        for lab in labs:
            int_id = lab.internal_id
            if int_id in self.validated_labs:
                existing = self.validated_labs[int_id]
                # Compare critical identity
                if existing.lab_name == lab.lab_name and existing.category == lab.category:
                    # Clean duplicate (same lab seen on multiple pages)
                    self.lab_duplicates.append({
                        "type": "CLEAN_DUPLICATE",
                        "internal_id": int_id,
                        "lab_name": lab.lab_name,
                        "kept_record_url": existing.source_url,
                        "duplicate_record_url": lab.source_url
                    })
                else:
                    # Conflict detected: retain both, flag for review
                    self.flagged_lab_conflicts.append({
                        "type": "FLAGGED_FOR_REVIEW_CONFLICT",
                        "internal_id": int_id,
                        "record_a": existing.to_dict(),
                        "record_b": lab.to_dict(),
                        "conflict_reason": "Conflicting name or category for same internal_id."
                    })
            else:
                self.validated_labs[int_id] = lab

        return list(self.validated_labs.values()), self.lab_duplicates

    def process_scopes(
        self, scopes: List[NormalizedLimsScope]
    ) -> Tuple[List[NormalizedLimsScope], List[Dict[str, Any]]]:
        for s in scopes:
            if s.scope_id in self.validated_scopes:
                existing = self.validated_scopes[s.scope_id]
                self.scope_duplicates.append({
                    "type": "CLEAN_SCOPE_DUPLICATE",
                    "scope_id": s.scope_id,
                    "internal_lab_id": s.internal_lab_id,
                    "standard_number": s.standard_number,
                    "kept_url": existing.source_url,
                    "duplicate_url": s.source_url
                })
            else:
                self.validated_scopes[s.scope_id] = s

        return list(self.validated_scopes.values()), self.scope_duplicates
