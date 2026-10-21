# Storefront (Shopify) — what is deployed and how

Store: www.tradeindiamarketplace.com (zx4uui-5c.myshopify.com)

## Deployed live on 2026-10-21 (via Shopify Admin API)

| Change | Where | Live? |
|---|---|---|
| Pages: How we work, Returns & refunds, Shipping policy, Terms of service | /pages/how-we-work, /pages/refund-policy, /pages/shipping-policy, /pages/terms-of-service | **Yes** |
| Contact page: address, phone, email, grievance officer | /pages/contact | **Yes** |
| Main menu: Home, Shop all, How we work, Help ▸ (Shipping, Returns, Terms, Contact) | header | **Yes** |
| Footer menus updated with policy pages | footer / timp-footer-help | **Yes** |
| Product fields: timp.hsn_code, timp.country_of_origin, timp.manufacturer_details, timp.product_id | Settings > Custom data > Products | **Yes** |
| Marketplace-style homepage + search bar + category strip + product cards with MRP/% off | theme "Horizon - TIMP v3 (ready to publish)" | **Ready, not live**: publish it (below) |

## Files here = files in the theme

```
theme/sections/timp-market-bar.liquid    big search bar, account/orders/cart, category strip (under the Horizon header)
theme/sections/timp-market-home.liquid   offer banners, category cards, trust strip, product rows (hide when empty)
theme/snippets/timp-card.liquid          product card: image, title, price, M.R.P. strike-through, % off, availability
theme/sections/timp-home.liquid          previous homepage section, kept (claims aligned with policies)
theme/sections/header-group.json         announcement text + market bar added under the header
theme/templates/index.json               homepage uses timp-market-home
policies/*.html, pages/*.html            page content as deployed
backups/                                 state before deployment, and how to roll back
```

## Publishing the new design (one click, owner only)

Shopify admin > Online Store > Themes > "Horizon - TIMP v3 (ready to publish)" > **Publish**.
Preview first: Customize, or `https://www.tradeindiamarketplace.com/?preview_theme_id=168012972197`.
Roll back: publish "Horizon" again (it is unchanged).

## Git → Shopify auto-deploy

`.github/workflows/ci-deploy.yml`: every push to `main` runs the tests, then `shopify theme push` uploads
`site/theme/` to the theme (default id 168012972197, override with the `SHOPIFY_THEME_ID` variable).
After you publish v3, that theme is the live one, so a push updates the live site.

One-time setup:
1. Shopify admin > Apps > install **Theme Access** (free, by Shopify) > create a password for your email.
2. GitHub repo > Settings > Secrets and variables > Actions > New secret `SHOPIFY_CLI_THEME_TOKEN` = that password.
3. GitHub repo > Settings > Environments > create `production` (optionally require your approval before deploys).

Rule: edit files in `site/theme/` in git, not in the Shopify theme editor; the next push overwrites editor changes
to those files. All other theme files and settings can still be edited in Shopify.

## Not possible from this session (do in Shopify admin)

* Official policy slots (Settings > Policies): the connection lacks `write_legal_policies`. Paste `policies/*.html`
  into Refund, Shipping, Terms of service and Contact information; they then also appear at checkout.
* Publishing a theme and editing the live theme directly are blocked for safety.
* Location address (Settings > Locations), payment gateway (Settings > Payments: Razorpay/PayU/Cashfree), shipping rates.
