# 03 · Agent responsibilities and permissions

Source of truth: `timp/permissions.py` (`MATRIX`). An assertion in that file guarantees no agent role holds an owner-only permission.

**Owner-only:** decide approvals · set thresholds · release an emergency stop · destructive changes · confirm manual marketplace uploads.

| Agent | Inputs | Outputs | May do (code permissions) | May NOT do | Escalates when |
|---|---|---|---|---|---|
| **A Orchestrator** | All events, task queue | Task assignments, daily summary, exception report | advance lifecycle (gates still apply), request approvals, publish/pause listings **after approval**, engage emergency stop, manage tasks, view orders | approve anything, bypass any gate, spend | Conflicting recommendations, blocked tasks, overdue tasks, any CRITICAL notification |
| **B Product discovery** | Public sources, supplier catalogues, trends | `ProductCandidate` with evidence, sources, dates, confidence | propose product, request approval | invent demand/sales figures, publish | Restricted or IP-risky products |
| **C Supplier sourcing** | Supplier leads | Supplier, verification, quotations (versioned), agreement, stock snapshots | record supplier, verification, quotation, agreement, inventory | order samples or commit money, treat a directory profile as proof | Verification fails, single-supplier concentration |
| **D Finance** | Quotes, fee cards, settlements | `EconomicsReport` (3 scenarios), reconciliations | calculate economics, reconcile settlements, record approved expenses | approve spend | Product below thresholds, settlement variance |
| **E Architect** | Systems | Design docs | — (no runtime permissions) | change production | Design risks |
| **F Developer** | Approved backlog | Code, tests, adapters | record test runs | claim an integration works untested, scrape or automate seller portals against their terms | Integration failures |
| **G Design** | Product facts | Listing content, images | edit listing content | alter specifications | Missing product facts |
| **H Marketing** | Products, analytics | Campaign proposals, copy | edit content, propose campaigns (creates `AD_BUDGET` approval) | start spend without approval | ROAS or CPA beyond limits |
| **I Pricing** | Estimates, competitor prices | Price recommendations | calculate economics, apply **pre-approved** pricing rules within floor/ceiling | change price outside approved rules | Competitor moves below our break-even |
| **J Fulfilment** | Orders, stock, carrier events | POs, shipments, cancellations, returns | submit POs within standing authorisation, record carrier events, cancel before dispatch, manage returns | mark shipped without carrier evidence, promise unconfirmed dispatch dates | Stock unknown, supplier rejects, SLA breach |
| **K QA** | Builds, test plans | Test runs | record test runs | create real orders or charge real cards | Any critical failure (blocks release) |
| **L Support** | Order view (masked) | Cases, drafted replies | view orders, manage cases, open returns, request refund approval | issue refunds or promise compensation | Safety, fraud, dispute, exceptional refunds |
| **M Compliance** | Product docs, policies | Compliance checks with policy version, fulfilment-arrangement checks | record compliance, verify suppliers, pause listings, engage emergency stop | approve products, release stops | Uncertain legal or tax questions go to the owner and a CA or lawyer |
| **System** (webhooks, schedulers) | Channel webhooks, carrier feeds | Orders, events | import orders, record carrier events and stock, submit POs within caps, record channel-executed refunds | anything requiring judgement | — |

## Approval scopes (each tied to a subject **and version**, and to a channel where relevant)

| Scope | Subject | Single use? | Created by |
|---|---|---|---|
| PRODUCT_OPPORTUNITY | product vN | no (superseded by vN+1) | B |
| SUPPLIER_TERMS | quotation vN | no | C |
| CHANNEL_PUBLICATION | product vN + channel | no | A |
| PRICE_CHANGE | product vN + channel | no | I |
| PURCHASE_COMMITMENT | order or sample request, with amount limit | **yes** | J / C |
| AD_BUDGET | campaign, with amount | no (spend auto-stops at budget) | H |
| EXCEPTIONAL_REFUND | order, with amount limit | **yes** | L |
| EXPENSE | expense, with amount limit | **yes** | D |
| DESTRUCTIVE_CHANGE | system change | **yes** | E / F |

**Standing authorisation for drop-ship POs** (an owner decision, set in `config/settings.toml`). After the owner approves a supplier's terms, a PO that exactly mirrors a real customer order, at the approved quotation price, may be sent without a fresh approval, but only if it is ≤ `per_po_cap_inr` and that day's total stays ≤ `daily_po_cap_inr`. Anything above either cap creates a single-use `PURCHASE_COMMITMENT` request. Speculative stock purchases always need an explicit approval.
