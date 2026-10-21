# 01 · Current-state audit and obsolete-feature inventory

Audit date: 2026-10-21. Method: read-only Shopify Admin GraphQL queries through the connected Shopify app. **Nothing in the store was changed.**

## What exists today

| Area | Finding |
|---|---|
| Store | "Trade India Market Place", `www.tradeindiamarketplace.com`, Shopify **Basic** plan, INR, IST, billing address Angul, Odisha. Prices are set tax-inclusive (`taxesIncluded: true`). |
| Products | **0** products. |
| Orders | **0** orders. |
| Customers | 3 accounts (created 8–14 Oct 2026), none with orders. |
| Collections | 6, all empty: Home page (frontpage), Kitchen Organisation, Home Storage, Cleaning & Utility, Festive Offers (rule: tag = `festive`), Home Appliances (rule: tag `home-appliances` OR type `Home Appliance`). |
| Navigation | `main-menu` (Home, Catalog, Contact), `footer` (Search), customer account menu, **`timp-main-menu`** (Home Appliances with 4 sub-collections, Festive Offers, Contact), **`timp-footer-help`** (Contact, Bulk & custom orders, Track my order, Search, Shop all). |
| Pages | 1: Contact (published). |
| Policies | **Only a privacy policy.** No refund, shipping, terms of service or contact-information policy. |
| Themes | **Horizon** (live) already carries the new home-and-kitchen, supplier-direct positioning (`sections/timp-home.liquid`). **TIMP Designer v2** (unpublished) is the old 3D-printing and clothing design. |
| Sales channels | Online Store, Point of Sale. No marketplace channel apps are installed. |
| Apps | Shopify Messaging, Shopify Claude Connector. No payment, shipping (Shiprocket etc.), review or marketplace-connector apps were visible. |
| Data model | No product metafield or metaobject definitions, no discounts, no webhook subscriptions. |
| Locations | 1 location, "Shop location", fulfils online orders, **no address set**. |
| Other systems | No repository, hosting, database or marketplace seller accounts were available to this session. Amazon, Flipkart and Meesho seller-account status is **unknown**. |

## Obsolete features (3D printing and clothing)

All of these are in the **unpublished** theme "TIMP Designer v2". None is in the live theme.

| Item | Location | What it does |
|---|---|---|
| `sections/timp-tshirt-designer.liquid` (32 KB) | TIMP Designer v2 | Interactive T-shirt designer |
| `templates/product.tshirt-designer.json` | TIMP Designer v2 | Product template using the designer, "180 GSM premium cotton" copy |
| `templates/product.design-addon.json` + `sections/timp-redirect.liquid` | TIMP Designer v2 | Redirects to `/products/custom-printed-t-shirt` |
| `templates/index.json` hero, categories, features, steps, CTA | TIMP Designer v2 | Custom T-shirts, "2D & 3D Shapes", STL/OBJ uploads, figurines |
| Links to `/collections/custom-printed-t-shirts`, `/collections/2d-3d-shapes`, `/collections/print-designs`, `/products/custom-printed-t-shirt` | TIMP Designer v2 | These collections and products **no longer exist** in the store (dead links) |
| Shop images (t-shirt, 3D photos) referenced by that theme | Files | Kept until the theme is deleted |

Reusable from TIMP Designer v2: `timp-categories`, `timp-usp`, `timp-steps`, `timp-cta`, `timp-feature`, `timp-footer` sections. They are generic and can be re-pointed at home-and-kitchen collections.

## Issues on the live site to fix before launch

1. **Claims run ahead of reality.** The live home page says "Verified makers only", "Ships from the source", "Honest delivery dates", "Easy returns" and "worldwide delivery rolling out". No supplier is verified, no return policy exists, and nothing has been checked for international shipping. Keep the copy, but launch only once those claims are true, or soften it now. Consumer-protection rules treat unsupported claims seriously.
2. **No refund, shipping or terms policies.** Marketplaces and the Consumer Protection (E-Commerce) Rules, 2020 expect clear seller details, return/refund terms and a grievance contact.
3. **"Home Appliances" collection.** Many electrical appliances fall under BIS compulsory certification (Quality Control Orders). It should stay empty until Agent M has a category-by-category BIS check (see docs/11).
4. **The location has no address.** It is needed for invoices, GST place of supply and pickups.
5. **Two parallel main menus.** Confirm which one the Horizon header uses and retire the other.
6. **No payment gateway was visible** to this audit. Shopify Payments is not offered in India, so a third-party gateway is needed (Razorpay/PayU/Cashfree), and Shopify charges an extra transaction fee on top on Basic.

## Migration and backup plan (needs owner authorisation)

Nothing destructive has been done. Proposed steps, each needing a `DESTRUCTIVE_CHANGE` approval:

| Step | Action | Backup first | Rollback |
|---|---|---|---|
| M1 | Duplicate "TIMP Designer v2" (Shopify: Themes, Duplicate) and download it (Themes, Download theme file). | Theme zip emailed to the owner | Re-upload the zip |
| M2 | Delete the "TIMP Designer v2" theme. | M1 | Re-upload |
| M3 | Delete unused shop images (t-shirt, 3D). | Export the file list and download the images | Re-upload |
| M4 | Retire `main-menu` or `timp-main-menu` (whichever the header doesn't use). | Export the menu JSON via the Admin API | Recreate from JSON |
| M5 | Add refund, shipping, terms and contact policies (non-destructive). | none | Edit |
| M6 | Set the location address (non-destructive). | none | Edit |

The live Horizon theme needs no removal work: it already reflects the new scope.
