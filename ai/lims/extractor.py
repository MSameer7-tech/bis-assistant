"""
Phase F3 Step 3: Authoritative BIS LIMS HTML Extractor.

Extracts:
1. Laboratory Directory Tables (Recognized, BIS Owned, Empanelled)
2. Laboratory Scope Pages (Standard, Product, Grade, Base Fee, Validity)
3. Modal Clause-by-Clause Tables (Clause No, Exclusion, Testing Fee, Effective Date, Remark)

Reuses:
- normalize_standard & parse_testing_charge from ai.acquisition.lims_scope.scope_parser
"""

import re
import hashlib
from datetime import datetime, timezone
from typing import List, Optional, Tuple, Dict, Any
from bs4 import BeautifulSoup

from ai.lims.models import (
    LabCategory,
    ClauseRecord,
    RawLimsLabRecord,
    RawLimsScopeRecord,
)
from ai.acquisition.lims_scope.scope_parser import (
    normalize_standard,
    parse_testing_charge,
)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def clean_text(text: Optional[str]) -> str:
    if not text:
        return ""
    return " ".join(text.split()).strip()


def extract_pincode(address_text: str) -> Optional[str]:
    if not address_text:
        return None
    matches = re.findall(r"(?:^|[^\d])([1-9][0-9]{5})(?:[^\d]|$)", address_text)
    return matches[-1] if matches else None


INDIAN_STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
    "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka",
    "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram",
    "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu",
    "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
    "Andaman and Nicobar Islands", "Chandigarh", "Dadra and Nagar Haveli",
    "Daman and Diu", "Delhi", "Jammu and Kashmir", "Ladakh", "Lakshadweep", "Puducherry"
]


def extract_state_from_address(address_text: str) -> Optional[str]:
    if not address_text:
        return None
    addr_lower = address_text.lower()
    for state in INDIAN_STATES:
        # Match whole word using character boundaries
        pattern = r"(?:^|[^a-z])" + re.escape(state.lower()) + r"(?:[^a-z]|$)"
        if re.search(pattern, addr_lower):
            return state
    return None


class LimsExtractor:
    """Authoritative BIS LIMS HTML Table & Scope Parser."""

    @staticmethod
    def extract_labs_from_directory_html(
        html_content: str,
        category: LabCategory,
        source_url: str
    ) -> List[RawLimsLabRecord]:
        """
        Extracts laboratory records from BIS LIMS directory pages.
        Supports Recognized (/home/labs/), BIS Owned (/home/bis_labs/),
        and Empanelled (/home/empaneled_labs/).
        """
        soup = BeautifulSoup(html_content, "html.parser")
        labs: List[RawLimsLabRecord] = []
        table = soup.find("table")
        if not table:
            return labs

        headers: List[str] = []
        header_row = table.find("tr")
        if header_row:
            headers = [clean_text(th.get_text()).upper() for th in header_row.find_all(["th", "td"])]

        # Map header names to column indices
        col_sno = -1
        col_code = -1
        col_name = -1
        col_addr = -1
        col_contact = -1
        col_phone = -1
        col_email = -1
        col_validity = -1
        col_scope = -1

        for idx, h in enumerate(headers):
            if "S.NO" in h or "SL" in h:
                col_sno = idx
            elif "LAB CODE" in h or "OSL CODE" in h:
                col_code = idx
            elif "LAB NAME" in h:
                col_name = idx
            elif "ADDRESS" in h:
                col_addr = idx
            elif "CONTACT PERSON" in h:
                col_contact = idx
            elif "CONTACT NUMBER" in h or "PHONE" in h:
                col_phone = idx
            elif "EMAIL" in h:
                col_email = idx
            elif "VALIDITY" in h:
                col_validity = idx
            elif "SCOPE" in h or "ACTION" in h:
                col_scope = idx

        # Default fallbacks if headers were missing or custom
        if col_name == -1 and len(headers) >= 3:
            col_code = 1
            col_name = 2
            col_addr = 3

        rows = table.find_all("tr")[1:]
        for r_idx, r in enumerate(rows):
            cells = r.find_all(["td", "th"])
            if len(cells) < 2:
                continue

            # Extract internal_id from View Scope link
            internal_id: Optional[int] = None
            scope_url = ""
            for a in r.find_all("a"):
                href = a.get("href", "")
                m = re.search(r'/home_lab_scope/(\d+)/', href)
                if m:
                    internal_id = int(m.group(1))
                    scope_url = href if href.startswith("http") else f"https://lims.bis.gov.in{href}"
                    break

            lab_name = clean_text(cells[col_name].get_text()) if col_name >= 0 and col_name < len(cells) else ""
            if not lab_name:
                continue

            raw_code = clean_text(cells[col_code].get_text()) if col_code >= 0 and col_code < len(cells) else ""
            lab_code = raw_code if raw_code and raw_code != "-" else None

            # Fallback synthetic code for BIS Owned laboratories
            if not lab_code and category == LabCategory.BIS_OWNED:
                # Look for acronym in parentheses e.g. (CL), (BNBL)
                acro = re.search(r'\(([A-Z]+)\)', lab_name)
                if acro:
                    lab_code = f"BIS_{acro.group(1)}"
                elif internal_id:
                    lab_code = f"BIS_OWNED_{internal_id}"

            raw_address = clean_text(cells[col_addr].get_text()) if col_addr >= 0 and col_addr < len(cells) else ""
            contact_person = clean_text(cells[col_contact].get_text()) if col_contact >= 0 and col_contact < len(cells) else None
            phone = clean_text(cells[col_phone].get_text()) if col_phone >= 0 and col_phone < len(cells) else None
            email = clean_text(cells[col_email].get_text()) if col_email >= 0 and col_email < len(cells) else None
            validity_date = clean_text(cells[col_validity].get_text()) if col_validity >= 0 and col_validity < len(cells) else None

            if contact_person == "-":
                contact_person = None
            if phone == "-":
                phone = None
            if email == "-":
                email = None
            if validity_date == "-":
                validity_date = None

            raw_row_str = "|".join(clean_text(c.get_text()) for c in cells)
            raw_id = f"RAW_LAB_{category.value}_{internal_id or r_idx}_{sha256_text(raw_row_str)[:8]}"

            lab_record = RawLimsLabRecord(
                raw_id=raw_id,
                internal_id=internal_id,
                lab_code=lab_code,
                lab_name=lab_name,
                category=category.value,
                raw_address=raw_address,
                contact_person=contact_person,
                phone=phone,
                email=email,
                validity_date=validity_date,
                source_url=source_url,
                retrieved_at=datetime.now(timezone.utc).isoformat(),
                raw_html_sha256=sha256_text(str(r)),
                extraction_metadata={
                    "row_index": r_idx,
                    "discovered_scope_url": scope_url
                }
            )
            labs.append(lab_record)

        return labs

    @staticmethod
    def extract_lab_from_scope_header(
        html_content: str,
        source_url: str,
        category: LabCategory = LabCategory.BIS_RECOGNIZED
    ) -> Optional[RawLimsLabRecord]:
        """
        Extracts laboratory metadata from the header banner of a /home_lab_scope/<id>/ page.
        """
        soup = BeautifulSoup(html_content, "html.parser")
        m = re.search(r'/home_lab_scope/(\d+)/', source_url)
        internal_id = int(m.group(1)) if m else None

        header_div = soup.find("div", class_="ml-2")
        if not header_div or not header_div.find("h3"):
            return None

        lab_name = clean_text(header_div.find("h3").get_text())
        if not lab_name:
            return None

        h5_tags = header_div.find_all("h5")
        raw_address = clean_text(h5_tags[0].get_text()) if len(h5_tags) > 0 else ""

        phone = None
        phone_icon = header_div.find("i", class_="fa-phone")
        if phone_icon and phone_icon.parent:
            phone_text = clean_text(phone_icon.parent.get_text())
            if phone_text and phone_text != "-":
                phone = phone_text

        email = None
        email_icon = header_div.find("i", class_="fa-envelope")
        if email_icon and email_icon.parent:
            email_text = clean_text(email_icon.parent.get_text())
            if email_text and email_text != "-":
                email = email_text

        # Determine category hint from name
        detected_category = category
        name_lower = lab_name.lower()
        if "bis," in name_lower or "central laboratory" in name_lower or "regional laboratory" in name_lower:
            detected_category = LabCategory.BIS_OWNED
        elif any(term in name_lower for term in ["national physical laboratory", "csir", "barc", "iit ", "central institute"]) and "private" not in name_lower:
            detected_category = LabCategory.BIS_EMPANELLED

        lab_code = None
        # Check if code is in parentheses in name
        code_match = re.search(r'(Code:\s*|\()([0-9]{7})\)?', lab_name)
        if code_match:
            lab_code = code_match.group(2)
        elif detected_category == LabCategory.BIS_OWNED:
            acro = re.search(r'\(([A-Z]+)\)', lab_name)
            if acro:
                lab_code = f"BIS_{acro.group(1)}"
            elif internal_id:
                lab_code = f"BIS_OWNED_{internal_id}"

        raw_id = f"RAW_SCOPE_LAB_{internal_id or sha256_text(lab_name)[:8]}"

        return RawLimsLabRecord(
            raw_id=raw_id,
            internal_id=internal_id,
            lab_code=lab_code,
            lab_name=lab_name,
            category=detected_category.value,
            raw_address=raw_address,
            contact_person=None,
            phone=phone,
            email=email,
            validity_date=None,
            source_url=source_url,
            retrieved_at=datetime.now(timezone.utc).isoformat(),
            raw_html_sha256=sha256_text(header_div.get_text()),
            extraction_metadata={"source": "scope_page_header"}
        )

    @staticmethod
    def extract_scope_from_scope_html(
        html_content: str,
        internal_lab_id: int,
        source_url: str,
        source_sha256: str = ""
    ) -> List[RawLimsScopeRecord]:
        """
        Extracts all standard testing scope rows and their modal clause tables from
        a /home_lab_scope/<id>/ page.
        """
        soup = BeautifulSoup(html_content, "html.parser")
        records: List[RawLimsScopeRecord] = []

        outer_table = soup.find("table", {"id": "review_lab_list"}) or soup.find("table", class_="table-bordered")
        if not outer_table:
            return records

        tbody = outer_table.find("tbody")
        rows = tbody.find_all("tr", recursive=False) if tbody else outer_table.find_all("tr", recursive=False)

        for r_idx, r in enumerate(rows):
            cells = r.find_all("td", recursive=False)
            if len(cells) < 4:
                continue

            sno = clean_text(cells[0].get_text())
            if not sno.isdigit():
                continue

            raw_std = clean_text(cells[1].get_text())
            raw_prod = clean_text(cells[2].get_text()) if len(cells) > 2 else None
            raw_grade = clean_text(cells[3].get_text()) if len(cells) > 3 else None
            raw_grade = None if raw_grade in ["-", "None", ""] else raw_grade

            # Cell 4 contains base test fee and the modal
            raw_fee_text = None
            modal_html = None
            if len(cells) > 4:
                fee_cell = cells[4]
                modal = fee_cell.find("div", class_="modal")
                if modal:
                    modal_html = str(modal)
                # Text excluding modal text
                fee_clone = BeautifulSoup(str(fee_cell), "html.parser")
                for m_tag in fee_clone.find_all("div", class_="modal"):
                    m_tag.decompose()
                raw_fee_text = clean_text(fee_clone.get_text())

            raw_validity = clean_text(cells[5].get_text()) if len(cells) > 5 else None
            raw_validity = None if raw_validity in ["-", ""] else raw_validity

            raw_remark = clean_text(cells[6].get_text()) if len(cells) > 6 else None
            raw_remark = None if raw_remark in ["-", ""] else raw_remark

            raw_scope_id = f"RAW_SCOPE_{internal_lab_id}_{r_idx}_{sha256_text(raw_std)[:8]}"

            rec = RawLimsScopeRecord(
                raw_scope_id=raw_scope_id,
                internal_lab_id=internal_lab_id,
                raw_standard=raw_std,
                raw_product=raw_prod,
                raw_grade_type_size=raw_grade,
                raw_fee_text=raw_fee_text,
                raw_validity_date=raw_validity,
                raw_remark=raw_remark,
                raw_modal_html=modal_html,
                source_url=source_url,
                source_sha256=source_sha256,
                retrieved_at=datetime.now(timezone.utc).isoformat()
            )
            records.append(rec)

        return records

    @staticmethod
    def extract_clauses_from_modal_html(modal_html: Optional[str]) -> Tuple[List[ClauseRecord], List[str]]:
        """
        Extracts structured clause records from the modal popup HTML (#assign_audit_list_table).
        Returns (clauses_list, excluded_clauses_list).
        """
        if not modal_html:
            return [], []

        soup = BeautifulSoup(modal_html, "html.parser")
        modal_table = soup.find("table", {"id": "assign_audit_list_table"}) or soup.find("table")
        if not modal_table:
            return [], []

        clauses: List[ClauseRecord] = []
        excluded_clauses: List[str] = []

        rows = modal_table.find_all("tr")
        for r in rows[1:]:  # Skip header
            if r.find("div", class_="scopeDe"):
                continue  # 'No Record Found' box

            cells = r.find_all(["td", "th"])
            if len(cells) < 3:
                continue

            clause_no = clean_text(cells[0].get_text())
            if not clause_no or clause_no == "-":
                continue

            raw_exclusion = clean_text(cells[1].get_text()) if len(cells) > 1 else "-"
            is_excluded = raw_exclusion not in ["-", "NA", "nil", "None", ""]

            raw_fee = clean_text(cells[2].get_text()) if len(cells) > 2 else ""
            fee_amount: Optional[float] = None
            if raw_fee and raw_fee != "-":
                parsed_charge = parse_testing_charge(raw_fee)
                if parsed_charge:
                    fee_amount = parsed_charge.amount

            eff_date = clean_text(cells[3].get_text()) if len(cells) > 3 else None
            eff_date = None if eff_date in ["-", "NA", ""] else eff_date

            remark = clean_text(cells[4].get_text()) if len(cells) > 4 else None
            remark = None if remark in ["-", ""] else remark

            c_rec = ClauseRecord(
                clause_number=clause_no,
                is_excluded=is_excluded,
                fee_amount=fee_amount,
                effective_date=eff_date,
                remark=remark,
                raw_text="|".join(clean_text(c.get_text()) for c in cells)
            )
            clauses.append(c_rec)
            if is_excluded:
                excluded_clauses.append(clause_no)

        return clauses, excluded_clauses
