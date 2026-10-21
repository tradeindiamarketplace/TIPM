"""Mandatory end-to-end scenarios 1-22 (docs/09-test-plan.md). Isolated data, simulated channels and suppliers.

Run:  python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import copy
import tomllib
import unittest
from datetime import timedelta
from decimal import Decimal as D

from timp.channels import AdapterError, ManualExportAdapter, ShopifyAdapter, SimulatedChannelAdapter, UnavailableAdapter
from timp.domain import *  # noqa: F403
from timp.economics import CostInputs
from timp.gates import GateBlocked
from timp.operations import SimulatedSupplierGateway
from timp.permissions import Actor, PermissionDenied, Role
from timp.platform import DEFAULT_CONFIG, FULFILLMENT_CHECKS, SUPPLIER_CHECKS, Platform
from timp.store import UniqueViolation

OWNER = Actor("owner", Role.OWNER)
A = Actor("agent_a", Role.ORCHESTRATOR)
B = Actor("agent_b", Role.PRODUCT_ANALYST)
C = Actor("agent_c", Role.SUPPLIER_SOURCING)
D_ = Actor("agent_d", Role.FINANCE)
G = Actor("agent_g", Role.DESIGN)
J = Actor("agent_j", Role.FULFILLMENT)
K = Actor("agent_k", Role.QA)
L_ = Actor("agent_l", Role.SUPPORT)
M = Actor("agent_m", Role.COMPLIANCE)
H = Actor("agent_h", Role.MARKETING)
SYS = Actor("system", Role.SYSTEM)


def test_config() -> dict:
    cfg = copy.deepcopy(tomllib.loads(DEFAULT_CONFIG.read_text()))
    # Test-only fee schedule for the simulated channel. Real channels stay unverified.
    cfg["channels"]["amazon_in"].update(fees_verified=True, commission_pct="0", fixed_fee_inr="10",
                                        fee_source="TEST FIXTURE")
    cfg["operations"]["auto_refund_limit_inr"] = "0"
    # Fixed test thresholds so the suite doesn't depend on the owner's live settings.
    cfg["thresholds"].update(min_contribution_inr="60", min_margin_pct="12", max_acquisition_cost_inr="80")
    return cfg


def ev(ref: str, kind: str = "document", at=None, summary: str = "") -> Evidence:
    return Evidence(kind, ref, at, summary)


GOOD_INPUTS = dict(selling_price_incl_gst=D("399"), output_gst_pct=D("18"), supplier_cost_excl_gst=D("112.50"),
                   supplier_gst_pct=D("18"), forward_shipping=D("65"), reverse_shipping=D("100"),
                   return_rate_pct=D("8"), ad_cost_per_order=D("30"), packaging=D("15"),
                   supplier_credit_on_return_pct=D("50"))


class Harness(unittest.TestCase):
    def setUp(self):
        self.amazon = SimulatedChannelAdapter("amazon_in")
        self.meesho = ManualExportAdapter("meesho", ["title", "description", "hsn_code"])
        self.gw = SimulatedSupplierGateway()
        self.p = Platform({"amazon_in": self.amazon, "meesho": self.meesho,
                           "flipkart": UnavailableAdapter("flipkart", "seller API access not yet approved")},
                          self.gw, config=test_config())
        self.now = self.p.clock.now

    # ---- building blocks
    def candidate(self, name="Microfiber cloth 40x40 pack of 5", category="cleaning_utility") -> Product:
        return self.p.propose_candidate(B, ProductCandidate(
            "", name, category, "urban households", {"size_cm": "40x40", "gsm": 350}, ["grey"],
            [ev("https://example.test/search-trend", "url", self.now())],
            [ev("https://example.test/competitor", "url", self.now())],
            D("349"), D("499"), ["lead-1"], ["commodity category"], "medium", "request quotations"))

    def supplier(self, verified=True) -> tuple[Supplier, SupplierQuotation]:
        s = self.p.add_supplier(C, Supplier("", "Test Textiles Pvt Ltd", "MANUFACTURER", "24ABCDE1234F1Z5",
                                            "contact-ref-1", True))
        checks = {c: CheckResult.PASS for c in SUPPLIER_CHECKS}
        if not verified:
            checks["authorised_to_distribute"] = CheckResult.FAIL
        self.p.record_supplier_verification(C, s.id, checks, {c: ev(f"doc-{c}") for c in SUPPLIER_CHECKS})
        return s, None

    def quote(self, product: Product, supplier: Supplier, cost=D("112.50")) -> SupplierQuotation:
        q = self.p.record_quotation(C, SupplierQuotation(
            "", supplier.id, product.id, "MF-5", cost, D("18"), 1, 48, self.now() + timedelta(days=60),
            ev("quotation-pdf-1", "quotation_pdf", self.now())))
        self.p.select_supplier(C, product.id, q.id)
        return q

    def to_financial_review(self, verified=True) -> tuple[Product, Supplier, SupplierQuotation]:
        prod = self.candidate()
        for st in (ProductStatus.UNDER_REVIEW, ProductStatus.SUPPLIER_VERIFICATION):
            self.p.advance(A, prod.id, st)
        s, _ = self.supplier(verified)
        q = self.quote(prod, s)
        if verified:
            self.p.advance(A, prod.id, ProductStatus.FINANCIAL_REVIEW)
        return prod, s, q

    def approve_product(self, prod, q, inputs=None):
        self.p.estimate(D_, prod.id, Channel.AMAZON_IN, CostInputs(**(inputs or GOOD_INPUTS)))
        a1 = self.p.request_approval(B, ApprovalScope.PRODUCT_OPPORTUNITY, prod.id, prod.version, "approve product")
        a2 = self.p.request_approval(C, ApprovalScope.SUPPLIER_TERMS, q.id, q.version, "approve supplier terms")
        self.p.decide(OWNER, a1.id, True)
        self.p.decide(OWNER, a2.id, True)
        self.p.advance(A, prod.id, ProductStatus.OWNER_APPROVED)

    def to_live(self, channel=Channel.AMAZON_IN) -> tuple[Product, ChannelListing, SupplierQuotation]:
        prod, s, q = self.to_financial_review()
        self.approve_product(prod, q)
        self.p.record_agreement(C, prod.id, {"payment": "net 7", "return_credit_pct": 100}, ev("signed-agreement"))
        self.p.advance(A, prod.id, ProductStatus.PRODUCT_ONBOARDING)
        prod.hsn_code, prod.gst_pct = "6307", D("18")
        for chk in self.p.required_checks(prod):
            self.p.record_compliance(M, prod.id, chk, CheckResult.PASS, [ev(f"evidence-{chk}")], "test-policy-2026-10")
        self.p.advance(A, prod.id, ProductStatus.COMPLIANCE_APPROVED)
        if channel is not Channel.AMAZON_IN:
            self.p.estimate(D_, prod.id, channel, CostInputs(**GOOD_INPUTS))
        lst = self.p.create_listing(G, prod.id, channel, "MF-5", D("399"), self.attrs())
        self.p.validate_listing(G, lst.id)
        self.p.advance(A, prod.id, ProductStatus.READY_FOR_TESTING)
        self.p.record_test_run(K, prod.id, "listing+fulfilment", [("content", True, Severity.CRITICAL),
                                                                  ("sim order", True, Severity.CRITICAL)])
        self.p.advance(A, prod.id, ProductStatus.READY_TO_PUBLISH)
        self.p.record_fulfillment_arrangement(M, prod.id, channel, "supplier_direct_self_ship",
                                              {c: True for c in FULFILLMENT_CHECKS}, [ev("channel-policy-page")])
        pub = self.p.request_approval(A, ApprovalScope.CHANNEL_PUBLICATION, prod.id, prod.version, "publish",
                                      channel=channel)
        self.p.decide(OWNER, pub.id, True)
        self.p.publish(A, lst.id)
        self.p.record_inventory(SYS, s_id := q.supplier_id, q.sku, 100, "supplier_api")
        return prod, lst, q

    @staticmethod
    def attrs():
        return {"title": "Microfiber cloth 40x40 (5)", "bullet_points": ["350 GSM"], "description": "Lint-free",
                "brand": "TIMP Home", "vendor": "TIMP Home", "product_type": "Cleaning cloth", "manufacturer": "Test Textiles", "hsn_code": "6307",
                "country_of_origin": "India", "images": ["img1"], "item_weight_g": 250, "mrp": "499"}

    def order(self, ext="AMZ-1", key="wh-1", qty=1):
        return self.p.import_order(SYS, Channel.AMAZON_IN, ext, [OrderLine("MF-5", qty, D("399"))],
                                   "addr-token-1", "751001", key)

    def po_for(self, order):
        return self.p.store.where("pos", lambda po: po.order_id == order.id)[0]


class Scenarios(Harness):
    def test_01_discover_and_recommend(self):
        prod = self.candidate()
        self.assertEqual(prod.status, ProductStatus.DISCOVERED)
        with self.assertRaises(UniqueViolation):          # deduplicated against the catalogue
            self.candidate(name="Pack of 5 microfiber CLOTH 40x40")
        with self.assertRaises(GateBlocked):              # incomplete recommendations are refused
            self.p.propose_candidate(B, ProductCandidate("", "x", "y", "", {}, [], [], [], None, None, [], [], "", ""))

    def test_02_rejected_cannot_publish(self):
        prod, s, q = self.to_financial_review()
        self.p.advance(A, prod.id, ProductStatus.REJECTED)
        with self.assertRaises(GateBlocked):
            self.p.advance(A, prod.id, ProductStatus.OWNER_APPROVED)
        lst = self.p.create_listing(G, prod.id, Channel.AMAZON_IN, "MF-5", D("399"), self.attrs())
        self.p.validate_listing(G, lst.id)
        with self.assertRaises(GateBlocked) as e:
            self.p.publish(A, lst.id)
        self.assertIn("product status is REJECTED", e.exception.reasons)

    def test_03_approved_but_supplier_fails_verification(self):
        prod, s, q = self.to_financial_review(verified=False)
        a = self.p.request_approval(B, ApprovalScope.PRODUCT_OPPORTUNITY, prod.id, prod.version, "approve")
        self.p.decide(OWNER, a.id, True)                  # owner likes the product...
        with self.assertRaises(GateBlocked) as e:         # ...but the gate still holds
            self.p.advance(A, prod.id, ProductStatus.FINANCIAL_REVIEW)
        self.assertIn("selected supplier is not verified", e.exception.reasons)
        self.assertEqual(self.amazon.remote_listings, {})

    def test_04_insufficient_profit_blocks(self):
        prod, s, q = self.to_financial_review()
        bad = dict(GOOD_INPUTS, selling_price_incl_gst=D("199"))
        est = self.p.estimate(D_, prod.id, Channel.AMAZON_IN, CostInputs(**bad))
        self.assertEqual(est.result.status, "FAIL")
        for scope, sid, v in ((ApprovalScope.PRODUCT_OPPORTUNITY, prod.id, prod.version),
                              (ApprovalScope.SUPPLIER_TERMS, q.id, q.version)):
            self.p.decide(OWNER, self.p.request_approval(B if sid == prod.id else C, scope, sid, v, "x").id, True)
        with self.assertRaises(GateBlocked) as e:
            self.p.advance(A, prod.id, ProductStatus.OWNER_APPROVED)
        self.assertIn("no channel meets the profit thresholds for this product version", e.exception.reasons)

    def test_05_supplier_terms_versioned(self):
        prod, s, q1 = self.to_financial_review()
        q2 = self.quote(prod, s, cost=D("120"))
        self.assertEqual((q1.version, q2.version, q2.supersedes_id, q1.active), (1, 2, q1.id, False))
        self.approve_product(prod, q2)
        ag = self.p.record_agreement(C, prod.id, {"payment": "net 7"}, ev("signed"))
        self.assertEqual((ag.quotation_id, ag.version), (q2.id, 1))
        self.assertTrue(self.p.audit.events("approval_decided", q2.id))

    def test_06_content_validates_channel_attributes(self):
        prod, *_ = self.to_financial_review()
        lst = self.p.create_listing(G, prod.id, Channel.AMAZON_IN, "MF-5", D("399"), {"title": "only a title"})
        self.p.validate_listing(G, lst.id)
        self.assertEqual(lst.status, ListingStatus.DRAFT)
        self.assertIn("missing hsn_code", lst.validation_errors)
        lst.attributes = self.attrs()
        self.assertEqual(self.p.validate_listing(G, lst.id).status, ListingStatus.VALIDATED)

    def test_07_publication_needs_channel_specific_approval(self):
        prod, lst, q = self.to_live()
        self.assertEqual(lst.status, ListingStatus.PUBLISHED)
        m = self.p.create_listing(G, prod.id, Channel.MEESHO, "MF-5", D("399"), self.attrs())
        self.p.validate_listing(G, m.id)
        with self.assertRaises(GateBlocked) as e:         # the Amazon approval does not cover Meesho
            self.p.publish(A, m.id)
        self.assertTrue(any("meesho" in r for r in e.exception.reasons))
        f = self.p.create_listing(G, prod.id, Channel.FLIPKART, "MF-5", D("399"), self.attrs())
        with self.assertRaises(GateBlocked) as e:
            self.p.publish(A, f.id)
        self.assertIn("flipkart integration unavailable", e.exception.reasons)

    def test_08_import_valid_order(self):
        self.to_live()
        o = self.order()
        self.assertEqual(o.status, OrderStatus.AWAITING_SUPPLIER)
        self.assertIsNone(o.dispatch_by)                  # nothing promised before the supplier confirms
        self.assertEqual(len(self.gw.received), 1)

    def test_09_unavailable_supplier_not_confirmed(self):
        prod, lst, q = self.to_live()
        self.p.record_inventory(SYS, q.supplier_id, q.sku, 0, "supplier_api")
        o = self.order()
        self.assertEqual(o.status, OrderStatus.NEEDS_ATTENTION)
        self.assertEqual(self.gw.received, {})
        self.assertNotIn(("ack", "AMZ-1"), self.amazon.calls)
        self.p.clock.advance(hours=30)                    # stale stock is treated the same as no stock
        o2 = self.order("AMZ-2", "wh-2")
        self.assertIn("stale", o2.notes[-1])

    def test_10_duplicate_webhooks_one_order(self):
        self.to_live()
        o1 = self.order(key="wh-1")
        o2 = self.order(key="wh-1")
        o3 = self.order(key="wh-1-retry")                 # same order, different delivery id
        self.assertEqual(o1.id, o2.id)
        self.assertEqual(o1.id, o3.id)
        self.assertEqual(len(self.p.store.all("orders")), 1)
        self.assertEqual(len(self.p.store.all("pos")), 1)

    def test_11_supplier_acceptance_records_po(self):
        self.to_live()
        o = self.order()
        po = self.po_for(o)
        with self.assertRaises(GateBlocked):              # acceptance without a dispatch time is refused
            self.p.record_supplier_response(J, po.id, True)
        when = self.now() + timedelta(hours=24)
        self.p.record_supplier_response(J, po.id, True, when)
        self.assertEqual((po.status, o.status, o.dispatch_by), (POStatus.ACCEPTED, OrderStatus.SUPPLIER_ACCEPTED, when))
        self.assertEqual(po.amount_incl_gst, D("132.75"))
        self.assertIn(("ack", "AMZ-1"), self.amazon.calls)

    def test_12_dispatch_and_tracking_sync(self):
        self.to_live()
        o = self.order()
        po = self.po_for(o)
        self.p.record_supplier_response(J, po.id, True, self.now() + timedelta(hours=24))
        with self.assertRaises(GateBlocked):              # supplier's word alone is not evidence
            self.p.record_carrier_event(J, po.id, "Delhivery", "", "PICKED_UP", ev("whatsapp", "message"))
        self.p.record_carrier_event(SYS, po.id, "Delhivery", "DL123", "PICKED_UP",
                                    ev("carrier-evt-1", "carrier_api", self.now()))
        self.assertEqual(o.status, OrderStatus.DISPATCHED)
        self.assertIn(("tracking", "AMZ-1:DL123"), self.amazon.calls)
        self.p.record_carrier_event(SYS, po.id, "Delhivery", "DL123", "DELIVERED",
                                    ev("carrier-evt-2", "carrier_api", self.now()))
        self.assertEqual(o.status, OrderStatus.DELIVERED)

    def test_13_delayed_shipment_escalates(self):
        self.to_live()
        o = self.order()
        self.p.record_supplier_response(J, self.po_for(o).id, True, self.now() + timedelta(hours=24))
        self.p.clock.advance(hours=30)
        self.assertEqual(self.p.check_slas(A), [o.id])
        self.assertEqual(self.p.check_slas(A), [])        # escalated once, not every run
        self.assertTrue(self.p.store.where("cases", lambda c: c.order_id == o.id))
        self.assertTrue(self.p.audit.events("sla_breach", o.id))

    def test_14_cancellation_updates_everything(self):
        self.to_live()
        o = self.order()
        po = self.po_for(o)
        self.p.cancel_order(J, o.id, "customer request")
        self.assertEqual((o.status, po.status), (OrderStatus.CANCELLED, POStatus.CANCELLED))
        self.assertIn(po.id, self.gw.cancelled)
        self.assertIn(("cancel", "AMZ-1"), self.amazon.calls)

    def test_15_return_refund_supplier_credit(self):
        self.to_live()
        o = self.order()
        po = self.po_for(o)
        self.p.record_supplier_response(J, po.id, True, self.now() + timedelta(hours=24))
        self.p.record_carrier_event(SYS, po.id, "Delhivery", "DL9", "PICKED_UP", ev("e1", "carrier_api", self.now()))
        self.p.record_carrier_event(SYS, po.id, "Delhivery", "DL9", "DELIVERED", ev("e2", "carrier_api", self.now()))
        rr = self.p.request_return(L_, o.id, "damaged")
        self.assertEqual(rr.status, ReturnStatus.APPROVED)
        self.p.receive_return(J, rr.id, ev("return-scan"), resellable=True)
        self.assertEqual(rr.supplier_credit_expected, D("132.75"))
        with self.assertRaises(GateBlocked):
            self.p.refund(SYS, rr.id, D("500"))           # more than was paid
        rf = self.p.refund(SYS, rr.id, D("399"))
        self.assertEqual((rf.executed_by, o.status), ("channel", OrderStatus.REFUNDED))
        self.p.record_supplier_credit(D_, rr.id, D("132.75"), ev("credit-note-1"))
        self.assertEqual(rr.supplier_credit_received, rr.supplier_credit_expected)

    def test_16_settlement_reconciliation(self):
        self.to_live()
        self.order("AMZ-1", "wh-1")
        self.order("AMZ-2", "wh-2")
        tcs = round(D("399") / D("1.18") * D("0.005"), 2)
        tds = round(D("399") / D("1.18") * D("0.001"), 2)
        good = dict(external_order_id="AMZ-1", gross="399", commission="0", fixed_fee="11.80", payment_fee="0",
                    tcs=str(tcs), tds=str(tds), net=str(D("399") - D("11.80") - tcs - tds))
        bad = dict(good, external_order_id="AMZ-2", fixed_fee="35.40",
                   net=str(D("399") - D("35.40") - tcs - tds))
        st = self.p.reconcile_settlement(D_, Channel.AMAZON_IN, "2026-11-W1", [good, bad])
        self.assertEqual(st.status, "VARIANCE")
        self.assertEqual({v["order"] for v in st.variances}, {"AMZ-2"})

    def test_17_api_outage_retries_and_recovers(self):
        prod, s, q = self.to_financial_review()
        self.amazon.fail_next(2)                          # transient: recovered inside the retry budget
        self.p.record_inventory(SYS, q.supplier_id, q.sku, 100, "supplier_api")
        # drive to publish with the flaky adapter
        self.approve_product(prod, q)
        self.p.record_agreement(C, prod.id, {"return_credit_pct": 100}, ev("signed"))
        self.p.advance(A, prod.id, ProductStatus.PRODUCT_ONBOARDING)
        prod.hsn_code, prod.gst_pct = "6307", D("18")
        for chk in self.p.required_checks(prod):
            self.p.record_compliance(M, prod.id, chk, CheckResult.PASS, [ev(chk)], "p")
        self.p.advance(A, prod.id, ProductStatus.COMPLIANCE_APPROVED)
        lst = self.p.create_listing(G, prod.id, Channel.AMAZON_IN, "MF-5", D("399"), self.attrs())
        self.p.validate_listing(G, lst.id)
        self.p.advance(A, prod.id, ProductStatus.READY_FOR_TESTING)
        self.p.record_test_run(K, prod.id, "s", [("x", True, Severity.CRITICAL)])
        self.p.advance(A, prod.id, ProductStatus.READY_TO_PUBLISH)
        self.p.record_fulfillment_arrangement(M, prod.id, Channel.AMAZON_IN, "sd", {c: True for c in FULFILLMENT_CHECKS}, [ev("x")])
        self.p.decide(OWNER, self.p.request_approval(A, ApprovalScope.CHANNEL_PUBLICATION, prod.id, prod.version, "p",
                                                     channel=Channel.AMAZON_IN).id, True)
        self.p.publish(A, lst.id)
        self.assertEqual(len(self.amazon.remote_listings), 1)
        # hard outage at the supplier: order held, nothing duplicated, recovery sends exactly one PO
        self.gw.fail_next(10)
        o = self.order()
        self.assertEqual(o.status, OrderStatus.NEEDS_ATTENTION)
        self.assertEqual(self.p.store.all("pos"), [])
        self.gw.fail_next(0)
        self.p.route_order(SYS, o.id)
        self.p.route_order(SYS, o.id)
        self.assertEqual(len(self.gw.received), 1)

    def test_18_agents_cannot_approve_or_spend(self):
        prod, s, q = self.to_financial_review()
        a = self.p.request_approval(B, ApprovalScope.PRODUCT_OPPORTUNITY, prod.id, prod.version, "x")
        for agent in (A, B, C, D_, G, J, K, L_, M, H):
            with self.assertRaises(PermissionDenied):
                self.p.decide(agent, a.id, True)
        c = self.p.propose_campaign(H, Channel.AMAZON_IN, "launch", D("5000"))
        with self.assertRaises(GateBlocked):
            self.p.start_campaign(SYS, c.id)
        exp = self.p.request_approval(D_, ApprovalScope.EXPENSE, "samples", 1, "samples", amount_limit=D("500"))
        with self.assertRaises(GateBlocked):
            self.p.record_expense(D_, "samples", D("400"), "samples", exp.id)
        self.p.decide(OWNER, exp.id, True)
        self.p.record_expense(D_, "samples", D("400"), "samples", exp.id)
        with self.assertRaises(GateBlocked):              # single-use approval is consumed
            self.p.record_expense(D_, "samples", D("50"), "more samples", exp.id)

    def test_19_margin_breach_pauses(self):
        prod, lst, q = self.to_live()
        worse = CostInputs(**dict(GOOD_INPUTS, supplier_cost_excl_gst=D("250")))
        self.assertEqual(self.p.check_margins(A, {lst.id: worse}), [lst.id])
        self.assertEqual(lst.status, ListingStatus.PAUSED)
        self.assertFalse(self.amazon.remote_listings[lst.id]["active"])
        self.assertTrue(self.p.store.where("notifications", lambda n: n.kind == "margin_breach"))

    def test_20_support_sees_accurate_order(self):
        self.to_live()
        o = self.order()
        view = self.p.order_view(L_, o.id)
        self.assertEqual(view["dispatch_by"], "not yet confirmed by supplier")
        self.assertEqual(view["ship_to"], "PIN 751***")
        self.assertNotIn("addr-token-1", str(view))
        with self.assertRaises(PermissionDenied):
            self.p.order_view(H, o.id)

    def test_21_retired_cannot_republish(self):
        prod, lst, q = self.to_live()
        self.p.advance(OWNER, prod.id, ProductStatus.RETIRED)
        self.assertEqual(lst.status, ListingStatus.WITHDRAWN)
        for to in (ProductStatus.LIVE, ProductStatus.READY_TO_PUBLISH):
            with self.assertRaises(GateBlocked):
                self.p.advance(OWNER, prod.id, to)
        with self.assertRaises(GateBlocked):
            self.p.publish(A, lst.id)
        self.assertEqual(self.order().status, OrderStatus.NEEDS_ATTENTION)

    def test_22_audit_captures_material_actions(self):
        prod, lst, q = self.to_live()
        o = self.order()
        actions = {e.action for e in self.p.audit.events()}
        for must in ("product_discovered", "supplier_verification", "quotation_recorded", "economics_estimated",
                     "approval_requested", "approval_decided", "supplier_agreement_recorded", "compliance_check",
                     "product_transition", "listing_published", "order_imported", "supplier_po_submitted"):
            self.assertIn(must, actions)
        decided = self.p.audit.events("approval_decided")[0]
        self.assertEqual(decided.actor_id, "owner")
        self.assertTrue(self.p.audit.verify())
        decided.details["granted"] = False                # tampering breaks the chain
        self.assertFalse(self.p.audit.verify())


class Safeguards(Harness):
    def test_material_change_requires_reapproval(self):
        prod, lst, q = self.to_live()
        self.p.material_change(A, prod.id, "supplier raised price", attributes={"cost_note": "new quote"})
        self.assertEqual((prod.status, lst.status), (ProductStatus.PAUSED, ListingStatus.PAUSED))
        with self.assertRaises(GateBlocked) as e:
            self.p.publish(A, lst.id)
        self.assertTrue(any("approved publication" in r for r in e.exception.reasons))

    def test_emergency_stop(self):
        self.to_live()
        self.p.engage_stop(M, StopSwitch.SUPPLIER_ORDERS, "supplier quality alert")
        self.assertEqual(self.order().status, OrderStatus.NEEDS_ATTENTION)
        with self.assertRaises(PermissionDenied):
            self.p.release_stop(M, StopSwitch.SUPPLIER_ORDERS)
        self.p.release_stop(OWNER, StopSwitch.SUPPLIER_ORDERS)

    def test_po_above_cap_needs_owner(self):
        self.to_live()
        o = self.order(qty=40)                            # 40 x 132.75 = 5,310 > 5,000 cap
        self.assertEqual(o.status, OrderStatus.NEEDS_ATTENTION)
        a = self.p.store.where("approvals", lambda a: a.scope is ApprovalScope.PURCHASE_COMMITMENT)[0]
        self.p.decide(OWNER, a.id, True)
        self.p.route_order(SYS, o.id)
        self.assertEqual(o.status, OrderStatus.AWAITING_SUPPLIER)
        self.assertEqual(a.status, ApprovalStatus.CONSUMED)

    def test_own_site_refund_needs_approval(self):
        shop = SimulatedChannelAdapter("shopify")
        self.p.adapters["shopify"] = shop
        self.p.config["channels"]["shopify"].update(fees_verified=True, payment_fee_pct="2", platform_fee_pct="2")
        prod, lst, q = self.to_live(channel=Channel.SHOPIFY)
        self.assertEqual(lst.status, ListingStatus.PUBLISHED)
        o = self.p.import_order(SYS, Channel.SHOPIFY, "#1001", [OrderLine("MF-5", 1, D("399"))], "addr", "560001", "s-1")
        po = self.po_for(o)
        self.p.record_supplier_response(J, po.id, True, self.now() + timedelta(hours=24))
        self.p.record_carrier_event(SYS, po.id, "Bluedart", "BD1", "PICKED_UP", ev("e1", "carrier_api", self.now()))
        self.p.record_carrier_event(SYS, po.id, "Bluedart", "BD1", "DELIVERED", ev("e2", "carrier_api", self.now()))
        rr = self.p.request_return(L_, o.id, "wrong colour")
        self.p.receive_return(J, rr.id, ev("scan"), resellable=True)
        with self.assertRaises(GateBlocked):              # our own gateway: owner must approve (limit is 0)
            self.p.refund(SYS, rr.id, D("399"))
        a = self.p.request_approval(L_, ApprovalScope.EXCEPTIONAL_REFUND, o.id, 1, "refund", amount_limit=D("399"))
        self.p.decide(OWNER, a.id, True)
        self.assertEqual(self.p.refund(SYS, rr.id, D("399"), a.id).executed_by, "own_gateway")
        self.assertEqual(a.status, ApprovalStatus.CONSUMED)

    def test_manual_channel_waits_for_owner_confirmation(self):
        self.p.config["channels"]["meesho"].update(fees_verified=True, commission_pct="0")
        prod, lst, q = self.to_live(channel=Channel.MEESHO)
        self.assertEqual(lst.status, ListingStatus.AWAITING_MANUAL_UPLOAD)
        self.assertIn("MF-5", self.meesho.exports[0])
        self.assertEqual(prod.status, ProductStatus.READY_TO_PUBLISH)
        self.p.confirm_manual_upload(OWNER, lst.id, "MEESHO-123")
        self.assertEqual(prod.status, ProductStatus.LIVE)

    def test_shopify_payload_is_idempotent_upsert(self):
        sent = []
        def transport(q, v):
            sent.append((q, v))
            return {"data": {"productSet": {"product": {"id": "gid://shopify/Product/1", "status": "ACTIVE"},
                                            "userErrors": []}}}
        ad = ShopifyAdapter(transport)
        prod = self.candidate()
        lst = ChannelListing("lst_x", prod.id, Channel.SHOPIFY, "MF-5", D("399"), self.attrs())
        self.assertEqual(ad.publish_listing(lst, prod), "gid://shopify/Product/1")
        self.assertEqual(sent[0][1]["identifier"], {"handle": "timp-mf-5"})
        self.assertEqual(sent[0][1]["input"]["variants"][0]["price"], "399")


if __name__ == "__main__":
    unittest.main()
