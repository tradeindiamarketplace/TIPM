"""Order-to-cash operations (Agents J, L, D, H) and orchestration (Agent A). Mixed into Platform."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from .channels import AdapterError
from .domain import *  # noqa: F403
from .gates import GateBlocked
from .permissions import Actor, Perm, Role, require

AGENT_FOR_TASK = {
    "verify_supplier": Role.SUPPLIER_SOURCING, "estimate_economics": Role.FINANCE,
    "compliance_review": Role.COMPLIANCE, "write_content": Role.DESIGN, "run_tests": Role.QA,
    "resolve_order": Role.FULFILLMENT, "support_case": Role.SUPPORT, "owner_decision": Role.OWNER,
    "integration_failure": Role.DEVELOPER, "campaign_review": Role.MARKETING, "pricing_review": Role.PRICING,
}


class SimulatedSupplierGateway:
    """Stands in for supplier email/portal/API in tests. Records POs; responses come back via the platform."""

    def __init__(self):
        self.received: dict[str, SupplierPurchaseOrder] = {}
        self.cancelled: list[str] = []
        self._fail_next = 0

    def fail_next(self, n: int) -> None:
        self._fail_next = n

    def submit_po(self, po: SupplierPurchaseOrder) -> None:
        if self._fail_next:
            self._fail_next -= 1
            raise AdapterError("supplier endpoint timeout")
        self.received.setdefault(po.idempotency_key, po)   # idempotent by key

    def cancel_po(self, po: SupplierPurchaseOrder) -> None:
        self.cancelled.append(po.id)


class OperationsMixin:
    # ------------------------------------------------------------- tasks (Agent A)
    def create_task(self, actor: Actor, kind: str, subject_id: str, depends_on: list[str] | None = None,
                    due_in_hours: int | None = None) -> AgentTask:
        require(actor, Perm.MANAGE_TASKS) if actor.role is not Role.SYSTEM else None
        dup = self.store.where("tasks", lambda t: t.kind == kind and t.subject_id == subject_id
                               and t.status in ("OPEN", "IN_PROGRESS", "BLOCKED"))
        if dup:
            return dup[0]
        t = AgentTask(self.store.new_id("tsk"), AGENT_FOR_TASK.get(kind, Role.ORCHESTRATOR), kind, subject_id,
                      "OPEN", self._now(), depends_on or [],
                      self._now() + timedelta(hours=due_in_hours) if due_in_hours else None)
        self.store.add("tasks", t)
        self._log(actor, "task_created", subject_id, task=t.id, kind=kind, agent=t.agent)
        return t

    def complete_task(self, actor: Actor, task_id: str, result: str) -> AgentTask:
        t = self.store.get("tasks", task_id)
        if actor.role is not t.agent and not actor.is_owner:
            raise GateBlocked("complete_task", [f"{actor.role} cannot complete a {t.agent} task"])
        blockers = [d for d in t.depends_on if self.store.get("tasks", d).status != "DONE"]
        if blockers:
            raise GateBlocked("complete_task", [f"waiting on {blockers}"])
        t.status, t.result = "DONE", result
        self._log(actor, "task_done", t.subject_id, task=t.id, result=result)
        return t

    def daily_summary(self) -> dict:
        s = self.store
        now = self._now()
        products = s.all("products")
        return {
            "as_of": now.isoformat(),
            "products_by_status": {st: sum(p.status is st for p in products) for st in ProductStatus},
            "pending_approvals": [(a.id, a.scope, a.summary) for a in s.all("approvals")
                                  if a.status is ApprovalStatus.PENDING],
            "suppliers": {v: sum(x.verification_status is v for x in s.all("suppliers")) for v in VerificationStatus},
            "live_listings_by_channel": {c: sum(l.channel == c and l.status is ListingStatus.PUBLISHED
                                                for l in s.all("listings")) for c in Channel},
            "integration_status": {c: getattr(a, "status", "missing") for c, a in self.adapters.items()},
            "orders_by_status": {st: sum(o.status is st for o in s.all("orders")) for st in OrderStatus},
            "open_tasks": [(t.id, t.agent, t.kind, t.subject_id) for t in s.all("tasks") if t.status != "DONE"],
            "overdue_tasks": [t.id for t in s.all("tasks") if t.status != "DONE" and t.due_by and t.due_by < now],
            "failed_jobs": len(self.dead_letters),
            "emergency_stops": sorted(self.stops),
            "exceptions": [(n.severity, n.kind, n.message) for n in s.all("notifications")
                           if n.severity in (Severity.HIGH, Severity.CRITICAL)
                           and n.created_at > now - timedelta(days=1)],
        }

    # ------------------------------------------------------------- orders (Agent J)
    def import_order(self, actor: Actor, channel: Channel, external_order_id: str, lines: list[OrderLine],
                     ship_to_ref: str, ship_to_pincode: str, idempotency_key: str) -> CustomerOrder:
        require(actor, Perm.IMPORT_ORDER)
        if idempotency_key in self.store.idempotency:
            existing = self.store.get("orders", self.store.idempotency[idempotency_key])
            self._log(actor, "duplicate_webhook_ignored", existing.id, key=idempotency_key)
            return existing
        same = self.store.lookup("order_channel_ext", (channel, external_order_id))
        if same:
            self.store.idempotency[idempotency_key] = same
            self._log(actor, "duplicate_order_ignored", same, external_order_id=external_order_id)
            return self.store.get("orders", same)
        o = CustomerOrder(self.store.new_id("ord"), channel, external_order_id, lines, OrderStatus.IMPORTED,
                          ship_to_ref, ship_to_pincode, self._now())
        self.store.add("orders", o, unique={"order_channel_ext": (channel, external_order_id)})
        self.store.idempotency[idempotency_key] = o.id
        self._log(actor, "order_imported", o.id, channel=channel, external_order_id=external_order_id,
                  lines=[(l.sku, l.qty, str(l.unit_price_incl_gst)) for l in lines])
        self.route_order(actor if actor.role is Role.SYSTEM else Actor("system", Role.SYSTEM), o.id)
        return o

    def _listing_for(self, channel: Channel, sku: str) -> ChannelListing | None:
        lid = self.store.lookup("listing_channel_sku", (channel, sku))
        return self.store.get("listings", lid) if lid else None

    def _hold(self, actor: Actor, o: CustomerOrder, reason: str, severity=Severity.HIGH) -> CustomerOrder:
        o.status = OrderStatus.NEEDS_ATTENTION
        o.notes.append(reason)
        self._log(actor, "order_on_hold", o.id, reason=reason)
        self.notify(severity, "order_on_hold", f"{o.channel} {o.external_order_id}: {reason}", o.id)
        self.create_task(actor, "resolve_order", o.id, due_in_hours=4)
        return o

    def route_order(self, actor: Actor, order_id: str, approval_id: str | None = None) -> CustomerOrder:
        """Check stock and authorisation, then send one PO to the supplier. Never confirms to the customer here."""
        require(actor, Perm.SUBMIT_SUPPLIER_PO)
        o = self.store.get("orders", order_id)
        if o.status not in (OrderStatus.IMPORTED, OrderStatus.NEEDS_ATTENTION):
            return o
        if StopSwitch.SUPPLIER_ORDERS in self.stops:
            return self._hold(actor, o, "emergency stop: supplier orders paused")
        max_age = timedelta(hours=self.ops["inventory_snapshot_max_age_hours"])
        by_supplier: dict[str, list[tuple[OrderLine, SupplierQuotation]]] = {}
        for line in o.lines:
            l = self._listing_for(o.channel, line.sku)
            if not l or l.status is not ListingStatus.PUBLISHED:
                return self._hold(actor, o, f"{line.sku} is not a published listing on {o.channel}")
            p = self.product(l.product_id)
            if p.status is not ProductStatus.LIVE:
                return self._hold(actor, o, f"{p.name} is {p.status}")
            q = self.store.get("quotations", p.selected_quotation_id)
            snap = self.latest_inventory(q.supplier_id, q.sku)
            if not snap or self._now() - snap.captured_at > max_age:
                return self._hold(actor, o, f"supplier stock for {q.sku} is unknown or stale")
            if snap.available_qty < line.qty:
                return self._hold(actor, o, f"supplier has {snap.available_qty} of {q.sku}, order needs {line.qty}")
            if not self.supplier_verified(q.supplier_id):
                return self._hold(actor, o, "supplier verification lapsed")
            by_supplier.setdefault(q.supplier_id, []).append((line, q))

        for supplier_id, items in by_supplier.items():
            key = f"po:{o.id}:{supplier_id}"
            if self.store.lookup("po_idem", (key,)):
                continue
            amount = sum(q.unit_cost_excl_gst * (1 + q.gst_pct / 100) * ln.qty for ln, q in items)
            approval = None
            today = self._now().date()
            spent_today = sum(po.amount_incl_gst for po in self.store.all("pos")
                              if po.submitted_at.date() == today and po.status is not POStatus.CANCELLED
                              and po.approval_id is None)
            over = amount > Decimal(self.ops["per_po_cap_inr"]) or \
                spent_today + amount > Decimal(self.ops["daily_po_cap_inr"])
            if over:
                approval = self._find_approval(ApprovalScope.PURCHASE_COMMITMENT, o.id, 1)
                if not approval or (approval.amount_limit is not None and amount > approval.amount_limit):
                    self.request_approval(Actor("agent_j", Role.FULFILLMENT), ApprovalScope.PURCHASE_COMMITMENT,
                                          o.id, 1, f"Supplier PO Rs {amount:.2f} for {o.external_order_id} exceeds "
                                          "standing authorisation", amount_limit=amount)
                    return self._hold(actor, o, f"PO Rs {amount:.2f} needs owner approval (above cap)")
            po = SupplierPurchaseOrder(self.store.new_id("po"), o.id, supplier_id, items[0][1].id,
                                       [ln for ln, _ in items], amount.quantize(Decimal("0.01")), key,
                                       POStatus.SUBMITTED, self._now(), approval.id if approval else None)
            try:
                self._adapter_call(actor, "submit_po", o.id, lambda po=po: self.suppliers_gw.submit_po(po))
            except AdapterError:
                return self._hold(actor, o, "could not reach supplier; PO not sent, will retry")
            self.store.add("pos", po, unique={"po_idem": (key,)})
            if approval:
                self._consume(actor, approval)
            self._log(actor, "supplier_po_submitted", o.id, po=po.id, supplier=supplier_id, amount=str(po.amount_incl_gst),
                      authorisation=approval.id if approval else "standing (agreement + caps)")
        o.status = OrderStatus.AWAITING_SUPPLIER
        self._log(actor, "order_awaiting_supplier", o.id)
        return o

    def record_supplier_response(self, actor: Actor, po_id: str, accepted: bool,
                                 confirmed_dispatch_by=None, reason: str = "") -> SupplierPurchaseOrder:
        require(actor, Perm.SUBMIT_SUPPLIER_PO)
        po = self.store.get("pos", po_id)
        o = self.store.get("orders", po.order_id)
        if po.status is not POStatus.SUBMITTED:
            return po
        if accepted:
            if confirmed_dispatch_by is None:
                raise GateBlocked("supplier_accept", ["acceptance must carry the supplier's confirmed dispatch time"])
            po.status, po.confirmed_dispatch_by = POStatus.ACCEPTED, confirmed_dispatch_by
            o.status, o.dispatch_by = OrderStatus.SUPPLIER_ACCEPTED, confirmed_dispatch_by
            self._adapter_call(actor, "ack", o.id, lambda: self.adapters[o.channel].acknowledge_order(o))
            self._log(actor, "supplier_accepted", o.id, po=po.id, dispatch_by=confirmed_dispatch_by.isoformat())
        else:
            po.status, po.rejection_reason = POStatus.REJECTED, reason
            self.store.release("po_idem", (po.idempotency_key,))
            self._log(actor, "supplier_rejected", o.id, po=po.id, reason=reason)
            self._hold(actor, o, f"supplier rejected PO: {reason}")
        return po

    def record_carrier_event(self, actor: Actor, po_id: str, carrier: str, tracking_number: str,
                             event_code: str, evidence: Evidence) -> Shipment:
        """Shipped/delivered states only move on carrier evidence with a tracking number."""
        require(actor, Perm.RECORD_SHIPMENT_EVENT)
        po = self.store.get("pos", po_id)
        o = self.store.get("orders", po.order_id)
        if not tracking_number or not carrier or evidence.kind not in ("carrier_api", "carrier_tracking_page"):
            raise GateBlocked("record_carrier_event", ["needs carrier, tracking number and carrier-sourced evidence"])
        ships = self.store.where("shipments", lambda s: s.po_id == po.id)
        if event_code in ("PICKED_UP", "IN_TRANSIT"):
            if ships:
                ships[0].events.append(evidence)
                return ships[0]
            sh = Shipment(self.store.new_id("shp"), o.id, po.id, carrier, tracking_number, ShipmentStatus.IN_TRANSIT,
                          [evidence], evidence.captured_at)
            self.store.add("shipments", sh, unique={"tracking": (carrier, tracking_number)})
            po.status, o.status = POStatus.DISPATCHED, OrderStatus.DISPATCHED
            self._adapter_call(actor, "tracking", o.id, lambda: self.adapters[o.channel].push_tracking(o, sh))
            self._log(actor, "order_dispatched", o.id, carrier=carrier, tracking=tracking_number,
                      evidence=evidence.reference, late=bool(o.dispatch_by and evidence.captured_at > o.dispatch_by))
            return sh
        if event_code == "DELIVERED":
            if not ships:
                raise GateBlocked("record_carrier_event", ["delivery event without a dispatched shipment"])
            sh = ships[0]
            sh.events.append(evidence)
            sh.status, sh.delivered_at, o.status = ShipmentStatus.DELIVERED, evidence.captured_at, OrderStatus.DELIVERED
            po.status = POStatus.CLOSED
            self._log(actor, "order_delivered", o.id, evidence=evidence.reference)
            return sh
        if event_code in ("EXCEPTION", "RTO"):
            sh = ships[0]
            sh.events.append(evidence)
            sh.status = ShipmentStatus[event_code]
            self._hold(actor, o, f"carrier reported {event_code}")
            return sh
        raise GateBlocked("record_carrier_event", [f"unknown event {event_code}"])

    def check_slas(self, actor: Actor) -> list[str]:
        require(actor, Perm.MANAGE_TASKS)
        now, flagged = self._now(), []
        timeout = timedelta(hours=self.ops["supplier_response_timeout_hours"])
        delay = timedelta(days=self.ops["delivery_delay_alert_days"])
        for o in self.store.all("orders"):
            issue = None
            if o.status is OrderStatus.SUPPLIER_ACCEPTED and o.dispatch_by and now > o.dispatch_by:
                issue = "dispatch SLA missed"
            elif o.status is OrderStatus.AWAITING_SUPPLIER and now - o.created_at > timeout:
                issue = "supplier has not responded"
            elif o.status is OrderStatus.DISPATCHED:
                sh = self.store.where("shipments", lambda s: s.order_id == o.id)
                if sh and now - sh[0].dispatched_at > delay:
                    issue = "delivery delayed"
            if issue and not self.store.where("notifications", lambda n: n.subject_id == o.id and n.kind == issue):
                flagged.append(o.id)
                self._log(actor, "sla_breach", o.id, issue=issue)
                self.notify(Severity.HIGH, issue, f"{o.channel} {o.external_order_id}: {issue}", o.id)
                self.open_case(Actor("agent_l", Role.SUPPORT), o.id, "proactive_delay", Severity.HIGH)
        return flagged

    def cancel_order(self, actor: Actor, order_id: str, reason: str) -> CustomerOrder:
        require(actor, Perm.CANCEL_ORDER)
        o = self.store.get("orders", order_id)
        if o.status in (OrderStatus.DISPATCHED, OrderStatus.DELIVERED):
            raise GateBlocked("cancel_order", ["already dispatched; use the return flow"])
        if o.status is OrderStatus.CANCELLED:
            return o
        for po in self.store.where("pos", lambda p: p.order_id == o.id and p.status in
                                   (POStatus.SUBMITTED, POStatus.ACCEPTED)):
            self._adapter_call(actor, "cancel_po", po.id, lambda po=po: self.suppliers_gw.cancel_po(po))
            po.status = POStatus.CANCELLED
        self._adapter_call(actor, "cancel", o.id, lambda: self.adapters[o.channel].cancel_order(o, reason))
        o.status = OrderStatus.CANCELLED
        self._log(actor, "order_cancelled", o.id, reason=reason)
        return o

    # ------------------------------------------------------------- returns and refunds (Agents J, L)
    def request_return(self, actor: Actor, order_id: str, reason: str) -> ReturnRequest:
        require(actor, Perm.MANAGE_RETURN)
        o = self.store.get("orders", order_id)
        sh = self.store.where("shipments", lambda s: s.order_id == o.id and s.status is ShipmentStatus.DELIVERED)
        if not sh:
            raise GateBlocked("request_return", ["order has no confirmed delivery"])
        in_window = self._now() - sh[0].delivered_at <= timedelta(days=self.ops["return_window_days"])
        rr = ReturnRequest(self.store.new_id("ret"), o.id, reason,
                           ReturnStatus.APPROVED if in_window else ReturnStatus.REQUESTED, self._now())
        self.store.add("returns", rr, unique={"return_order": (o.id,)})
        o.status = OrderStatus.RETURN_REQUESTED
        self._log(actor, "return_requested", o.id, ret=rr.id, within_policy=in_window, reason=reason)
        if not in_window:
            self.create_task(actor, "support_case", o.id)
        return rr

    def receive_return(self, actor: Actor, return_id: str, evidence: Evidence, resellable: bool) -> ReturnRequest:
        require(actor, Perm.MANAGE_RETURN)
        rr = self.store.get("returns", return_id)
        if rr.status is not ReturnStatus.APPROVED:
            raise GateBlocked("receive_return", [f"return is {rr.status}"])
        o = self.store.get("orders", rr.order_id)
        po = self.store.where("pos", lambda p: p.order_id == o.id)[0]
        rr.status, rr.received_evidence = ReturnStatus.RECEIVED, evidence
        ag = self.store.where("agreements", lambda a: a.quotation_id == po.quotation_id)
        credit_pct = Decimal(str(ag[-1].terms.get("return_credit_pct", 0))) if ag and resellable else Decimal(0)
        rr.supplier_credit_expected = (po.amount_incl_gst * credit_pct / 100).quantize(Decimal("0.01"))
        o.status = OrderStatus.RETURNED
        self._log(actor, "return_received", o.id, ret=rr.id, evidence=evidence.reference, resellable=resellable,
                  supplier_credit_expected=str(rr.supplier_credit_expected))
        return rr

    def refund(self, actor: Actor, return_id: str, amount: Decimal, approval_id: str | None = None) -> Refund:
        require(actor, Perm.ISSUE_REFUND)
        rr = self.store.get("returns", return_id)
        o = self.store.get("orders", rr.order_id)
        paid = sum(l.unit_price_incl_gst * l.qty for l in o.lines)
        if rr.status is not ReturnStatus.RECEIVED:
            raise GateBlocked("refund", [f"return is {rr.status}"])
        if amount > paid:
            raise GateBlocked("refund", [f"refund {amount} exceeds amount paid {paid}"])
        if self.store.where("refunds", lambda r: r.return_id == rr.id):
            raise GateBlocked("refund", ["already refunded"])
        executed_by = "channel" if o.channel is not Channel.SHOPIFY else "own_gateway"
        if executed_by == "own_gateway" and amount > Decimal(self.ops["auto_refund_limit_inr"]):
            a = self.store.get("approvals", approval_id) if approval_id else None
            if not a or a.scope is not ApprovalScope.EXCEPTIONAL_REFUND or a.status is not ApprovalStatus.GRANTED \
                    or a.subject_id != o.id or (a.amount_limit is not None and amount > a.amount_limit):
                raise GateBlocked("refund", [f"refund {amount} above auto limit needs an owner-approved EXCEPTIONAL_REFUND"])
            self._consume(actor, a)
        rf = Refund(self.store.new_id("rfd"), o.id, rr.id, amount, executed_by, approval_id, self._now())
        self.store.add("refunds", rf)
        rr.status, o.status = ReturnStatus.REFUNDED, OrderStatus.REFUNDED
        self._log(actor, "refund_recorded", o.id, refund=rf.id, amount=str(amount), executed_by=executed_by,
                  approval=approval_id)
        return rf

    def record_supplier_credit(self, actor: Actor, return_id: str, amount: Decimal, evidence: Evidence) -> None:
        require(actor, Perm.RECONCILE_SETTLEMENT)
        rr = self.store.get("returns", return_id)
        rr.supplier_credit_received += amount
        self._log(actor, "supplier_credit", rr.order_id, ret=rr.id, amount=str(amount), evidence=evidence.reference,
                  outstanding=str(rr.supplier_credit_expected - rr.supplier_credit_received))

    # ------------------------------------------------------------- settlement (Agent D)
    def reconcile_settlement(self, actor: Actor, channel: Channel, period: str, lines: list[dict]) -> MarketplaceSettlement:
        """lines: {external_order_id, gross, commission, fixed_fee, payment_fee, tcs, tds, net}."""
        require(actor, Perm.RECONCILE_SETTLEMENT)
        fees = self.fees(channel)
        tol = Decimal(self.ops["settlement_tolerance_inr"])
        variances = []
        for ln in lines:
            gross = Decimal(str(ln["gross"]))
            oid = self.store.lookup("order_channel_ext", (channel, ln["external_order_id"]))
            if not oid:
                variances.append({"order": ln["external_order_id"], "issue": "settlement for unknown order"})
                continue
            o = self.store.get("orders", oid)
            expected_gross = sum(l.unit_price_incl_gst * l.qty for l in o.lines)
            gst = self.product(self._listing_for(channel, o.lines[0].sku).product_id).gst_pct or 0
            taxable = expected_gross / (1 + Decimal(gst) / 100)
            fee_ex = expected_gross * (fees.commission_pct or 0) / 100 + (fees.fixed_fee_inr or 0) \
                + expected_gross * ((fees.payment_fee_pct or 0) + (fees.platform_fee_pct or 0)) / 100
            exp = {"gross": expected_gross,
                   "fees_incl_gst": fee_ex * (1 + fees.fee_gst_pct / 100),
                   "tcs": taxable * fees.tcs_pct / 100, "tds": taxable * fees.tds_pct / 100}
            act = {"gross": gross,
                   "fees_incl_gst": sum(Decimal(str(ln.get(k, 0))) for k in ("commission", "fixed_fee", "payment_fee")),
                   "tcs": Decimal(str(ln.get("tcs", 0))), "tds": Decimal(str(ln.get("tds", 0)))}
            exp_net = exp["gross"] - exp["fees_incl_gst"] - exp["tcs"] - exp["tds"]
            for k in exp:
                if abs(exp[k] - act[k]) > tol:
                    variances.append({"order": ln["external_order_id"], "field": k,
                                      "expected": str(exp[k].quantize(Decimal("0.01"))), "actual": str(act[k])})
            if abs(exp_net - Decimal(str(ln["net"]))) > tol:
                variances.append({"order": ln["external_order_id"], "field": "net",
                                  "expected": str(exp_net.quantize(Decimal("0.01"))), "actual": str(ln["net"])})
        st = MarketplaceSettlement(self.store.new_id("stl"), channel, period, lines,
                                   "VARIANCE" if variances else "MATCHED", variances, self._now())
        self.store.add("settlements", st, unique={"settlement_period": (channel, period)})
        self._log(actor, "settlement_reconciled", st.id, channel=channel, period=period, status=st.status,
                  variances=len(variances))
        if variances:
            self.notify(Severity.MEDIUM, "settlement_variance", f"{channel} {period}: {len(variances)} variances", st.id)
        return st

    # ------------------------------------------------------------- support (Agent L)
    def order_view(self, actor: Actor, order_id: str) -> dict:
        """Only verified facts. No promise is made that a supplier or carrier has not confirmed."""
        require(actor, Perm.VIEW_ORDER)
        o = self.store.get("orders", order_id)
        sh = self.store.where("shipments", lambda s: s.order_id == o.id)
        rr = self.store.where("returns", lambda r: r.order_id == o.id)
        return {
            "order": o.external_order_id, "channel": o.channel, "status": o.status,
            "items": [(l.sku, l.qty) for l in o.lines],
            "dispatch_by": o.dispatch_by.isoformat() if o.dispatch_by else "not yet confirmed by supplier",
            "carrier": sh[0].carrier if sh else None,
            "tracking_number": sh[0].tracking_number if sh else None,
            "last_carrier_event": sh[0].events[-1].summary if sh else None,
            "delivered_at": sh[0].delivered_at.isoformat() if sh and sh[0].delivered_at else None,
            "return": rr[0].status if rr else None,
            "ship_to": f"PIN {o.ship_to_pincode[:3]}***",   # masked; full address stays with the channel
        }

    def open_case(self, actor: Actor, order_id: str | None, category: str, severity: Severity) -> CustomerSupportCase:
        require(actor, Perm.MANAGE_SUPPORT_CASE)
        hours = {Severity.CRITICAL: 4, Severity.HIGH: 12, Severity.MEDIUM: 24, Severity.LOW: 48}[severity]
        c = CustomerSupportCase(self.store.new_id("case"), order_id, category, severity, "OPEN", self._now(),
                                self._now() + timedelta(hours=hours))
        self.store.add("cases", c)
        self._log(actor, "support_case_opened", order_id or c.id, case=c.id, category=category, severity=severity)
        if category in ("safety", "fraud", "dispute"):
            self.notify(Severity.CRITICAL, "support_escalation", f"{category} case {c.id}", c.id)
        return c

    # ------------------------------------------------------------- marketing (Agent H)
    def propose_campaign(self, actor: Actor, channel: Channel, name: str, budget: Decimal) -> MarketingCampaign:
        require(actor, Perm.PROPOSE_CAMPAIGN)
        c = MarketingCampaign(self.store.new_id("cmpgn"), channel, name, budget, "PROPOSED")
        self.store.add("campaigns", c)
        a = self.request_approval(actor, ApprovalScope.AD_BUDGET, c.id, 1, f"{name}: Rs {budget}", channel, budget)
        c.approval_id = a.id
        self._log(actor, "campaign_proposed", c.id, budget=str(budget))
        return c

    def start_campaign(self, actor: Actor, campaign_id: str) -> MarketingCampaign:
        require(actor, Perm.RUN_CAMPAIGN)
        c = self.store.get("campaigns", campaign_id)
        a = self.store.get("approvals", c.approval_id)
        r = []
        if StopSwitch.CAMPAIGNS in self.stops:
            r.append("emergency stop: campaigns paused")
        if a.status is not ApprovalStatus.GRANTED:
            r.append(f"budget approval is {a.status}")
        if r:
            raise GateBlocked("start_campaign", r)
        c.status = "RUNNING"
        self._log(actor, "campaign_started", c.id)
        return c

    def record_ad_spend(self, actor: Actor, campaign_id: str, amount: Decimal) -> MarketingCampaign:
        require(actor, Perm.RUN_CAMPAIGN)
        c = self.store.get("campaigns", campaign_id)
        c.spent_inr += amount
        if c.spent_inr >= c.budget_inr and c.status == "RUNNING":
            c.status = "PAUSED"
            self._log(actor, "campaign_paused", c.id, reason="budget reached", spent=str(c.spent_inr))
            self.notify(Severity.MEDIUM, "campaign_budget", f"{c.name} reached its approved budget", c.id)
        return c

    def record_expense(self, actor: Actor, category: str, amount: Decimal, description: str, approval_id: str) -> Expense:
        require(actor, Perm.RECONCILE_SETTLEMENT)
        a = self.store.get("approvals", approval_id)
        if a.scope is not ApprovalScope.EXPENSE or a.status is not ApprovalStatus.GRANTED or \
                (a.amount_limit is not None and amount > a.amount_limit):
            raise GateBlocked("record_expense", ["needs a granted EXPENSE approval covering this amount"])
        self._consume(actor, a)
        e = Expense(self.store.new_id("exp"), category, amount, description, a.id, self._now())
        self.store.add("expenses", e)
        self._log(actor, "expense_recorded", e.id, amount=str(amount), approval=a.id)
        return e
