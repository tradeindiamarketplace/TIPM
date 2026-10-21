# 02 · Architecture

## Current state

```
 Customer ──► Shopify Online Store (Horizon theme, 0 products) ──► (no gateway seen, no shipping app)
 Owner    ──► Shopify Admin
 Amazon.in / Flipkart / Meesho : no connection, seller-account status unknown
```

## Target state

```
                         ┌────────────────────────── Owner (web dashboard + mobile approvals) ──────────────────────────┐
                         │   approve / deny · thresholds · emergency stop · manual-upload confirmation                  │
                         └───────────────────────────────────────────┬──────────────────────────────────────────────────┘
                                                                     │ HTTPS + step-up auth for approvals
┌──────────────────────────────── TIMP Ops (single source of truth) ─▼──────────────────────────────────────────────────┐
│                                                                                                                        │
│  Agent runtime (A orchestrator + B..M specialists)                                                                     │
│     │ every agent action is an API call as its own service account ──► permissions.require(actor, perm)              │
│     ▼                                                                                                                  │
│  Domain core (timp/)                                                                                                   │
│   catalog · suppliers · economics · compliance · approvals · lifecycle gates · listings                                │
│   orders · supplier POs · shipments · returns/refunds · settlements · support · campaigns · tasks                      │
│     │                         │                              │                                                         │
│     ▼                         ▼                              ▼                                                         │
│  PostgreSQL              Hash-chained audit log      Job queue + workers (retries, backoff, dead-letter, reconcilers)  │
│  (db/schema.sql)         (append-only table)         schedulers: SLA check, stock freshness, margin monitor, recon     │
│                                                                                                                        │
│  Channel adapters (one per channel, honest IntegrationStatus)            Supplier gateways                            │
│   shopify  ── Admin GraphQL (productSet / productUpdate / orders webhooks)  email+portal / CSV feed / API per supplier  │
│   amazon_in ─ SP-API (needs seller account + developer registration)       Carrier tracking (aggregator API)          │
│   flipkart ── Seller API (needs seller account + API access approval)                                                 │
│   meesho  ─── ManualExportAdapter (CSV + supplier panel) until an API is confirmed                                    │
│                                                                                                                        │
│  Secrets: cloud secret manager (no secrets in code, prompts or logs) · Object storage: evidence files (hashed)        │
└────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Key decisions

| Decision | Why | Trade-off |
|---|---|---|
| **The Ops service is the source of truth**, and Shopify is one channel among four. | Prevents the website and the marketplaces drifting apart. Supports adding channels without a rewrite. | Two systems to keep in sync (handled by adapters and reconcilers). |
| **Shared catalogue vs channel listing.** `Product` holds the facts; `ChannelListing` holds the title, attributes and price per channel. | Each channel has different required attributes and fees. | Content duplication is handled by templates per channel. |
| **Gates in code, not in prompts.** Approvals, thresholds and evidence rules live in `timp/platform.py`. | An LLM agent can be wrong or manipulated, but a code gate cannot be talked past. | Changing a rule needs a code or config change (intended). |
| **Product versioning.** Any material change bumps `Product.version` and supersedes approvals. | "One approval must not authorise every future change." | The owner re-approves after cost or price changes. |
| **Stock is never "assumed".** A supplier snapshot older than `inventory_snapshot_max_age_hours` counts as unknown. | Avoids overselling with no warehouse. | Some orders go to NEEDS_ATTENTION until the supplier updates. |
| **Cross-channel oversell guard.** Available-to-sell = latest supplier snapshot − open POs, shared by all channels; channel stock is pushed from that one number. | One supplier stock pool backs four channels. | Planned (backlog F-09); the current code checks the snapshot per order. |
| **Python 3.13 + PostgreSQL + a queue (e.g. Postgres-backed or Cloud Tasks)** | Simple, typed, cheap to run; stdlib-only core today. | — |

### Events (outbox pattern, planned)

`product.transitioned`, `approval.decided`, `listing.published`, `listing.paused`, `order.imported`, `po.submitted`, `po.accepted`, `po.rejected`, `shipment.dispatched`, `shipment.delivered`, `return.received`, `refund.recorded`, `settlement.reconciled`, `margin.breached`, `sla.breached`, `stop.engaged`. Each is written in the same DB transaction as the state change and delivered at least once. Consumers are idempotent by event id.

### Error handling

* Adapter calls: `call_with_retry` (4 attempts, exponential backoff). Then dead-letter, a HIGH notification, and a `retry_dead_letters` job.
* Publish uses an upsert keyed by handle/listing id, so a retry after a timeout cannot create a duplicate listing.
* Supplier POs are keyed `po:{order}:{supplier}`. A PO that fails to send is not recorded, and re-routing sends exactly one.
* Webhooks are deduplicated by delivery id **and** by `(channel, external_order_id)`.

### Environments

`test` (simulated adapters, used by `tests/`), `staging` (Shopify development store + marketplace sandboxes where they exist), `production`. Separate databases, secrets and service accounts. Test code can't load production secrets.
