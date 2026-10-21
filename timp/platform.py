"""Platform facade: one place where every agent action goes through permission checks,
approval gates and the audit log. Agents call these methods; they never touch the store directly."""
from __future__ import annotations

import re
import tomllib
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable

from . import economics as econ
from .audit import AuditLog
from .channels import AdapterError, ChannelAdapter
from .domain import *  # noqa: F403  (the shared data model)
from .gates import GateBlocked, call_with_retry
from .operations import OperationsMixin
from .permissions import Actor, Perm, Role, require
from .store import Clock, Store, UniqueViolation

DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "config" / "settings.toml"


SYSTEM = Actor("system", Role.SYSTEM)

TRANSITIONS: dict[ProductStatus, set[ProductStatus]] = {
    ProductStatus.DISCOVERED: {ProductStatus.UNDER_REVIEW},
    ProductStatus.UNDER_REVIEW: {ProductStatus.SUPPLIER_VERIFICATION},
    ProductStatus.SUPPLIER_VERIFICATION: {ProductStatus.FINANCIAL_REVIEW},
    ProductStatus.FINANCIAL_REVIEW: {ProductStatus.OWNER_APPROVED},
    ProductStatus.OWNER_APPROVED: {ProductStatus.PRODUCT_ONBOARDING},
    ProductStatus.PRODUCT_ONBOARDING: {ProductStatus.COMPLIANCE_APPROVED},
    ProductStatus.COMPLIANCE_APPROVED: {ProductStatus.READY_FOR_TESTING},
    ProductStatus.READY_FOR_TESTING: {ProductStatus.READY_TO_PUBLISH},
    ProductStatus.READY_TO_PUBLISH: {ProductStatus.LIVE},
    ProductStatus.LIVE: {ProductStatus.PAUSED},
    ProductStatus.PAUSED: {ProductStatus.LIVE},
    ProductStatus.RETIRED: set(),
    ProductStatus.REJECTED: set(),
}
PRE_APPROVAL = {ProductStatus.DISCOVERED, ProductStatus.UNDER_REVIEW, ProductStatus.SUPPLIER_VERIFICATION,
                ProductStatus.FINANCIAL_REVIEW}
for _s in TRANSITIONS:
    if _s not in (ProductStatus.RETIRED, ProductStatus.REJECTED):
        TRANSITIONS[_s].add(ProductStatus.RETIRED)
    if _s in PRE_APPROVAL:
        TRANSITIONS[_s].add(ProductStatus.REJECTED)

SUPPLIER_CHECKS = ("business_identity", "gstin_active", "contact_verified", "authorised_to_distribute",
                   "quality_evidence", "dispatch_capability", "tracking_available", "return_handling",
                   "third_party_fulfilment_agreed")
FULFILLMENT_CHECKS = ("channel_permits_method", "owner_is_seller_of_record", "packaging_invoice_compliant",
                      "supplier_meets_sla", "return_process_documented", "stock_feed_reliable",
                      "authenticity_evidence", "tax_documents_available")


def normalize(name: str) -> str:
    return " ".join(sorted(set(re.findall(r"[a-z0-9]+", name.lower()))))


class Platform(OperationsMixin):
    def __init__(self, adapters: dict[str, ChannelAdapter], supplier_gateway, clock: Clock | None = None,
                 config: dict | None = None, sleep: Callable[[float], None] = lambda s: None):
        self.clock = clock or Clock()
        self.store = Store()
        self.audit = AuditLog(self.clock)
        self.config = config or tomllib.loads(DEFAULT_CONFIG.read_text())
        self.thresholds = econ.Thresholds.from_config(self.config["thresholds"])
        self.scenarios = tuple(econ.Scenario(k, *(Decimal(v[f]) for f in ("return_rate_mult", "ad_cost_mult",
                                                                         "shipping_mult")))
                               for k, v in self.config["scenarios"].items())
        self.ops = self.config["operations"]
        self.adapters = adapters
        self.suppliers_gw = supplier_gateway
        self.sleep = sleep
        self.stops: set[StopSwitch] = set()
        self.dead_letters: list[dict] = []

    # ---------------------------------------------------------------- helpers
    def _now(self):
        return self.clock.now()

    def _log(self, actor: Actor, action: str, subject: str, **details) -> None:
        self.audit.record(actor.id, action, subject, **details)

    def notify(self, severity: Severity, kind: str, message: str, subject_id: str) -> Notification:
        n = Notification(self.store.new_id("ntf"), severity, kind, message, subject_id, self._now())
        self.store.add("notifications", n)
        self.audit.record("system", "notification", subject_id, severity=severity, kind=kind, message=message)
        return n

    def fees(self, channel: str) -> econ.ChannelFees:
        return econ.ChannelFees.from_config(channel, self.config["channels"][channel])

    def _adapter_call(self, actor: Actor, op: str, subject: str, fn: Callable[[], Any]) -> Any:
        try:
            return call_with_retry(fn, sleep=self.sleep)
        except AdapterError as e:
            self.dead_letters.append({"op": op, "subject": subject, "error": str(e), "at": self._now(), "fn": fn})
            self._log(actor, "adapter_failed", subject, op=op, error=str(e))
            self.notify(Severity.HIGH, "integration_error", f"{op} failed after retries: {e}", subject)
            raise

    def retry_dead_letters(self, actor: Actor) -> int:
        require(actor, Perm.MANAGE_TASKS)
        done, pending = 0, []
        for job in self.dead_letters:
            try:
                job["fn"]()
                done += 1
                self._log(actor, "dead_letter_recovered", job["subject"], op=job["op"])
            except AdapterError:
                pending.append(job)
        self.dead_letters = pending
        return done

    # --------------------------------------------------------- emergency stop
    def engage_stop(self, actor: Actor, switch: StopSwitch, reason: str) -> None:
        require(actor, Perm.ENGAGE_EMERGENCY_STOP)
        self.stops.add(switch)
        self._log(actor, "emergency_stop_engaged", switch, reason=reason)
        self.notify(Severity.CRITICAL, "emergency_stop", f"{switch} stopped: {reason}", switch)

    def release_stop(self, actor: Actor, switch: StopSwitch) -> None:
        require(actor, Perm.RELEASE_EMERGENCY_STOP)
        self.stops.discard(switch)
        self._log(actor, "emergency_stop_released", switch)

    # --------------------------------------------------------- approvals
    def request_approval(self, actor: Actor, scope: ApprovalScope, subject_id: str, subject_version: int,
                         summary: str, channel: Channel | None = None, amount_limit: Decimal | None = None
                         ) -> ApprovalRequest:
        require(actor, Perm.REQUEST_APPROVAL)
        open_ = self._find_approval(scope, subject_id, subject_version, channel, {ApprovalStatus.PENDING})
        if open_:
            return open_
        a = ApprovalRequest(self.store.new_id("apr"), scope, subject_id, subject_version, summary, actor.id,
                            self._now(), channel, amount_limit)
        self.store.add("approvals", a)
        self._log(actor, "approval_requested", subject_id, approval=a.id, scope=scope, version=subject_version,
                  channel=channel, amount_limit=amount_limit)
        return a

    def decide(self, actor: Actor, approval_id: str, grant: bool, note: str = "") -> ApprovalRequest:
        require(actor, Perm.DECIDE_APPROVAL)
        a = self.store.get("approvals", approval_id)
        if a.status is not ApprovalStatus.PENDING:
            raise GateBlocked("decide", [f"approval {a.id} is {a.status}"])
        a.status = ApprovalStatus.GRANTED if grant else ApprovalStatus.DENIED
        a.decided_by, a.decided_at, a.note = actor.id, self._now(), note
        self._log(actor, "approval_decided", a.subject_id, approval=a.id, scope=a.scope, granted=grant,
                  version=a.subject_version, channel=a.channel, amount_limit=a.amount_limit, note=note)
        return a

    def _find_approval(self, scope, subject_id, version, channel=None, statuses=frozenset({ApprovalStatus.GRANTED})):
        hits = self.store.where("approvals", lambda a: a.scope is scope and a.subject_id == subject_id
                                and a.subject_version == version and a.channel == channel and a.status in statuses)
        return hits[-1] if hits else None

    def _consume(self, actor: Actor, a: ApprovalRequest) -> None:
        if a.scope in SINGLE_USE_SCOPES:
            a.status = ApprovalStatus.CONSUMED
            self._log(actor, "approval_consumed", a.subject_id, approval=a.id)

    # --------------------------------------------------------- discovery (Agent B)
    REQUIRED_CANDIDATE_FIELDS = ("name", "category", "intended_customer", "specifications", "demand_evidence",
                                 "competition_evidence", "indicative_price_low", "indicative_price_high",
                                 "supplier_leads", "risks", "confidence", "recommended_action")

    def propose_candidate(self, actor: Actor, cand: ProductCandidate) -> Product:
        require(actor, Perm.PROPOSE_PRODUCT)
        missing = [f for f in self.REQUIRED_CANDIDATE_FIELDS if not getattr(cand, f)]
        if missing:
            raise GateBlocked("propose_candidate", [f"recommendation incomplete: {', '.join(missing)}"])
        key = normalize(f"{cand.name} {cand.category}")
        existing = self.store.lookup("product_key", (key,))
        if existing:
            raise UniqueViolation(f"duplicate of {existing}")
        cand.id, cand.created_by, cand.created_at = self.store.new_id("cand"), actor.id, self._now()
        self.store.add("candidates", cand)
        p = Product(self.store.new_id("prd"), cand.id, cand.name, key, cand.category, ProductStatus.DISCOVERED,
                    branded=cand.branded, brand=cand.brand, created_at=self._now(), updated_at=self._now())
        self.store.add("products", p, unique={"product_key": (key,)})
        self._log(actor, "product_discovered", p.id, candidate=cand.id, name=cand.name,
                  sources=[e.reference for e in cand.demand_evidence + cand.competition_evidence])
        return p

    def material_change(self, actor: Actor, product_id: str, reason: str, **changes) -> Product:
        """Cost, price, supplier or specification changes bump the version, so earlier approvals no longer apply."""
        require(actor, Perm.ADVANCE_LIFECYCLE)
        p = self.product(product_id)
        if p.status in (ProductStatus.RETIRED, ProductStatus.REJECTED):
            raise GateBlocked("material_change", [f"product is {p.status}"])
        for k, v in changes.items():
            setattr(p, k, v)
        p.version += 1
        p.updated_at = self._now()
        for a in self.store.where("approvals", lambda a: a.subject_id == p.id and a.status in
                                  (ApprovalStatus.GRANTED, ApprovalStatus.PENDING) and a.subject_version < p.version):
            a.status = ApprovalStatus.SUPERSEDED
        self._log(actor, "product_material_change", p.id, version=p.version, reason=reason,
                  changes={k: str(v) for k, v in changes.items()})
        if p.status is ProductStatus.LIVE:
            self._pause_product(actor, p, f"material change: {reason}; re-approval required")
        elif p.status not in PRE_APPROVAL and p.status is not ProductStatus.PAUSED:
            p.status = ProductStatus.FINANCIAL_REVIEW
            self._log(actor, "product_transition", p.id, to=p.status, reason="re-review after material change")
        return p

    def product(self, product_id: str) -> Product:
        return self.store.get("products", product_id)

    # --------------------------------------------------------- suppliers (Agent C)
    def add_supplier(self, actor: Actor, s: Supplier) -> Supplier:
        require(actor, Perm.RECORD_SUPPLIER)
        s.id, s.created_at = self.store.new_id("sup"), self._now()
        self.store.add("suppliers", s, unique={"supplier_gstin": (s.gstin,)} if s.gstin else None)
        self._log(actor, "supplier_added", s.id, kind=s.kind)
        return s

    def record_supplier_verification(self, actor: Actor, supplier_id: str, checks: dict[str, CheckResult],
                                     evidence: dict[str, Evidence], valid_days: int = 180) -> SupplierVerification:
        require(actor, Perm.RECORD_VERIFICATION)
        s = self.store.get("suppliers", supplier_id)
        missing = [c for c in SUPPLIER_CHECKS if c not in checks]
        no_evidence = [c for c, r in checks.items() if r is CheckResult.PASS and c not in evidence]
        failed = [c for c, r in checks.items() if r is CheckResult.FAIL]
        if missing or no_evidence:
            status = VerificationStatus.IN_PROGRESS
        elif failed or not s.supports_third_party_fulfillment:
            status = VerificationStatus.FAILED
        elif all(r in (CheckResult.PASS, CheckResult.NOT_APPLICABLE) for r in checks.values()):
            status = VerificationStatus.VERIFIED
        else:
            status = VerificationStatus.IN_PROGRESS
        v = SupplierVerification(self.store.new_id("sver"), supplier_id, checks, evidence, status, actor.id,
                                 self._now(), self._now() + timedelta(days=valid_days))
        self.store.add("supplier_verifications", v)
        s.verification_status = status
        self._log(actor, "supplier_verification", supplier_id, status=status, failed=failed, missing=missing,
                  unevidenced=no_evidence, evidence={k: e.reference for k, e in evidence.items()})
        return v

    def supplier_verified(self, supplier_id: str) -> bool:
        vs = self.store.where("supplier_verifications", lambda v: v.supplier_id == supplier_id)
        return bool(vs) and vs[-1].status is VerificationStatus.VERIFIED and \
            (vs[-1].expires_at is None or vs[-1].expires_at > self._now())

    def record_quotation(self, actor: Actor, q: SupplierQuotation) -> SupplierQuotation:
        require(actor, Perm.RECORD_QUOTATION)
        prev = self.store.where("quotations", lambda o: o.supplier_id == q.supplier_id and o.sku == q.sku and o.active)
        for o in prev:
            o.active = False
        q.id = self.store.new_id("quo")
        q.version = (prev[-1].version + 1) if prev else 1
        q.supersedes_id = prev[-1].id if prev else None
        self.store.add("quotations", q, unique={"quotation_version": (q.supplier_id, q.sku, q.version)})
        self._log(actor, "quotation_recorded", q.product_id, quotation=q.id, version=q.version,
                  unit_cost=q.unit_cost_excl_gst, evidence=q.evidence.reference)
        return q

    def select_supplier(self, actor: Actor, product_id: str, quotation_id: str) -> None:
        require(actor, Perm.RECORD_QUOTATION)
        p, q = self.product(product_id), self.store.get("quotations", quotation_id)
        p.selected_supplier_id, p.selected_quotation_id = q.supplier_id, q.id
        self._log(actor, "supplier_selected", p.id, supplier=q.supplier_id, quotation=q.id)

    def record_agreement(self, actor: Actor, product_id: str, terms: dict, signed: Evidence | None) -> SupplierAgreement:
        require(actor, Perm.RECORD_AGREEMENT)
        p = self.product(product_id)
        q = self.store.get("quotations", p.selected_quotation_id)
        appr = self._find_approval(ApprovalScope.SUPPLIER_TERMS, q.id, q.version)
        if not appr:
            raise GateBlocked("record_agreement", ["owner has not approved these supplier terms"])
        prev = self.store.where("agreements", lambda a: a.supplier_id == q.supplier_id and a.product_id == p.id)
        ag = SupplierAgreement(self.store.new_id("agr"), q.supplier_id, q.id, p.id, len(prev) + 1, terms, appr.id,
                               signed, self._now())
        self.store.add("agreements", ag, unique={"agreement_version": (q.supplier_id, p.id, ag.version)})
        self._log(actor, "supplier_agreement_recorded", p.id, agreement=ag.id, version=ag.version, approval=appr.id,
                  terms=terms)
        return ag

    def record_inventory(self, actor: Actor, supplier_id: str, sku: str, qty: int, source: str) -> None:
        require(actor, Perm.RECORD_INVENTORY)
        self.store.add("inventory", SupplierInventorySnapshot(self.store.new_id("inv"), supplier_id, sku, qty,
                                                             self._now(), source))

    def latest_inventory(self, supplier_id: str, sku: str) -> SupplierInventorySnapshot | None:
        snaps = self.store.where("inventory", lambda s: s.supplier_id == supplier_id and s.sku == sku)
        return snaps[-1] if snaps else None

    # --------------------------------------------------------- economics (Agent D / I)
    def estimate(self, actor: Actor, product_id: str, channel: Channel, inputs: econ.CostInputs) -> CostEstimate:
        require(actor, Perm.CALCULATE_ECONOMICS)
        p = self.product(product_id)
        rep = econ.evaluate(inputs, self.fees(channel), self.thresholds, self.scenarios)
        ce = CostEstimate(self.store.new_id("est"), p.id, p.version, channel, inputs.selling_price_incl_gst, rep,
                          actor.id, self._now())
        self.store.add("estimates", ce)
        self._log(actor, "economics_estimated", p.id, channel=channel, version=p.version, status=rep.status,
                  expected=str(rep.scenarios["base"].expected_contribution) if rep.scenarios else None,
                  reasons=rep.reasons)
        if rep.status != "PASS":
            self.notify(Severity.MEDIUM, "economics_fail", f"{p.name} on {channel}: {'; '.join(rep.reasons)}", p.id)
        return ce

    def latest_estimate(self, product: Product, channel: Channel) -> CostEstimate | None:
        es = self.store.where("estimates", lambda e: e.product_id == product.id and e.channel == channel
                              and e.product_version == product.version)
        return es[-1] if es else None

    # --------------------------------------------------------- compliance (Agent M)
    def required_checks(self, p: Product) -> list[str]:
        c = self.config["compliance"]
        return list(dict.fromkeys(c.get("all", []) + (c.get("branded", []) if p.branded else [])
                                  + c.get(p.category, [])))

    def record_compliance(self, actor: Actor, product_id: str, check_type: str, result: CheckResult,
                          evidence: list[Evidence], policy_version: str, notes: str = "") -> ComplianceCheck:
        require(actor, Perm.RECORD_COMPLIANCE)
        p = self.product(product_id)
        if result is CheckResult.PASS and not evidence:
            raise GateBlocked("record_compliance", ["a PASS needs evidence"])
        cc = ComplianceCheck(self.store.new_id("cmp"), p.id, p.version, check_type, result, evidence, policy_version,
                             actor.id, self._now(), notes)
        self.store.add("compliance", cc)
        self._log(actor, "compliance_check", p.id, check=check_type, result=result, policy_version=policy_version,
                  evidence=[e.reference for e in evidence])
        return cc

    def record_fulfillment_arrangement(self, actor: Actor, product_id: str, channel: Channel, method: str,
                                       checks: dict[str, bool], evidence: list[Evidence]) -> FulfillmentArrangement:
        require(actor, Perm.RECORD_FULFILLMENT_ARRANGEMENT)
        ok = all(checks.get(c) for c in FULFILLMENT_CHECKS) and bool(evidence)
        fa = FulfillmentArrangement(self.store.new_id("ful"), product_id, channel, method, checks, evidence, ok,
                                    actor.id, self._now())
        self.store.add("fulfillment_arrangements", fa)
        self._log(actor, "fulfillment_arrangement", product_id, channel=channel, method=method, verified=ok,
                  failing=[c for c in FULFILLMENT_CHECKS if not checks.get(c)])
        return fa

    def fulfillment_ok(self, product_id: str, channel: Channel) -> bool:
        fa = self.store.where("fulfillment_arrangements", lambda f: f.product_id == product_id and f.channel == channel)
        return bool(fa) and fa[-1].verified

    def record_test_run(self, actor: Actor, product_id: str, suite: str,
                        results: list[tuple[str, bool, Severity]]) -> TestRun:
        require(actor, Perm.RECORD_TEST_RUN)
        p = self.product(product_id)
        tr = TestRun(self.store.new_id("tst"), p.id, p.version, suite, results, self._now())
        self.store.add("test_runs", tr)
        self._log(actor, "test_run", p.id, suite=suite, critical_failures=tr.critical_failures,
                  passed=sum(ok for _, ok, _ in results), total=len(results))
        return tr

    # --------------------------------------------------------- lifecycle (Agent A enforces)
    def _preconditions(self, p: Product, to: ProductStatus) -> list[str]:
        r: list[str] = []
        if to is ProductStatus.UNDER_REVIEW:
            cand = self.store.get("candidates", p.candidate_id)
            if not cand.demand_evidence:
                r.append("no demand evidence")
        elif to is ProductStatus.SUPPLIER_VERIFICATION:
            if not self.store.get("candidates", p.candidate_id).supplier_leads:
                r.append("no supplier leads")
        elif to is ProductStatus.FINANCIAL_REVIEW:
            if not p.selected_quotation_id:
                r.append("no supplier quotation selected")
            elif not self.supplier_verified(p.selected_supplier_id):
                r.append("selected supplier is not verified")
            else:
                q = self.store.get("quotations", p.selected_quotation_id)
                if not q.active or q.valid_until < self._now():
                    r.append("quotation inactive or expired")
        elif to is ProductStatus.OWNER_APPROVED:
            r += self._preconditions(p, ProductStatus.FINANCIAL_REVIEW)
            passing = [c for c in Channel if (e := self.latest_estimate(p, c)) and e.result.status == "PASS"]
            if not passing:
                r.append("no channel meets the profit thresholds for this product version")
            if not self._find_approval(ApprovalScope.PRODUCT_OPPORTUNITY, p.id, p.version):
                r.append(f"owner has not approved product opportunity v{p.version}")
            if p.selected_quotation_id:
                q = self.store.get("quotations", p.selected_quotation_id)
                if not self._find_approval(ApprovalScope.SUPPLIER_TERMS, q.id, q.version):
                    r.append("owner has not approved the selected supplier terms")
        elif to is ProductStatus.PRODUCT_ONBOARDING:
            if not self.store.where("agreements", lambda a: a.product_id == p.id
                                    and a.quotation_id == p.selected_quotation_id):
                r.append("no supplier agreement for the selected quotation")
        elif to is ProductStatus.COMPLIANCE_APPROVED:
            checks = {c.check_type: c for c in self.store.where("compliance", lambda c: c.product_id == p.id
                                                                 and c.product_version == p.version)}
            for need in self.required_checks(p):
                c = checks.get(need)
                if not c or c.result not in (CheckResult.PASS, CheckResult.NOT_APPLICABLE):
                    r.append(f"compliance {need}: {c.result if c else 'not done'}")
            if not p.hsn_code or p.gst_pct is None:
                r.append("HSN code / GST rate not set")
        elif to is ProductStatus.READY_FOR_TESTING:
            if not self.store.where("listings", lambda l: l.product_id == p.id and l.status is ListingStatus.VALIDATED):
                r.append("no channel listing with validated content")
        elif to is ProductStatus.READY_TO_PUBLISH:
            runs = self.store.where("test_runs", lambda t: t.product_id == p.id and t.product_version == p.version)
            if not runs:
                r.append("no test run for this product version")
            elif runs[-1].critical_failures:
                r.append(f"critical test failures: {runs[-1].critical_failures}")
        elif to is ProductStatus.LIVE:
            if not self.store.where("listings", lambda l: l.product_id == p.id and l.status is ListingStatus.PUBLISHED):
                r.append("no published listing")
        return r

    def advance(self, actor: Actor, product_id: str, to: ProductStatus, reason: str = "") -> Product:
        require(actor, Perm.ADVANCE_LIFECYCLE)
        p = self.product(product_id)
        if to not in TRANSITIONS[p.status]:
            reasons = [f"{p.status} -> {to} is not an allowed transition"]
        else:
            reasons = self._preconditions(p, to)
        if reasons:
            self._log(actor, "transition_blocked", p.id, frm=p.status, to=to, reasons=reasons)
            raise GateBlocked(f"{p.status}->{to}", reasons)
        frm, p.status, p.updated_at = p.status, to, self._now()
        self._log(actor, "product_transition", p.id, frm=frm, to=to, version=p.version, reason=reason)
        if to in (ProductStatus.RETIRED, ProductStatus.REJECTED):
            for l in self.store.where("listings", lambda l: l.product_id == p.id and l.status is ListingStatus.PUBLISHED):
                self._adapter_call(actor, "pause", l.id, lambda l=l: self.adapters[l.channel].pause_listing(l))
                l.status = ListingStatus.WITHDRAWN
        return p

    def _pause_product(self, actor: Actor, p: Product, reason: str) -> None:
        for l in self.store.where("listings", lambda l: l.product_id == p.id and l.status is ListingStatus.PUBLISHED):
            self._adapter_call(actor, "pause", l.id, lambda l=l: self.adapters[l.channel].pause_listing(l))
            l.status = ListingStatus.PAUSED
            self._log(actor, "listing_paused", l.id, reason=reason)
        if p.status is ProductStatus.LIVE:
            p.status = ProductStatus.PAUSED
            self._log(actor, "product_transition", p.id, frm=ProductStatus.LIVE, to=ProductStatus.PAUSED, reason=reason)
        self.notify(Severity.HIGH, "product_paused", f"{p.name}: {reason}", p.id)

    # --------------------------------------------------------- listings (Agents G/H/I, F)
    def create_listing(self, actor: Actor, product_id: str, channel: Channel, sku: str, price: Decimal,
                       attributes: dict) -> ChannelListing:
        require(actor, Perm.EDIT_CONTENT)
        p = self.product(product_id)
        l = ChannelListing(self.store.new_id("lst"), p.id, channel, sku, price, attributes, product_version=p.version)
        self.store.add("listings", l, unique={"listing_channel_sku": (channel, sku)})
        self._log(actor, "listing_created", l.id, product=p.id, channel=channel, price=price)
        return l

    def validate_listing(self, actor: Actor, listing_id: str) -> ChannelListing:
        require(actor, Perm.EDIT_CONTENT)
        l = self.store.get("listings", listing_id)
        req = self.config["channels"][l.channel].get("required_attributes", [])
        l.validation_errors = [f"missing {a}" for a in req if not l.attributes.get(a)]
        if not l.validation_errors:
            l.status = ListingStatus.VALIDATED
        self._log(actor, "listing_validated", l.id, errors=l.validation_errors)
        return l

    def publish(self, actor: Actor, listing_id: str) -> ChannelListing:
        require(actor, Perm.PUBLISH_LISTING)
        l = self.store.get("listings", listing_id)
        p = self.product(l.product_id)
        r: list[str] = []
        if StopSwitch.PUBLISHING in self.stops:
            r.append("emergency stop: publishing is paused")
        if p.status not in (ProductStatus.READY_TO_PUBLISH, ProductStatus.LIVE, ProductStatus.PAUSED):
            r.append(f"product status is {p.status}")
        if l.status not in (ListingStatus.VALIDATED, ListingStatus.PAUSED):
            r.append(f"listing status is {l.status}")
        if l.product_version != p.version:
            r.append("listing content was made for an older product version")
        if not self._find_approval(ApprovalScope.CHANNEL_PUBLICATION, p.id, p.version, l.channel):
            r.append(f"owner has not approved publication on {l.channel} for v{p.version}")
        if not self.fulfillment_ok(p.id, l.channel):
            r.append(f"no verified fulfilment arrangement for {l.channel}")
        est = self.latest_estimate(p, l.channel)
        if not est or est.price_incl_gst != l.price_incl_gst:
            r.append("no profitability estimate at this listing price")
        elif not est.result.gate_open:
            r.append("profitability gate closed: " + "; ".join(est.result.reasons))
        adapter = self.adapters.get(l.channel)
        if adapter is None or adapter.status is IntegrationStatus.UNAVAILABLE:
            r.append(f"{l.channel} integration unavailable")
        if r:
            self._log(actor, "publish_blocked", l.id, reasons=r)
            raise GateBlocked("publish", r)
        ext = self._adapter_call(actor, "publish", l.id, lambda: adapter.publish_listing(l, p))
        if adapter.status is IntegrationStatus.MANUAL:
            l.status = ListingStatus.AWAITING_MANUAL_UPLOAD
        else:
            l.status, l.external_id, l.published_at = ListingStatus.PUBLISHED, ext, self._now()
            if p.status in (ProductStatus.READY_TO_PUBLISH, ProductStatus.PAUSED):
                self.advance(Actor("orchestrator", Role.ORCHESTRATOR), p.id, ProductStatus.LIVE, "listing published")
        self._log(actor, "listing_published", l.id, channel=l.channel, external_id=ext, status=l.status,
                  integration=adapter.status)
        return l

    def confirm_manual_upload(self, actor: Actor, listing_id: str, external_id: str) -> ChannelListing:
        require(actor, Perm.CONFIRM_MANUAL_UPLOAD)
        l = self.store.get("listings", listing_id)
        if l.status is not ListingStatus.AWAITING_MANUAL_UPLOAD:
            raise GateBlocked("confirm_manual_upload", [f"listing is {l.status}"])
        l.status, l.external_id, l.published_at = ListingStatus.PUBLISHED, external_id, self._now()
        p = self.product(l.product_id)
        if p.status is ProductStatus.READY_TO_PUBLISH:
            self.advance(Actor("orchestrator", Role.ORCHESTRATOR), p.id, ProductStatus.LIVE, "manual upload confirmed")
        self._log(actor, "manual_upload_confirmed", l.id, external_id=external_id)
        return l

    def check_margins(self, actor: Actor, actual: dict[str, econ.CostInputs]) -> list[str]:
        """Re-run economics on live listings with actual costs. Breaches alert, and pause if configured."""
        require(actor, Perm.PAUSE_LISTING)
        breached = []
        for lid, inputs in actual.items():
            l = self.store.get("listings", lid)
            rep = econ.evaluate(inputs, self.fees(l.channel), self.thresholds, self.scenarios)
            if rep.status != "PASS":
                breached.append(lid)
                self._log(actor, "margin_breach", l.id, reasons=rep.reasons)
                self.notify(Severity.HIGH, "margin_breach", f"{l.sku} on {l.channel}: {'; '.join(rep.reasons)}", l.id)
                if self.ops.get("auto_pause_on_margin_breach") and l.status is ListingStatus.PUBLISHED:
                    self._adapter_call(actor, "pause", l.id, lambda l=l: self.adapters[l.channel].pause_listing(l))
                    l.status = ListingStatus.PAUSED
                    self._log(actor, "listing_paused", l.id, reason="margin breach")
        return breached

