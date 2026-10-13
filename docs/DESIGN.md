# JurisScan-AI Dataset: Design (Deliverable A)

Status: design for v0.1 pilot. Nothing here is legally validated.

## 1. Final schema (15 fields, fixed types)

| Field | Type | Allowed values / rule |
|---|---|---|
| id | string | `JSIN_` + 6 digits, stable across batches |
| clause_text | string | Complete synthetic clause, plain text, no Markdown |
| clause_category | string | One of the 25 approved labels |
| risk_level | string | LOW / MEDIUM / HIGH |
| risk_reason | string | 1-2 sentences naming the party, the wording that drives the label, and what mitigates it |
| affected_party | string | TENANT, LANDLORD, EMPLOYEE, EMPLOYER, SERVICE_PROVIDER, SERVICE_RECIPIENT, CONSUMER, DATA_PRINCIPAL, DISCLOSING_PARTY, RECEIVING_PARTY, FREELANCER, CLIENT, VENDOR, BUYER, BOTH_PARTIES |
| risk_type | string | LEGAL_COMPLIANCE, FINANCIAL, PRIVACY, CONTRACTUAL, OPERATIONAL, NONE (NONE only with LOW) |
| jurisdiction | string | `INDIA` |
| contract_type | string | RENTAL_LEASE, EMPLOYMENT, SERVICE_AGREEMENT, NDA, PRIVACY_POLICY, TERMS_AND_CONDITIONS, FREELANCE_CONSULTING, VENDOR_BUSINESS, CONSUMER_SERVICE |
| context_required | boolean | true if the label depends on other clauses or facts |
| legal_reference | string or null | Verified citation only. **Null for every pilot record** (nothing verified against India Code yet) |
| legal_reference_status | string | VERIFIED / NEEDS_REVIEW / NOT_APPLICABLE |
| review_status | string | SYNTHETIC_UNREVIEWED / LEGALLY_REVIEWED / REQUIRES_REVISION |
| generation_source | string | `SYNTHETIC_AI` |
| split_group_id | string | `SG_...`; related or contrast-pair clauses share one id |
| notes | string or null | Required when context_required is true or status is NEEDS_REVIEW |

Convention: where a statute is a plausible hook but unverified, `legal_reference` stays null, status is NEEDS_REVIEW, and `notes` begins "Candidate provision for expert verification (not verified)". Candidates are leads for the reviewer, not citations.

Proposed optional additions (not in v0.1 unless you approve): `secondary_categories` (list of labels), `clause_style` (balanced / unilateral / ambiguous / mitigated), `label_confidence` (1-3) for later noise analysis.

## 2. Category definitions (primary-category rule)

Pick the category of the clause's operative obligation or right, not incidental mentions.

- TERMINATION: right to end the agreement, grounds, consequences. NOTICE_PERIOD: notice length and delivery mechanics. If a clause is mostly "30 days' notice to terminate", use TERMINATION; if mostly about how notice is served or served-out, use NOTICE_PERIOD.
- PAYMENT_AND_FEES: amounts, schedule, taxes, fee changes. PAYMENT_DEFAULT_AND_LATE_FEES: consequences of non-payment. PENALTIES_AND_LIQUIDATED_DAMAGES: pre-agreed sums for non-payment-related breach (delay, early exit, confidentiality breach).
- LIABILITY: caps, exclusions, allocation of loss. INDEMNIFICATION: duty to reimburse or defend against third-party or specified loss.
- CONFIDENTIALITY: non-disclosure of business information. DATA_PRIVACY: personal data handling, retention, sharing. CONSENT_AND_AUTHORIZATION: the consent or authorization mechanism itself (scope, form, withdrawal).
- INTELLECTUAL_PROPERTY: ownership, licences, assignment.
- DISPUTE_RESOLUTION: escalation, complaint windows, non-arbitral deciders. ARBITRATION: arbitral agreements, seat, appointment, costs. JURISDICTION_AND_GOVERNING_LAW: governing law, court forum.
- RENEWAL_AND_AUTO_RENEWAL; WARRANTIES_AND_REPRESENTATIONS; SERVICE_LEVELS_AND_DELIVERABLES (uptime, acceptance, response times); NON_COMPETE_AND_NON_SOLICITATION; FORCE_MAJEURE; ASSIGNMENT_AND_SUBCONTRACTING; AUDIT_AND_ACCESS_RIGHTS (inspection, monitoring, entry to systems); EMPLOYMENT_AND_COMPENSATION; RENTAL_AND_TENANCY (deposit, rent, repairs, entry, tenancy-specific terms); CONSUMER_RIGHTS_AND_REFUNDS; OTHER (boilerplate such as severability, amendment).

## 3. Risk-labeling guide

Risk is judged for the `affected_party`, from the text provided.

- LOW: clear, reasonably balanced, with safeguards visible in the wording.
- MEDIUM: meaningful concern needing clarification or negotiation (vague terms, unilateral but defensible discretion, missing safeguards), not clearly severe. Default when context is missing and the text is ambiguous.
- HIGH: substantial apparent exposure on the face of the text: uncapped or fault-independent liability, forfeiture of earned money, blanket data waivers, unilateral decider, no procedural protection, or sums that look disproportionate. HIGH never rests on a keyword alone.
- Commercial disadvantage is not legal invalidity. A HIGH label means "priority review", never "illegal".
- Mitigators lower the label: caps, notice, cure periods, carve-outs, reasonableness standards.
- If the label turns on missing facts, set `context_required` true and state what is missing in `notes`.
- Write `risk_reason` before settling the label; if the reason and label disagree, fix the label.

## 4. Generation and QC plan

1. Authoring: clauses are written per category as contrast sets (same topic at different risk levels, e.g. capped vs uncapped liability) so the model cannot learn risk from topic alone.
2. Per-batch checks (scripted): unique IDs, required fields, enum membership, types, risk_type vs risk_level consistency, notes required rules, exact duplicates, near-duplicates (5-word shingle Jaccard), length spread.
3. Manual checks per batch: reason-label agreement, affected-party plausibility, no invented citations, no overuse of privacy/termination.
4. Manifest per batch: ID range, counts by category, risk, contract type, review flags, check results.
5. Targets: about 80 records per category average for 2,000, with LOW/MEDIUM/HIGH near one-third where realistic. Shortfalls are reported, not padded.
6. Legal review queue: every NEEDS_REVIEW or context_required record goes to an Indian-law reviewer before any label is treated as reliable.

## 5. Split plan

- 70/15/15 train/validation/test, stratified on clause_category x risk_level where counts allow.
- Split on `split_group_id`, never on rows. Contrast pairs and paraphrase families stay together.
- With pilot-scale data (about 4 per category) per-category evaluation is meaningless; the pilot is for pipeline testing only. Test set stays untouched until tuning ends.
- Categories with fewer than about 10 test examples are reported as unreliable.

## 6. Pilot plan

100 records, about 4 per category (2 to 5), all 9 contract types, all three risk levels per category where realistic. No legal references asserted. Everything is `SYNTHETIC_UNREVIEWED`.
