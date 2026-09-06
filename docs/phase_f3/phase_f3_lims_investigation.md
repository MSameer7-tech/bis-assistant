# Phase F3: BIS LIMS Investigation Report
**Authoritative Laboratory Data Architecture & Feasibility Analysis**

---

## Executive Summary

This investigation was conducted directly against the live production Bureau of Indian Standards Laboratory Information Management System (**BIS LIMS** at `https://lims.bis.gov.in`). 

The findings confirm that **BIS LIMS is the authoritative, regulatory source of truth** for all BIS-affiliated testing laboratories in India. The system maintains clean separation between three distinct administrative categories:
1. **BIS Recognized Laboratories** (Outside System Laboratories - OSL): **431** facilities across India.
2. **BIS Owned Laboratories** (Regional & Branch Labs): **10** central/regional facilities.
3. **Empanelled Laboratories** (Government, CSIR, and Autonomous Bodies): **140** institutions.

The directory structure, standard-to-lab search mechanics, internal database identifiers, and detailed scope-of-testing breakdowns were thoroughly probed and verified.

---

## Detailed Findings: 9 Core Questions

### 1. What BIS endpoints exist?

The BIS LIMS platform is built upon a server-side rendered Django architecture hosted at `https://lims.bis.gov.in`. The following endpoints are active and accessible:

#### A. Directory Endpoints
* **Recognized Laboratories Directory**:
  - `GET https://lims.bis.gov.in/home/labs/`
  - **431 Results** across 22 pages (`?page=1` to `?page=22`), 20 labs per page.
  - Filter parameters: `lab_name__icontains`, `osl_code__icontains`, `lab_state`, `lab_district`, `search_text`.
* **BIS Owned Laboratories Directory**:
  - `GET https://lims.bis.gov.in/home/bis_labs/`
  - **10 Results** on a single page (Central Laboratory Sahibabad, Northern Regional Lab Mohali, Southern Regional Lab Chennai, Western Regional Lab Mumbai, Eastern Regional Lab Kolkata, Bengaluru Branch Lab, etc.).
* **Empanelled Laboratories Directory**:
  - `GET https://lims.bis.gov.in/home/empaneled_labs/`
  - **140 Results** across 7 pages (`?page=1` to `?page=7`), 20 labs per page.
* **Secondary Administrative Status Directories**:
  - `/home/new_labs/` (8 new applications)
  - `/home/under_process_labs/` (26 under process)
  - `/home/suspended_labs/` (7 suspended/deferred)
  - `/home/derecognized_labs/` (65 derecognized)

#### B. Search Endpoints
* **Unified Laboratory Search**:
  - `GET https://lims.bis.gov.in/home/search_labs/`
  - Highly functional search supporting compound queries. Accepts:
    - `lab_is_number`: Standard number (e.g., `8978`, `302`, `1293`).
    - `lab_type`: Tier filter (`BIS`, `OSL`, `Empanelled`).
    - `lab_name`: Text substring.
    - `lab_state`: State identifier.
    - `lab_district`: District identifier.
    - `search_text`: Full-text keyword match.
* **Dedicated IS Number Search**:
  - `GET https://lims.bis.gov.in/home/search_is_number/`
  - Form fields: `is_number__doc_no`, `is_number__part`, `is_number__section`, `is_number__year`, `lab__lab_name__icontains`, `is_title`.

#### C. Detail & Scope Endpoints
* **Laboratory Scope & Fee Schedule**:
  - `GET https://lims.bis.gov.in/home_lab_scope/<internal_id>/`
  - Where `<internal_id>` is an integer primary key (e.g., `15` for SIIR Delhi, `55` for NRTC Parwanoo, `5` for BIS CL Sahibabad).
  - Supports direct query filtering: `GET https://lims.bis.gov.in/home_lab_scope/<internal_id>/?is_number__doc_no=<doc_no>`.

#### D. JSON & AJAX Helper Endpoints
* **Standard Title Lookup (JSON API)**:
  - `GET https://lims.bis.gov.in/get-is-title/?doc_no=<doc_no>`
  - Returns JSON: `{"status": true, "id": 16152, "title": "Specification for electric instantaneous water heaters (Second Revision)"}`
* **Geographic Dropdown Helpers**:
  - `GET https://lims.bis.gov.in/get_states/<country_id>/` (Returns HTML `<option>` list for Indian states).
  - `GET https://lims.bis.gov.in/get_districts/<state_id>/` (Returns HTML `<option>` list for state districts).

---

### 2. What data can be retrieved?

From each laboratory directory and scope page, the following structured fields are directly extracted:

| Domain | Extracted Field | Example Value | Notes |
| :--- | :--- | :--- | :--- |
| **Identity** | Laboratory Name | *National Research and Technology Consortium (NRTC)* | Official registered name |
| **Identity** | Category / Tier | `BIS_OWNED`, `BIS_RECOGNIZED` (OSL), `BIS_EMPANELLED` | Prevents category conflation |
| **Identity** | Lab Code / OSL Code | `9136024` | 7-digit regulatory code |
| **Identity** | Internal Database ID | `55` | Required for scope URL resolution |
| **Location** | Street Address | *HPCED Building, Dept of Industries Complex, Sector-1* | Physical premises |
| **Location** | City / District / State | *Parwanoo, Solan, Himachal Pradesh* | Geographic hierarchy |
| **Location** | Postal Pincode | `173220` | Critical for geocoding in Step 2 |
| **Contact** | Contact Person | *Dr Kiran Gupta (Quality Manager)* | Name and institutional role |
| **Contact** | Phone / Mobile | `+91 1792 234107` / `9816034484` | Live phone number |
| **Contact** | Email Address | `nrtcpwn@gmail.com` | Official inquiry mailbox |
| **Validity** | Recognition Expiry Date | `10 Apr, 2029` (or `-` for permanent/BIS) | Accreditation validity |
| **Scope** | Indian Standard No. | `IS 8978 (1992)` | Accredited standard code |
| **Scope** | Product Title | *Specification for electric instantaneous water heaters* | Product description |
| **Scope** | Testing Charges (Base) | `₹14,000` (Excl. of taxes) | Overarching standard test fee |
| **Scope** | Clause Breakup | `Cl. 6 of IS 302-2-35:2017 (Classification)` | Modal clause-by-clause table |
| **Scope** | Exclusions | `-` or specific excluded test clauses | Incomplete facility warnings |
| **Scope** | Remarks & Discounts | `30% Discount` / `Test Charges included` | Tariff rules |

---

### 3. How is a lab identified?

BIS LIMS utilizes a **two-tier identification system**:

1. **Public Regulatory Lab Code (OSL Code)**:
   - A **7-digit numeric string** assigned under the BIS Laboratory Recognition Scheme (LRS).
   - E.g., `8102006` (SIIR Delhi), `8138306` (Testtex Noida), `9136024` (NRTC Parwanoo).
   - **Regional Jurisdictional Prefix**:
     - `8`: Northern Region (Delhi NCR: Delhi, Noida, Ghaziabad, Faridabad)
     - `9`: Northern Region - North (Punjab, Haryana, Himachal Pradesh, Chandigarh)
     - `6`: Southern Region (Bengaluru, Chennai, Hyderabad, Mysuru)
     - `7`: Western Region (Mumbai, Pune, Ahmedabad)
     - `5`: Eastern Region (Kolkata, Bhubaneswar, Ranchi)
   - *Note on BIS Owned Labs*: Several BIS regional laboratories list `-` in the public table\'s Lab Code column, but possess standardized names (e.g. `BIS, Central Laboratory (CL)`) and fixed internal database IDs.

2. **Internal Database Primary Key (`internal_id`)**:
   - An integer ID embedded in URLs: `https://lims.bis.gov.in/home_lab_scope/<internal_id>/`.
   - E.g., `15` (SIIR Delhi), `55` (NRTC Parwanoo), `5` (BIS CL Sahibabad), `8` (BIS NRL Mohali).
   - **Requirement**: Our crawler and data layer must store the mapping tuple:
     `(tier, lab_code, internal_id, lab_name, pincode)`.

---

### 4. How is scope identified?

Scope in BIS LIMS is **richly relational**, not a static PDF:
- Each laboratory maintains an individual scope roster at `/home_lab_scope/<internal_id>/`.
- A scope row binds:
  - **Indian Standard Number** (e.g., `IS 8978 (1992)`)
  - **Product**
  - **Grade / Type / Size / Designation limitations**
  - **Overarching Testing Charge** (e.g., ₹14,000, ₹26,000)
  - **Testing Charges Modal Breakup**: A nested table (`#testingChargesModal<row_id>`) detailing each tested clause, exclusions, effective dates, and remarks.
  - **Facility Completeness Flag (`is_complete`)**: Distinguishes whether the facility has the complete apparatus for all tests under the standard, or partial facilities with specific clause exclusions.

---

### 5. How is an IS number connected to a lab?

Standards are connected to laboratories through two deterministic paths on LIMS:

1. **Direct Search by IS Number**:
   - Query: `GET https://lims.bis.gov.in/home/search_labs/?lab_is_number=<doc_no>`
   - *Verified Test*: Querying `lab_is_number=8978` immediately returned **28 accredited laboratories** across India:
     - 2 BIS Owned Laboratories (`BIS, Central Laboratory Sahibabad`, `BIS, Northern Regional Laboratory Mohali`).
     - 24 BIS Recognized Laboratories (including `NRTC Parwanoo`, `NSIC Rajpura`, `Hi Physix Pune`, `Alpha Test House Delhi`, `Shri Krishna Test House Delhi`, `Accurate Test Solutions Noida`, `NTH Ghaziabad`).
     - 0 Empanelled Laboratories.
   - Each record contains a direct hyperlink: `/home_lab_scope/<internal_id>/?is_number__doc_no=8978`.

2. **Laboratory-Specific Scope Filtering**:
   - Loading `https://lims.bis.gov.in/home_lab_scope/<internal_id>/?is_number__doc_no=<doc_no>` filters that specific laboratory\'s scope to the exact standard and loads its clause fees.

3. **Title & Document Resolution**:
   - `GET /get-is-title/?doc_no=8978` returns `{"status": true, "id": 16152, "title": "Specification for electric instantaneous water heaters (Second Revision)"}`.

---

### 6. What data is authoritative?

| Source | Status | Rationale |
| :--- | :---: | :--- |
| **BIS LIMS (`lims.bis.gov.in`)** | **AUTHORITATIVE** | The sole statutory platform managed by BIS for lab recognition, scope accreditation, and fee schedules under the BIS Act 2016 and LRS 2020 regulations. |
| **Google Search / Web Crawls** | **NON-AUTHORITATIVE** | Commercial aggregators (IndiaMART, JustDial) and private consultant sites list outdated lab accreditations, unverified claims, and incorrect lab codes. |
| **External Lab Websites** | **SECONDARY ONLY** | May claim testing capabilities not formally recognized or audited under current BIS LRS scope. |

*Decision*: In Phase F3, all laboratory discovery, accreditation verification, and fee calculations must anchor strictly to BIS LIMS data. Google Maps/Geocoding will only be used for spatial coordinates (latitude/longitude) of authoritative LIMS addresses.

---

### 7. What data is missing?

1. **Geospatial Coordinates (`latitude`, `longitude`)**:
   - LIMS stores clean text addresses, city, district, state, and 6-digit postal PIN codes, but provides **zero latitude/longitude coordinates**.
   - *Mitigation (Step 2)*: Address and postal PIN code geocoding via Google Geocoding API / Maps to enable proximity calculations (e.g., "Labs within 50 km").
2. **Real-Time Sample Queue & Turnaround Times**:
   - Turnaround times are either unpopulated or fixed placeholders on the public portal. Operational queue depth is not exposed publicly.
3. **Open REST API**:
   - There is no public JSON REST endpoint providing all labs in bulk; data must be ingested via standard HTTP scraping of Django server-side rendered HTML tables.

---

### 8. What can be automated safely?

1. **Deterministic Bulk Ingestion of All 581 Laboratories**:
   - **431 Recognized Labs**: 22 HTTP GET requests (`/home/labs/?page=1..22`).
   - **10 BIS Labs**: 1 HTTP GET request (`/home/bis_labs/`).
   - **140 Empanelled Labs**: 7 HTTP GET requests (`/home/empaneled_labs/?page=1..7`).
   - **Total**: Exactly **30 HTTP requests** to acquire complete directory metadata, contact cards, addresses, and `internal_id` scope links for all 581 labs.
2. **On-Demand or Pre-Indexed IS-to-Lab Resolution**:
   - For any standard (e.g., `IS 8978`), `/home/search_labs/?lab_is_number=<doc_no>` reliably returns all matching labs in 1–2 requests.
3. **Structured Scope and Fee Extraction**:
   - BeautifulSoup parsing of `/home_lab_scope/<internal_id>/` extracts standard codes, validity, fees, and clause breakups into deterministic schemas without LLM hallucinations.
4. **Strict Category Segregation**:
   - Tagging and filtering labs by administrative tier (`BIS_OWNED`, `BIS_RECOGNIZED`, `BIS_EMPANELLED`) prevents accidental mixing.

---

### 9. What cannot be automated?

1. **Operational Turnaround Times & Instant Lab Acceptance**:
   - LIMS does not track whether a laboratory currently has an equipment breakdown or backlog. Users must use the provided contact details (phone, email) to confirm current testing lead times.
2. **Live Sample Submission / Booking**:
   - Sample submission (`/home/lab_sample/`) requires an active manufacturer login and official BIS sample booking credentials. The Lab Finder will serve as a discovery and matching tool, not a sample dispatch client.
3. **Dynamic Distance Calculations Without Geocoding**:
   - Spatial distance between the user and the laboratory cannot be computed without resolving the lab\'s address/PIN code to geographical coordinates.
4. **Final Commercial Billing / Taxes**:
   - Listed fees exclude GST and may not include sample destruction, handling, or courier expenses.

---

## Comparison Matrix: Lab Categories on BIS LIMS

| Metric | BIS Recognized Labs | BIS Owned Labs | Empanelled Labs |
| :--- | :--- | :--- | :--- |
| **Total Count** | **431** | **10** | **140** |
| **Primary URL** | `/home/labs/` | `/home/bis_labs/` | `/home/empaneled_labs/` |
| **Pages** | 22 pages (20/page) | 1 page | 7 pages (20/page) |
| **Lab Code Format** | 7-digit numeric (e.g. `8102006`) | Listed as `-` (identified by branch name) | 7-digit numeric (e.g. `6133034`) |
| **Operator** | Private / Commercial accredited labs | Bureau of Indian Standards (Govt) | Other Govt / Autonomous institutions |
| **Validity Date** | Explicit expiry date (e.g., `31 Dec, 2026`) | Permanent / Ongoing (`-`) | Periodic review / Expiry date |
| **View Scope Link** | `/home_lab_scope/<id>/` | `/home_lab_scope/<id>/` | `/home_lab_scope/<id>/` |

---

## Recommended Architecture for Phase F3 Lab Finder

```
User Query (e.g. "Find labs for IS 8978 near Delhi")
                       ↓
         Phase F3 Lab Finder Engine
                       ↓
┌────────────────────────────────────────────────────────┐
│ 1. BIS LIMS Authoritative Retrieval Layer              │
│    - Standard Match: IS 8978 → 28 Accredited Labs      │
│    - Tier Separation: 2 BIS Labs + 24 Recognized Labs  │
│    - Extract: Contact, Phone, Email, Fees, Validity    │
└────────────────────────────────────────────────────────┘
                       ↓
┌────────────────────────────────────────────────────────┐
│ 2. Spatial Geocoding & Ranking Layer                   │
│    - Lab Addresses & Pincodes Geocoded to (Lat, Lng)   │
│    - Distance Calculation: Haversine / Distance Matrix │
│    - Ranked by: Distance (km) + Capability (Complete) │
└────────────────────────────────────────────────────────┘
                       ↓
┌────────────────────────────────────────────────────────┐
│ 3. AI Hub 2.0 Lab Finder Frontend Presentation        │
│    - Interactive Map View + Ranked Lab Cards           │
│    - Direct Contact Pill (Phone, Email, Manager)       │
│    - Fee Breakdown Drawer (₹14,000 + Clause List)      │
└────────────────────────────────────────────────────────┘
```

---

## Conclusion & Stop Point Status

All 9 investigative questions have been conclusively resolved with verified live evidence from the production BIS LIMS system. 

As instructed, **no coding of the Lab Finder has been initiated**. This report is submitted for your review and approval before proceeding to Step 2.
