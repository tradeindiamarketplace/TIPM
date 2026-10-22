"""First-pass product candidates (Agent B) and research-based fee estimates (Agent D).

Status of every number here: ESTIMATED from public web listings on 2026-10-21.
None of it is a supplier quotation, and none of the marketplace fees has been
verified on the official seller fee pages. The publication gate stays closed until
real quotations and verified fee cards replace these values.
"""
from decimal import Decimal as D

RESEARCH_DATE = "2026-10-21"

# ---------------------------------------------------------------------------
# Channel fee estimates (third-party summaries; the sources disagree; verify)
# ---------------------------------------------------------------------------

def amazon_closing_fee(price: D) -> D:
    # Higher of the two published-by-third-party tables, to stay conservative.
    if price <= 250: return D("5")
    if price <= 500: return D("10")
    if price <= 1000: return D("30")
    return D("61")


def flipkart_fixed_fee(price: D) -> D:
    # Sources quote Rs 5-35 by price slab; mid-to-high values used.
    if price <= 300: return D("15")
    if price <= 500: return D("20")
    return D("30")


CHANNELS = {
    "shopify": dict(
        label="TradeIndiaMarketplace.com (Shopify Basic)",
        commission_pct=lambda p: D("0"), fixed_fee=lambda p: D("0"),
        payment_fee_pct=D("2"),    # gateway MDR, e.g. Razorpay standard 2% (+18% GST)
        platform_fee_pct=D("2"),   # Shopify third-party-gateway fee on Basic, per Razorpay's guide
        ship_le_500g=D("60"), ship_le_1kg=D("80"), ship_le_2kg=D("120"), reverse=D("100"),
        ads=D("60"),               # a new site has to buy its traffic
        return_rate=D("8"),
        tcs=D("0"), tds=D("0"),
    ),
    "amazon_in": dict(
        label="Amazon.in (Easy Ship)",
        commission_pct=lambda p: D("0") if p <= 1000 else D("12"),  # 0% referral up to Rs 1,000 from 16 Mar 2026 (reported)
        fixed_fee=amazon_closing_fee,
        payment_fee_pct=D("0"), platform_fee_pct=D("0"),
        ship_le_500g=D("65"), ship_le_1kg=D("80"), ship_le_2kg=D("115"), reverse=D("100"),
        ads=D("30"),
        return_rate=D("8"),
        tcs=D("0.5"), tds=D("0.1"),
    ),
    "flipkart": dict(
        label="Flipkart",
        commission_pct=lambda p: D("0") if p < 1000 else D("12"),   # 0% under Rs 1,000 since Nov 2025 (reported)
        fixed_fee=flipkart_fixed_fee,
        payment_fee_pct=D("2.5"),  # collection fee: ~2% prepaid, 2-3% COD
        platform_fee_pct=D("0"),
        ship_le_500g=D("65"), ship_le_1kg=D("85"), ship_le_2kg=D("120"), reverse=D("100"),
        ads=D("30"),
        return_rate=D("8"),
        tcs=D("0.5"), tds=D("0.1"),
    ),
    "meesho": dict(
        label="Meesho",
        commission_pct=lambda p: D("0"),
        fixed_fee=lambda p: D("10"),   # sources conflict on whether a small fixed fee applies
        payment_fee_pct=D("0"), platform_fee_pct=D("0"),
        ship_le_500g=D("75"), ship_le_1kg=D("100"), ship_le_2kg=D("150"), reverse=D("155"),
        ads=D("20"),
        return_rate=D("15"),       # Meesho returns/RTO run higher; estimate
        tcs=D("0.5"), tds=D("0.1"),
    ),
}

# ---------------------------------------------------------------------------
# Candidates. supplier_cost = IndiaMART listing price, assumed EXCL. GST (confirm).
# price = proposed selling price incl. GST, set at or below observed retail.
# ---------------------------------------------------------------------------

CANDIDATES = [
    dict(
        id="PC-001", name="Microfiber cleaning cloth 40x40 cm, 350 GSM, pack of 5",
        category="cleaning_utility", weight="le_500g",
        supplier_cost=D("112.50"), supplier_cost_range=("80", "155"),
        supplier_cost_note="Rs 16-31/piece on IndiaMART (S K International Rs 16-27 with MOQ 500; Radiant Global Rs 22.50 for 350 GSM) x 5",
        price=D("399"),
        retail_observed="Kuber Industries 5-pack Rs 499 (GlobalBees); Swachh Touch 5-pack Rs 695 (BigBasket)",
        gst_pct=D("18"),
        risks=["Commodity category, many sellers", "GSM claims must match the supplier test report"],
        odisha_leads="IndiaMART Khordha/Bhubaneswar directory: 350 GSM 40x60 cm cloth Rs 38/piece; 500 GSM polishing cloth Rs 20/piece (sizes differ; get a 40x40 quote)",
        sources=[
            "https://www.indiamart.com/skenterprisegujarat/microfiber-cleaning-cloth.html",
            "https://m.indiamart.com/impcat/microfiber-cloths.html",
            "https://shop.globalbees.com/products/kuber-industries-multi-utility-microfiber-duster-1000000131187",
            "https://dir.indiamart.com/khurda/microfiber-cloths.html",
            "https://www.bigbasket.com/pd/40258178/swachh-touch-microfiber-cloth-40x40-cms-for-cleaning-super-absorbent-non-scratch-5-pcs/",
        ],
    ),
    dict(
        id="PC-002", name="Pure copper water bottle 1 L",
        category="kitchen_organisation", weight="le_1kg",
        supplier_cost=D("450"), supplier_cost_range=("400", "580"),
        supplier_cost_note="Moradabad makers on IndiaMART: Rs 400 (S I Metal), 410 (Shree Krishna Metal), 450 (Ansar Handicrafts), 580 (Krishna Metals)",
        price=D("749"),
        retail_observed="Amazon.in deals: AMARY Rs 469, Sisq Rs 786, The Better Home Rs 799; Borosil Rs 1,271+",
        gst_pct=D("18"),
        risks=["'Pure copper' claim needs a material test report", "Dents in transit raise returns",
               "Food-contact / lacquer claims need evidence"],
        sources=[
            "https://m.indiamart.com/impcat/copper-sipper-bottle.html",
            "https://dir.indiamart.com/moradabad/copper-water-bottle.html",
            "https://www.dealsmagnet.com/deal/sisq-pure-copper-water-bottle-1-litre-1d0VSk3N",
            "https://www.dealsmagnet.com/deal/amary-pure-copper-water-bottle-1l-pack-of-1-1bsZsbVw",
        ],
    ),
    dict(
        id="PC-003", name="Silicone spatula / cooking tool set, 6 pieces",
        category="kitchen_organisation", weight="le_500g",
        supplier_cost=D("120"), supplier_cost_range=("70", "180"),
        supplier_cost_note="Surat sellers: 6-pc nonstick tool set Rs 70; 9-inch 6-pc silicone set Rs 180 (unit unclear)",
        price=D("299"),
        retail_observed="Flipkart Easymart silicone set Rs 144-244",
        gst_pct=D("18"),
        risks=["Food-grade silicone (LFGB/FDA-type) evidence needed", "Low observed retail price"],
        sources=[
            "https://m.indiamart.com/impcat/silicone-spatula.html",
            "https://m.indiamart.com/impcat/kitchen-tools.html",
            "https://www.flipkart.com/easymart-silicone-kitchen-spatula-set-tool/p/itmb0c550becd950",
        ],
    ),
    dict(
        id="PC-004", name="Airtight PET kitchen storage jars, set of 6 (~1 L)",
        category="home_storage", weight="le_2kg",
        supplier_cost=D("144"), supplier_cost_range=("83", "200"),
        supplier_cost_note="Rajkot sellers: Eniver Mart Rs 24/piece for 6-pc 1000 ml set; Dynamic Plastic Rs 83 for a 900 ml PET set",
        price=D("449"),
        retail_observed="Kuber Industries 6 x 500 ml PET set Rs 449; 12 x 800 ml Rs 999 (GlobalBees)",
        gst_pct=D("18"),
        odisha_leads="Joshna Polymers, Bhubaneswar (airtight containers Rs 35-72, larger sizes); Subhalaxmi Plastics, Cuttack (manufacturer, HSN 3924 kitchenware); Jagdamba Polymers, Balasore; Apoorba Industries, Bhubaneswar (Rs 257 square container)",
        risks=["Bulky: volumetric weight drives shipping", "Breakage / cracked lids in transit",
               "Food-contact material evidence needed"],
        sources=[
            "https://m.indiamart.com/eniver-mart/fish-container.html",
            "https://m.indiamart.com/dynamicplastic/plastic-storage-containers.html",
            "https://m.indiamart.com/joshnapolymers/plastic-drum.html",
            "https://m.indiamart.com/company/104177997",
            "https://m.indiamart.com/apoorbaindustries/plastic-container.html",
            "https://shop.globalbees.com/products/kuber-industries-opal-plastic-airtight-pet-jar-2000000086457",
        ],
    ),
    dict(
        id="PC-005", name="Manual pull-string vegetable chopper, 500 ml",
        category="kitchen_organisation", weight="le_500g",
        supplier_cost=D("44"), supplier_cost_range=("35", "53"),
        supplier_cost_note="Rajkot sellers on IndiaMART: Rs 35, 44, 45, 53 per piece; L&T-SuFin 1000 ml Rs 89-92 (MOQ 144)",
        price=D("199"),
        retail_observed="Only competitor price found: Flipkart pull-string chopper Rs 67. Rs 199 is UNVALIDATED.",
        gst_pct=D("18"),
        risks=["Extremely price-competitive", "Blade quality complaints drive returns"],
        sources=[
            "https://m.indiamart.com/impcat/kitchen-chopper.html",
            "https://lntsufin.com/product/apex-6-blades-1000-ml-manual-vegetable-chopper/16560-1795",
            "https://www.flipkart.com/amr-store-manual-vegetable-chopper-pull-string-multipurpose-kitchen-food-fruit/p/itm5f95564e00d60",
        ],
    ),
    dict(
        id="PC-006", name="Stainless steel masala dabba, 7 containers",
        category="kitchen_organisation", weight="le_1kg",
        supplier_cost=None, supplier_cost_range=None,
        supplier_cost_note="No stainless 7-container wholesale price found; IndiaMART showed only a plastic version (Rs 40) and a jumbo steel box (Rs 2,106)",
        price=D("549"),
        retail_observed="Flipkart 7-compartment box Rs 495; Sumeet stainless 7-container Rs 556 (ad block)",
        gst_pct=D("18"),
        risks=["Needs a real supplier quote before any estimate"],
        sources=["https://m.indiamart.com/impcat/spice-boxes.html",
                 "https://www.flipkart.com/hi/asdesignimpex-spice-set-iron/p/itmc5eb14ae130c9"],
    ),
    # ---- 2026-10-21 second pass: trending everyday women / kids / home items (owner target: >= 30% margin)
    dict(
        id="PC-007", name="Korean-style hair claw clips, set of 6",
        category="women_accessories", weight="le_500g",
        supplier_cost=D("66"), supplier_cost_range=("16", "120"),
        supplier_cost_note="IndiaMART: Rs 132/dozen (Lady Care, Dijan Creation), Rs 235/dozen premium acrylic (Sabka Retail); 6 x Rs 11",
        price=D("249"),
        retail_observed="No reliable retail price found. Rs 249 is UNVALIDATED; check marketplace listings before approving.",
        gst_pct=D("18"),
        risks=["Breakage in transit", "Very crowded on Meesho", "Retail price not yet validated"],
        sources=["https://m.indiamart.com/impcat/hair-clips.html", "https://dir.indiamart.com/impcat/hair-clutcher.html",
                 "https://m.indiamart.com/ladycaredelhi"],
    ),
    dict(
        id="PC-008", name="Non-woven saree / clothes cover organisers, set of 12",
        category="home_storage", weight="le_1kg",
        supplier_cost=D("216"), supplier_cost_range=("132", "260"),
        supplier_cost_note="IndiaMART Jaipur/Delhi: Rs 11-20/piece (Samrathal Rs 20, Aman Packers Rs 17); Aarav Industries 12-pc set Rs 260",
        price=D("549"),
        retail_observed="Kuber Industries 12-piece non-woven set Rs 628 (GlobalBees)",
        gst_pct=D("12"),
        risks=["Low differentiation", "GST rate for HSN 6307/4202 to confirm"],
        sources=["https://m.indiamart.com/impcat/saree-cover.html",
                 "https://m.indiamart.com/samrathalindustries-jaipur/saree-cover-organizer.html",
                 "https://m.indiamart.com/aaravindustries-jaipur",
                 "https://shop.globalbees.com/products/kuber-industries-12-piece-non-woven-single-saree-2000000081136"],
    ),
    dict(
        id="PC-009", name="Cotton fridge vegetable storage bags, set of 6",
        category="kitchen_organisation", weight="le_500g",
        supplier_cost=D("117"), supplier_cost_range=("72", "120"),
        supplier_cost_note="IndiaMART: cotton fridge bag Rs 19-20/piece; nylon mesh Rs 15/piece",
        price=D("199"),
        retail_observed="Beddify set of 6 Rs 199 (MRP 599); Clazkit cotton set of 6 Rs 182 on Amazon",
        gst_pct=D("5"),
        risks=["Retail price too low for shipping costs"],
        sources=["https://m.indiamart.com/impcat/vegetable-mesh-bag.html",
                 "https://www.dealsmagnet.com/deal/beddify-set-of-6-reusable-fridge-storage-bags-whit-1d9ut2hW"],
    ),
    dict(
        id="PC-010", name="Makeup brush set, 13 pieces",
        category="beauty", weight="le_500g",
        supplier_cost=D("78"), supplier_cost_range=("45", "120"),
        supplier_cost_note="IndiaMART Surat: 13-pc set Rs 78; 9-pc pack Rs 45",
        price=D("299"),
        retail_observed="No reliable retail price found. Rs 299 is UNVALIDATED.",
        gst_pct=D("18"),
        risks=["Cosmetic tool quality complaints", "Retail price not yet validated"],
        sources=["https://m.indiamart.com/impcat/cosmetic-brush-set.html",
                 "https://m.indiamart.com/impcat/professional-makeup-brushes.html"],
    ),
    dict(
        id="PC-011", name="Kids stainless steel insulated lunch box (3 containers)",
        category="kids", weight="le_1kg",
        supplier_cost=D("245"), supplier_cost_range=("194", "350"),
        supplier_cost_note="IndiaMART: Bluecoin Rajkot insulated 3-container Rs 245; Gee Enterprises Rs 194; kids bento Rs 230-350",
        price=D("599"),
        retail_observed="No reliable retail price found. Rs 599 is UNVALIDATED.",
        gst_pct=D("12"),
        risks=["Food-contact material evidence", "Retail price not yet validated", "GST rate to confirm"],
        sources=["https://m.indiamart.com/impcat/insulated-lunch-box.html", "https://m.indiamart.com/impcat/bento-boxes.html"],
    ),
    dict(
        id="PC-012", name="Microfiber cleaning cloth 40x40 cm, 350 GSM, pack of 5 (at Rs 449)",
        category="cleaning_utility", weight="le_500g",
        supplier_cost=D("112.50"), supplier_cost_range=("80", "155"),
        supplier_cost_note="Same supplier data as PC-001, priced at Rs 449 instead of Rs 399",
        price=D("449"),
        retail_observed="Kuber Industries 5-pack Rs 499 (GlobalBees); Swachh Touch 5-pack Rs 695 (BigBasket)",
        gst_pct=D("18"),
        risks=["Commodity category"],
        sources=["https://dir.indiamart.com/khurda/microfiber-cloths.html"],
    ),
    # ---- combos / multi-packs: the way to clear 30% after fixed per-order shipping and return costs
    dict(id="PC-013", name="Microfiber cleaning cloth 40x40 cm, 350 GSM, pack of 10", category="cleaning_utility", weight="le_500g",
         supplier_cost=D("225"), supplier_cost_range=("160", "310"), supplier_cost_note="2 x PC-001 supplier estimate",
         price=D("699"), retail_observed="5-packs retail Rs 499-695, so 10 for Rs 699 is competitive", gst_pct=D("18"),
         risks=["Commodity category"], sources=["https://m.indiamart.com/impcat/microfiber-cloths.html"]),
    dict(id="PC-014", name="Makeup brush set 13 pcs with storage pouch", category="beauty", weight="le_500g",
         supplier_cost=D("110"), supplier_cost_range=("80", "150"), supplier_cost_note="13-pc set Rs 78 + pouch ~Rs 32 (pouch price is an ASSUMPTION, get a quote)",
         price=D("449"), retail_observed="UNVALIDATED", gst_pct=D("18"),
         risks=["Retail price not yet validated", "Pouch cost assumed"], sources=["https://m.indiamart.com/impcat/cosmetic-brush-set.html"]),
    dict(id="PC-015", name="Hair claw clips, pack of 12", category="women_accessories", weight="le_500g",
         supplier_cost=D("132"), supplier_cost_range=("96", "235"), supplier_cost_note="Rs 132/dozen (Lady Care, Dijan Creation)",
         price=D("449"), retail_observed="UNVALIDATED", gst_pct=D("18"),
         risks=["Retail price not yet validated", "Breakage"], sources=["https://m.indiamart.com/impcat/hair-clips.html"]),
    dict(id="PC-016", name="Wardrobe + fridge organiser combo (12 saree covers + 6 fridge bags)", category="home_storage", weight="le_2kg",
         supplier_cost=D("333"), supplier_cost_range=("204", "380"), supplier_cost_note="PC-008 + PC-009 supplier estimates; two suppliers unless one stocks both",
         price=D("899"), retail_observed="Separately Rs 628 + Rs 182-199 at retail", gst_pct=D("12"),
         risks=["Two suppliers = two parcels unless one supplier stocks both"], sources=["https://m.indiamart.com/impcat/saree-cover.html"]),
    # ---- 2026-10-21 third pass: non-electrical gadget accessories (no BIS, low defect risk)
    dict(id="PC-017", name="Aluminium adjustable laptop stand, foldable", category="electronics_accessories_non_electrical", weight="le_1kg",
         supplier_cost=D("150"), supplier_cost_range=("130", "170"), supplier_cost_note="IndiaMART Delhi/Surat: Rs 130-170 per piece",
         price=D("599"), retail_observed="Amazon.in deals seen at Rs 199 and Rs 385; Rs 599 needs a differentiated product (sturdier, height-adjustable)",
         gst_pct=D("18"), risks=["Observed deals are cheaper than Rs 599", "Sharp edges / finish quality"],
         sources=["https://m.indiamart.com/impcat/laptop-stands.html", "https://m.indiamart.com/apareal-computer/laptop-stand.html"]),
    dict(id="PC-018", name="Desk combo: aluminium laptop stand + phone stand", category="electronics_accessories_non_electrical", weight="le_2kg",
         supplier_cost=D("300"), supplier_cost_range=("240", "350"), supplier_cost_note="Laptop stand Rs 130-170 + phone stand Rs 110-179 (IndiaMART)",
         price=D("899"), retail_observed="UNVALIDATED", gst_pct=D("18"),
         risks=["Two suppliers = two parcels unless one stocks both", "Retail price not yet validated"],
         sources=["https://m.indiamart.com/impcat/laptop-stands.html", "https://m.indiamart.com/ismart-technology/mobile-stands.html"]),
]

def _load_inbox():
    """Candidates written by the research agent (research/inbox/*.json, one object or a list per file)."""
    import json
    from pathlib import Path
    out = []
    for f in sorted((Path(__file__).parent / "inbox").glob("*.json")):
        data = json.loads(f.read_text())
        for c in data if isinstance(data, list) else [data]:
            for k in ("supplier_cost", "price", "gst_pct"):
                if c.get(k) is not None:
                    c[k] = D(str(c[k]))
            c.setdefault("supplier_cost_range", None)
            c.setdefault("risks", [])
            c.setdefault("sources", [])
            c.setdefault("supplier_cost_note", "")
            c.setdefault("retail_observed", "")
            c["inbox_file"] = f.name
            out.append(c)
    return out


_known = {c["id"] for c in CANDIDATES}
CANDIDATES += [c for c in _load_inbox() if c["id"] not in _known]


def _apply_verdicts():
    """Review/CA verdicts for candidates defined in this file (research/reviews/<id>.json).

    Inbox candidates carry their verdicts inline; these overlay files let the review and CA agents
    record verdicts for the hand-written candidates above without editing Python."""
    import json
    from pathlib import Path
    by_id = {c["id"]: c for c in CANDIDATES}
    for f in sorted((Path(__file__).parent / "reviews").glob("*.json")):
        v = json.loads(f.read_text())
        c = by_id.get(v.get("id"))
        if c is None:
            continue
        for k in ("review", "ca"):
            if k in v:
                c[k] = v[k]
        if v.get("ca", {}).get("gst_pct_confirmed") is not None:
            c["gst_pct"] = D(str(v["ca"]["gst_pct_confirmed"]))


_apply_verdicts()

FEE_SOURCES = {
    "amazon_in": [
        "https://press.aboutamazon.com/in/2026/3/amazon-announces-zero-referral-fees-on-over-12-5-crore-products-sellers-to-save-up-to-70-in-fees",
        "https://www.sellership.in/blog/amazon-referral-fees-guide",
        "https://listingpilot.in/blog/amazon-seller-fees-india-2026/",
        "https://globalwebsters.com/amazon-price-calculator/",
        "https://novadata.io/resources/news/amazon-india-cancellation-closing-fees-august-2026",
    ],
    "flipkart": [
        "https://digitalterminal.in/amp/story/e-commerce/flipkart-unveils-zero-commission-model-for-products-under-1000-to-boost-seller-growth",
        "https://stories.flipkart.com/announcement/flipkart-expands-zero-commission-across-fashion-empowering-sellers-and-accelerating-the-growth-of-india-s-fashion-ecosystem",
        "https://swcybernetics.in/blog/flipkart-commission-rates-seller-fees-2026",
        "https://blooprint.in/blog/flipkart-seller-fees-explained/",
    ],
    "meesho": [
        "https://blooprint.in/blog/meesho-seller-fees-explained/",
        "https://www.ecomvanshika.com/blog/meesho-seller-fees-explained",
        "https://listiq.in/tools/meesho-fee-calculator",
    ],
    "shopify": [
        "https://razorpay.com/blog/razorpay-shopify-payment-gateway-pricing-explained/",
        "https://razorpay.com/blog/shopify-payment-gateway-cost-india/",
        "https://www.shiprocket.in/demo/ship-now/",
    ],
}

COMMON = dict(
    packaging=D("15"),                      # supplier pack/handling charge for drop-ship; negotiate
    supplier_credit_on_return_pct=D("50"),  # assume half of returns are resellable/credited; negotiate
)
