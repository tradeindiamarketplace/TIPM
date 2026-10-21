# Agent briefing to the owner (first cycle, 2026-10-21)

Each agent reports what it found, how sure it is, and what it needs from you. Numbers come from `reports/product-profit-report.md`. They are **estimates** from public web listings and third-party fee summaries, not supplier quotations or official fee cards.

---

### Agent A, Orchestrator: summary and exceptions

* **Store state:** live, 0 products, 0 orders, 6 empty collections. Old T-shirt/3D design exists only in the unpublished theme.
* **Pipeline:** 6 product candidates discovered. 0 suppliers verified. 0 approvals pending (nothing is ready for you to approve yet).
* **Exceptions:** (1) The website has no refund, shipping or terms policy. (2) The live home page makes claims ("verified makers only", "easy returns") that aren't true yet. (3) Marketplace seller-account status is still unknown.
* **Update 2026-10-21:** you confirmed GST registration in **Odisha**. Sourcing now prioritises Odisha suppliers for marketplace sales (see Agent J).
* **Needs from you:** answers to the 4 questions at the end of this briefing.

### Agent B, Product discovery: what's worth chasing

| Candidate | Retail seen | Verdict | Confidence |
|---|---|---|---|
| Microfiber cloth, 5-pack | ₹499–695 | **Best candidate**: light, cheap to ship, low returns | medium |
| Airtight PET jars, set of 6 | ₹449 | Possible if the supplier price is low; bulky to ship | medium |
| Copper bottle 1 L | ₹469–799 (Borosil ₹1,271+) | Only works at a higher price or a lower supplier cost; quality claims need proof | medium |
| Silicone tool set, 6 pcs | ₹144–244 | Retail price too low | medium |
| Pull-string chopper | ₹67 (one listing) | **Drop**: can't make money below ~₹290 even at a ₹0 supplier cost | high |
| Steel masala dabba | ₹495–556 | No supplier price found yet | low |

I found **no reliable sales-volume data** in public sources, so I won't give you a monthly revenue figure. Demand has to be measured in a pilot (or with marketplace tools once you have seller accounts).

### Agent C, Supplier sourcing: negotiation targets

The most a supplier can charge per unit (excl. GST) and still pass your thresholds at the proposed price:

| Product (price) | Lowest listing seen | Max cost: Website | Amazon | Flipkart | Meesho |
|---|---|---|---|---|---|
| Microfiber 5-pack (₹399) | ₹80 (₹16/pc) | ₹96 | **₹128** | ₹107 | ₹91 |
| PET jars ×6 (₹449) | ₹83 | ₹72 | **₹117** | ₹89 | ₹49 |
| Copper bottle (₹749) | ₹400 | ₹334 | **₹366** | ₹341 | ₹331 |
| Silicone set (₹299) | ₹70 | ₹19 | ₹47 | ₹34 | ₹13 |
| Chopper (₹199) | ₹35 | ₹0 | ₹0 | ₹0 | ₹0 |

**Odisha leads (unverified, from IndiaMART):** microfiber cloths in the Khordha/Bhubaneswar directory (350 GSM 40×60 cm at ₹38/pc, a bigger size than our 40×40); plastic containers from Joshna Polymers (Bhubaneswar), Subhalaxmi Plastics (Cuttack, manufacturer, kitchenware HSN 3924), Jagdamba Polymers (Balasore). No Odisha copper-bottle maker found yet.

IndiaMART prices are bulk prices with minimum order quantities. Single-piece drop-ship prices will usually be **higher**. No supplier is verified. A directory profile isn't proof. **Next step (needs your OK):** contact 3 microfiber and 3 PET-jar makers for written drop-ship quotes. No money is spent.

### Agent D, Finance: profit per order

* **Only one combination passes all your thresholds:** microfiber 5-pack on Amazon.in at ₹399, about **₹75 profit per order (24% margin)** in the base case. It is *fragile*: ₹29 if returns, ads and shipping run 20–50% worse.
* The same product gives ₹55 on Flipkart, ₹44 on your website and ₹40 on Meesho. Those are positive but below your ₹60 minimum. At ₹449 it would pass on every channel.
* **Why most products fail:** about ₹65–120 of shipping plus about ₹100–155 reverse shipping on returns is a fixed cost per order. On a ₹200–300 item that cost wipes out the margin. Aim for **₹399+ selling prices, under 500 g, low breakage**.
* Your own website pays about 4% in payment and Shopify fees plus about ₹60 of ads per order, because a new site has to buy its traffic. Marketplaces bring their own traffic.
* GST is excluded from revenue, and input GST is assumed recoverable. That needs GST registration.
* For illustration, 100 orders of the microfiber pack on Amazon ≈ ₹7,500 contribution, before fixed costs (Shopify plan, tools, your time). This is arithmetic, not a forecast.

### Agent E, Architect

The design is in docs/02. Ops service is the source of truth; Shopify and the marketplaces are channels behind adapters; gates live in code. No production changes were made.

### Agent F, Developer: what actually works

| Part | Status |
|---|---|
| Domain core, approvals, lifecycle gates, margin engine, orders, returns, settlement, audit log | **Implemented and tested** (28/28 tests pass, simulated) |
| Shopify adapter | **Partial**: payload checked against the live schema, never run against the store |
| Amazon.in, Flipkart | **Unavailable**: need seller accounts + API approval |
| Meesho | **Manual** CSV workflow |
| Database, HTTP API, dashboard UI | **Planned** (schema and API contract written) |

### Agent G, Design

The live Horizon theme already fits the new scope. Needed before launch: product image standards (white background, size chart, what's in the box) and policy pages.

### Agent H, Marketing

No campaigns proposed. Advertise only after a product passes in the conservative scenario. Assumed ad cost: ₹30/order on marketplaces, ₹60 on the website.

### Agent I, Pricing

Price floors (minimum viable price, base scenario): microfiber ₹380 (Amazon) / ₹405 (Flipkart) / ₹420 (website) / ₹427 (Meesho). Copper bottle ₹867+. Don't compete with ₹67 choppers.

### Agent J, Fulfilment

With an **Odisha GSTIN**, an extra pickup address can only be added inside Odisha. So:

* **Odisha supplier:** works on all four channels (their premises added as an APOB on your GSTIN and used as the marketplace pickup address).
* **Out-of-state supplier** (most IndiaMART sellers, in Gujarat or UP): probably fine for **your website** using "bill to – ship to" (CA to confirm). **Not usable for marketplace pickup** unless you register GST in that state too.

Start the pilot with one Odisha supplier. Details: docs/05.

### Agent K, QA

All 22 mandatory scenarios pass in simulation. Nothing has been tested against a live system yet. Next: a Shopify development store.

### Agent L, Support

There's no return/refund policy to point customers to yet. Draft needed (docs/01 M5).

### Agent M, Compliance

Before any listing: GST + HSN per SKU (confirm rates with a CA after the 2025 changes), Legal Metrology label on the pack, country of origin, evidence for claims (GSM, "pure copper", food-grade). For home appliances: BIS certification check. Keep that collection empty until then.

---

## Decisions for you

1. ~~GST~~ Answered: registered in Odisha.
   **New:** please ask your CA the 3 questions in docs/05 (supplier premises as an extra place of business, bill-to-ship-to, HSN/rates).
2. **Accounts:** do Amazon.in / Flipkart / Meesho seller accounts exist?
3. **Thresholds:** keep ₹60 minimum profit/order, 12% margin, ₹80 max ad cost?
4. **Quotes:** may Agent C request written drop-ship quotes, **Odisha suppliers first**, for **microfiber cloth packs** (target ≤ ₹128 for 5) and **storage jars** (target ≤ ₹117 for 6), plus the copper bottle at ≤ ₹360? No money is committed.
