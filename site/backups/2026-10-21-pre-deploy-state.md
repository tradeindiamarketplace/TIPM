# Store state before the 2026-10-21 deployment (for rollback)

* Live theme: Horizon (gid://shopify/OnlineStoreTheme/167565983909). Not modified by this deployment.
* main-menu (gid://shopify/Menu/274244141221) items: Home (FRONTPAGE, /), Catalog (CATALOG, /collections/all),
  Contact (PAGE, /pages/contact, gid://shopify/Page/166436962469).
* Policies: only PRIVACY_POLICY existed (not modified). REFUND_POLICY, SHIPPING_POLICY, TERMS_OF_SERVICE,
  CONTACT_INFORMATION were empty.
* Pages: Contact only.
* Product metafield definitions: none.

Rollback: restore main-menu to the three items above; clear the four policy bodies; unpublish/delete the
"How we work" page; delete the timp.* metafield definitions (no products use them yet); delete the
"Horizon - TIMP v3" theme copy if not published.
