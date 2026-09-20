# Phase 12.CB: Entity-Bound Grounding Report

## Decision
`PHASE_12_CB_STATUS: PASS`

## 1. Validation Queries
### Query: `What is IS 616?`
- **Generation Mode**: FALLBACK
- **Retrieval Count**: 37
- **Selected Evidence Count**: 6
- **Global Evidence Status**: INSUFFICIENT

#### Subquestions
- **Intent**: STANDARD_LOOKUP
  - **Status**: INSUFFICIENT
  - **Confidence**: NONE (0.0)
  - **Gaps**: Factual claims could not be verified by exact identifier/relationship matching.

#### Supported Claims

#### Unsupported Claims (Rejected by validation gate)
- [BIS_FACT] The standard is Standard IS 1599. (UNSUPPORTED)
  - Binding: (STANDARD:IS 1599 -> HAS_TITLE -> Standard IS 1599)

#### Answer Trace
```text
I could not verify this from the available BIS evidence.
```

### Query: `What is the title of IS 616?`
- **Generation Mode**: FALLBACK
- **Retrieval Count**: 39
- **Selected Evidence Count**: 6
- **Global Evidence Status**: INSUFFICIENT

#### Subquestions
- **Intent**: STANDARD_LOOKUP
  - **Status**: INSUFFICIENT
  - **Confidence**: NONE (0.0)
  - **Gaps**: Factual claims could not be verified by exact identifier/relationship matching.

#### Supported Claims

#### Unsupported Claims (Rejected by validation gate)

#### Answer Trace
```text
I could not verify this from the available BIS evidence.
```

### Query: `What is the latest revision of IS 8978?`
- **Generation Mode**: GROUNDED
- **Retrieval Count**: 47
- **Selected Evidence Count**: 10
- **Global Evidence Status**: PARTIAL

#### Subquestions
- **Intent**: HISTORICAL_VERSION
  - **Status**: INSUFFICIENT
  - **Confidence**: LOW (0.0)
  - **Gaps**: No explicit evidence of revision or latest status found.
- **Intent**: STANDARD_LOOKUP
  - **Status**: INSUFFICIENT
  - **Confidence**: LOW (0.0)

#### Supported Claims
- [META] The available evidence is insufficient to answer the query. (SUPPORTED)
- [BIS_FACT] The standard is Standard IS 8978. (SUPPORTED)
  - Binding: (STANDARD:IS 8978 -> HAS_TITLE -> Standard IS 8978)

#### Unsupported Claims (Rejected by validation gate)

#### Answer Trace
```text
### Historical Version
I could not verify this from the available BIS evidence.

Missing:
- No explicit evidence of revision or latest status found.

### Standard Lookup
The standard is Standard IS 8978.
```

### Query: `Which laboratories explicitly have scope for IS 8978?`
- **Generation Mode**: GROUNDED
- **Retrieval Count**: 40
- **Selected Evidence Count**: 9
- **Global Evidence Status**: SUFFICIENT

#### Subquestions
- **Intent**: LABORATORY_LOOKUP
  - **Status**: SUFFICIENT
  - **Confidence**: LOW (0.0)
- **Intent**: LABORATORY_SCOPE
  - **Status**: SUFFICIENT
  - **Confidence**: LOW (0.0)
- **Intent**: STANDARD_LOOKUP
  - **Status**: SUFFICIENT
  - **Confidence**: LOW (0.0)

#### Supported Claims
- [BIS_FACT] Laboratory 840 is listed with testing scope for IS 8978 (1992). (SUPPORTED)
  - Binding: (LABORATORY:840 -> HAS_SCOPE_FOR -> STANDARD:IS 8978 (1992))
- [BIS_FACT] Laboratory 112 is listed with testing scope for IS 8978 (1992). (SUPPORTED)
  - Binding: (LABORATORY:112 -> HAS_SCOPE_FOR -> STANDARD:IS 8978 (1992))
- [BIS_FACT] Laboratory 112 is listed with testing scope for IS 8978 (1992). (SUPPORTED)
  - Binding: (LABORATORY:112 -> HAS_SCOPE_FOR -> STANDARD:IS 8978 (1992))
- [BIS_FACT] Laboratory 840 is listed with testing scope for IS 8978 (1992). (SUPPORTED)
  - Binding: (LABORATORY:840 -> HAS_SCOPE_FOR -> STANDARD:IS 8978 (1992))
- [BIS_FACT] Scope: IS 8978 (840) {"lab_code": "840", "standard": "IS 8978 (1992)", "test": "Specification for electric instantaneous water heaters (Second Revision)"} IS 8978 IS 8978 IS 8978 (SUPPORTED)
  - Binding: (QUERY -> GENERAL_INFORMATION -> EVIDENCE_TEXT)
- [BIS_FACT] The standard is Standard IS 8978. (SUPPORTED)
  - Binding: (STANDARD:IS 8978 -> HAS_TITLE -> Standard IS 8978)

#### Unsupported Claims (Rejected by validation gate)

#### Answer Trace
```text
### Laboratory Lookup
- Laboratory 840 is listed with testing scope for IS 8978 (1992).

- Laboratory 112 is listed with testing scope for IS 8978 (1992).

- Laboratory 112 is listed with testing scope for IS 8978 (1992).

- Laboratory 840 is listed with testing scope for IS 8978 (1992).

### Laboratory Scope
Scope: IS 8978 (840) {"lab_code": "840", "standard": "IS 8978 (1992)", "test": "Specification for electric instantaneous water heaters (Second Revision)"} IS 8978 IS 8978 IS 8978

### Standard Lookup
The standard is Standard IS 8978.
```

### Query: `What tests are covered under the laboratory scope for IS 8978?`
- **Generation Mode**: GROUNDED
- **Retrieval Count**: 44
- **Selected Evidence Count**: 10
- **Global Evidence Status**: SUFFICIENT

#### Subquestions
- **Intent**: LABORATORY_LOOKUP
  - **Status**: SUFFICIENT
  - **Confidence**: LOW (0.0)
- **Intent**: LABORATORY_SCOPE
  - **Status**: SUFFICIENT
  - **Confidence**: LOW (0.0)
- **Intent**: STANDARD_LOOKUP
  - **Status**: SUFFICIENT
  - **Confidence**: LOW (0.0)

#### Supported Claims
- [BIS_FACT] Laboratory 840 is listed with testing scope for IS 8978 (1992). (SUPPORTED)
  - Binding: (LABORATORY:840 -> HAS_SCOPE_FOR -> STANDARD:IS 8978 (1992))
- [BIS_FACT] Laboratory 112 is listed with testing scope for IS 8978 (1992). (SUPPORTED)
  - Binding: (LABORATORY:112 -> HAS_SCOPE_FOR -> STANDARD:IS 8978 (1992))
- [BIS_FACT] Laboratory 840 is listed with testing scope for IS 8978 (1992). (SUPPORTED)
  - Binding: (LABORATORY:840 -> HAS_SCOPE_FOR -> STANDARD:IS 8978 (1992))
- [BIS_FACT] Laboratory 112 is listed with testing scope for IS 8978 (1992). (SUPPORTED)
  - Binding: (LABORATORY:112 -> HAS_SCOPE_FOR -> STANDARD:IS 8978 (1992))
- [BIS_FACT] Scope: IS 8978 (840) {"lab_code": "840", "standard": "IS 8978 (1992)", "test": "Specification for electric instantaneous water heaters (Second Revision)"} IS 8978 IS 8978 IS 8978 (SUPPORTED)
  - Binding: (QUERY -> GENERAL_INFORMATION -> EVIDENCE_TEXT)
- [BIS_FACT] The standard is Standard IS 8978. (SUPPORTED)
  - Binding: (STANDARD:IS 8978 -> HAS_TITLE -> Standard IS 8978)

#### Unsupported Claims (Rejected by validation gate)

#### Answer Trace
```text
### Laboratory Lookup
- Laboratory 840 is listed with testing scope for IS 8978 (1992).

- Laboratory 112 is listed with testing scope for IS 8978 (1992).

- Laboratory 840 is listed with testing scope for IS 8978 (1992).

- Laboratory 112 is listed with testing scope for IS 8978 (1992).

### Laboratory Scope
Scope: IS 8978 (840) {"lab_code": "840", "standard": "IS 8978 (1992)", "test": "Specification for electric instantaneous water heaters (Second Revision)"} IS 8978 IS 8978 IS 8978

### Standard Lookup
The standard is Standard IS 8978.
```

### Query: `What is the testing fee for IS 8978?`
- **Generation Mode**: GROUNDED
- **Retrieval Count**: 30
- **Selected Evidence Count**: 9
- **Global Evidence Status**: PARTIAL

#### Subquestions
- **Intent**: STANDARD_LOOKUP
  - **Status**: PARTIAL
  - **Confidence**: LOW (0.0)
- **Intent**: TESTING_FEE
  - **Status**: PARTIAL
  - **Confidence**: LOW (0.0)
  - **Gaps**: Detailed clause charges exist but no total fee is specified.

#### Supported Claims
- [BIS_FACT] The standard is Standard IS 8978. (SUPPORTED)
  - Binding: (STANDARD:IS 8978 -> HAS_TITLE -> Standard IS 8978)
- [BIS_FACT] At 112, the charge for Specification for electric instantaneous water heaters (Second Revision) under IS 8978 is INR 22000. (SUPPORTED)
  - Binding: (STANDARD:IS 8978 -> HAS_FEE -> 22000)
- [BIS_FACT] At 840, the charge for Electric instantaneous water heater testing under IS 8978 is INR 22000. (SUPPORTED)
  - Binding: (STANDARD:IS 8978 -> HAS_FEE -> 22000)
- [BIS_FACT] At 112, the charge for Electric instantaneous water heater testing under IS 8978 is INR 22000. (SUPPORTED)
  - Binding: (STANDARD:IS 8978 -> HAS_FEE -> 22000)
- [BIS_FACT] At 840, the charge for Specification for electric instantaneous water heaters (Second Revision) under IS 8978 is INR 22000. (SUPPORTED)
  - Binding: (STANDARD:IS 8978 -> HAS_FEE -> 22000)

#### Unsupported Claims (Rejected by validation gate)

#### Answer Trace
```text
### Standard Lookup
The standard is Standard IS 8978.

### Testing Fee
The available BIS evidence provides partial information.

- Limitation: Detailed clause charges exist but no total fee is specified.

The available LIMS evidence lists the following testing charges:


The source does not establish that these constitute the complete testing cost.

- At 112, the charge for Specification for electric instantaneous water heaters (Second Revision) under IS 8978 is INR 22000.

- At 840, the charge for Electric instantaneous water heater testing under IS 8978 is INR 22000.

- At 112, the charge for Electric instantaneous water heater testing under IS 8978 is INR 22000.

- At 840, the charge for Specification for electric instantaneous water heaters (Second Revision) under IS 8978 is INR 22000.
```

### Query: `What are the individual testing charges for IS 8978?`
- **Generation Mode**: GROUNDED
- **Retrieval Count**: 44
- **Selected Evidence Count**: 10
- **Global Evidence Status**: PARTIAL

#### Subquestions
- **Intent**: STANDARD_LOOKUP
  - **Status**: PARTIAL
  - **Confidence**: LOW (0.0)
- **Intent**: TESTING_FEE
  - **Status**: PARTIAL
  - **Confidence**: LOW (0.0)
  - **Gaps**: Detailed clause charges exist but no total fee is specified.

#### Supported Claims
- [BIS_FACT] The standard is Standard IS 8978. (SUPPORTED)
  - Binding: (STANDARD:IS 8978 -> HAS_TITLE -> Standard IS 8978)
- [BIS_FACT] At 112, the charge for Electric instantaneous water heater testing under IS 8978 is INR 22000. (SUPPORTED)
  - Binding: (STANDARD:IS 8978 -> HAS_FEE -> 22000)
- [BIS_FACT] At 112, the charge for Specification for electric instantaneous water heaters (Second Revision) under IS 8978 is INR 22000. (SUPPORTED)
  - Binding: (STANDARD:IS 8978 -> HAS_FEE -> 22000)
- [BIS_FACT] At 840, the charge for Electric instantaneous water heater testing under IS 8978 is INR 22000. (SUPPORTED)
  - Binding: (STANDARD:IS 8978 -> HAS_FEE -> 22000)
- [BIS_FACT] At 840, the charge for Specification for electric instantaneous water heaters (Second Revision) under IS 8978 is INR 22000. (SUPPORTED)
  - Binding: (STANDARD:IS 8978 -> HAS_FEE -> 22000)

#### Unsupported Claims (Rejected by validation gate)

#### Answer Trace
```text
### Standard Lookup
The standard is Standard IS 8978.

### Testing Fee
The available BIS evidence provides partial information.

- Limitation: Detailed clause charges exist but no total fee is specified.

The available LIMS evidence lists the following testing charges:


The source does not establish that these constitute the complete testing cost.

- At 112, the charge for Electric instantaneous water heater testing under IS 8978 is INR 22000.

- At 112, the charge for Specification for electric instantaneous water heaters (Second Revision) under IS 8978 is INR 22000.

- At 840, the charge for Electric instantaneous water heater testing under IS 8978 is INR 22000.

- At 840, the charge for Specification for electric instantaneous water heaters (Second Revision) under IS 8978 is INR 22000.
```

### Query: `Which laboratories can test cement products?`
- **Generation Mode**: FALLBACK
- **Retrieval Count**: 37
- **Selected Evidence Count**: 5
- **Global Evidence Status**: INSUFFICIENT

#### Subquestions
- **Intent**: LABORATORY_LOOKUP
  - **Status**: INSUFFICIENT
  - **Confidence**: LOW (0.0)
  - **Gaps**: Laboratory found but specific testing scope for the IS/product is missing.

#### Supported Claims
- [META] The available evidence is insufficient to answer the query. (SUPPORTED)

#### Unsupported Claims (Rejected by validation gate)

#### Answer Trace
```text
I could not verify this from the available BIS evidence.

Missing:
- Laboratory found but specific testing scope for the IS/product is missing.
```

### Query: `How does BIS hallmarking work for gold jewellery?`
- **Generation Mode**: FALLBACK
- **Retrieval Count**: 35
- **Selected Evidence Count**: 5
- **Global Evidence Status**: INSUFFICIENT

#### Subquestions
- **Intent**: HALLMARKING
  - **Status**: INSUFFICIENT
  - **Confidence**: NONE (0.0)
  - **Gaps**: Factual claims could not be verified by exact identifier/relationship matching.

#### Supported Claims

#### Unsupported Claims (Rejected by validation gate)

#### Answer Trace
```text
I could not verify this from the available BIS evidence.
```

### Query: `How can I apply for a BIS product certification licence?`
- **Generation Mode**: FALLBACK
- **Retrieval Count**: 28
- **Selected Evidence Count**: 5
- **Global Evidence Status**: INSUFFICIENT

#### Subquestions
- **Intent**: LICENCE_PROCEDURE
  - **Status**: INSUFFICIENT
  - **Confidence**: NONE (0.0)
  - **Gaps**: Factual claims could not be verified by exact identifier/relationship matching.

#### Supported Claims

#### Unsupported Claims (Rejected by validation gate)

#### Answer Trace
```text
I could not verify this from the available BIS evidence.
```

### Query: `How can I file a complaint through BIS Care?`
- **Generation Mode**: FALLBACK
- **Retrieval Count**: 39
- **Selected Evidence Count**: 5
- **Global Evidence Status**: INSUFFICIENT

#### Subquestions
- **Intent**: CONSUMER_COMPLAINT
  - **Status**: INSUFFICIENT
  - **Confidence**: NONE (0.0)
  - **Gaps**: Factual claims could not be verified by exact identifier/relationship matching.

#### Supported Claims

#### Unsupported Claims (Rejected by validation gate)

#### Answer Trace
```text
I could not verify this from the available BIS evidence.
```

### Query: `Is BIS certification mandatory for toys?`
- **Generation Mode**: FALLBACK
- **Retrieval Count**: 30
- **Selected Evidence Count**: 5
- **Global Evidence Status**: INSUFFICIENT

#### Subquestions
- **Intent**: QCO_APPLICABILITY
  - **Status**: INSUFFICIENT
  - **Confidence**: NONE (0.0)
  - **Gaps**: Factual claims could not be verified by exact identifier/relationship matching.

#### Supported Claims

#### Unsupported Claims (Rejected by validation gate)
- [BIS_FACT] Mandatory certification (QCO) applies according to Compulsory BIS certification. (UNSUPPORTED)
  - Binding: (GENERAL_PRODUCT -> HAS_QCO -> Compulsory BIS certification)

#### Answer Trace
```text
I could not verify this from the available BIS evidence.
```

### Query: `What is LAB-UNKNOWN_79dcb12d?`
- **Generation Mode**: FALLBACK
- **Retrieval Count**: 40
- **Selected Evidence Count**: 5
- **Global Evidence Status**: INSUFFICIENT

#### Subquestions
- **Intent**: UNKNOWN
  - **Status**: INSUFFICIENT
  - **Confidence**: NONE (0.0)
  - **Gaps**: Query references an explicitly UNKNOWN entity.

#### Supported Claims
- [META] The available evidence is insufficient to answer the query. (SUPPORTED)

#### Unsupported Claims (Rejected by validation gate)

#### Answer Trace
```text
I could not verify this from the available BIS evidence.

Missing:
- Query references an explicitly UNKNOWN entity.
```

### Query: `Give me a multi-part answer covering standard, certification requirement, laboratory and testing fee.`
- **Generation Mode**: FALLBACK
- **Retrieval Count**: 35
- **Selected Evidence Count**: 5
- **Global Evidence Status**: INSUFFICIENT

#### Subquestions
- **Intent**: LABORATORY_LOOKUP
  - **Status**: INSUFFICIENT
  - **Confidence**: LOW (0.0)
  - **Gaps**: No explicit laboratory evidence found.
- **Intent**: QCO_APPLICABILITY
  - **Status**: INSUFFICIENT
  - **Confidence**: LOW (0.0)
  - **Gaps**: No explicit evidence of mandatory certification (QCO) found.
- **Intent**: STANDARD_LOOKUP
  - **Status**: INSUFFICIENT
  - **Confidence**: NONE (0.0)
  - **Gaps**: Factual claims could not be verified by exact identifier/relationship matching.
- **Intent**: TESTING_FEE
  - **Status**: INSUFFICIENT
  - **Confidence**: LOW (0.0)
  - **Gaps**: No explicit testing fee was found in the authoritative evidence.

#### Supported Claims
- [META] The available evidence is insufficient to answer the query. (SUPPORTED)
- [META] The available evidence is insufficient to answer the query. (SUPPORTED)
- [META] The available evidence is insufficient to answer the query. (SUPPORTED)

#### Unsupported Claims (Rejected by validation gate)

#### Answer Trace
```text
### Laboratory Lookup
I could not verify this from the available BIS evidence.

Missing:
- No explicit laboratory evidence found.

### Qco Applicability
I could not verify this from the available BIS evidence.

Missing:
- No explicit evidence of mandatory certification (QCO) found.

### Standard Lookup
I could not verify this from the available BIS evidence.

### Testing Fee
I could not verify this from the available BIS evidence.

Missing:
- No explicit testing fee was found in the authoritative evidence.
```

