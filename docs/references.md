# MPLADS AI Shield — Reference Documentation

## Source hierarchy

1. **Current official MPLADS Guidelines / MoSPI material** are the primary source for current scheme rules. The 2023 MPLADS Guidelines are the current primary guidance recorded in this tracker.
2. **Older MPLADS guidelines** are historical/contextual sources. They must not be treated as the current rule set when a newer guideline supersedes them.
3. **CAG, PAC, and audit documents** provide documented audit observations and control concerns. They are evidence of observed risks and control expectations, not necessarily current legal rules.
4. **Government and official parliamentary answers** can provide current clarifications and implementation context, including how current guidance is understood or applied.

## References

| ID | Source | Issuing organization | Date/version | URL | Used for | Authority type |
| --- | --- | --- | --- | --- | --- | --- |
| R01 | 2023 MPLADS Guidelines | Ministry of Statistics & Programme Implementation | Effective 1 April 2023 | [Official MPLADS Guidelines page](https://www.mplads.gov.in/MPLADS/En/2034.aspx) | Phase 4 compliance rules, including C01/C02, and future MPLADS-specific constraints | Current primary scheme guidance |
| R02 | 2016 MPLADS Guidelines | Ministry of Statistics & Programme Implementation | 2016 | [Official PDF](https://www.mplads.gov.in/mplads/uploadedfiles/mpladsguidelines2016english_638.pdf) | Historical provisions concerning duplication of allocation and duplicate accounting; not treated as the current rule set | Historical/contextual |
| R03 | CAG Report No. 31 of 2010-2011 — Performance Audit of MPLADS | Comptroller and Auditor General of India | 2010-2011 | [Official audit report](https://cag.gov.in/en/audit-report/details/2341) | Documented audit and control concerns, including avoiding duplication and overlapping in selection of works | Audit evidence |
| R04 | CAG Performance Audit — relevant report document | Comptroller and Auditor General of India | Not recorded in this tracker | [Official MPLADS/CAG report](https://www.mplads.gov.in/MPLADS/UploadedFiles/cag%20performance%20report.pdf) | Audit objective concerning controls that avoided duplication and overlapping | Audit evidence |
| R05 | Lok Sabha Unstarred Question No. 1916 — Convergence of MPLADS with Major Rural Development Schemes | Lok Sabha / Government of India | 11 February 2026 | [Official Parliament PDF](https://sansad.in/getFile/loksabhaquestions/annex/187/AU1916_Mu9WOV.pdf) | 2023 Guideline Para 7.1 context; convergence may occur, but duplication of resources for a particular work is to be strictly avoided | Current government clarification |
| R06 | Official MPLADS portal | Ministry of Statistics & Programme Implementation | Current portal | [Official scheme portal](https://www.mplads.gov.in/) | Official work-register, data, reporting, and scheme-information context | Official scheme portal |

## Phase 4 references

The following references are used to document the authority and limits of Phase 4 compliance rules:

| Rule | Reference basis | Documentation status |
| --- | --- | --- |
| C01: recommendation-to-sanction 45-day rule | R01, 2023 MPLADS Guidelines | The rule is attributed to the 2023 Guidelines. The exact paragraph citation should be recorded after verification against the source text. |
| C02: sanction-to-completion 1-year rule | R01, 2023 MPLADS Guidelines | The rule is attributed to the 2023 Guidelines. The exact paragraph citation should be recorded after verification against the source text. |
| C03-C11 | R01 where the relevant rule is covered by the 2023 Guidelines; other references may provide context where applicable | Do not infer or invent paragraph citations. Each rule needs an exact source-text verification before a specific citation is added. |

R01 is the controlling source for rules identified as current MPLADS scheme requirements. R02, R03, and R04 may explain historical provisions or documented control concerns, but do not replace the current guidance. R05 can clarify current implementation context. This tracker does not claim a source for any C03-C11 rule until its exact provision has been verified.

## Phase 6 research relevance

Official and audit material identifies duplication, overlap, duplication of resources, and duplicate accounting as control concerns. This source-supported problem is the reason Phase 6 research is relevant to the MPLADS AI Shield pipeline.

The proposed analytical implementation is narrower and must remain explainable: Phase 6 will generate candidate evidence for potentially overlapping or similar works for human review. The sources do not define the exact future algorithm, thresholds, text model, matching logic, or decision policy.

The system must not claim that high text similarity means fraud, that the same amount is duplicate evidence, or that the same description proves a duplicate. A candidate signal is not a legal conclusion, fraud label, or final finding.

## Phase 6 design principles

- Duplicate detection operates at canonical Work ID level.
- Repeated work types across different legitimate locations are not automatically suspicious.
- Same amount alone is not duplicate evidence.
- Same description alone is not sufficient evidence.
- State, constituency, MP, and implementing agency are contextual evidence, not automatic duplicate rules.
- Missing or unusable descriptions must become `NOT_EVALUABLE` rather than being treated as non-duplicates.
- A potential duplicate is an evidence/review signal, not a fraud verdict.
- Phase 6 must account for legitimate repeated government works.
- Do not modify Phase 3 `ml_features.csv` just to add text.

## Research questions for Phase 6

- What constitutes a meaningful overlap candidate?
- Which contextual fields are actually available and reliable?
- How should generic or high-frequency descriptions be handled?
- How should cross-year works be interpreted?
- How should different states or constituencies be treated?
- How should multilingual or garbled descriptions be handled?
- What evidence is sufficient for a strong review candidate?
