# TradeIndiaMarketplace Platform

AI-assisted, inventory-free e-commerce operations for **TradeIndiaMarketplace.com**, Amazon.in, Flipkart and Meesho. Products come from verified suppliers and ship supplier-direct. The owner approves every material decision, and the agents automate the approved work.

**Start here:** [`reports/agent-briefing.md`](reports/agent-briefing.md) (what each agent found, and the decisions needed from you), then [`reports/product-profit-report.md`](reports/product-profit-report.md).

## Status at a glance

| | Status |
|---|---|
| Domain core: lifecycle gates, approvals, permissions, margin engine, orders → POs → shipments → returns → refunds, settlement reconciliation, support view, campaigns, emergency stop, hash-chained audit | **Implemented, tested (28/28 passing)**, simulated channels and suppliers only |
| Shopify adapter | **Partial**: payloads match the Admin GraphQL schema; not run against the live store |
| Amazon.in / Flipkart adapters | **Unavailable**: seller accounts and API approvals needed |
| Meesho | **Manual** CSV export + owner confirmation |
| PostgreSQL schema, HTTP API | **Written, not yet run** (`db/schema.sql`, `api/openapi.yaml`) |
| Dashboard UI, supplier gateway, carrier tracking | **Planned** (docs/10) |
| Live store | **Updated 2026-10-21**: policy pages, contact details, menus, product compliance fields. New marketplace-style design is in theme "Horizon - TIMP v3 (ready to publish)", waiting for the owner to click Publish. See [`site/README.md`](site/README.md) |
| Git → Shopify deploy | `.github/workflows/ci-deploy.yml` (tests, then `shopify theme push`). Needs the repo connected and a Theme Access token |

## Deliverables

| # | Document |
|---|---|
| 1 | [Current-state audit and obsolete-feature inventory](docs/01-current-state-audit.md) |
| 2 | [Architecture](docs/02-architecture.md) |
| 3 | [Agent responsibility and permission matrix](docs/03-agent-permission-matrix.md) |
| 4 | [Database schema and API contracts](docs/04-schema-and-api.md) |
| 5 | [Supplier-direct fulfilment feasibility](docs/05-fulfillment-feasibility.md) |
| 6 | [Product discovery and approval workflow](docs/06-discovery-approval-workflow.md) |
| 7 | [Margin calculation specification](docs/07-margin-specification.md) |
| 8 | [Integration capability matrix](docs/08-integration-matrix.md) |
| 9 | [End-to-end test plan and results](docs/09-test-plan.md) |
| 10 | [Phased backlog](docs/10-backlog.md) |
| 11 | [Risk register](docs/11-risk-register.md) |
| 12 | [Deployment and rollback](docs/12-deployment-rollback.md) |

## Layout

```
config/settings.toml      owner thresholds, scenarios, operations caps, channel fee cards (UNVERIFIED), compliance checklists
timp/domain.py            the 28 entities
timp/permissions.py       agent roles × permissions (owner-only actions asserted)
timp/economics.py         margin engine (net contribution, 3 scenarios, break-even, min viable price)
timp/platform.py          catalogue, suppliers, compliance, approvals, lifecycle gates, listings, margin monitor
timp/operations.py        orders, supplier POs, carrier events, SLAs, cancel, returns, refunds, settlements, support, campaigns, tasks
timp/channels/            Shopify (partial), simulated, manual-export, unavailable adapters
timp/audit.py             hash-chained audit log
site/                     storefront: theme sections/snippets/templates, policy and page content, backups (see site/README.md)
.github/workflows/        CI tests + Shopify theme deploy on push to main
research/candidates.py    first research pass: products, supplier prices, fee estimates, with sources
scripts/profit_report.py  regenerates reports/product-profit-report.md
tests/test_e2e.py         the 22 mandatory scenarios + safeguards
db/schema.sql             PostgreSQL target schema
api/openapi.yaml          API contract
```

## Commands

```bash
python3 -m unittest discover -s tests -t . -v   # run all tests (Python 3.11+, no dependencies)
python3 scripts/profit_report.py                # recompute profit estimates after editing research/ or config/
```

To evaluate a new product, add it to `research/candidates.py` with its sources, then rerun the report. When you get a real supplier quote or verify a fee card, update the value and set `fees_verified = true` with the source and date. The gate only opens on verified fees.
