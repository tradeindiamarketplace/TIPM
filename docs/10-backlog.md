# 10 · Phased implementation backlog

Legend: ✅ done in this project · 🟡 partial · ⬜ not started · 🔑 needs an owner or external action

## Phase 1: Audit ✅
| ID | Item | Status | Acceptance |
|---|---|---|---|
| P1-1 | Read-only Shopify audit | ✅ | docs/01 |
| P1-2 | Obsolete-feature inventory | ✅ | docs/01 |
| P1-3 | Confirm marketplace seller-account and GST status | 🔑 | Owner answers: GSTIN? Amazon/Flipkart/Meesho accounts? |

## Phase 2: Design ✅
Architecture, permissions, schema, API, risk register, deployment plan: docs/02–12 ✅

## Phase 3: Core catalogue, suppliers, approvals, calculator, dashboard
| ID | Item | Depends | Status | Acceptance |
|---|---|---|---|---|
| F-01 | Domain core, lifecycle gates, approvals, audit | — | ✅ | 28 tests pass |
| F-02 | PostgreSQL repository replacing the in-memory store | F-01 | ⬜ | Same test suite passes on Postgres; concurrent-webhook test |
| F-03 | HTTP API (FastAPI) per openapi.yaml, service-account auth, owner step-up | F-02 | ⬜ | Contract tests; 403/409 behaviour |
| F-04 | Owner dashboard (approval queue, margins, supplier health, channel status, stops) | F-03 | ⬜ | Each metric shows definition, period, freshness |
| F-05 | Margin engine | — | ✅ | docs/07; scripts/profit_report.py |
| F-06 | Evidence store (object storage + sha256) | F-02 | ⬜ | Evidence immutable and linked |

## Phase 4: Discovery and supplier verification
| F-07 | Agent B research job (permitted sources only) writing candidates | F-03 | 🟡 | First manual research pass done (reports/) |
| F-08 | Agent C supplier verification workflow: GSTIN check on the GST portal, documents, test dispatches | F-03 | ⬜ 🔑 | Supplier scorecard |
| F-09 | Available-to-sell pool shared across channels (cross-channel oversell guard) | F-02 | ⬜ | Two channels can't sell the last unit twice |

## Phase 5: Listings, content, adapters, compliance
| F-10 | Shopify adapter: publishablePublish, price, inventory, webhooks | F-03 🔑 custom-app token | 🟡 | Run against a Shopify dev store |
| F-11 | Amazon SP-API adapter | 🔑 seller + developer registration | ⬜ | Sandbox tests |
| F-12 | Flipkart adapter | 🔑 API access | ⬜ | |
| F-13 | Meesho manual workflow | — | ✅ | CSV export + owner confirmation |
| F-14 | Compliance checklists per category with a policy-version library | — | 🟡 | Config `[compliance]`; CA/lawyer review 🔑 |

## Phase 6: Orders, fulfilment, returns, support
| F-15 | Order import, supplier PO, carrier events, SLA, cancel, returns, refunds | — | ✅ (domain) | Tests 8–15, 17, 20 |
| F-16 | Supplier gateway (email/WhatsApp Business/portal) with acceptance capture | F-03 🔑 | ⬜ | |
| F-17 | Carrier tracking via aggregator API | 🔑 | ⬜ | |
| F-18 | Support inbox integration | F-03 | ⬜ | |

## Phase 7: Marketing, pricing, analytics, settlement
| F-19 | Settlement import per channel | F-11/12 | 🟡 | Reconciler done (test 16) |
| F-20 | Pricing rules within floor/ceiling | F-03 | ⬜ | |
| F-21 | Campaign proposals + spend tracking | — | ✅ (domain) | |

## Phase 8: Hardening
| F-22 | Staging E2E against Shopify dev store and SP-API sandbox | F-10/11 | ⬜ | |
| F-23 | Security review, secret rotation, backup-restore drill | F-02 | ⬜ | |

## Phase 9: Pilot 🔑
1–3 owner-approved products from one verified in-state supplier, on TradeIndiaMarketplace.com, then Amazon.in.
**Exit criteria:** ≥ 50 orders · ≥ 95% on-time dispatch · return rate ≤ the assumption used in the estimate · actual contribution ≥ threshold · zero compliance issues.

## Phase 10: Scale
Add products and channels only after the pilot exit criteria are met for 8 consecutive weeks.

## Storefront (done 2026-10-21)
| S-1 | Policy pages, contact details, menus, product compliance metafields | ✅ live |
| S-2 | Marketplace-style homepage, search bar, category strip, product cards | ✅ in theme v3; 🔑 owner publishes |
| S-3 | Git → Shopify deploy workflow | ✅ written; 🔑 repo access + Theme Access token |
| S-4 | Official Shopify policy slots | 🔑 paste in Settings > Policies (scope not available to the connector) |

## Your next actions (owner)
1. Tell me your GST status and which marketplace seller accounts exist.
2. Decide the thresholds in `config/settings.toml` (₹60 / 12% / ₹80 are placeholders).
3. Choose 2–3 products from reports/product-profit-report.md to get **real quotations** for.
4. Authorise (or not) migration steps M1–M6 in docs/01.
