"""Run every research candidate through the margin engine and write the owner report.

    python3 scripts/profit_report.py   ->  reports/product-profit-report.md, reports/product-profit.json
"""
from __future__ import annotations

import json
import sys
import tomllib
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from research.candidates import CANDIDATES, CHANNELS, COMMON, FEE_SOURCES, RESEARCH_DATE  # noqa: E402
from timp.economics import ChannelFees, CostInputs, Thresholds, evaluate  # noqa: E402

cfg = tomllib.loads((ROOT / "config/settings.toml").read_text())
thresholds = Thresholds.from_config(cfg["thresholds"])


def run(c: dict, ch_key: str):
    ch = CHANNELS[ch_key]
    price = c["price"]
    fees = ChannelFees(
        channel=ch_key,
        commission_pct=ch["commission_pct"](price),
        fixed_fee_inr=ch["fixed_fee"](price),
        payment_fee_pct=ch["payment_fee_pct"],
        platform_fee_pct=ch["platform_fee_pct"],
        tcs_pct=ch["tcs"], tds_pct=ch["tds"],
        verified=False, source="third-party summaries, " + RESEARCH_DATE,
    )
    inputs = CostInputs(
        selling_price_incl_gst=price,
        output_gst_pct=c["gst_pct"],
        supplier_cost_excl_gst=c["supplier_cost"],
        supplier_gst_pct=c["gst_pct"],
        forward_shipping=ch["ship_" + c["weight"]],
        reverse_shipping=ch["reverse"],
        return_rate_pct=ch["return_rate"],
        ad_cost_per_order=ch["ads"],
        **COMMON,
    )
    return evaluate(inputs, fees, thresholds)


def inr(x: Decimal | None) -> str:
    if x is None:
        return "n/a"
    sign = "-" if x < 0 else ""
    return f"{sign}Rs {abs(x):,.0f}"


def main() -> None:
    rows, data = [], []
    for c in CANDIDATES:
        for ch_key in CHANNELS:
            rep = run(c, ch_key)
            rec = dict(id=c["id"], product=c["name"], channel=ch_key, price=str(c["price"]), status=rep.status,
                       fragile=rep.fragile, reasons=rep.reasons, missing=rep.missing,
                       break_even=str(rep.break_even_price_incl_gst), min_viable=str(rep.min_viable_price_incl_gst),
                       scenarios={k: dict(expected=str(v.expected_contribution), margin_pct=str(v.margin_pct),
                                          net_revenue=str(v.net_revenue), cash_out=str(v.cash_out_per_order),
                                          lines=[(n, str(a)) for n, a in v.lines])
                                  for k, v in rep.scenarios.items()})
            data.append(rec)
            rows.append((c, ch_key, rep))

    out = ROOT / "reports"
    out.mkdir(exist_ok=True)
    (out / "product-profit.json").write_text(json.dumps(
        dict(research_date=RESEARCH_DATE, thresholds={k: str(v) for k, v in vars(thresholds).items()}, results=data),
        indent=2))

    L = []
    L.append(f"# Product profit report (estimates, {RESEARCH_DATE})\n")
    L.append("> **Every number below is an ESTIMATE.** Supplier costs are public IndiaMART listing prices, not quotations. "
             "Marketplace fees come from third-party 2026 summaries that disagree with each other and are NOT verified "
             "on the official seller fee pages. Shipping, returns and advertising are assumptions. IndiaMART prices are usually "
             "bulk (MOQ) prices; a supplier who drop-ships single pieces will usually charge more, so these results are "
             "likely OPTIMISTIC. Use this to choose which products to get real quotes for, not to set prices.\n")
    L.append(f"Owner thresholds (config/settings.toml): minimum contribution **Rs {thresholds.min_contribution_inr}/order**, "
             f"minimum margin **{thresholds.min_margin_pct}%**, maximum acquisition cost **Rs {thresholds.max_acquisition_cost_inr}/order**. "
             "GST is treated as pass-through with input tax credit (needs GST registration).\n")

    L.append("## Ranking by expected profit per order (base scenario)\n")
    L.append("| # | Product | Channel | Price | Profit/order (cons / **base** / opt) | Margin | Profit per 100 orders | Min price to pass | Verdict |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    ranked = sorted([r for r in rows if r[2].status != "INCOMPLETE"],
                    key=lambda r: r[2].scenarios["base"].expected_contribution, reverse=True)
    for n, (c, ch, rep) in enumerate(ranked, 1):
        s = rep.scenarios
        verdict = "PASS" + (" (fragile)" if rep.fragile else "") if rep.status == "PASS" else "FAIL"
        L.append(f"| {n} | {c['name']} | {CHANNELS[ch]['label']} | {inr(c['price'])} | "
                 f"{inr(s['conservative'].expected_contribution)} / **{inr(s['base'].expected_contribution)}** / "
                 f"{inr(s['optimistic'].expected_contribution)} | {s['base'].margin_pct}% | "
                 f"{inr(s['base'].expected_contribution * 100)} | {inr(rep.min_viable_price_incl_gst)} | {verdict} |")
    for c, ch, rep in rows:
        if rep.status == "INCOMPLETE" and ch == "shopify":
            L.append(f"| - | {c['name']} | all channels | {inr(c['price'])} | cannot calculate | - | - | - | INCOMPLETE: {c['supplier_cost_note']} |")
    L.append("\n'Profit per 100 orders' is arithmetic, not a sales forecast: no reliable sales-volume data was available. "
             "'Fragile' means it passes in the base case but fails if returns, ads and shipping come in worse.\n")

    L.append("## Product details\n")
    for c in CANDIDATES:
        L.append(f"### {c['id']} {c['name']}\n")
        L.append(f"- **Supplier cost (est.)**: {inr(c['supplier_cost'])} excl. GST, range {c['supplier_cost_range']}. {c['supplier_cost_note']}")
        L.append(f"- **Retail observed**: {c['retail_observed']}")
        L.append(f"- **Proposed price**: {inr(c['price'])} incl. GST")
        if c.get("odisha_leads"):
            L.append(f"- **Odisha supplier leads (unverified)**: {c['odisha_leads']}")
        L.append(f"- **Risks**: " + "; ".join(c["risks"]))
        L.append("- **Sources**: " + ", ".join(f"[{i+1}]({u})" for i, u in enumerate(c["sources"])))
        base = [(ch, rep) for cc, ch, rep in rows if cc is c]
        if base[0][1].status == "INCOMPLETE":
            L.append("\nNo estimate: " + "; ".join(base[0][1].reasons) + "\n")
            continue
        L.append("\n| Line (base scenario) | " + " | ".join(CHANNELS[ch]["label"] for ch, _ in base) + " |")
        L.append("|---|" + "---|" * len(base))
        labels = [n for n, _ in base[0][1].scenarios["base"].lines]
        for i, label in enumerate(labels):
            L.append(f"| {label} | " + " | ".join(inr(rep.scenarios['base'].lines[i][1]) for _, rep in base) + " |")
        L.append("| Margin on net revenue | " + " | ".join(f"{rep.scenarios['base'].margin_pct}%" for _, rep in base) + " |")
        L.append("| Break-even price | " + " | ".join(inr(rep.break_even_price_incl_gst) for _, rep in base) + " |")
        L.append("| Cash out before payout | " + " | ".join(inr(rep.scenarios['base'].cash_out_per_order) for _, rep in base) + " |")
        L.append("| TCS+TDS withheld (creditable) | " + " | ".join(inr(rep.scenarios['base'].tax_withheld_per_order) for _, rep in base) + " |")
        L.append("")

    L.append("## Assumptions used\n")
    L.append("| Channel | Commission | Fixed/closing fee | Payment + platform fee | Ship <=500g / <=1kg / <=2kg | Reverse ship | Returns | Ads/order |")
    L.append("|---|---|---|---|---|---|---|---|")
    for k, ch in CHANNELS.items():
        L.append(f"| {ch['label']} | {ch['commission_pct'](Decimal('500'))}% under Rs 1,000 | by price band | "
                 f"{ch['payment_fee_pct']}% + {ch['platform_fee_pct']}% | Rs {ch['ship_le_500g']} / {ch['ship_le_1kg']} / {ch['ship_le_2kg']} | "
                 f"Rs {ch['reverse']} | {ch['return_rate']}% | Rs {ch['ads']} |")
    L.append(f"\nAll channels: packaging/handling Rs {COMMON['packaging']}; supplier credits {COMMON['supplier_credit_on_return_pct']}% of cost on a return; "
             "output and input GST 18% (confirm HSN rates with your CA; GST 2.0 changed many rates in 2025).\n")
    L.append("### Fee sources (unverified)\n")
    for k, urls in FEE_SOURCES.items():
        L.append(f"- **{CHANNELS[k]['label']}**: " + ", ".join(f"[{i+1}]({u})" for i, u in enumerate(urls)))
    (out / "product-profit-report.md").write_text("\n".join(L) + "\n")
    print("\n".join(L[:20 + len(ranked)]))


if __name__ == "__main__":
    main()
