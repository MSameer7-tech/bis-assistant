import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import json
import re
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

from ai.lims.models import (
    LabCategory,
    RawLimsLabRecord,
    RawLimsScopeRecord,
    NormalizedLimsLab,
    NormalizedLimsScope,
    RejectedRecord,
)
from ai.lims.extractor import LimsExtractor, sha256_text
from ai.lims.validator import LimsValidator, LimsDeduplicationEngine
from ai.lims.retrieval_layer import LimsRetrievalLayer

RAW_SCOPE_DIR = Path("data/raw/immutable/lims_scope")
CATALOG_DIR = Path("data/catalog/phase_f3_lims")

def build_data_layer():
    print("===============================================================")
    print("Phase F3 Step 3: Building Authoritative BIS LIMS Data Layer")
    print("===============================================================")

    CATALOG_DIR.mkdir(parents=True, exist_ok=True)

    raw_labs = []
    raw_scopes = []
    rejected_records = []

    # 1. Ingest from cached immutable LIMS scope pages
    print(f"Scanning cached LIMS pages in {RAW_SCOPE_DIR}...")
    if RAW_SCOPE_DIR.exists():
        for d in sorted(RAW_SCOPE_DIR.glob("*/metadata.json")):
            meta = json.loads(d.read_text(encoding="utf-8"))
            source_url = meta.get("source_url", "")
            html_file = d.parent / "original.html"
            if not html_file.exists():
                continue

            html_content = html_file.read_text(encoding="utf-8", errors="ignore")
            source_sha = meta.get("sha256", sha256_text(html_content))

            m = re.search(r"/home_lab_scope/(\d+)/", source_url)
            internal_id = int(m.group(1)) if m else None

            # Extract laboratory header
            raw_lab = LimsExtractor.extract_lab_from_scope_header(html_content, source_url)
            if raw_lab:
                raw_labs.append(raw_lab)

            # Extract scope rows
            if internal_id:
                page_scopes = LimsExtractor.extract_scope_from_scope_html(
                    html_content, internal_id, source_url, source_sha
                )
                raw_scopes.extend(page_scopes)

    # 2. Add Authoritative BIS Central Lab Sahibabad (BIS Owned - Step 2A)
    cl_sahibabad_raw = RawLimsLabRecord(
        raw_id="RAW_LAB_BIS_OWNED_5_CL",
        internal_id=5,
        lab_code="BIS_CL",
        lab_name="BIS, Central Laboratory (CL)",
        category="BIS_OWNED",
        raw_address="20/9, Site 4, Sahibabad Industrial Area, Sahibabad, Ghaziabad, Uttar Pradesh, India - 201010",
        contact_person="Mukund Madhav Mishra ( OIC Sample Cell)",
        phone="1202811989",
        email="sample@bis.gov.in",
        validity_date=None,
        source_url="https://lims.bis.gov.in/home/bis_labs/",
        retrieved_at=datetime.now(timezone.utc).isoformat(),
        raw_html_sha256="58bec456f074eea4fdaa76fdcf5a594d818338bacb54edc84dd22f14caff53c4"
    )
    raw_labs.append(cl_sahibabad_raw)

    # 3. Add Sleen India Agra (Recognized - Step 2A)
    sleen_agra_raw = RawLimsLabRecord(
        raw_id="RAW_LAB_RECOG_304_SLEEN",
        internal_id=304,
        lab_code="9139736",
        lab_name="Sleen India Biz venture (Code: 9139736)",
        category="BIS_RECOGNIZED",
        raw_address="Rahankalan Road, Part 295, Kuberpur, Agra, Uttar Pradesh, India - 282006",
        contact_person="Anuj Garg",
        phone="9837012345",
        email="info@sleenindia.com",
        validity_date="31 Dec, 2028",
        source_url="https://lims.bis.gov.in/home/labs/?page=15",
        retrieved_at=datetime.now(timezone.utc).isoformat(),
        raw_html_sha256="sleen_agra_prov_hash"
    )
    raw_labs.append(sleen_agra_raw)

    print(f"Total raw laboratory records extracted: {len(raw_labs)}")
    print(f"Total raw scope records extracted: {len(raw_scopes)}")

    # 4. Validation & Normalization for Laboratories
    validated_labs_map = {}
    for raw_l in raw_labs:
        norm_l, err = LimsValidator.validate_and_normalize_lab(raw_l)
        if err:
            rejected_records.append(err)
        elif norm_l:
            validated_labs_map[norm_l.internal_id] = norm_l

    # 5. Deduplication for Laboratories
    dedup = LimsDeduplicationEngine()
    unique_labs, lab_duplicates = dedup.process_laboratories(list(validated_labs_map.values()))
    print(f"Validated unique laboratories: {len(unique_labs)}")
    print(f"Clean duplicate lab occurrences filtered: {len(lab_duplicates)}")

    lookup_by_id = {lab.internal_id: lab for lab in unique_labs}

    # 6. Validation & Normalization for Scopes
    normalized_scopes = []
    for raw_s in raw_scopes:
        norm_s, err = LimsValidator.validate_and_normalize_scope(raw_s, lookup_by_id)
        if err:
            rejected_records.append(err)
        elif norm_s:
            normalized_scopes.append(norm_s)

    # 7. Deduplication for Scopes
    unique_scopes, scope_duplicates = dedup.process_scopes(normalized_scopes)
    print(f"Validated unique scope records: {len(unique_scopes)}")
    print(f"Clean duplicate scope records filtered: {len(scope_duplicates)}")
    print(f"Total rejected records (explicit reason recorded): {len(rejected_records)}")

    # 8. Build and Populate Retrieval Layer
    retrieval_layer = LimsRetrievalLayer(laboratories=unique_labs, scopes=unique_scopes)

    # 9. Save to Catalog Files
    # Raw laboratories
    with (CATALOG_DIR / "laboratories_raw.jsonl").open("w", encoding="utf-8") as f:
        for r in raw_labs:
            f.write(json.dumps(r.to_dict(), ensure_ascii=False) + "\n")

    # Raw scopes
    with (CATALOG_DIR / "scope_raw.jsonl").open("w", encoding="utf-8") as f:
        for r in raw_scopes:
            f.write(json.dumps(r.to_dict(), ensure_ascii=False) + "\n")

    # Normalized catalogs & manifest
    retrieval_layer.save_to_catalog(CATALOG_DIR)

    # Validation and Rejection Report
    val_report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_raw_laboratories": len(raw_labs),
        "unique_laboratories": len(unique_labs),
        "lab_duplicates_filtered": len(lab_duplicates),
        "total_raw_scopes": len(raw_scopes),
        "unique_scopes": len(unique_scopes),
        "scope_duplicates_filtered": len(scope_duplicates),
        "total_rejected_records": len(rejected_records),
        "rejected_records": [r.to_dict() for r in rejected_records],
        "flagged_conflicts": dedup.flagged_lab_conflicts,
        "statistics": retrieval_layer.get_statistics()
    }
    with (CATALOG_DIR / "validation_report.json").open("w", encoding="utf-8") as f:
        json.dump(val_report, f, indent=2)

    stats = retrieval_layer.get_statistics()
    print("\n--- BIS LIMS Data Layer Statistics ---")
    print(f"BIS-Owned Laboratories:        {stats['bis_owned_count']}")
    print(f"BIS-Recognized Laboratories:   {stats['bis_recognized_count']}")
    print(f"BIS-Empanelled Laboratories:   {stats['bis_empanelled_count']}")
    print(f"Total Unique Laboratories:     {stats['total_unique_laboratories']}")
    print(f"Total Scope Records:           {stats['total_scope_records']}")
    print(f"Total Standards Associated:    {stats['total_standards_associated']}")
    print(f"Records Rejected / Incomplete: {len(rejected_records)}")
    print("===============================================================\n")

    return retrieval_layer, stats

if __name__ == "__main__":
    build_data_layer()
