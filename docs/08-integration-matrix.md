# 08 · Integration capability matrix

Status meanings: **LIVE_TESTED** = exercised against the real environment · **PARTIAL** = code exists, not run live · **SIMULATED** = test double only · **MANUAL** = export file plus human upload · **UNAVAILABLE** = needs account or approval · **PLANNED** = not written.

Nothing below is LIVE_TESTED yet. That is deliberate: nothing goes live without your approval.

| Capability | TradeIndiaMarketplace.com (Shopify) | Amazon.in | Flipkart | Meesho |
|---|---|---|---|---|
| Auth | Admin API access token via a custom app (store this in a secret manager). The Claude connector used for the audit is read-only in practice. | SP-API: seller account + developer registration + LWA OAuth | Seller API: seller account + API access application, OAuth client credentials | No public seller API confirmed. Supplier panel login |
| Create/update listing | **PARTIAL**: `productSet` upsert by handle (field names checked against the schema 2026-10-21) | PLANNED: Listings Items API | PLANNED: Listings API | **MANUAL**: CSV via `ManualExportAdapter`; owner confirms upload |
| Publish to storefront | PLANNED: `publishablePublish` to the Online Store publication | via listing | via listing | manual |
| Pause / delist | **PARTIAL**: `productUpdate` status DRAFT | PLANNED | PLANNED | manual task |
| Price sync | PLANNED: `productVariantsBulkUpdate` | PLANNED | PLANNED | manual task |
| Inventory sync | PLANNED: `inventorySetQuantities` from available-to-sell | PLANNED | PLANNED | manual |
| Category/attribute mapping | config `required_attributes` (validated) | same (attribute list to confirm per category) | same | same |
| Order import | PLANNED: `orders/create` webhook (HMAC verified) + hourly `orders` query reconcile | PLANNED: Orders API + notifications | PLANNED: Orders API | manual: panel export |
| Fulfilment/tracking | PLANNED: `fulfillmentCreate` with tracking | PLANNED: confirm shipment | PLANNED | manual task |
| Cancel/return | PLANNED: `orderCancel`, returns | PLANNED | PLANNED | manual |
| Settlement | Payment gateway settlement report (CSV) | PLANNED: Finances / settlement reports | PLANNED: payments report | manual: panel payment report CSV |
| Rate limits | GraphQL cost-based; backoff on throttle | per-operation quotas | per API | n/a |
| Retries / reconciliation | `call_with_retry`, dead-letter, idempotent upsert | same pattern | same | n/a |
| Test status | Payload test with fake transport (`test_shopify_payload_is_idempotent_upsert`) | SIMULATED adapter in tests | UnavailableAdapter in tests | ManualExportAdapter tested |

## External approvals still required

1. **GST registration** (and APOB for each supplier pickup address). Without it you can't sell on the marketplaces as described here.
2. Amazon.in seller account, then SP-API developer registration.
3. Flipkart seller account, then Seller API access approval.
4. Meesho supplier account.
5. Payment gateway for Shopify (Razorpay, PayU or Cashfree) with KYC.
6. Courier aggregator account for website orders.
7. Shopify custom app with the scopes `write_products`, `read_orders`, `write_fulfillments`, `write_inventory`, `read_locations`.
