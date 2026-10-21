"""Channel adapters. Each declares an honest IntegrationStatus that the dashboard shows."""
from __future__ import annotations

import csv
import io
from typing import Any, Callable

from ..domain import ChannelListing, CustomerOrder, IntegrationStatus, Product, Shipment


class AdapterError(Exception):
    """Transient failure (timeout, 5xx, rate limit). Safe to retry."""


class ChannelAdapter:
    channel: str
    status: IntegrationStatus
    capabilities: dict[str, str]           # operation -> "api" | "manual" | "none"

    def publish_listing(self, listing: ChannelListing, product: Product) -> str | None: ...
    def update_price(self, listing: ChannelListing) -> None: ...
    def pause_listing(self, listing: ChannelListing) -> None: ...
    def acknowledge_order(self, order: CustomerOrder) -> None: ...
    def push_tracking(self, order: CustomerOrder, shipment: Shipment) -> None: ...
    def cancel_order(self, order: CustomerOrder, reason: str) -> None: ...


class SimulatedChannelAdapter(ChannelAdapter):
    """Test double. Never used against a real seller account."""
    status = IntegrationStatus.SIMULATED

    def __init__(self, channel: str):
        self.channel = channel
        self.capabilities = {op: "api" for op in ("publish", "price", "pause", "orders", "tracking", "cancel")}
        self.remote_listings: dict[str, dict] = {}   # keyed by our listing id => idempotent publish
        self.calls: list[tuple[str, str]] = []
        self._fail_next = 0

    def fail_next(self, n: int) -> None:
        self._fail_next = n

    def _call(self, op: str, ref: str) -> None:
        self.calls.append((op, ref))
        if self._fail_next:
            self._fail_next -= 1
            raise AdapterError(f"simulated outage during {op}")

    def publish_listing(self, listing, product):
        self._call("publish", listing.id)
        entry = self.remote_listings.setdefault(listing.id, {"external_id": f"{self.channel}-{len(self.remote_listings) + 1}"})
        entry.update(price=listing.price_incl_gst, active=True)
        return entry["external_id"]

    def update_price(self, listing):
        self._call("price", listing.id)
        self.remote_listings[listing.id]["price"] = listing.price_incl_gst

    def pause_listing(self, listing):
        self._call("pause", listing.id)
        self.remote_listings[listing.id]["active"] = False

    def acknowledge_order(self, order):
        self._call("ack", order.external_order_id)

    def push_tracking(self, order, shipment):
        self._call("tracking", f"{order.external_order_id}:{shipment.tracking_number}")

    def cancel_order(self, order, reason):
        self._call("cancel", order.external_order_id)


class ManualExportAdapter(ChannelAdapter):
    """For channels without an API we can use (Meesho by default): produces an upload file.
    The listing stays AWAITING_MANUAL_UPLOAD until the owner confirms the upload."""
    status = IntegrationStatus.MANUAL

    def __init__(self, channel: str, columns: list[str]):
        self.channel = channel
        self.columns = columns
        self.capabilities = {"publish": "manual", "price": "manual", "pause": "manual", "orders": "manual",
                             "tracking": "manual", "cancel": "manual"}
        self.exports: list[str] = []
        self.manual_tasks: list[str] = []

    def publish_listing(self, listing, product):
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=["sku", "price_incl_gst", *self.columns], extrasaction="ignore")
        w.writeheader()
        w.writerow({"sku": listing.sku, "price_incl_gst": str(listing.price_incl_gst), **listing.attributes})
        self.exports.append(buf.getvalue())
        return None

    def _task(self, text: str) -> None:
        self.manual_tasks.append(text)

    def update_price(self, listing):
        self._task(f"Change price of {listing.sku} on {self.channel} to {listing.price_incl_gst}")

    def pause_listing(self, listing):
        self._task(f"Deactivate {listing.sku} on {self.channel}")

    def acknowledge_order(self, order):
        self._task(f"Accept order {order.external_order_id} in the {self.channel} panel")

    def push_tracking(self, order, shipment):
        self._task(f"Enter tracking {shipment.tracking_number} for {order.external_order_id}")

    def cancel_order(self, order, reason):
        self._task(f"Cancel {order.external_order_id} on {self.channel}: {reason}")


class UnavailableAdapter(ChannelAdapter):
    """Seller account / API approval not in place yet. Every call refuses."""
    status = IntegrationStatus.UNAVAILABLE

    def __init__(self, channel: str, reason: str):
        self.channel = channel
        self.reason = reason
        self.capabilities = {}

    def __getattribute__(self, name: str):
        if name in {"publish_listing", "update_price", "pause_listing", "acknowledge_order",
                    "push_tracking", "cancel_order"}:
            raise AdapterError(f"{object.__getattribute__(self, 'channel')} unavailable: "
                               f"{object.__getattribute__(self, 'reason')}")
        return object.__getattribute__(self, name)


class ShopifyAdapter(ChannelAdapter):
    """TradeIndiaMarketplace.com via the Shopify Admin GraphQL API.

    PARTIAL: payloads are built and unit-tested against a fake transport. It has not
    been run against the live store, by design: nothing is published without approval.
    `transport(query, variables) -> dict` is injected (an Admin API client in production).
    """
    status = IntegrationStatus.PARTIAL

    PRODUCT_SET = """mutation productSet($input: ProductSetInput!, $identifier: ProductSetIdentifiers) {
  productSet(input: $input, identifier: $identifier, synchronous: true) {
    product { id status }
    userErrors { field message }
  }
}"""

    PRODUCT_UPDATE = """mutation productUpdate($product: ProductUpdateInput!) {
  productUpdate(product: $product) {
    product { id status }
    userErrors { field message }
  }
}"""

    # Field names checked against the Admin GraphQL schema (productSet, ProductSetInput,
    # ProductVariantSetInput, ProductSetIdentifiers) on 2026-10-21. ACTIVE alone does not show the
    # product on the Online Store: publishablePublish to that publication is still to be added.

    def __init__(self, transport: Callable[[str, dict], dict]):
        self.channel = "shopify"
        self.transport = transport
        self.capabilities = {"publish": "api", "price": "api", "pause": "api", "orders": "webhook",
                             "tracking": "api", "cancel": "api"}

    def _run(self, query: str, variables: dict) -> dict:
        try:
            res = self.transport(query, variables)
        except TimeoutError as e:
            raise AdapterError(str(e)) from e
        payload = next(iter(res.get("data", {}).values()), {}) or {}
        if res.get("errors") or payload.get("userErrors"):
            raise ValueError(f"Shopify rejected request: {res.get('errors') or payload.get('userErrors')}")
        return payload

    def product_input(self, listing: ChannelListing, product: Product, status: str = "ACTIVE") -> dict[str, Any]:
        a = listing.attributes
        return {
            "title": a["title"],
            "descriptionHtml": a["description"],
            "vendor": a["vendor"],
            "productType": a["product_type"],
            "status": status,
            "handle": f"timp-{listing.sku.lower()}",
            "productOptions": [{"name": "Title", "values": [{"name": "Default Title"}]}],
            "variants": [{"optionValues": [{"optionName": "Title", "name": "Default Title"}],
                          "sku": listing.sku, "price": str(listing.price_incl_gst)}],
            "metafields": [
                {"namespace": "timp", "key": "product_id", "type": "single_line_text_field", "value": product.id},
                {"namespace": "timp", "key": "hsn_code", "type": "single_line_text_field", "value": a["hsn_code"]},
                {"namespace": "timp", "key": "country_of_origin", "type": "single_line_text_field",
                 "value": a["country_of_origin"]},
            ],
        }

    def publish_listing(self, listing, product):
        # Upsert keyed by handle => a retry after a timeout cannot create a duplicate product.
        out = self._run(self.PRODUCT_SET, {"input": self.product_input(listing, product),
                                           "identifier": {"handle": f"timp-{listing.sku.lower()}"}})
        return out["product"]["id"]

    def pause_listing(self, listing):
        # productUpdate touches only the given fields; productSet would reconcile list fields.
        self._run(self.PRODUCT_UPDATE, {"product": {"id": listing.external_id, "status": "DRAFT"}})

    def update_price(self, listing):
        raise NotImplementedError("planned: productVariantsBulkUpdate")

    def acknowledge_order(self, order):
        pass   # Shopify orders need no acceptance; fulfilment orders are created on dispatch

    def push_tracking(self, order, shipment):
        raise NotImplementedError("planned: fulfillmentCreate with trackingInfo")

    def cancel_order(self, order, reason):
        raise NotImplementedError("planned: orderCancel")
