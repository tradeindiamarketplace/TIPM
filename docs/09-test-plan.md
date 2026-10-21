# 09 · End-to-end test plan

Run: `python3 -m unittest discover -s tests -t . -v` (stdlib only, ~0.2 s).

**Result on 2026-10-21: 28 tests, 28 passed** (22 mandatory scenarios + 6 safeguards). All use isolated in-memory data, `SimulatedChannelAdapter`, `ManualExportAdapter`, `UnavailableAdapter` and `SimulatedSupplierGateway`. No real store, marketplace, supplier, customer or payment was touched.

| # | Scenario | Test | What is asserted |
|---|---|---|---|
| 1 | Discover and recommend | `test_01` | Product DISCOVERED; duplicate refused; incomplete recommendation refused |
| 2 | Rejected cannot publish | `test_02` | REJECTED is terminal; publish blocked with reason |
| 3 | Approved, supplier fails verification | `test_03` | Owner approval does not override the verification gate; nothing on the channel |
| 4 | Insufficient profit | `test_04` | Estimate FAIL; OWNER_APPROVED blocked even with both approvals granted |
| 5 | Supplier terms versioned | `test_05` | v1 superseded by v2; agreement bound to v2 |
| 6 | Channel attributes | `test_06` | Missing attributes keep the listing DRAFT |
| 7 | Channel-specific publication | `test_07` | Amazon approval doesn't cover Meesho; Flipkart unavailable |
| 8 | Import a valid order | `test_08` | AWAITING_SUPPLIER, one PO, **no dispatch promise** |
| 9 | Unavailable supplier | `test_09` | Zero or stale stock goes to NEEDS_ATTENTION; no PO; no channel acknowledgement |
| 10 | Duplicate webhooks | `test_10` | Same delivery id and a new delivery id both resolve to 1 order and 1 PO |
| 11 | Supplier acceptance | `test_11` | Acceptance without a dispatch time is refused; PO amount incl. GST; channel acknowledged |
| 12 | Dispatch and tracking | `test_12` | Supplier message alone refused; carrier evidence moves to DISPATCHED, then DELIVERED; tracking pushed |
| 13 | Delayed shipment | `test_13` | SLA breach flagged once, support case opened, audited |
| 14 | Cancellation | `test_14` | Order + PO cancelled, supplier and channel informed |
| 15 | Return, refund, supplier credit | `test_15` | Within window; credit expected = PO; refund ≤ paid; credit reconciled |
| 16 | Settlement reconciliation | `test_16` | Correct line MATCHED; overcharged closing fee flagged |
| 17 | API outage | `test_17` | 2 transient failures retried; hard supplier outage holds the order; recovery sends exactly 1 PO |
| 18 | Unauthorised agents | `test_18` | All 10 agent roles denied approval; campaign won't start; expense needs approval; single-use consumed |
| 19 | Margin breach | `test_19` | Alert + listing paused on the channel |
| 20 | Support accuracy | `test_20` | "not yet confirmed by supplier"; PIN masked; marketing denied |
| 21 | Retired cannot republish | `test_21` | Listing withdrawn; no transitions out; new orders held |
| 22 | Audit completeness | `test_22` | 12 key actions present; owner recorded as approver; tampering detected |
| + | Material change | `test_material_change_requires_reapproval` | Version bump pauses the live listing; old approval no longer valid |
| + | Emergency stop | `test_emergency_stop` | Stops POs; only the owner can release |
| + | PO above cap | `test_po_above_cap_needs_owner` | Held until owner approves; approval consumed |
| + | Own-site refund | `test_own_site_refund_needs_approval` | Refund through own gateway needs an EXCEPTIONAL_REFUND approval |
| + | Manual channel | `test_manual_channel_waits_for_owner_confirmation` | Export file made; LIVE only after owner confirms |
| + | Shopify payload | `test_shopify_payload_is_idempotent_upsert` | Upsert by handle, price string |

## Still to test (not done yet)

* Against a **Shopify development store** (staging): productSet, publishablePublish, orders webhook HMAC, fulfillmentCreate.
* PostgreSQL migration and constraint behaviour under concurrency (two webhook deliveries in parallel).
* Load (1,000 orders/day), restore-from-backup drill, secret rotation drill.
* Marketplace sandboxes where available (SP-API has a sandbox; Flipkart and Meesho need confirmation).

Release rule: any HIGH or CRITICAL failure blocks release (`TestRun.critical_failures`).
