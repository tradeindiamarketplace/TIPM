# 13 · Product photos: the exact product, legally

**Rule:** every photo on a listing shows the exact item the supplier will ship: same model, size, colour, pack count and packaging. No AI-generated product photos, and no photos copied from other sellers or marketplaces.

Why:
* **Returns and complaints.** "Item not as shown" is a top return reason, and it erodes the margin (docs/07).
* **Law and platform rules.** Misleading product images count as a misleading representation under the Consumer Protection Act, 2019 and the E-Commerce Rules, 2020. Amazon and Flipkart flag reused images, and reused images can trigger copyright takedowns.
* **Copyright.** Photos on IndiaMART, Amazon and Flipkart belong to whoever took them. You may use a supplier's photos only with their written permission.

## Where photos come from (in order of preference)

1. **Supplier's own photos, with written permission** (ask while requesting the quotation: template below). Most manufacturers supply catalogue images to resellers.
2. **Your own photos of a sample.** You need a sample anyway, to check quality. A phone, a white sheet and daylight are enough.
3. **A local product photographer** in Bhubaneswar or Cuttack: typically per-product pricing; get quotes.

AI tools are fine for **banners and backgrounds that don't depict the product**, such as the colour bands on the homepage, but never for the product itself.

## Photo checklist per product (Agent G checks before publish)

| # | Shot | Notes |
|---|---|---|
| 1 | Main image | Product only, pure white background, fills ~85% of the frame |
| 2 | Everything in the pack | All pieces laid out ("pack of 10" shows all 10) |
| 3 | Size reference | Ruler, or held in a hand |
| 4 | Close-up of material / texture | GSM, steel finish, bristles |
| 5 | In use / lifestyle | Kitchen, wardrobe, bathroom |
| 6 | Pack label | Shows MRP, net quantity, manufacturer/packer and country of origin (Legal Metrology) |

Specs: JPG or PNG, at least **1000 × 1000 px** (Amazon zoom needs ≥ 1000 px on the longest side; 2000 × 2000 is better), square, sRGB, under 5 MB, no watermarks, no text claims on the main image.

## Message to send suppliers (with the quotation request)

> Namaste. We sell home and kitchen products on our own website (tradeindiamarketplace.com) and on Indian marketplaces, using drop-shipping: you ship single orders directly to our customers with our invoice.
>
> For **[product, size, pack count]**, please share:
> 1. Your price per piece for single-piece drop-ship orders (excl. GST), and for 10 / 50 / 100 units per month.
> 2. Dispatch time after an order, pickup location (city, PIN), and courier tracking.
> 3. How returns and damaged items are handled.
> 4. Your GSTIN, and test reports or certificates for any claims (material, GSM, food grade).
> 5. **Product photos of exactly this item** (white background, all pieces, close-ups, pack label), at least 1000 × 1000 px, **and written permission** for TradeIndia Marketplace to use them on our website and marketplace listings.
>
> We can also order one paid sample to check quality.
>
> Thank you,
> Trade India Market Place, Angul, Odisha · tradeindiamarketplace@gmail.com · +91 801 841 6106

## How photos reach the store

* **Shopify:** upload in the product's *Media* section (or give Claude public HTTPS image URLs and they can be attached with the product). The theme's cards and product page use `product.featured_image` and the media gallery automatically.
* **Preview artifact:** add URLs to `photos` on the product in `site/preview/storefront-preview.html`. The card shows the real photo instead of the illustration.
* Keep the supplier's permission email or WhatsApp message as evidence. The compliance check `PRODUCT_CLAIMS_REVIEW` should reference it.
