# Product recommendations

Ranked by expected profit per order (base scenario). Minimum 30% margin and Rs 60 per order; hard rules in `config/product_policy.toml`. All supplier costs and fees are estimates until quotations and fee cards are verified.

| Stage | Product | Best channel | Price | Profit/order | Margin | Worse case | Channels ≥ target | Why |
|---|---|---|---|---|---|---|---|---|
| AWAITING_REVIEW | Desk combo: aluminium laptop stand + phone stand | Amazon.in (Easy Ship) | Rs 899 | Rs 215 | 30.7% | Rs 146 | amazon_in | profit target met; waiting for the review agent · retail price unvalidated |
| AWAITING_REVIEW | Microfiber cleaning cloth 40x40 cm, 350 GSM, pack of 10 | Amazon.in (Easy Ship) | Rs 699 | Rs 181 | 33.2% | Rs 127 | amazon_in, flipkart, meesho | profit target met; waiting for the review agent |
| AWAITING_REVIEW | Aluminium adjustable laptop stand, foldable | Amazon.in (Easy Ship) | Rs 599 | Rs 160 | 34.3% | Rs 105 | amazon_in | profit target met; waiting for the review agent |
| AWAITING_REVIEW | Makeup brush set 13 pcs with storage pouch | Amazon.in (Easy Ship) | Rs 449 | Rs 116 | 33.3% | Rs 69 | amazon_in | profit target met; waiting for the review agent · retail price unvalidated |
| AWAITING_REVIEW | Microfiber cleaning cloth 40x40 cm, 350 GSM, pack of 5 (at Rs 449) | Amazon.in (Easy Ship) | Rs 449 | Rs 114 | 32.6% | Rs 67 | amazon_in | profit target met; waiting for the review agent |
| BELOW_TARGET | Wardrobe + fridge organiser combo (12 saree covers + 6 fridge bags) | Amazon.in (Easy Ship) | Rs 899 | Rs 221 | 29.9% | Rs 151 | - | no channel reaches 30% margin |
| BELOW_TARGET | Hair claw clips, pack of 12 | Amazon.in (Easy Ship) | Rs 449 | Rs 95 | 27.2% | Rs 48 | - | no channel reaches 30% margin · retail price unvalidated |
| BELOW_TARGET | Kids stainless steel insulated lunch box (3 containers) | Amazon.in (Easy Ship) | Rs 599 | Rs 94 | 19.1% | Rs 40 | - | no channel reaches 30% margin · retail price unvalidated |
| BELOW_TARGET | Non-woven saree / clothes cover organisers, set of 12 | Amazon.in (Easy Ship) | Rs 549 | Rs 81 | 17.9% | Rs 28 | - | no channel reaches 30% margin |
| BELOW_TARGET | Airtight PET kitchen storage jars, set of 6 (~1 L) | Amazon.in (Easy Ship) | Rs 449 | Rs 34 | 9.7% | Rs -23 | - | no channel reaches 30% margin |
| BELOW_TARGET | Pure copper water bottle 1 L | Amazon.in (Easy Ship) | Rs 749 | Rs -11 | -1.9% | Rs -65 | - | no channel reaches 30% margin |
| REJECTED | Microfiber cleaning cloth 40x40 cm, 350 GSM, pack of 5 | Amazon.in (Easy Ship) | Rs 399 | Rs 75 | 24.1% | Rs 29 | - | price below Rs 449 |
| REJECTED | Makeup brush set, 13 pieces | Amazon.in (Easy Ship) | Rs 299 | Rs 30 | 13.0% | Rs -13 | - | price below Rs 449 · retail price unvalidated |
| REJECTED | Korean-style hair claw clips, set of 6 | Amazon.in (Easy Ship) | Rs 249 | Rs 8 | 4.0% | Rs -34 | - | price below Rs 449 · retail price unvalidated |
| REJECTED | Silicone spatula / cooking tool set, 6 pieces | Amazon.in (Easy Ship) | Rs 299 | Rs -10 | -4.3% | Rs -52 | - | price below Rs 449 |
| REJECTED | Manual pull-string vegetable chopper, 500 ml | Amazon.in (Easy Ship) | Rs 199 | Rs -10 | -6.5% | Rs -50 | - | price below Rs 449 · retail price unvalidated |
| REJECTED | Cotton fridge vegetable storage bags, set of 6 | Amazon.in (Easy Ship) | Rs 199 | Rs -61 | -35.0% | Rs -101 | - | price below Rs 449 |
| REJECTED | Stainless steel masala dabba, 7 containers | - | Rs 549 | - | - | - | - | no supplier cost yet |
