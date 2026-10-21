# 05 · Supplier-direct fulfilment feasibility (India)

**Bottom line:** supplier-direct (drop-ship) selling is *possible*, but in India the binding constraint is usually **GST registration of the dispatch address**, not marketplace policy. Each supplier warehouse that ships your orders generally has to be on your GST registration as an Additional Place of Business (APOB), and the marketplace pickup address has to match it. Plan for that per supplier before signing anyone up.

> These are working assumptions from general knowledge of Indian e-commerce practice, **not legal or tax advice**, and policies change. Agent M must confirm each row against the current policy page and with a CA, and record the policy version in `ComplianceCheck.policy_version` before any listing goes live.

## What has to be true (section 9 checklist, enforced by code)

`FULFILLMENT_CHECKS` in `timp/platform.py`. A listing cannot publish until every item is `true` with evidence:

| Check | What evidence looks like |
|---|---|
| `channel_permits_method` | Screenshot or URL of the channel's current policy plus the date read |
| `owner_is_seller_of_record` | Invoice template showing your legal name and GSTIN; the supplier's name and price are not visible to the customer |
| `packaging_invoice_compliant` | Sample package photo: your invoice inside, no supplier invoice or price list, Legal Metrology label present |
| `supplier_meets_sla` | Signed SLA (dispatch hours, cut-off time) plus 10 test dispatches |
| `return_process_documented` | Return address, who inspects, credit terms (`return_credit_pct` in the agreement) |
| `stock_feed_reliable` | Feed or API cadence ≤ `inventory_snapshot_max_age_hours`, and 2 weeks of feed history |
| `authenticity_evidence` | Manufacturer invoice, or brand authorisation for branded goods |
| `tax_documents_available` | Supplier's tax invoice to you (for ITC), HSN, and your APOB registration for that address |

## Channel-by-channel

| Channel | Supplier-direct model | Key conditions to verify | Initial verdict |
|---|---|---|---|
| **TradeIndiaMarketplace.com** (Shopify) | Supplier ships with your invoice and packing; you book the courier (Shiprocket or another aggregator) from the supplier's pickup address | Your invoice and branding; APOB for the supplier address if you invoice from there; refund, shipping and terms policies published | **Feasible**, and the cleanest place to pilot |
| **Amazon.in** (Easy Ship / Self Ship) | Amazon picks up from your registered pickup address | Amazon's drop-shipping policy (seller of record, your name on all slips, no third-party invoices); pickup address must be on your GST registration; dispatch SLA and cancellation penalties (a cancellation fee of 10% of order value under ₹10,000 reportedly took effect 17 Aug 2026) | **Feasible with APOB per supplier**; strict SLAs |
| **Flipkart** | Flipkart picks up from your registered pickup address | Pickup address and GST registration must match; late-dispatch and cancellation penalties reportedly introduced 23 Aug 2026 | **Feasible with APOB per supplier**; API access needs approval |
| **Meesho** | Pickup from your supplier-panel address | Same address and GST requirement; higher return/RTO exposure; non-GST enrolment is possible only for small intra-state sellers (reported) | **Feasible but riskiest** on returns; manual workflow first |

## Alternatives when supplier-direct isn't permitted

1. **Marketplace fulfilment (FBA / Flipkart Smart Fulfilment)**: the supplier ships bulk stock to the marketplace warehouse. You don't own a warehouse, but you **do own inventory**, so this needs a `PURCHASE_COMMITMENT` approval and a working-capital decision.
2. **3PL with per-order billing**: a fulfilment provider holds your stock. Same inventory risk as option 1.
3. **Reject** the product for that channel.

## Recommended path

1. Get GST registration in place (if not already) and talk to a CA about adding supplier locations as APOBs.
2. Pilot on TradeIndiaMarketplace.com with 1–3 products from **one** supplier in your state, which keeps intra-state GST and logistics simple.
3. Add Amazon.in second (largest demand), with the same supplier address registered as an APOB.
4. Flipkart third. Meesho last, and only for products with low return rates.
