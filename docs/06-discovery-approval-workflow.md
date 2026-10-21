# 06 · Product discovery and approval workflow

Enforced by `Platform.advance()` and `Platform._preconditions()`. Every transition and every blocked attempt is written to the audit log.

```
DISCOVERED ─► UNDER_REVIEW ─► SUPPLIER_VERIFICATION ─► FINANCIAL_REVIEW ─► OWNER_APPROVED ─► PRODUCT_ONBOARDING
     │              │                  │                      │                    │
     └──────────────┴──────────────────┴──────────────────────┴─► REJECTED (terminal)
                                                                                    ▼
          RETIRED (terminal, from any state) ◄── PAUSED ◄─► LIVE ◄── READY_TO_PUBLISH ◄── READY_FOR_TESTING ◄── COMPLIANCE_APPROVED
```

| Transition | Preconditions (all must hold) | Who acts | Owner gate |
|---|---|---|---|
| propose → DISCOVERED | Complete recommendation (all fields of section 4-B), not a duplicate of an existing product | B | — |
| → UNDER_REVIEW | Demand evidence present | A | — |
| → SUPPLIER_VERIFICATION | At least one supplier lead | A | — |
| → FINANCIAL_REVIEW | Quotation selected; supplier **VERIFIED** and not expired; quotation active and in date | A | — |
| → OWNER_APPROVED | All of the above; at least one channel estimate **PASS** for this product version; `PRODUCT_OPPORTUNITY` granted for this version; `SUPPLIER_TERMS` granted for this quotation version | A | **Yes ×2** |
| → PRODUCT_ONBOARDING | Supplier agreement recorded against the selected quotation (needs the `SUPPLIER_TERMS` approval) | C, A | — |
| → COMPLIANCE_APPROVED | Every required check for the category (config `[compliance]`) is PASS or N/A with evidence and a policy version; HSN and GST set | M, A | — |
| → READY_FOR_TESTING | At least one listing with validated channel attributes | G, A | — |
| → READY_TO_PUBLISH | Latest test run for this version has no HIGH or CRITICAL failures | K, A | — |
| → LIVE (per channel publish) | No PUBLISHING stop; listing VALIDATED for the current version; `CHANNEL_PUBLICATION` granted for this version **and channel**; verified fulfilment arrangement for the channel; estimate at this exact price with the gate open (PASS **and** verified fee card); adapter available | A | **Yes, per channel** |
| LIVE ↔ PAUSED | Pausing is always allowed. Resuming goes through publish again. | A, M, owner | Re-approval if the version changed |
| → RETIRED | Always allowed. Published listings are withdrawn on the channel. No transition out. | A, owner | — |

## Material changes

`Platform.material_change()` covers supplier price changes, a new supplier, specification changes and price changes beyond pricing-rule limits.

1. `Product.version` increments.
2. Every pending or granted approval for older versions becomes **SUPERSEDED**.
3. A LIVE product is **paused** on every channel. A product in onboarding returns to FINANCIAL_REVIEW.
4. The owner sees a new approval request with the before/after economics.

## What the owner sees for each decision

The approval card shows the recommendation, sources with dates, all three scenario results, the break-even and minimum viable price, supplier verification evidence, compliance status and the exact scope of what the approval will authorise ("publish v3 on amazon_in only").
