"""Product recommendations for the owner: policy filter -> margin engine -> reviewer and CA verdicts -> ranking.

    python3 scripts/recommend.py   ->  reports/recommendations.md, reports/recommendations.json

Pipeline stage per candidate (fields written by the agents, see .claude/agents/):
  research agent   adds the candidate (research/inbox/*.json)          stage NEW
  review agent     sets  candidate["review"] = {verdict, notes, ...}   stage REVIEWED
  CA agent         sets  candidate["ca"]     = {verdict, hsn, gst_pct_confirmed, notes, ...}
A product is RECOMMENDED only when it passes the hard rules, the economics on at least one channel,
and both agents approved it. Everything else is listed with the reason, so nothing is hidden.
"""
from __future__ import annotations

import json
import sys
import tomllib
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from research.candidates import CANDIDATES, CHANNELS, RESEARCH_DATE  # noqa: E402
from scripts.profit_report import run  # noqa: E402

POLICY = tomllib.loads((ROOT / "config/product_policy.toml").read_text())
SLABS = ["le_500g", "le_1kg", "le_2kg"]


def policy_problems(c: dict, policy: dict = POLICY) -> list[str]:
    e, h = policy["economics"], policy["hard_rules"]
    out = []
    cat = c.get("category", "")
    if cat in h["blocked_categories"]:
        exc = policy.get("exception", {}).get("electrical", {})
        docs = set(c.get("documents", []))
        if cat in ("electrical_appliances",) and exc.get("allowed") and set(exc["required_documents"]) <= docs:
            pass
        else:
            out.append(f"blocked category: {cat}")
    if c.get("electrical"):
        need = set(policy["exception"]["electrical"]["required_documents"]) - set(c.get("documents", []))
        if need:
            out.append("electrical item without " + ", ".join(sorted(need)))
    if c.get("price") is not None and c["price"] < Decimal(str(e["min_price_inr"])):
        out.append(f"price below Rs {e['min_price_inr']}")
    if c.get("weight") not in SLABS or SLABS.index(c["weight"]) > SLABS.index(e["max_weight_slab"]):
        out.append(f"weight slab {c.get('weight')} over {e['max_weight_slab']}")
    if c.get("supplier_cost") is None:
        out.append("no supplier cost yet")
    return out


def evaluate(c: dict) -> dict:
    problems = policy_problems(c)
    chans = {}
    if c.get("supplier_cost") is not None and c.get("price") is not None:
        for ch in CHANNELS:
            r = run(c, ch)
            b = r.scenarios.get("base") if r.scenarios else None
            chans[ch] = dict(status=r.status, fragile=r.fragile,
                             expected=float(b.expected_contribution) if b else None,
                             margin=float(b.margin_pct) if b else None,
                             conservative=float(r.scenarios["conservative"].expected_contribution) if b else None)
    min_m = POLICY["economics"]["min_margin_pct"]
    passing = {k: v for k, v in chans.items() if v["margin"] is not None and v["margin"] >= min_m
               and v["expected"] >= POLICY["economics"]["min_contribution_inr"]}
    best = max(passing.items(), key=lambda kv: kv[1]["expected"]) if passing else \
        (max(chans.items(), key=lambda kv: kv[1]["expected"] or -1e9) if chans else (None, None))
    review = (c.get("review") or {}).get("verdict")
    ca = (c.get("ca") or {}).get("verdict")
    if problems:
        stage, reason = "REJECTED", "; ".join(problems)
    elif not passing:
        stage, reason = "BELOW_TARGET", f"no channel reaches {min_m}% margin"
    elif review == "reject" or ca == "reject":
        stage, reason = "REJECTED", "reviewer or CA rejected: " + "; ".join(
            filter(None, [(c.get("review") or {}).get("notes"), (c.get("ca") or {}).get("notes")]))
    elif review != "approve":
        stage, reason = "AWAITING_REVIEW", "profit target met; waiting for the review agent"
    elif ca != "approve":
        stage, reason = "AWAITING_CA", "reviewed; waiting for the CA agent (GST/HSN, licences)"
    else:
        stage, reason = "RECOMMENDED", "passes policy, profit target, review and CA"
    return dict(id=c["id"], name=c["name"], category=c.get("category"), price=float(c["price"]) if c.get("price") else None,
                supplier_cost=float(c["supplier_cost"]) if c.get("supplier_cost") is not None else None,
                stage=stage, reason=reason, best_channel=best[0], best=best[1], channels=chans,
                passing_channels=sorted(passing), retail_validated="UNVALIDATED" not in c.get("retail_observed", ""),
                sources=c.get("sources", []), review=c.get("review"), ca=c.get("ca"))


ORDER = ["RECOMMENDED", "AWAITING_CA", "AWAITING_REVIEW", "BELOW_TARGET", "REJECTED"]


def main() -> list[dict]:
    rows = [evaluate(c) for c in CANDIDATES]
    rows.sort(key=lambda r: (ORDER.index(r["stage"]), -((r["best"] or {}).get("expected") or -1e9)))
    out = ROOT / "reports"
    out.mkdir(exist_ok=True)
    (out / "recommendations.json").write_text(json.dumps(dict(research_date=RESEARCH_DATE, policy=POLICY["economics"],
                                                               items=rows), indent=2, default=str))
    L = [f"# Product recommendations\n",
         f"Ranked by expected profit per order (base scenario). Minimum {POLICY['economics']['min_margin_pct']}% margin and "
         f"Rs {POLICY['economics']['min_contribution_inr']} per order; hard rules in `config/product_policy.toml`. "
         "All supplier costs and fees are estimates until quotations and fee cards are verified.\n",
         "| Stage | Product | Best channel | Price | Profit/order | Margin | Worse case | Channels ≥ target | Why |",
         "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        b = r["best"] or {}
        L.append(f"| {r['stage']} | {r['name']} | {CHANNELS[r['best_channel']]['label'] if r['best_channel'] else '-'} | "
                 f"{'Rs %d' % r['price'] if r['price'] else '-'} | {'Rs %.0f' % b['expected'] if b.get('expected') is not None else '-'} | "
                 f"{'%.1f%%' % b['margin'] if b.get('margin') is not None else '-'} | "
                 f"{'Rs %.0f' % b['conservative'] if b.get('conservative') is not None else '-'} | "
                 f"{', '.join(r['passing_channels']) or '-'} | {r['reason']}{'' if r['retail_validated'] else ' · retail price unvalidated'} |")
    (out / "recommendations.md").write_text("\n".join(L) + "\n")
    return rows


if __name__ == "__main__":
    for r in main():
        b = r["best"] or {}
        print(f"{r['stage']:16} {r['name'][:60]:60} {b.get('expected')}")
