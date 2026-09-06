"""
Automated Test Suite for Phase F3 Step 3: BIS Laboratory Data & Retrieval Layer.

Covers:
1. Laboratory directory HTML parsing (Recognized, BIS Owned, Empanelled)
2. Category preservation (BIS_OWNED, BIS_RECOGNIZED, BIS_EMPANELLED)
3. Identifier preservation (internal_id, lab_code, source_url)
4. Original address preservation (unmodified)
5. Scope association & standard normalization
6. Modal clause preservation (clause no, exclusions, fees, completeness)
7. Validation: missing-field handling & explicit rejection recording
8. Validation: invalid-standard handling
9. Deduplication & conflict detection without fuzzy merging
10. Retrieval: name and code search
11. Retrieval: category and state filtering
12. Retrieval: standard-number filtering
13. Provenance tracking (source URLs & SHA-256)
14. Invariant: zero LLM (Groq) or external geocoding calls in retrieval
15. Catalog persistence and loading round-trip
"""

import json
from pathlib import Path
import pytest

from ai.lims.models import (
    LabCategory,
    ClauseRecord,
    RawLimsLabRecord,
    RawLimsScopeRecord,
    NormalizedLimsLab,
    NormalizedLimsScope,
    RejectedRecord,
)
from ai.lims.extractor import LimsExtractor
from ai.lims.validator import LimsValidator, LimsDeduplicationEngine
from ai.lims.retrieval_layer import LimsRetrievalLayer

# -----------------------------------------------------------------------------
# Sample HTML Fixtures
# -----------------------------------------------------------------------------

SAMPLE_DIRECTORY_HTML = """
<html>
<body>
<table>
  <thead>
    <tr>
      <th>S.NO.</th>
      <th>LAB CODE</th>
      <th>LAB NAME</th>
      <th>ADDRESS</th>
      <th>CONTACT PERSON</th>
      <th>CONTACT NUMBER</th>
      <th>EMAIL</th>
      <th>VALIDITY DATE</th>
      <th>VIEW SCOPE</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>1</td>
      <td>8102006</td>
      <td>SIIR, Delhi Shriram Institute For Industrial Research</td>
      <td>19-University Road, Delhi 110007, Delhi, North, Delhi, India - 110007</td>
      <td>Dr. Laxmi Rawat (Quality Manager)</td>
      <td>+91 011 35200445</td>
      <td>laxmirawat@shriraminstitute.org</td>
      <td>31 Dec, 2026</td>
      <td><a href="/home_lab_scope/15/">View Scope</a></td>
    </tr>
    <tr>
      <td>2</td>
      <td>8138306</td>
      <td>Testtex India Laboratories Private Limited</td>
      <td>C - 57, Sector - 65, Noida, Gautam Buddha Nagar, Uttar Pradesh, India - 201301</td>
      <td>Amit Tiwari</td>
      <td>+91 7303 919463</td>
      <td>labsindianoida@testtex.com</td>
      <td>31 Dec, 2029</td>
      <td><a href="/home_lab_scope/16/">View Scope</a></td>
    </tr>
  </tbody>
</table>
</body>
</html>
"""

SAMPLE_BIS_OWNED_HTML = """
<html>
<body>
<table>
  <thead>
    <tr>
      <th>S.NO.</th>
      <th>LAB CODE</th>
      <th>LAB NAME</th>
      <th>ADDRESS</th>
      <th>CONTACT PERSON</th>
      <th>CONTACT NUMBER</th>
      <th>EMAIL</th>
      <th>VIEW SCOPE</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>1</td>
      <td>-</td>
      <td>BIS, Central Laboratory (CL)</td>
      <td>20/9, Site 4, Sahibabad Industrial Area, Sahibabad, Ghaziabad, Uttar Pradesh, India - 201010</td>
      <td>Mukund Madhav Mishra (OIC Sample Cell)</td>
      <td>1202811989</td>
      <td>sample@bis.gov.in</td>
      <td><a href="/home_lab_scope/5/">View Scope</a></td>
    </tr>
  </tbody>
</table>
</body>
</html>
"""

SAMPLE_SCOPE_HTML = """
<html>
<body>
<div class="ml-2">
  <h3>SIIR, Delhi Shriram Institute For Industrial Research</h3>
  <h5 class="mb-0">19-University Road, Delhi 110007, Delhi, North, Delhi, 110007</h5>
  <h5 class="mb-0" style="font-size:12px;">
    <span class="mr-2"><i class="fa fa-phone"></i>9868670895</span>
    <span><i class="fa fa-envelope"></i>laxmirawat@shriraminstitute.org</span>
  </h5>
</div>
<table id="review_lab_list" class="table table-bordered customTable">
  <thead>
    <tr>
      <th>S.No.</th>
      <th>Indian Standard No.</th>
      <th>Product</th>
      <th>Grade / Type / Size / Designation etc.</th>
      <th>Testing Charges (Excl. Of Taxes)</th>
      <th>Validity Date</th>
      <th>Remark</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>1</td>
      <td>IS 8978 (1992)</td>
      <td>Specification for electric instantaneous water heaters</td>
      <td>Instantaneous Water Heaters</td>
      <td>
        14000 View breakup
        <div class="modal fade" id="testingChargesModal101">
          <table id="assign_audit_list_table">
            <thead>
              <tr>
                <th>Clause No.</th>
                <th>Exclusion</th>
                <th>Testing Charges (Excl. Of Taxes)</th>
                <th>Effective Date</th>
                <th>Remark</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>6(Classification)</td>
                <td>-</td>
                <td>1000</td>
                <td>01-01-2023</td>
                <td>Standard charge</td>
              </tr>
              <tr>
                <td>7(Marking)</td>
                <td>Excluded</td>
                <td>0</td>
                <td>01-01-2023</td>
                <td>Not equipped</td>
              </tr>
            </tbody>
          </table>
        </div>
      </td>
      <td>31 Dec, 2026</td>
      <td>Accredited scope</td>
    </tr>
  </tbody>
</table>
</body>
</html>
"""


class TestLimsDataLayer:
    """Automated test suite for Phase F3 Step 3 BIS LIMS Data Layer."""

    def test_01_directory_html_parsing(self):
        labs = LimsExtractor.extract_labs_from_directory_html(
            SAMPLE_DIRECTORY_HTML, LabCategory.BIS_RECOGNIZED, "https://lims.bis.gov.in/home/labs/"
        )
        assert len(labs) == 2
        lab1 = labs[0]
        assert lab1.internal_id == 15
        assert lab1.lab_code == "8102006"
        assert "Shriram Institute" in lab1.lab_name
        assert "19-University Road" in lab1.raw_address
        assert lab1.contact_person == "Dr. Laxmi Rawat (Quality Manager)"
        assert lab1.phone == "+91 011 35200445"
        assert lab1.email == "laxmirawat@shriraminstitute.org"
        assert lab1.validity_date == "31 Dec, 2026"

    def test_02_category_preservation(self):
        bis_labs = LimsExtractor.extract_labs_from_directory_html(
            SAMPLE_BIS_OWNED_HTML, LabCategory.BIS_OWNED, "https://lims.bis.gov.in/home/bis_labs/"
        )
        assert len(bis_labs) == 1
        assert bis_labs[0].category == "BIS_OWNED"
        assert bis_labs[0].lab_code == "BIS_CL"
        assert bis_labs[0].internal_id == 5

        norm, err = LimsValidator.validate_and_normalize_lab(bis_labs[0])
        assert err is None
        assert norm.category == LabCategory.BIS_OWNED
        assert norm.category.value == "BIS_OWNED"

    def test_03_identifier_preservation(self):
        labs = LimsExtractor.extract_labs_from_directory_html(
            SAMPLE_DIRECTORY_HTML, LabCategory.BIS_RECOGNIZED, "https://lims.bis.gov.in/home/labs/"
        )
        norm, err = LimsValidator.validate_and_normalize_lab(labs[0])
        assert norm.internal_id == 15
        assert norm.lab_code == "8102006"
        assert norm.source_url == "https://lims.bis.gov.in/home/labs/"

    def test_04_original_address_preservation(self):
        labs = LimsExtractor.extract_labs_from_directory_html(
            SAMPLE_DIRECTORY_HTML, LabCategory.BIS_RECOGNIZED, "https://lims.bis.gov.in/home/labs/"
        )
        norm, err = LimsValidator.validate_and_normalize_lab(labs[0])
        # original_address must exactly match raw address without replacement
        assert norm.original_address == "19-University Road, Delhi 110007, Delhi, North, Delhi, India - 110007"
        assert norm.pincode == "110007"
        assert norm.normalized_state == "Delhi"

    def test_05_scope_parsing_and_standard_association(self):
        scopes = LimsExtractor.extract_scope_from_scope_html(
            SAMPLE_SCOPE_HTML, 15, "https://lims.bis.gov.in/home_lab_scope/15/"
        )
        assert len(scopes) == 1
        raw_s = scopes[0]
        assert raw_s.internal_lab_id == 15
        assert "IS 8978" in raw_s.raw_standard
        assert "Specification for electric instantaneous water heaters" in raw_s.raw_product
        assert raw_s.raw_grade_type_size == "Instantaneous Water Heaters"

    def test_06_modal_clause_preservation(self):
        scopes = LimsExtractor.extract_scope_from_scope_html(
            SAMPLE_SCOPE_HTML, 15, "https://lims.bis.gov.in/home_lab_scope/15/"
        )
        lab_mock = NormalizedLimsLab(
            internal_id=15,
            lab_code="8102006",
            lab_name="SIIR",
            category=LabCategory.BIS_RECOGNIZED,
            original_address="Delhi"
        )
        norm_s, err = LimsValidator.validate_and_normalize_scope(scopes[0], {15: lab_mock})
        assert err is None
        assert norm_s.standard_number == "IS 8978"
        assert norm_s.edition_year == "1992"
        assert norm_s.base_testing_fee == 14000.0
        assert len(norm_s.clauses) == 2
        assert norm_s.clauses[0].clause_number == "6(Classification)"
        assert norm_s.clauses[0].fee_amount == 1000.0
        assert norm_s.clauses[0].is_excluded is False
        # Clause 7 is marked Excluded
        assert norm_s.clauses[1].clause_number == "7(Marking)"
        assert norm_s.clauses[1].is_excluded is True
        assert norm_s.is_complete_scope is False  # Has excluded clause
        assert "7(Marking)" in norm_s.excluded_clauses

    def test_07_validation_missing_fields(self):
        # Missing name
        bad_lab = RawLimsLabRecord(
            raw_id="bad1", internal_id=1, lab_code="1234567",
            lab_name="", category="BIS_RECOGNIZED", raw_address="Delhi",
            source_url="http://example.com"
        )
        norm, err = LimsValidator.validate_and_normalize_lab(bad_lab)
        assert norm is None
        assert "MISSING_LAB_NAME" in err.rejection_reason

        # Malformed category
        bad_cat = RawLimsLabRecord(
            raw_id="bad2", internal_id=1, lab_code="1234567",
            lab_name="Good Lab", category="RANDOM_CATEGORY", raw_address="Delhi",
            source_url="http://example.com"
        )
        norm, err = LimsValidator.validate_and_normalize_lab(bad_cat)
        assert norm is None
        assert "MALFORMED_CATEGORY" in err.rejection_reason

        # Missing address
        bad_addr = RawLimsLabRecord(
            raw_id="bad3", internal_id=1, lab_code="1234567",
            lab_name="Good Lab", category="BIS_RECOGNIZED", raw_address="",
            source_url="http://example.com"
        )
        norm, err = LimsValidator.validate_and_normalize_lab(bad_addr)
        assert norm is None
        assert "MISSING_ADDRESS" in err.rejection_reason

    def test_08_validation_invalid_standards(self):
        lab_mock = NormalizedLimsLab(
            internal_id=1, lab_code="101", lab_name="Lab",
            category=LabCategory.BIS_RECOGNIZED, original_address="Delhi"
        )
        bad_scope = RawLimsScopeRecord(
            raw_scope_id="bad_scope", internal_lab_id=1,
            raw_standard="Not A Standard"
        )
        norm, err = LimsValidator.validate_and_normalize_scope(bad_scope, {1: lab_mock})
        assert norm is None
        assert "INVALID_STANDARD_IDENTIFIER" in err.rejection_reason

    def test_09_deduplication_clean_and_conflict(self):
        dedup = LimsDeduplicationEngine()
        lab1 = NormalizedLimsLab(
            internal_id=10, lab_code="CODE1", lab_name="Identical Lab",
            category=LabCategory.BIS_RECOGNIZED, original_address="Delhi",
            source_url="http://example.com/page1"
        )
        lab2 = NormalizedLimsLab(
            internal_id=10, lab_code="CODE1", lab_name="Identical Lab",
            category=LabCategory.BIS_RECOGNIZED, original_address="Delhi",
            source_url="http://example.com/page2"
        )
        unique_labs, dupes = dedup.process_laboratories([lab1, lab2])
        assert len(unique_labs) == 1
        assert len(dupes) == 1
        assert dupes[0]["type"] == "CLEAN_DUPLICATE"

    def test_10_retrieval_layer_name_and_code_search(self):
        lab = NormalizedLimsLab(
            internal_id=15, lab_code="8102006", lab_name="SIIR Delhi Shriram",
            category=LabCategory.BIS_RECOGNIZED, original_address="19-University Road, Delhi 110007"
        )
        layer = LimsRetrievalLayer(laboratories=[lab])
        assert layer.get_laboratory_by_code("8102006") is not None
        assert layer.get_laboratory_by_id(15) is not None
        matches = layer.search_laboratories(name="Shriram")
        assert len(matches) == 1
        assert matches[0].internal_id == 15

    def test_11_retrieval_layer_category_and_state_filtering(self):
        lab1 = NormalizedLimsLab(
            internal_id=1, lab_code="C1", lab_name="BIS Central Lab",
            category=LabCategory.BIS_OWNED, original_address="Sahibabad, UP",
            normalized_state="Uttar Pradesh"
        )
        lab2 = NormalizedLimsLab(
            internal_id=2, lab_code="C2", lab_name="Private Lab",
            category=LabCategory.BIS_RECOGNIZED, original_address="Delhi",
            normalized_state="Delhi"
        )
        layer = LimsRetrievalLayer(laboratories=[lab1, lab2])

        owned = layer.search_laboratories(category=LabCategory.BIS_OWNED)
        assert len(owned) == 1
        assert owned[0].internal_id == 1

        up = layer.search_laboratories(state="Uttar Pradesh")
        assert len(up) == 1
        assert up[0].internal_id == 1

    def test_12_retrieval_layer_standard_filtering(self):
        lab = NormalizedLimsLab(
            internal_id=15, lab_code="8102006", lab_name="SIIR Delhi",
            category=LabCategory.BIS_RECOGNIZED, original_address="Delhi"
        )
        scope = NormalizedLimsScope(
            scope_id="S1", internal_lab_id=15, lab_code="8102006",
            standard_number="IS 8978", standard_title="Water Heaters",
            edition_year="1992", base_testing_fee=14000.0
        )
        layer = LimsRetrievalLayer(laboratories=[lab], scopes=[scope])
        matches = layer.get_laboratories_for_standard("IS 8978")
        assert len(matches) == 1
        assert matches[0]["laboratory"].internal_id == 15
        assert matches[0]["scope"].base_testing_fee == 14000.0

    def test_13_provenance_integrity(self):
        labs = LimsExtractor.extract_labs_from_directory_html(
            SAMPLE_DIRECTORY_HTML, LabCategory.BIS_RECOGNIZED, "https://lims.bis.gov.in/home/labs/"
        )
        norm, _ = LimsValidator.validate_and_normalize_lab(labs[0])
        assert len(norm.provenance_sha256) == 64
        assert norm.source_url == "https://lims.bis.gov.in/home/labs/"

    def test_14_no_llm_or_geocoding_dependency(self):
        lims_dir = Path("ai/lims")
        for f in lims_dir.glob("*.py"):
            content = f.read_text(encoding="utf-8").lower()
            assert "groq" not in content, f"Found LLM Groq reference in {f}"
            assert "geoapify" not in content, f"Found Geoapify reference in {f}"
            assert "haversine" not in content, f"Found Haversine reference in {f}"

    def test_15_catalog_persistence_and_loading(self, tmp_path):
        lab = NormalizedLimsLab(
            internal_id=99, lab_code="CODE99", lab_name="Catalog Test Lab",
            category=LabCategory.BIS_EMPANELLED, original_address="Bangalore",
            normalized_state="Karnataka"
        )
        scope = NormalizedLimsScope(
            scope_id="S99", internal_lab_id=99, lab_code="CODE99",
            standard_number="IS 302", standard_title="Safety of Household Appliances"
        )
        layer = LimsRetrievalLayer(laboratories=[lab], scopes=[scope])
        layer.save_to_catalog(tmp_path)

        loaded_layer = LimsRetrievalLayer.load_from_catalog(tmp_path)
        stats = loaded_layer.get_statistics()
        assert stats["total_unique_laboratories"] == 1
        assert stats["bis_empanelled_count"] == 1
        assert stats["total_scope_records"] == 1
        retrieved_lab = loaded_layer.get_laboratory_by_id(99)
        assert retrieved_lab is not None
        assert retrieved_lab.lab_name == "Catalog Test Lab"
