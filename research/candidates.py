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
        sources=[
            "https://www.indiamart.com/skenterprisegujarat/microfiber-cleaning-cloth.html",
            "https://m.indiamart.com/impcat/microfiber-cloths.html",
            "https://shop.globalbees.com/products/kuber-industries-multi-utility-microfiber-duster-1000000131187",
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
        risks=["Bulky: volumetric weight drives shipping", "Breakage / cracked lids in transit",
               "Food-contact material evidence needed"],
        sources=[
            "https://m.indiamart.com/eniver-mart/fish-container.html",
            "https://m.indiamart.com/dynamicplastic/plastic-storage-containers.html",
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
]

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
