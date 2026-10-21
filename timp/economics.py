"""Agent D margin engine: per-SKU, per-channel expected net contribution.

Definitions (docs/07-margin-specification.md):

  net revenue      = (selling price - discount) / (1 + output GST)       GST is a pass-through, never revenue
  channel fees     = commission + fixed + payment + platform fees         (+ GST on fees when input tax is NOT recoverable)
  cogs             = supplier unit cost excl. GST                         (+ supplier GST when input tax is NOT recoverable)
  kept order       = net revenue - cogs - forward ship - packaging - fees - ads - other
  returned order   = -(forward + reverse ship + packaging + non-refunded fees + ads + other + unrecovered cogs)
  expected / order = (1 - r) * kept + r * returned
  margin %         = expected / ((1 - r) * net revenue)

TCS/TDS withheld by marketplaces are creditable taxes: they hit cash, not contribution.
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields, replace
from decimal import ROUND_HALF_UP, Decimal

ZERO = Decimal("0")
HUNDRED = Decimal("100")


def money(x: Decimal) -> Decimal:
    return Decimal(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def D(x) -> Decimal | None:
    return None if x is None else Decimal(str(x))


@dataclass(frozen=True)
class ChannelFees:
    channel: str
    commission_pct: Decimal | None
    fixed_fee_inr: Decimal | None
    payment_fee_pct: Decimal | None
    platform_fee_pct: Decimal | None
    fee_gst_pct: Decimal = Decimal("18")
    fees_refunded_on_return_pct: Decimal = ZERO
    tcs_pct: Decimal = ZERO
    tds_pct: Decimal = ZERO
    verified: bool = False
    source: str = ""

    def missing(self) -> list[str]:
        return [f"fees.{f}" for f in ("commission_pct", "fixed_fee_inr", "payment_fee_pct", "platform_fee_pct")
                if getattr(self, f) is None]

    @classmethod
    def from_config(cls, channel: str, cfg: dict) -> "ChannelFees":
        return cls(
            channel=channel,
            commission_pct=D(cfg.get("commission_pct")),
            fixed_fee_inr=D(cfg.get("fixed_fee_inr")),
            payment_fee_pct=D(cfg.get("payment_fee_pct")),
            platform_fee_pct=D(cfg.get("platform_fee_pct")),
            fee_gst_pct=D(cfg.get("fee_gst_pct", "18")),
            fees_refunded_on_return_pct=D(cfg.get("fees_refunded_on_return_pct", "0")),
            tcs_pct=D(cfg.get("tcs_pct", "0")),
            tds_pct=D(cfg.get("tds_pct", "0")),
            verified=bool(cfg.get("fees_verified", False)),
            source=cfg.get("fee_source", ""),
        )


@dataclass(frozen=True)
class CostInputs:
    selling_price_incl_gst: Decimal | None
    output_gst_pct: Decimal | None
    supplier_cost_excl_gst: Decimal | None
    supplier_gst_pct: Decimal | None
    forward_shipping: Decimal | None
    reverse_shipping: Decimal | None
    return_rate_pct: Decimal | None
    ad_cost_per_order: Decimal | None
    packaging: Decimal = ZERO
    discount_incl_gst: Decimal = ZERO
    other_variable: Decimal = ZERO
    supplier_credit_on_return_pct: Decimal = ZERO   # share of cogs the supplier credits back on a return
    input_tax_recoverable: bool = True              # GST-registered and eligible for ITC
    basis: dict[str, str] = field(default_factory=dict, hash=False, compare=False)  # field -> quoted|actual|estimated

    def missing(self) -> list[str]:
        return [f.name for f in fields(self) if f.name != "basis" and getattr(self, f.name) is None]


@dataclass(frozen=True)
class Thresholds:
    min_contribution_inr: Decimal
    min_margin_pct: Decimal
    max_acquisition_cost_inr: Decimal
    gate_scenario: str = "base"

    @classmethod
    def from_config(cls, cfg: dict) -> "Thresholds":
        return cls(D(cfg["min_contribution_inr"]), D(cfg["min_margin_pct"]),
                   D(cfg["max_acquisition_cost_inr"]), cfg.get("gate_scenario", "base"))


@dataclass(frozen=True)
class Scenario:
    name: str
    return_rate_mult: Decimal = Decimal("1")
    ad_cost_mult: Decimal = Decimal("1")
    shipping_mult: Decimal = Decimal("1")


DEFAULT_SCENARIOS = (
    Scenario("conservative", Decimal("1.5"), Decimal("1.5"), Decimal("1.2")),
    Scenario("base"),
    Scenario("optimistic", Decimal("0.7"), Decimal("0.7"), Decimal("1")),
)


@dataclass
class ScenarioResult:
    scenario: str
    gross_sales_incl_gst: Decimal
    net_revenue: Decimal
    lines: list[tuple[str, Decimal]]
    kept_order_contribution: Decimal
    returned_order_contribution: Decimal
    expected_contribution: Decimal
    margin_pct: Decimal
    cash_out_per_order: Decimal
    tax_withheld_per_order: Decimal
    passes: bool
    reasons: list[str]


@dataclass
class EconomicsReport:
    channel: str
    status: str                  # PASS | FAIL | INCOMPLETE
    missing: list[str]
    fees_verified: bool
    scenarios: dict[str, ScenarioResult]
    break_even_price_incl_gst: Decimal | None
    min_viable_price_incl_gst: Decimal | None
    fragile: bool                # gate scenario passes, conservative does not
    reasons: list[str]

    @property
    def gate_open(self) -> bool:
        return self.status == "PASS" and self.fees_verified


def _scenario(i: CostInputs, f: ChannelFees, t: Thresholds, s: Scenario) -> ScenarioResult:
    price = i.selling_price_incl_gst - i.discount_incl_gst
    net_rev = price / (1 + i.output_gst_pct / HUNDRED)
    r = min(i.return_rate_pct * s.return_rate_mult, HUNDRED) / HUNDRED
    ads = i.ad_cost_per_order * s.ad_cost_mult
    fwd = i.forward_shipping * s.shipping_mult
    rev = i.reverse_shipping * s.shipping_mult

    fees_ex = (price * f.commission_pct / HUNDRED + f.fixed_fee_inr
               + price * f.payment_fee_pct / HUNDRED + price * f.platform_fee_pct / HUNDRED)
    fee_gst = fees_ex * f.fee_gst_pct / HUNDRED
    fees = fees_ex if i.input_tax_recoverable else fees_ex + fee_gst
    cogs = i.supplier_cost_excl_gst if i.input_tax_recoverable else \
        i.supplier_cost_excl_gst * (1 + i.supplier_gst_pct / HUNDRED)

    kept = net_rev - cogs - fwd - i.packaging - fees - ads - i.other_variable
    unrefunded_fees = fees * (1 - f.fees_refunded_on_return_pct / HUNDRED)
    returned = -(fwd + rev + i.packaging + unrefunded_fees + ads + i.other_variable
                 + cogs * (1 - i.supplier_credit_on_return_pct / HUNDRED))
    expected = (1 - r) * kept + r * returned
    exp_rev = (1 - r) * net_rev
    margin = expected / exp_rev * HUNDRED if exp_rev > 0 else Decimal("-100")

    supplier_gross = i.supplier_cost_excl_gst * (1 + i.supplier_gst_pct / HUNDRED)
    cash_out = supplier_gross + fwd + i.packaging + ads
    withheld = net_rev * (f.tcs_pct + f.tds_pct) / HUNDRED

    reasons = []
    if expected < t.min_contribution_inr:
        reasons.append(f"contribution {money(expected)} < minimum {t.min_contribution_inr}")
    if margin < t.min_margin_pct:
        reasons.append(f"margin {money(margin)}% < minimum {t.min_margin_pct}%")
    if ads > t.max_acquisition_cost_inr:
        reasons.append(f"acquisition cost {money(ads)} > maximum {t.max_acquisition_cost_inr}")

    lines = [
        ("Gross sale incl. GST (after discount)", price),
        ("Output GST (pass-through)", -(price - net_rev)),
        ("Net revenue", net_rev),
        ("Supplier cost" + ("" if i.input_tax_recoverable else " incl. GST"), -cogs),
        ("Forward shipping", -fwd),
        ("Packaging", -i.packaging),
        ("Channel fees" + (" excl. GST (ITC)" if i.input_tax_recoverable else " incl. GST"), -fees),
        ("Advertising per order", -ads),
        ("Other variable", -i.other_variable),
        ("= Contribution if kept", kept),
        (f"Return exposure at {money(r * HUNDRED)}% returns", expected - kept),
        ("= Expected contribution per order", expected),
    ]
    return ScenarioResult(s.name, money(price), money(net_rev), [(n, money(v)) for n, v in lines],
                          money(kept), money(returned), money(expected), money(margin),
                          money(cash_out), money(withheld), not reasons, reasons)


def _solve_price(i: CostInputs, f: ChannelFees, t: Thresholds, s: Scenario, ok) -> Decimal | None:
    lo, hi = Decimal("1"), max(Decimal("100"), i.supplier_cost_excl_gst * 50)
    if not ok(_scenario(replace(i, selling_price_incl_gst=hi), f, t, s)):
        return None
    for _ in range(60):
        mid = (lo + hi) / 2
        if ok(_scenario(replace(i, selling_price_incl_gst=mid), f, t, s)):
            hi = mid
        else:
            lo = mid
    return money(hi)


def evaluate(i: CostInputs, f: ChannelFees, t: Thresholds,
             scenarios: tuple[Scenario, ...] = DEFAULT_SCENARIOS) -> EconomicsReport:
    missing = i.missing() + f.missing()
    if missing:
        return EconomicsReport(f.channel, "INCOMPLETE", missing, f.verified, {}, None, None, False,
                               [f"missing inputs: {', '.join(missing)}"])
    results = {s.name: _scenario(i, f, t, s) for s in scenarios}
    gate = results[t.gate_scenario]
    gate_s = next(s for s in scenarios if s.name == t.gate_scenario)
    reasons = list(gate.reasons)
    if not f.verified:
        reasons.append(f"{f.channel} fee schedule not verified ({f.source or 'no source'})")
    fragile = gate.passes and "conservative" in results and not results["conservative"].passes
    return EconomicsReport(
        channel=f.channel,
        status="PASS" if gate.passes else "FAIL",
        missing=[],
        fees_verified=f.verified,
        scenarios=results,
        break_even_price_incl_gst=_solve_price(i, f, t, gate_s, lambda r: r.expected_contribution >= 0),
        min_viable_price_incl_gst=_solve_price(i, f, t, gate_s, lambda r: r.passes),
        fragile=fragile,
        reasons=reasons,
    )
