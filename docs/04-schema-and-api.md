# 04 · Database schema and API contracts

* **Schema:** [`db/schema.sql`](../db/schema.sql). PostgreSQL 16, all 28 required entities plus `evidence`, `product_version`, `idempotency_key`, `emergency_stop` and `job_dead_letter`. **Status: written, not yet run against a database.**
* **Running model:** [`timp/domain.py`](../timp/domain.py) (dataclasses mirroring the schema) and [`timp/store.py`](../timp/store.py) (in-memory store enforcing the same unique constraints). **Status: implemented and tested.**
* **API:** [`api/openapi.yaml`](../api/openapi.yaml). OpenAPI 3.1. **Status: contract only.** The domain functions behind each path exist and are tested; the HTTP layer is backlog F-03.

## Integrity rules that prevent duplicates and double-spend

| Rule | Constraint |
|---|---|
| One product per normalised name + category | `product_key UNIQUE (normalized_key)` |
| One listing per channel SKU | `listing_channel_sku UNIQUE (channel, sku)` |
| One order per channel order id | `order_channel_ext UNIQUE (channel, external_order_id)` + `idempotency_key` table for webhook delivery ids |
| One live PO per order × supplier | `po_idem` partial unique index (a rejected PO frees the key for re-routing) |
| One tracking number per carrier | `tracking UNIQUE (carrier, tracking_number)` |
| One return, one refund per return | `return_order`, `refund_once` |
| One settlement per channel × period | `settlement_period` |
| Quotation and agreement versions | `quotation_version`, `agreement_version`, `one_active_quotation` |
| One pending approval per scope × subject × version × channel | `one_pending_approval` |
| One open task per kind × subject | `one_open_task` |
| Audit log is append-only and hash-chained | `REVOKE UPDATE, DELETE` + `prev_hash`/`hash` |

## Personal data

Orders store a **token** (`ship_to_ref`) for the address held by the channel or vault, plus the 6-digit PIN for logistics. No card data is stored. Support sees a masked PIN (`751***`).
