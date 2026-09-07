"""
Phase F3 Step 3: Deterministic BIS Laboratory Retrieval Layer.

Provides deterministic querying and filtering over authoritative normalized
BIS LIMS laboratory data.

Supported queries:
1. Laboratory name search (case-insensitive substring)
2. Laboratory code search (exact & prefix)
3. Category filtering (BIS_OWNED, BIS_RECOGNIZED, BIS_EMPANELLED)
4. State filtering
5. District / City filtering
6. Indian Standard filtering (e.g. "IS 8978", "IS 302")

Invariants:
- 100% deterministic (no fuzzy guesses, no semantic vector similarity, no distance ranking).
- Zero external LLM dependencies.
- Zero external geocoding calls.
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Optional, Union, Any, Set
from collections import defaultdict

from ai.lims.models import (
    LabCategory,
    ClauseRecord,
    NormalizedLimsLab,
    NormalizedLimsScope,
)
from ai.acquisition.lims_scope.scope_parser import normalize_standard


class LimsRetrievalLayer:
    """Authoritative BIS LIMS In-Memory Search and Retrieval Engine."""

    def __init__(
        self,
        laboratories: Optional[List[NormalizedLimsLab]] = None,
        scopes: Optional[List[NormalizedLimsScope]] = None
    ):
        self._labs: Dict[int, NormalizedLimsLab] = {}
        self._labs_by_code: Dict[str, NormalizedLimsLab] = {}
        self._labs_by_category: Dict[LabCategory, List[NormalizedLimsLab]] = defaultdict(list)
        self._labs_by_state: Dict[str, List[NormalizedLimsLab]] = defaultdict(list)

        self._scopes: Dict[str, NormalizedLimsScope] = {}
        self._scopes_by_lab_id: Dict[int, List[NormalizedLimsScope]] = defaultdict(list)
        self._scopes_by_standard: Dict[str, List[NormalizedLimsScope]] = defaultdict(list)

        if laboratories:
            self.load_laboratories(laboratories)
        if scopes:
            self.load_scopes(scopes)

    def load_laboratories(self, laboratories: List[NormalizedLimsLab]) -> None:
        for lab in laboratories:
            self._labs[lab.internal_id] = lab
            if lab.lab_code:
                self._labs_by_code[lab.lab_code.strip().upper()] = lab
            cat = lab.category if isinstance(lab.category, LabCategory) else LabCategory(lab.category)
            self._labs_by_category[cat].append(lab)
            if lab.normalized_state:
                self._labs_by_state[lab.normalized_state.strip().lower()].append(lab)

    def load_scopes(self, scopes: List[NormalizedLimsScope]) -> None:
        for s in scopes:
            self._scopes[s.scope_id] = s
            self._scopes_by_lab_id[s.internal_lab_id].append(s)
            std_norm = self._normalize_std_key(s.standard_number)
            self._scopes_by_standard[std_norm].append(s)

    @staticmethod
    def _normalize_std_key(std_text: str) -> str:
        base, _, _, _ = normalize_standard(std_text or "")
        cleaned = re.sub(r'[:\/\s\-\.]+$', '', base).strip()
        cleaned = re.sub(r'\s+', ' ', cleaned).strip().upper()
        if not cleaned.startswith("IS"):
            cleaned = f"IS {cleaned}"
        return cleaned

    def search_scopes_by_text(self, text: str) -> List[NormalizedLimsScope]:
        """
        Deterministic, case-insensitive search across scopes by standard number,
        standard title, or product description. Uses verified scope fields.
        """
        text_lower = text.strip().lower()
        if not text_lower:
            return []
        matches: List[NormalizedLimsScope] = []
        for scope in self._scopes.values():
            std_num = (scope.standard_number or "").lower()
            std_title = (scope.standard_title or "").lower()
            prod = (scope.product or "").lower()
            if text_lower in std_num or text_lower in std_title or text_lower in prod:
                matches.append(scope)
        return matches

    def get_laboratory_by_id(self, internal_id: int) -> Optional[NormalizedLimsLab]:
        return self._labs.get(internal_id)

    def get_laboratory_by_code(self, lab_code: str) -> Optional[NormalizedLimsLab]:
        if not lab_code:
            return None
        return self._labs_by_code.get(lab_code.strip().upper())

    def get_scope_for_laboratory(self, internal_lab_id: int) -> List[NormalizedLimsScope]:
        return list(self._scopes_by_lab_id.get(internal_lab_id, []))

    def get_laboratories_for_standard(
        self,
        standard_number: str,
        category: Optional[Union[LabCategory, str]] = None,
        state: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Returns all accredited laboratories for a given standard number,
        with optional category and state filters.
        """
        std_key = self._normalize_std_key(standard_number)
        matching_scopes = self._scopes_by_standard.get(std_key, [])

        cat_filter = None
        if category:
            cat_filter = category if isinstance(category, LabCategory) else LabCategory(category)

        state_filter = state.strip().lower() if state else None

        results = []
        seen_labs = set()
        for scope in matching_scopes:
            lab = self._labs.get(scope.internal_lab_id)
            if not lab:
                continue

            if cat_filter and lab.category != cat_filter:
                continue

            if state_filter:
                lab_state = (lab.normalized_state or "").strip().lower()
                lab_addr = lab.original_address.lower()
                if state_filter not in lab_state and state_filter not in lab_addr:
                    continue

            key = (lab.internal_id, scope.scope_id)
            if key not in seen_labs:
                seen_labs.add(key)
                results.append({
                    "laboratory": lab,
                    "scope": scope
                })

        return results

    def search_laboratories(
        self,
        name: Optional[str] = None,
        lab_code: Optional[str] = None,
        category: Optional[Union[LabCategory, str]] = None,
        state: Optional[str] = None,
        city: Optional[str] = None,
        standard_number: Optional[str] = None,
        limit: int = 50
    ) -> List[NormalizedLimsLab]:
        """
        Deterministic multi-parameter filter over laboratories.
        """
        # If standard_number is supplied, resolve matching lab IDs first
        allowed_lab_ids: Optional[Set[int]] = None
        if standard_number:
            std_key = self._normalize_std_key(standard_number)
            scopes = self._scopes_by_standard.get(std_key, [])
            allowed_lab_ids = {s.internal_lab_id for s in scopes}

        cat_filter = None
        if category:
            cat_filter = category if isinstance(category, LabCategory) else LabCategory(category)

        name_lower = name.strip().lower() if name else None
        code_upper = lab_code.strip().upper() if lab_code else None
        state_lower = state.strip().lower() if state else None
        city_lower = city.strip().lower() if city else None

        matches: List[NormalizedLimsLab] = []
        for lab in self._labs.values():
            if allowed_lab_ids is not None and lab.internal_id not in allowed_lab_ids:
                continue

            if cat_filter and lab.category != cat_filter:
                continue

            if code_upper and (not lab.lab_code or code_upper not in lab.lab_code.upper()):
                continue

            if name_lower and name_lower not in lab.lab_name.lower():
                continue

            if state_lower:
                lab_state = (lab.normalized_state or "").lower()
                lab_addr = lab.original_address.lower()
                if state_lower not in lab_state and state_lower not in lab_addr:
                    continue

            if city_lower:
                lab_city = (lab.normalized_city or "").lower()
                lab_addr = lab.original_address.lower()
                if city_lower not in lab_city and city_lower not in lab_addr:
                    continue

            matches.append(lab)
            if len(matches) >= limit:
                break

        return matches

    def get_statistics(self) -> Dict[str, Any]:
        unique_standards = set(self._scopes_by_standard.keys())
        return {
            "total_unique_laboratories": len(self._labs),
            "bis_owned_count": len(self._labs_by_category.get(LabCategory.BIS_OWNED, [])),
            "bis_recognized_count": len(self._labs_by_category.get(LabCategory.BIS_RECOGNIZED, [])),
            "bis_empanelled_count": len(self._labs_by_category.get(LabCategory.BIS_EMPANELLED, [])),
            "total_scope_records": len(self._scopes),
            "total_standards_associated": len(unique_standards),
            "total_states_covered": len([s for s in self._labs_by_state.keys() if s])
        }

    def save_to_catalog(self, catalog_dir: Path) -> None:
        catalog_dir.mkdir(parents=True, exist_ok=True)
        # Save laboratories
        labs_file = catalog_dir / "laboratories_normalized.jsonl"
        with labs_file.open("w", encoding="utf-8") as f:
            for lab in self._labs.values():
                f.write(json.dumps(lab.to_dict(), ensure_ascii=False) + "\n")

        # Save scopes
        scopes_file = catalog_dir / "scope_normalized.jsonl"
        with scopes_file.open("w", encoding="utf-8") as f:
            for scope in self._scopes.values():
                f.write(json.dumps(scope.to_dict(), ensure_ascii=False) + "\n")

        # Save statistics
        stats_file = catalog_dir / "catalog_manifest.json"
        with stats_file.open("w", encoding="utf-8") as f:
            json.dump(self.get_statistics(), f, indent=2)

    @classmethod
    def load_from_catalog(cls, catalog_dir: Path) -> "LimsRetrievalLayer":
        labs_file = catalog_dir / "laboratories_normalized.jsonl"
        scopes_file = catalog_dir / "scope_normalized.jsonl"

        labs = []
        if labs_file.exists():
            with labs_file.open("r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        d = json.loads(line)
                        d["category"] = LabCategory(d["category"])
                        labs.append(NormalizedLimsLab(**d))

        scopes = []
        if scopes_file.exists():
            with scopes_file.open("r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        d = json.loads(line)
                        d["clauses"] = [ClauseRecord(**c) for c in d.get("clauses", [])]
                        scopes.append(NormalizedLimsScope(**d))

        return cls(laboratories=labs, scopes=scopes)
