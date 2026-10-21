# 11 · Security, compliance and operational risk register

Likelihood and impact: H/M/L. Owner = the agent that monitors it; the human owner decides.

| # | Risk | L | I | Mitigation (✅ in code · ⬜ planned) | Monitor |
|---|---|---|---|---|---|
| R1 | Products lose money once real fees, shipping and returns land (the research shows most low-ticket items do) | H | H | ✅ Margin gate, 3 scenarios, verified-fee requirement, post-launch margin monitor with auto-pause | D |
| R2 | Supplier dispatch location not registered as an APOB, so GST non-compliance or marketplace account suspension | H | H | ✅ `tax_documents_available` and `channel_permits_method` checks block publish; ⬜ CA review | M |
| R3 | Overselling: supplier sold out, stock feed stale | H | M | ✅ Stale snapshot counts as no stock; order held, never confirmed; ⬜ cross-channel pool (F-09) | J |
| R4 | Late dispatch penalties and cancellation fees (Amazon/Flipkart 2026) | M | M | ✅ Only supplier-confirmed dispatch times; SLA escalation; ⬜ supplier SLA penalties in agreement | J |
| R5 | Counterfeit or unauthorised branded goods | M | H | ✅ Brand authorisation + trademark checks for branded items; ⬜ prefer unbranded / own-label | M |
| R6 | BIS / Quality Control Order products (many electrical appliances) sold without certification | M | H | ✅ `BIS_QCO_CRS` required for `home_appliances`; keep that collection empty until checked | M |
| R7 | Legal Metrology labelling (MRP, net quantity, manufacturer/packer, country of origin, consumer care) missing on supplier packaging | M | M | ✅ `LEGAL_METROLOGY_LABEL` required for all products | M |
| R8 | Unsupported claims ("pure copper", "food grade", "350 GSM") | M | M | ✅ `PRODUCT_CLAIMS_REVIEW` with evidence (test reports) | M, G |
| R9 | Consumer Protection (E-Commerce) Rules: seller details, grievance officer, return policy missing on the website | H | M | ⬜ Publish policies (docs/01 M5) | M |
| R10 | An agent is manipulated by supplier or product text (prompt injection) into approving, spending or publishing | M | H | ✅ Gates in code; no agent holds owner permissions (asserted); supplier text is data only | M |
| R11 | Duplicate orders or POs from webhook retries | M | H | ✅ Idempotency keys + unique constraints (test 10, 17) | F |
| R12 | Credential leak (Shopify token, SP-API keys) | L | H | ⬜ Secret manager, least-privilege scopes, rotation every 90 days, no secrets in logs | M |
| R13 | Customer PII exposure | L | H | ✅ Address tokenised, PIN masked for support; ⬜ access logging, retention policy (DPDP Act 2023) | M |
| R14 | Cash-flow squeeze: you pay the supplier before the marketplace pays you, and TCS/TDS is withheld | M | M | ✅ Cash-out per order and tax withheld reported; ✅ PO caps | D |
| R15 | Supplier concentration | M | M | ⬜ Backup supplier per live SKU before scaling | C |
| R16 | High returns/RTO on Meesho and COD | H | M | ✅ 15% return assumption for Meesho; prefer prepaid on the website | D |
| R17 | Integration claimed working when it isn't | M | M | ✅ Honest `IntegrationStatus` shown on the dashboard; nothing LIVE_TESTED yet | F |
| R18 | Fee schedules change (Amazon, Flipkart changed fees several times in 2025–26) | H | M | ✅ `fee_as_of`/`fees_verified`; ⬜ monthly fee-card re-verification task | D |
| R19 | Accidental destructive change to the live store | L | H | ✅ DESTRUCTIVE_CHANGE is owner-only and single-use; backups before M1–M4 | E |
| R20 | Tax treatment errors (ITC eligibility, HSN rate changes after the 2025 GST rationalisation) | M | M | ⬜ CA sign-off on HSN and rate per SKU, recorded as a compliance check | M |

Legal and tax items (R2, R5–R9, R13, R20) need confirmation from a qualified CA or lawyer. The checklist here is a starting point, not advice.
