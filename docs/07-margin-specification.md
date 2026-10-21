# 07 · Margin calculation specification

Implementation: `timp/economics.py`. Run it on research data with `python3 scripts/profit_report.py`.

## Definitions

| Term | Formula | Notes |
|---|---|---|
| Gross sale | selling price incl. GST − discount | What the customer pays for the item |
| Output GST | gross − gross / (1 + GST%) | **Pass-through. Never revenue.** |
| **Net revenue** | gross / (1 + GST%) | Accounting definition used everywhere |
| COGS | supplier price excl. GST | + supplier GST if input tax is **not** recoverable (`input_tax_recoverable=false`) |
| Channel fees | commission% × gross + fixed/closing fee + payment% × gross + platform% × gross | + 18% GST on fees if ITC is not available |
| Kept-order contribution | net revenue − COGS − forward ship − packaging − fees − ads − other | |
| Returned-order contribution | −(forward + reverse ship + packaging + non-refunded fees + ads + other + COGS × (1 − supplier credit%)) | Revenue is refunded |
| **Expected contribution / order** | (1 − r) × kept + r × returned | r = return rate (incl. RTO) |
| **Contribution margin %** | expected ÷ ((1 − r) × net revenue) | |
| Break-even price | lowest price at which expected contribution ≥ 0 | Solved numerically |
| Minimum viable price | lowest price that passes every owner threshold | Use this instead of an arbitrary markup |
| Cash out per order | supplier price incl. GST + shipping + packaging + ads | Paid before the marketplace payout |
| Tax withheld | net revenue × (TCS% + TDS%) | Creditable; affects cash, **not** profit |

## Scenarios

| | Return rate | Ads | Shipping |
|---|---|---|---|
| Conservative | ×1.5 | ×1.5 | ×1.2 |
| Base | ×1 | ×1 | ×1 |
| Optimistic | ×0.7 | ×0.7 | ×1 |

Configured in `[scenarios]`. The gate uses `gate_scenario` (default `base`). A product that passes base but fails conservative is flagged **fragile**.

## Thresholds (owner-only)

`min_contribution_inr` (default ₹60), `min_margin_pct` (12%), `max_acquisition_cost_inr` (₹80). A product must meet all three.

## Missing data

Any missing input or fee makes the result **INCOMPLETE**. It is never guessed. An unverified fee card means the result can be PASS but the **gate stays closed** (`gate_open = PASS and fees_verified`). Every input carries `basis`: `quoted`, `actual` or `estimated`. The dashboard shows estimated values in a different style.

## After launch: actuals

`Platform.check_margins()` re-runs the engine on live listings with actual costs from settlements, supplier invoices and ad spend. A breach raises a HIGH alert and, when `auto_pause_on_margin_breach = true`, pauses the listing.

## Not counted as an expense

* GST collected (pass-through).
* Recoverable input GST on supplier invoices and channel fees (when registered and eligible).
* TCS/TDS withheld by marketplaces (claimable). It is tracked as working capital.

Confirm the accounting treatment with your CA, especially ITC eligibility and HSN rates after the 2025 GST rate rationalisation.
