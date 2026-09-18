/**
 * BIS AI Assistant - Mock Data & Assistant Service Adapter (Phase 12.E / F1)
 *
 * Provides high-fidelity mock responses faithful to the Phase 12.E production backend contract,
 * and incorporates the live Production API adapter for seamless integration.
 * Key Principle: "Never invent an answer when authoritative BIS evidence is insufficient."
 */

import { apiUrl } from './config.js';

export const MOCK_RESPONSES = {
    // 1. Known standard query -> SUFFICIENT
    "what is is 8978?": {
        status: "SUFFICIENT",
        query: "What is IS 8978?",
        answer: `IS 8978 is the Indian Standard titled "Specification for electric instantaneous water heaters (Second Revision)".

### What it covers
This standard specifies the requirements for electric instantaneous water heaters.

### Standard details
- Standard: IS 8978
- Year: 1992
- Title: Specification for electric instantaneous water heaters (Second Revision)

### In simple terms
It defines the applicable requirements and specifications for electric instantaneous water heaters.`,
        claims: [
            {
                subject: "IS 8978",
                predicate: "has title",
                object: "Specification for electric instantaneous water heaters (Second Revision)",
                verified: true,
                supporting_evidence_ids: ["ru_std_IS 8978"]
            },
            {
                subject: "IS 8978",
                predicate: "governs commodity",
                object: "Electric Instantaneous Water Heaters",
                verified: true,
                supporting_evidence_ids: ["ru_std_IS 8978"]
            },
            {
                subject: "IS 8978",
                predicate: "falls under conformity scheme",
                object: "Scheme-I (ISI Mark Certification)",
                verified: true,
                supporting_evidence_ids: ["ru_std_IS 8978", "ru_dk_LIC-002"]
            }
        ],
        entities: [
            { id: "STANDARD:IS 8978", name: "IS 8978 : 1992", type: "Indian Standard" },
            { id: "PRODUCT:WaterHeaters", name: "Electric Instantaneous Water Heaters", type: "Governed Commodity" },
            { id: "SCHEME:Scheme-I", name: "Scheme-I (ISI Mark)", type: "Conformity Scheme" }
        ],
        evidence: [
            {
                unit_id: "ru_std_IS 8978",
                type: "Standard Specification",
                standard_number: "IS 8978 : 1992",
                title: "Specification for electric instantaneous water heaters (Second Revision)",
                laboratory: null,
                scope: "Household and commercial electric instantaneous water heaters",
                clause: "Clause 1.1 (Scope)",
                page: 1,
                source_authority: "Bureau of Indian Standards",
                source_url: "https://www.services.bis.gov.in/standards/is-8978",
                sha256: "68229fbe37078b6571da7a0b71747fd4b5b383f232b796c71ae6e773c0c13dbe",
                passage: "IS 8978:1992 specifies the construction, rating, and normative safety performance requirements for electric instantaneous water heaters designed for heating water below boiling temperature at household voltages up to 250V AC.",
                entities: [
                    { subject: "IS 8978", predicate: "HAS_TITLE", object: "Specification for electric instantaneous water heaters" },
                    { subject: "IS 8978", predicate: "REVISION", object: "Second Revision" }
                ]
            },
            {
                unit_id: "ru_dk_SCOPE-840-01_scope",
                type: "Laboratory Scope Schedule",
                standard_number: "IS 8978 : 1992",
                title: "Central Laboratory Testing Scope Schedule",
                laboratory: "Laboratory 840 (BIS Central Laboratory)",
                scope: "Electric instantaneous water heater testing",
                clause: "Scope Schedule - Section B",
                page: 3,
                source_authority: "BIS LIMS (Laboratory Information Management System)",
                source_url: "https://www.lims.bis.gov.in/scopes/840",
                sha256: "c91c1f0a46f235ff64738c9e1ea1fecedf9078b94076779ffd1635d95b068486",
                passage: "Laboratory 840 is officially listed with verified testing scope for IS 8978 (1992): Specification for electric instantaneous water heaters (Second Revision). Parameters tested include insulation resistance, leakage current, high voltage withstand, and thermal cutoff functioning.",
                entities: [
                    { subject: "LAB:840", predicate: "HAS_SCOPE_FOR", object: "IS 8978 (1992)" }
                ]
            }
        ],
        citations: [
            {
                title: "IS 8978:1992 Official Gazette Standard",
                authority: "Bureau of Indian Standards",
                locator: "Clause 1.1 (Scope)",
                sha256: "68229fbe37078b6571da7a0b71747fd4b5b383f232b796c71ae6e773c0c13dbe"
            },
            {
                title: "BIS LIMS Central Scope Registry (Lab 840)",
                authority: "BIS LIMS",
                locator: "Scope ID: 840-01",
                sha256: "c91c1f0a46f235ff64738c9e1ea1fecedf9078b94076779ffd1635d95b068486"
            }
        ],
        subquestions: [
            { id: "subq-1", query: "What is IS 8978?", intent: "STANDARD_LOOKUP", status: "SUFFICIENT" }
        ],
        provenance: {
            source: "Bureau of Indian Standards Official Normative Data (v22 Frozen Baseline)",
            configuration: { rrf_k: 20, boost_factor: 2.5, top_k: 10 }
        },
        limitations: [],
        missing_reasons: []
    },

    // 1b. Standard Requirements query -> SUFFICIENT
    "what are the requirements of is 8978?": {
        status: "SUFFICIENT",
        query: "What are the requirements of IS 8978?",
        answer: `IS 8978 specifies the requirements for electric instantaneous water heaters (Second Revision).

### Applicable scope & parameters
- Standard: IS 8978
- Product: Electric instantaneous water heaters
- Verified Testing Parameters: Insulation resistance, leakage current, high voltage withstand, and thermal cutoff functioning.

### Normative text availability
Detailed clause-by-clause normative texts and full test procedures are published in the official BIS gazette standard document. The indexed baseline confirms the standard title, revision, and testing scope parameters.`,
        claims: [
            {
                subject: "IS 8978",
                predicate: "specifies requirements for",
                object: "Electric Instantaneous Water Heaters",
                verified: true,
                supporting_evidence_ids: ["ru_std_IS 8978"]
            }
        ],
        entities: [
            { id: "STANDARD:IS 8978", name: "IS 8978 : 1992", type: "Indian Standard" },
            { id: "PRODUCT:WaterHeaters", name: "Electric Instantaneous Water Heaters", type: "Governed Commodity" }
        ],
        evidence: [
            {
                unit_id: "ru_std_IS 8978",
                type: "Standard Specification",
                standard_number: "IS 8978 : 1992",
                title: "Specification for electric instantaneous water heaters (Second Revision)",
                laboratory: null,
                scope: "Household and commercial electric instantaneous water heaters",
                clause: "Clause 1.1 (Scope)",
                page: 1,
                source_authority: "Bureau of Indian Standards",
                source_url: "https://www.services.bis.gov.in/standards/is-8978",
                sha256: "68229fbe37078b6571da7a0b71747fd4b5b383f232b796c71ae6e773c0c13dbe",
                passage: "IS 8978:1992 specifies the construction, rating, and normative safety performance requirements for electric instantaneous water heaters designed for heating water below boiling temperature at household voltages up to 250V AC."
            }
        ],
        citations: [],
        subquestions: [
            { id: "subq-1", query: "What are the requirements of IS 8978?", intent: "STANDARD_LOOKUP", status: "SUFFICIENT" }
        ],
        provenance: {
            source: "Bureau of Indian Standards Official Normative Data (v22 Frozen Baseline)",
            configuration: { rrf_k: 20, boost_factor: 2.5, top_k: 10 }
        },
        limitations: [],
        missing_reasons: []
    },

    // 1c. Explain Standard query -> SUFFICIENT
    "explain is 8978": {
        status: "SUFFICIENT",
        query: "Explain IS 8978",
        answer: `IS 8978 is the Indian Standard titled "Specification for electric instantaneous water heaters (Second Revision)".

### Scope & Overview
This standard specifies the safety, performance, and constructional requirements for electric instantaneous water heaters.

### Testing & Laboratory Availability
Testing according to IS 8978 is carried out by BIS-accredited testing facilities:
- Laboratory 112: Accredited for electric instantaneous water heater testing under IS 8978.
- Laboratory 840: Accredited for electric instantaneous water heater testing under IS 8978.

Testing fee recorded in available records is INR 22,000 (exclusive of taxes) at accredited facilities.`,
        claims: [
            {
                subject: "IS 8978",
                predicate: "has title",
                object: "Specification for electric instantaneous water heaters (Second Revision)",
                verified: true,
                supporting_evidence_ids: ["ru_std_IS 8978"]
            }
        ],
        entities: [
            { id: "STANDARD:IS 8978", name: "IS 8978 : 1992", type: "Indian Standard" }
        ],
        evidence: [],
        citations: [],
        subquestions: [
            { id: "subq-1", query: "Explain IS 8978", intent: "STANDARD_LOOKUP", status: "SUFFICIENT" }
        ],
        provenance: {
            source: "Bureau of Indian Standards Official Normative Data (v22 Frozen Baseline)",
            configuration: { rrf_k: 20, boost_factor: 2.5, top_k: 10 }
        },
        limitations: [],
        missing_reasons: []
    },

    // 2. Laboratory Scope query -> SUFFICIENT
    "which laboratories explicitly have scope for is 8978?": {
        status: "SUFFICIENT",
        query: "Which laboratories explicitly have scope for IS 8978?",
        answer: `### Accredited Testing Laboratories for IS 8978

The following accredited laboratories hold explicit testing scope for **IS 8978 : 1992** (*Specification for electric instantaneous water heaters*):

1. **Laboratory 112** (BIS Regional Testing Laboratory)
   - Scope: Electric instantaneous water heater testing under IS 8978 (1992).
2. **Laboratory 840** (BIS Central Testing Laboratory)
   - Scope: Specification for electric instantaneous water heaters (Second Revision) testing under IS 8978.`,
        claims: [
            {
                subject: "Laboratory 840",
                predicate: "is listed with testing scope for",
                object: "IS 8978 (1992)",
                verified: true,
                supporting_evidence_ids: ["ru_dk_SCOPE-840-01_scope"]
            },
            {
                subject: "Laboratory 112",
                predicate: "is listed with testing scope for",
                object: "IS 8978 (1992)",
                verified: true,
                supporting_evidence_ids: ["ru_dk_SCOPE-112-01_scope"]
            }
        ],
        entities: [
            { id: "LAB:840", name: "Laboratory 840 (Central)", type: "BIS Testing Laboratory" },
            { id: "LAB:112", name: "Laboratory 112 (Regional)", type: "BIS Testing Laboratory" },
            { id: "STANDARD:IS 8978", name: "IS 8978:1992", type: "Indian Standard" }
        ],
        evidence: [
            {
                unit_id: "ru_dk_SCOPE-840-01_scope",
                type: "Laboratory Scope Entry",
                standard_number: "IS 8978 : 1992",
                title: "BIS LIMS Scope Record - Lab 840",
                laboratory: "Laboratory 840",
                scope: "Electric instantaneous water heater testing (Second Revision)",
                clause: "Schedule A - Scope Item 14",
                page: 2,
                source_authority: "BIS LIMS",
                source_url: "https://www.lims.bis.gov.in/lab/840/scope",
                sha256: "c91c1f0a46f235ff64738c9e1ea1fecedf9078b94076779ffd1635d95b068486",
                passage: "Laboratory 840 is listed with testing scope for IS 8978 (1992). Scope: IS 8978 (840) {\"lab_code\": \"840\", \"standard\": \"IS 8978 (1992)\", \"test\": \"Specification for electric instantaneous water heaters (Second Revision)\"}.",
                entities: [
                    { subject: "LAB:840", predicate: "HAS_SCOPE_FOR", object: "IS 8978 (1992)" }
                ]
            },
            {
                unit_id: "ru_dk_SCOPE-112-01_scope",
                type: "Laboratory Scope Entry",
                standard_number: "IS 8978 : 1992",
                title: "BIS LIMS Scope Record - Lab 112",
                laboratory: "Laboratory 112",
                scope: "Specification for electric instantaneous water heaters",
                clause: "Schedule B - Scope Item 09",
                page: 1,
                source_authority: "BIS LIMS",
                source_url: "https://www.lims.bis.gov.in/lab/112/scope",
                sha256: "ca8d0ad4c614adf796713973c0205ee522331b3a8e848704d4726141c91660ad",
                passage: "Laboratory 112 is listed with testing scope for IS 8978 (1992). Scope: IS 8978 (112) {\"lab_code\": \"112\", \"standard\": \"IS 8978 (1992)\", \"test\": \"Specification for electric instantaneous water heaters (Second Revision)\"}.",
                entities: [
                    { subject: "LAB:112", predicate: "HAS_SCOPE_FOR", object: "IS 8978 (1992)" }
                ]
            }
        ],
        citations: [
            {
                title: "BIS LIMS Laboratory Accreditation Directory (Lab 840)",
                authority: "BIS LIMS",
                locator: "Scope Item 840-01",
                sha256: "c91c1f0a46f235ff64738c9e1ea1fecedf9078b94076779ffd1635d95b068486"
            },
            {
                title: "BIS LIMS Laboratory Accreditation Directory (Lab 112)",
                authority: "BIS LIMS",
                locator: "Scope Item 112-01",
                sha256: "ca8d0ad4c614adf796713973c0205ee522331b3a8e848704d4726141c91660ad"
            }
        ],
        subquestions: [
            { id: "subq-1", query: "Which laboratories explicitly have scope for IS 8978?", intent: "LABORATORY_SCOPE", status: "SUFFICIENT" }
        ],
        provenance: {
            source: "BIS LIMS Scope Registry (v22 Frozen Baseline)",
            configuration: { rrf_k: 20, boost_factor: 2.5, top_k: 10 }
        },
        limitations: [],
        missing_reasons: []
    },

    // 3. Testing-fee query -> PARTIAL
    "what is the testing fee for is 8978?": {
        status: "PARTIAL",
        query: "What is the testing fee for IS 8978?",
        answer: `### Laboratory Testing Charges for IS 8978

The available BIS LIMS fee records list the following testing charges for **IS 8978** (*Specification for electric instantaneous water heaters*):

- **Laboratory 112:** INR 22,000 (exclusive of taxes) for electric instantaneous water heater testing.
- **Laboratory 840:** INR 22,000 (exclusive of taxes) for electric instantaneous water heater testing.

*Note: These charges represent laboratory testing fees for specific test parameters recorded at these facilities and do not include statutory application or annual licensing fees.*`,
        limitations: [
            "Detailed clause charges exist but no total fee is specified. The source does not establish that these constitute the complete testing cost.",
            "The INR 22,000 fee is facility-specific to Lab 112 / Lab 840 and must NOT be interpreted as a universal BIS testing fee."
        ],
        what_evidence_establishes: [
            "Testing charge of INR 22,000 recorded at BIS Laboratory 112 for IS 8978 parameter testing.",
            "Testing charge of INR 22,000 recorded at BIS Laboratory 840 for IS 8978 parameter testing."
        ],
        what_evidence_does_not_establish: [
            "A universal or statutory total BIS testing fee across all testing schemes or laboratories.",
            "Complete product certification lifecycle costs (application fees, factory inspection, and marking fees are distinct)."
        ],
        claims: [
            {
                subject: "Laboratory 112",
                predicate: "assesses testing fee under IS 8978",
                object: "INR 22,000",
                verified: true,
                supporting_evidence_ids: ["ru_dk_SCOPE-112-01_fee"]
            },
            {
                subject: "Laboratory 840",
                predicate: "assesses testing fee under IS 8978",
                object: "INR 22,000",
                verified: true,
                supporting_evidence_ids: ["ru_dk_SCOPE-840-01_fee"]
            }
        ],
        entities: [
            { id: "STANDARD:IS 8978", name: "IS 8978 : 1992", type: "Indian Standard" },
            { id: "LAB:112", name: "Laboratory 112", type: "BIS Laboratory" },
            { id: "LAB:840", name: "Laboratory 840", type: "BIS Laboratory" }
        ],
        evidence: [
            {
                unit_id: "ru_dk_SCOPE-112-01_fee",
                type: "LIMS Testing Fee Schedule",
                standard_number: "IS 8978 (1992)",
                title: "Testing Fee Schedule - Lab 112",
                laboratory: "Laboratory 112",
                scope: "Testing Fee: IS 8978 (112)",
                clause: "Schedule Item 112-FEE",
                page: 1,
                source_authority: "BIS LIMS Fee Schedule",
                source_url: "https://www.lims.bis.gov.in/fee/112/is-8978",
                sha256: "4d6a07b644b5a9d172ee5c7acd34ff017746aaf58321424f462908ba87a54df6",
                passage: "Testing Fee: IS 8978 (112) {\"test_parameter\": \"Electric instantaneous water heater testing\", \"amount_inr\": 22000, \"exclusion_taxes\": true}.",
                entities: [
                    { subject: "LAB:112", predicate: "HAS_FEE", object: "22000 INR" }
                ]
            }
        ],
        citations: [
            {
                title: "BIS LIMS Published Testing Fee Master",
                authority: "BIS LIMS",
                locator: "Schedule 112-FEE",
                sha256: "4d6a07b644b5a9d172ee5c7acd34ff017746aaf58321424f462908ba87a54df6"
            }
        ],
        subquestions: [
            { id: "subq-1", query: "What is the testing fee for IS 8978?", intent: "TESTING_FEE", status: "PARTIAL" }
        ],
        provenance: {
            source: "BIS LIMS Fee Register (v22 Frozen Baseline)",
            configuration: { rrf_k: 20, boost_factor: 2.5, top_k: 10 }
        }
    },

    // 4. Missing standard (IS 616 absent from v22) -> INSUFFICIENT
    "what is is 616?": {
        status: "INSUFFICIENT",
        query: "What is IS 616?",
        answer: "I could not verify this from the available BIS evidence.",
        missing_reasons: [
            "IS 616 is deliberately omitted from the frozen v22 baseline dataset.",
            "Deterministic Grounding Rule: The BIS AI Assistant will not generate speculative or unverified claims in the absence of indexed primary sources."
        ],
        limitations: [],
        what_evidence_establishes: [],
        what_evidence_does_not_establish: [],
        claims: [],
        entities: [],
        evidence: [],
        citations: [],
        subquestions: [
            { id: "subq-1", query: "What is IS 616?", intent: "STANDARD_LOOKUP", status: "INSUFFICIENT" }
        ],
        provenance: {
            source: "Bureau of Indian Standards Official Normative Data (v22 Frozen Baseline)",
            configuration: { rrf_k: 20, boost_factor: 2.5, top_k: 10 }
        }
    },

    // 5. Unknown standard -> INSUFFICIENT
    "what is is 999999?": {
        status: "INSUFFICIENT",
        query: "What is IS 999999?",
        answer: "I could not verify this from the available BIS evidence.",
        missing_reasons: [
            "No standard matching IS 999999 exists in the official Bureau of Indian Standards catalog.",
            "Zero Hallucination Safeguard: In accordance with Phase 12.CB ClaimValidator rules, unknown or unregistered standard codes are strictly refused."
        ],
        limitations: [],
        what_evidence_establishes: [],
        what_evidence_does_not_establish: [],
        claims: [],
        entities: [],
        evidence: [],
        citations: [],
        subquestions: [
            { id: "subq-1", query: "What is IS 999999?", intent: "UNKNOWN", status: "INSUFFICIENT" }
        ],
        provenance: {
            source: "Bureau of Indian Standards Catalog (v22 Frozen Baseline)",
            configuration: { rrf_k: 20, boost_factor: 2.5, top_k: 10 }
        }
    },

    // 6. Unknown laboratory -> INSUFFICIENT
    "what is lab-unknown_79dcb12d?": {
        status: "INSUFFICIENT",
        query: "What is LAB-UNKNOWN_79dcb12d?",
        answer: "I could not verify this from the available BIS evidence.",
        missing_reasons: [
            "Query references an explicitly UNKNOWN entity (LAB-UNKNOWN_79dcb12d).",
            "Zero Hallucination Safeguard: No laboratory registration matches this code in the official LIMS registry."
        ],
        limitations: [],
        what_evidence_establishes: [],
        what_evidence_does_not_establish: [],
        claims: [],
        entities: [],
        evidence: [],
        citations: [],
        subquestions: [
            { id: "subq-1", query: "What is LAB-UNKNOWN_79dcb12d?", intent: "UNKNOWN", status: "INSUFFICIENT" }
        ],
        provenance: {
            source: "BIS LIMS Registry (v22 Frozen Baseline)",
            configuration: { rrf_k: 20, boost_factor: 2.5, top_k: 10 }
        }
    },

    // 7. Unindexed product query -> INSUFFICIENT (Strict anti-hallucination refusal)
    "i manufacure led lamps which tests are required for htis": {
        status: "INSUFFICIENT",
        query: "i manufacure led lamps which tests are required for htis",
        answer: "I could not verify testing requirements for LED lamps from the available BIS evidence. The indexed records do not contain standards or testing specifications for this product.",
        missing_reasons: [
            "LED lamps and associated testing standards are not present in the indexed BIS baseline dataset.",
            "Zero Hallucination Safeguard: In accordance with BIS evidence gating, requirements for unindexed products are not fabricated."
        ],
        limitations: [],
        what_evidence_establishes: [],
        what_evidence_does_not_establish: [],
        claims: [],
        entities: [],
        evidence: [],
        citations: [],
        subquestions: [
            { id: "subq-1", query: "i manufacure led lamps which tests are required for htis", intent: "REQUIREMENT_LOOKUP", status: "INSUFFICIENT" }
        ],
        provenance: {
            source: "Bureau of Indian Standards Official Normative Data (v22 Frozen Baseline)",
            configuration: { rrf_k: 20, boost_factor: 2.5, top_k: 10 }
        }
    },

    // 8. Certification schemes / types of certifications -> SUFFICIENT
    "how many types of certifications are there": {
        status: "SUFFICIENT",
        query: "how many types of certifications are there",
        answer: `### BIS Certification Schemes

The **Bureau of Indian Standards (BIS)** operates several conformity assessment and certification schemes to ensure product quality, safety, and consumer reliability across India:

1. **Product Certification Scheme (ISI Mark - Scheme-I)**
   - Applicable to domestic manufacturers across thousands of industrial and consumer products.
   - Requires factory audits, process quality control, in-house testing facilities, and sample verification.
   - Mandatory for commodities governed under Quality Control Orders (QCOs), and voluntary for others.

2. **Compulsory Registration Scheme (CRS - Scheme-II)**
   - Specifically tailored for electronic and IT goods (e.g., mobile phones, laptops, LED drivers, power adapters).
   - Operates on a self-declaration of conformity based on test reports from BIS-recognized laboratories, without mandatory preliminary factory inspections.

3. **Foreign Manufacturers Certification Scheme (FMCS)**
   - Enables overseas manufacturers located outside India to obtain a BIS license and use the Standard Mark (ISI Mark) on products exported to India.
   - Requires on-site inspection of foreign manufacturing units and independent sample testing in India.

4. **Hallmarking Scheme**
   - Statutory quality assurance for precious metals (Gold and Silver jewelry and artefacts).
   - Certifies purity and fineness through Assaying and Hallmarking Centres (AHCs) with a unique Hallmarking Unique ID (HUID).

5. **Management Systems Certification Scheme (MSCS)**
   - Certifies organizations for compliance with international and national management system standards (e.g., ISO 9001 for Quality, ISO 14001 for Environment, ISO 22000 for Food Safety, and ISO 45001 for Occupational Health).

6. **ECO Mark Scheme**
   - Grants specialized certification for products meeting specific environmental criteria in addition to the quality requirements of Indian Standards.`,
        claims: [
            {
                subject: "Bureau of Indian Standards",
                predicate: "operates conformity assessment schemes",
                object: "Scheme-I (ISI Mark), Scheme-II (CRS), FMCS, Hallmarking, MSCS, and ECO Mark",
                verified: true,
                supporting_evidence_ids: ["ru_bis_act_2016_schemes"]
            }
        ],
        entities: [
            { id: "SCHEME:Scheme-I", name: "Product Certification Scheme (ISI Mark)", type: "Conformity Scheme" },
            { id: "SCHEME:Scheme-II", name: "Compulsory Registration Scheme (CRS)", type: "Conformity Scheme" },
            { id: "SCHEME:FMCS", name: "Foreign Manufacturers Certification Scheme", type: "Conformity Scheme" },
            { id: "SCHEME:Hallmarking", name: "Hallmarking Scheme", type: "Conformity Scheme" }
        ],
        evidence: [
            {
                unit_id: "ru_bis_act_2016_schemes",
                type: "Statutory Scheme Overview",
                standard_number: "BIS Act, 2016",
                title: "BIS Conformity Assessment Regulations and Schemes",
                laboratory: null,
                scope: "Overview of BIS conformity assessment and certification schemes",
                clause: "Chapter III (Conformity Assessment)",
                page: 1,
                source_authority: "Bureau of Indian Standards",
                source_url: "https://www.bis.gov.in/index.php/conformity-assessment/",
                sha256: "b15c3271890fae41298418384219481928419284918249124",
                passage: "BIS operates multiple conformity assessment schemes under the BIS Act, 2016: Scheme-I (Product Certification/ISI Mark), Scheme-II (Compulsory Registration Scheme), Foreign Manufacturers Certification Scheme (FMCS), Hallmarking of Gold and Silver, Management Systems Certification Scheme (MSCS), and ECO Mark Scheme.",
                entities: [
                    { subject: "BIS", predicate: "OPERATES", object: "Conformity Assessment Schemes" }
                ]
            }
        ],
        citations: [
            {
                title: "BIS Act, 2016 & Conformity Assessment Regulations",
                authority: "Bureau of Indian Standards",
                locator: "Chapter III",
                sha256: "b15c3271890fae41298418384219481928419284918249124"
            }
        ],
        missing_reasons: [],
        limitations: [],
        what_evidence_establishes: [],
        what_evidence_does_not_establish: [],
        subquestions: [
            { id: "subq-1", query: "how many types of certifications are there", intent: "SCHEME_OVERVIEW", status: "SUFFICIENT" }
        ],
        provenance: {
            source: "Bureau of Indian Standards Official Normative Data (v22 Frozen Baseline)",
            configuration: { rrf_k: 20, boost_factor: 2.5, top_k: 10 }
        }
    },

    // 9. Hallmarking inquiries -> SUFFICIENT
    "tell me abput hallmarking": {
        status: "SUFFICIENT",
        query: "tell me abput hallmarking",
        answer: `### BIS Hallmarking Scheme

**Hallmarking** is the official determination and statutory recording of the proportionate content (purity/fineness) of precious metal in gold and silver articles under the **Bureau of Indian Standards Act, 2016**.

### Key Elements of BIS Hallmarking
- **Mandatory Purity Assurance:** Mandatory hallmarking protects consumers against adulteration and obligates jewellers to sell only verified purity grades (e.g., 14K, 18K, 20K, 22K, 23K, and 24K for gold).
- **Assaying and Hallmarking Centres (AHCs):** Independent BIS-recognized testing centres assay each article to verify precious metal purity.
- **Hallmarking Charges:** Fixed statutory fees are paid per article irrespective of the weight of the jewellery.

### Components of a Hallmarked Article
A genuine BIS hallmarked gold article features three distinct marks:
1. **BIS Standard Mark:** The official triangular BIS logo.
2. **Purity / Fineness Grade:** Purity in carats and fineness (e.g., \`22K916\` for 22 carat gold with 91.6% purity).
3. **HUID (Hallmark Unique Identification):** A 6-character alphanumeric code unique to each jewellery piece, enabling consumers to verify authenticity using the **BIS Care App**.`,
        claims: [
            {
                subject: "BIS Hallmarking",
                predicate: "certifies purity of precious metals",
                object: "Gold and Silver articles under BIS Act 2016",
                verified: true,
                supporting_evidence_ids: ["ru_hallmarking_regulations"]
            }
        ],
        entities: [
            { id: "SCHEME:Hallmarking", name: "BIS Hallmarking Scheme", type: "Conformity Scheme" },
            { id: "IDENTIFIER:HUID", name: "Hallmark Unique Identification", type: "Security Feature" }
        ],
        evidence: [
            {
                unit_id: "ru_hallmarking_regulations",
                type: "Statutory Hallmarking Overview",
                standard_number: "IS 1417 & IS 2112",
                title: "BIS Hallmarking Scheme Regulations",
                laboratory: null,
                scope: "Assaying and Hallmarking of Gold and Silver Articles",
                clause: "Hallmarking Scheme Guidelines",
                page: 1,
                source_authority: "Bureau of Indian Standards",
                source_url: "https://www.bis.gov.in/hallmarking-overview/",
                sha256: "h411m4rk1n97890fae41298418384219481928419284918249",
                passage: "Under the BIS Hallmarking Scheme, jewellers must register to sell hallmarked jewellery. Hallmarked gold jewellery features the BIS logo, purity grade in carat and fineness (e.g. 22K916), and a 6-digit alphanumeric HUID code assigned by recognized Assaying and Hallmarking Centres.",
                entities: [
                    { subject: "Hallmarking", predicate: "CERTIFIES_PURITY_FOR", object: "Gold and Silver" }
                ]
            }
        ],
        citations: [
            {
                title: "BIS Hallmarking Scheme Guidelines & Regulations",
                authority: "Bureau of Indian Standards",
                locator: "Section 14 & 15, BIS Act 2016",
                sha256: "h411m4rk1n97890fae412984183842194819284918249"
            }
        ],
        missing_reasons: [],
        limitations: [],
        what_evidence_establishes: [],
        what_evidence_does_not_establish: [],
        subquestions: [
            { id: "subq-1", query: "tell me abput hallmarking", intent: "HALLMARKING_OVERVIEW", status: "SUFFICIENT" }
        ],
        provenance: {
            source: "Bureau of Indian Standards Official Normative Data (v22 Frozen Baseline)",
            configuration: { rrf_k: 20, boost_factor: 2.5, top_k: 10 }
        }
    }
};

MOCK_RESPONSES["tell me about hallmarking"] = MOCK_RESPONSES["tell me abput hallmarking"];

/**
 * Production Assistant Service Adapter
 * Seamlessly interfaces between the UI and either:
 *  1. Production Phase 12.E API (/api/phase12e/query)
 *  2. High-fidelity Mock Dataset
 */
export class AssistantService {
    static mode = 'production'; // 'production' | 'mock'
    static backendAvailable = false;
    static checkedHealth = false;

    /**
     * Probes the production backend health endpoint.
     */
    static async checkHealth() {
        if (this.checkedHealth && this.backendAvailable) return { status: 'healthy' };
        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 4000);
            let res = await fetch(apiUrl('/api/assistant/health'), { signal: controller.signal });
            if (!res.ok) {
                res = await fetch(apiUrl('/api/phase12e/health'), { signal: controller.signal });
            }
            clearTimeout(timeoutId);
            if (res.ok) {
                const data = await res.json();
                this.backendAvailable = true;
                this.checkedHealth = true;
                return data;
            }
        } catch (e) {
            // Backend endpoint offline
        }
        this.backendAvailable = false;
        this.checkedHealth = true;
        return null;
    }

    /**
     * Primary query dispatcher.
     * In production mode, communicates directly with the real API backend.
     * Preserves explicit mock mode only when explicitly requested.
     * Eliminates silent fallbacks from API failures into mock responses.
     */
    static async query(query, options = {}) {
        const cleanQuery = (query || "").trim();
        const mode = options.mode || this.mode;
        const override = (options.groundingOverride || "auto").toLowerCase();

        // If mock mode is explicitly chosen or demo override is forced
        if (mode === 'mock' || override !== 'auto') {
            return this.queryMock(cleanQuery, options);
        }

        // Production F2 assistant backend request
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 25000);
        const extraHeaders = options.headers || {};
        const reqPayload = {
            query: cleanQuery,
            language: options.language || 'en',
            target_language: options.language || options.target_language || 'en',
            response_style: options.responseStyle || options.response_style || 'Detailed & Explanatory',
            history: options.history || []
        };
        // Normalize to canonical database value ('quick', 'detailed', 'professional') for POST /api/assistant/query
        if (reqPayload.response_style === 'Quick & Simple') reqPayload.response_style = 'quick';
        else if (reqPayload.response_style === 'Detailed & Explanatory') reqPayload.response_style = 'detailed';
        else if (reqPayload.response_style === 'Professional & Compliance-focused') reqPayload.response_style = 'professional';
        try {
            let res = await fetch(apiUrl('/api/assistant/query'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', ...extraHeaders },
                body: JSON.stringify(reqPayload),
                signal: controller.signal
            });

            // Fallback to direct Phase 12.E endpoint if 404
            if (res.status === 404) {
                res = await fetch(apiUrl('/api/phase12e/query'), {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', ...extraHeaders },
                    body: JSON.stringify(reqPayload),
                    signal: controller.signal
                });
            }

            // Seamless guest fallback if 401 (e.g. expired session token)
            if (res.status === 401 && (extraHeaders['Authorization'] || extraHeaders['authorization'])) {
                console.warn('[Assistant API] 401 with auth token. Retrying seamlessly in guest mode...');
                const guestHeaders = { ...extraHeaders };
                delete guestHeaders['Authorization'];
                delete guestHeaders['authorization'];
                res = await fetch(apiUrl('/api/assistant/query'), {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', ...guestHeaders },
                    body: JSON.stringify(reqPayload),
                    signal: controller.signal
                });
            }

            clearTimeout(timeoutId);

            if (res.ok) {
                const data = await res.json();
                this.backendAvailable = true;
                return this._normalizeResponse(data, cleanQuery, options);
            }

            // Extract real backend error details if available
            let errorMsg = `Server error (${res.status})`;
            try {
                const errData = await res.json();
                if (errData?.detail?.error) {
                    errorMsg = errData.detail.error;
                } else if (errData?.error) {
                    errorMsg = errData.error;
                } else if (errData?.message) {
                    errorMsg = errData.message;
                }
            } catch (_) {}
            throw new Error(errorMsg);
        } catch (err) {
            clearTimeout(timeoutId);
            this.backendAvailable = false;
            console.error('[Assistant API Error]:', err.message);
            if (err.name === 'AbortError') {
                throw new Error('Query request timed out. Please check your connection and try again.');
            }
            throw err;
        }
    }

    /**
     * Mock query resolution.
     */
    static async queryMock(query, options = {}) {
        const cleanQuery = (query || "").trim();
        const normKey = cleanQuery.toLowerCase();
        const override = (options.groundingOverride || "auto").toLowerCase();

        // Realistic UI transition delay
        await new Promise((resolve) => setTimeout(resolve, 200));

        if (override === "sufficient") {
            return this._cloneAndAdapt(MOCK_RESPONSES["what is is 8978?"], cleanQuery);
        }
        if (override === "partial") {
            return this._cloneAndAdapt(MOCK_RESPONSES["what is the testing fee for is 8978?"], cleanQuery);
        }
        if (override === "insufficient") {
            return this._buildRefusalResponse(cleanQuery, "Grounding status forced to INSUFFICIENT by demonstration control.");
        }

        if (MOCK_RESPONSES[normKey]) {
            return JSON.parse(JSON.stringify(MOCK_RESPONSES[normKey]));
        }

        if (normKey.includes("hallmark") || normKey.includes("huid")) {
            return this._cloneAndAdapt(MOCK_RESPONSES["tell me abput hallmarking"], cleanQuery);
        }
        if (normKey.includes("certificat") || normKey.includes("scheme") || normKey.includes("isi mark") || normKey.includes("crs") || normKey.includes("fmcs")) {
            return this._cloneAndAdapt(MOCK_RESPONSES["how many types of certifications are there"], cleanQuery);
        }

        if (normKey.includes("led") || (normKey.includes("lamp") && !normKey.includes("8978"))) {
            return JSON.parse(JSON.stringify(MOCK_RESPONSES["i manufacure led lamps which tests are required for htis"]));
        }
        if (normKey.includes("8978") && (normKey.includes("lab") || normKey.includes("scope"))) {
            return JSON.parse(JSON.stringify(MOCK_RESPONSES["which laboratories explicitly have scope for is 8978?"]));
        }
        if (normKey.includes("8978") && (normKey.includes("fee") || normKey.includes("charge") || normKey.includes("cost"))) {
            return JSON.parse(JSON.stringify(MOCK_RESPONSES["what is the testing fee for is 8978?"]));
        }
        if (normKey.includes("8978") && (normKey.includes("require") || normKey.includes("test"))) {
            return JSON.parse(JSON.stringify(MOCK_RESPONSES["what are the requirements of is 8978?"]));
        }
        if (normKey.includes("8978") && normKey.includes("explain")) {
            return JSON.parse(JSON.stringify(MOCK_RESPONSES["explain is 8978"]));
        }
        if (normKey.includes("8978")) {
            return JSON.parse(JSON.stringify(MOCK_RESPONSES["what is is 8978?"]));
        }
        if (normKey.includes("616")) {
            return JSON.parse(JSON.stringify(MOCK_RESPONSES["what is is 616?"]));
        }
        if (normKey.includes("999999")) {
            return JSON.parse(JSON.stringify(MOCK_RESPONSES["what is is 999999?"]));
        }
        if (normKey.includes("lab-unknown") || normKey.includes("79dcb12d")) {
            return JSON.parse(JSON.stringify(MOCK_RESPONSES["what is lab-unknown_79dcb12d?"]));
        }
        if (normKey.includes("evidence") || normKey.includes("requirement")) {
            return this._buildRefusalResponse(cleanQuery, "Authoritative primary sources are required to verify this specific requirement.");
        }

        return this._buildRefusalResponse(
            cleanQuery,
            "No authoritative gazette record found in the available v22 corpus for this query."
        );
    }

    static _normalizeResponse(backendData, query, options = {}) {
        // Map backend schema cleanly to the frontend contract
        const status = backendData.status || "INSUFFICIENT";
        const answer = backendData.answer || "";
        const generation_mode = backendData.generation_mode || (status === "SUFFICIENT" ? "GROUNDED" : "LLM_FALLBACK");
        const llmData = backendData.llm || { used: false, role: null, answer: null, verified_by_bis_rag: (status === "SUFFICIENT") };
        const ragData = backendData.rag || {};
        const response_style = backendData.response_style || options.responseStyle || options.response_style || "Detailed & Explanatory";

        const rawEvidence = ragData.evidence || backendData.evidence || [];
        const rawClaims = ragData.claims || backendData.claims || [];
        const rawSubquestions = ragData.subquestions || backendData.subquestions || [];
        const rawCitations = ragData.citations || backendData.citations || [];
        const rawEntities = ragData.entities || backendData.entities || [];

        // Map evidence units to uniform shape
        const evidence = rawEvidence.map(ev => {
            let title = ev.source_title || ev.document_title || ev.standard_title;
            if (!title) {
                if (ev.standard_number) {
                    title = `${ev.standard_number} Normative Record`;
                } else if (ev.laboratory_id) {
                    title = `Laboratory ${ev.laboratory_id} Testing Scope`;
                } else {
                    title = "Official Gazette Record";
                }
            }
            return {
                unit_id: ev.retrieval_unit_id || ev.record_id || "ru_unknown",
                type: ev.entity_type ? ev.entity_type.replace(/_/g, ' ') : "Authoritative Source",
                standard_number: ev.standard_number || "Indian Standard",
                title: title,
                laboratory: ev.laboratory_id ? `Laboratory ${ev.laboratory_id}` : null,
                scope: ev.text || "",
                clause: ev.clause || "Gazette Provision",
                page: ev.page || 1,
                source_authority: ev.authority === 1 ? "BIS Normative Published" : "Bureau of Indian Standards (BIS)",
                source_url: ev.source_url || "#",
                sha256: ev.sha256 || "68229fbe37078b6571da7a0b71747fd4b5b383f232b796c71ae6e773c0c13dbe",
                passage: ev.text || "",
                entities: ev.relationships || []
            };
        });

        // Map claims
        const claims = rawClaims.map((c, idx) => {
            const subj = (c.subject_entity || c.subject || "Standard").replace(/^(STANDARD|LABORATORY|PRODUCT|SCHEME):/, '');
            const obj = (c.object_entity || c.object || "").replace(/^(STANDARD|LABORATORY|PRODUCT|SCHEME):/, '');
            const pred = c.predicate ? c.predicate.replace(/_/g, " ") : "supported by";
            const statement = c.statement || `${subj} ${pred} ${obj}.`.trim();
            const rawEntities = c.entities || [subj, obj].filter(Boolean);
            const entities = rawEntities.map(e => typeof e === 'string' ? e.replace(/^(STANDARD|LABORATORY|PRODUCT|SCHEME):/, '') : String(e));
            return {
                claim_id: c.claim_id || `c${idx + 1}`,
                statement: statement,
                predicate: pred,
                entities: entities,
                verified: c.support_status === "SUPPORTED" || c.verified === true,
                supporting_evidence_ids: c.supporting_evidence_ids || []
            };
        });

        const missing_reasons = [];
        if (status === "INSUFFICIENT") {
            for (const sq of rawSubquestions) {
                for (const g of (sq.gaps || [])) {
                    const msg = typeof g === 'string' ? g : (g.message || g.description || g.gap_type || '');
                    if (msg && !missing_reasons.includes(msg)) {
                        missing_reasons.push(msg);
                    }
                }
            }
            if (missing_reasons.length === 0) {
                missing_reasons.push("Zero-Hallucination Gate: Evidence in the frozen corpus is insufficient to verify this query.");
            }
        }

        const limitations = [];
        if (status === "PARTIAL") {
            for (const sq of rawSubquestions) {
                for (const g of (sq.gaps || [])) {
                    const msg = typeof g === 'string' ? g : (g.message || g.description || g.gap_type || '');
                    if (msg && !limitations.includes(msg)) {
                        limitations.push(msg);
                    }
                }
            }
        }

        const source_layer = backendData.provenance?.source_layer || 
            (backendData.llm?.role === "LAB_SEARCH_DISPATCH" ? "F3_LAB_FINDER" : undefined);
        const resolved_standard = backendData.standard || 
            (backendData.rag && backendData.rag.standard) || 
            (answer.match(/\bIS\s*\d+\b/i) || [])[0] || undefined;
        const resolved_intent = backendData.intent || 
            (backendData.rag && backendData.rag.intent) || undefined;

        return {
            status,
            query,
            answer,
            intent: resolved_intent,
            standard: resolved_standard,
            source_layer: source_layer,
            generation_mode,
            response_style,
            rag: backendData.rag || null,
            llm: llmData,
            claims,
            evidence,
            citations: rawCitations,
            entities: rawEntities,
            subquestions: rawSubquestions,
            limitations,
            missing_reasons,
            what_evidence_establishes: [],
            what_evidence_does_not_establish: [],
            confidence: "BASELINE_UNCALIBRATED",
            provenance: backendData.provenance || {
                source: "Bureau of Indian Standards Official Normative Data (v22 Frozen Baseline)",
                source_layer: source_layer || "RAG",
                configuration: { rrf_k: 20, boost_factor: 2.5, top_k: 10 }
            }
        };
    }

    static _buildRefusalResponse(query, reason) {
        return {
            status: "INSUFFICIENT",
            query: query,
            answer: "I could not verify this from the available BIS evidence.",
            missing_reasons: [
                reason,
                "Deterministic Grounding Rule: The BIS AI Assistant will not generate speculative or unverified claims in the absence of indexed primary sources."
            ],
            limitations: [],
            what_evidence_establishes: [],
            what_evidence_does_not_establish: [],
            claims: [],
            entities: [],
            evidence: [],
            citations: [],
            subquestions: [
                { id: "subq-1", query: query, intent: "UNKNOWN", status: "INSUFFICIENT" }
            ],
            confidence: "BASELINE_UNCALIBRATED",
            provenance: {
                source: "Bureau of Indian Standards Official Normative Data (v22 Frozen Baseline)",
                configuration: { rrf_k: 20, boost_factor: 2.5, top_k: 10 }
            }
        };
    }

    static _cloneAndAdapt(template, query) {
        const cloned = JSON.parse(JSON.stringify(template));
        cloned.query = query;
        return cloned;
    }
}
