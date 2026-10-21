# 12 · Deployment and rollback plan

## Environments

| Env | Data | Channels | Who deploys |
|---|---|---|---|
| test | in-memory | simulated | CI on every commit |
| staging | Postgres (staging) | Shopify **development store**, SP-API sandbox | CI on merge to `main` |
| production | Postgres (prod, PITR backups) | live store + approved marketplaces | manual promotion with owner approval |

## Release steps

1. CI: unit + E2E suite (must be 100% green), lint, dependency audit, secret scan.
2. Deploy to staging, run DB migrations, run the staging E2E (F-22).
3. QA agent records a `TestRun`. Any HIGH or CRITICAL failure blocks the release.
4. Owner approves the release (`DESTRUCTIVE_CHANGE` scope if it includes data migrations).
5. Production: **engage the PUBLISHING and SUPPLIER_ORDERS stops** → back up (DB snapshot + Shopify product export) → migrate → deploy → smoke test (read-only) → release the stops.
6. Watch for 24 h: error rate, dead letters, webhook lag, margin alerts.

## Rollback

| Failure | Action |
|---|---|
| App bug, no schema change | Redeploy the previous image (stops engaged meanwhile) |
| Bad migration | Migrations are expand-then-contract; roll back to the previous image (old columns still exist). Worst case: point-in-time restore |
| Bad listing push | Pause the affected listings (`pause_listing`), restore content from `product_version` snapshots, republish after re-approval |
| Wrong prices on a channel | Engage PUBLISHING stop, push the last approved price from `pricing_rule` / estimates |
| Theme change on the live store | Shopify keeps the previous theme. Republish it from Online Store > Themes |
| Supplier PO storm | Engage SUPPLIER_ORDERS stop; POs are idempotent, so resume once fixed |

The emergency stop pauses activity without deleting any history. Releasing it is owner-only.

## Backups

* Postgres: daily snapshot + WAL point-in-time recovery, 30-day retention. Restore drill monthly (F-23).
* Evidence files: versioned object storage, never deleted.
* Shopify: weekly product + theme export.
