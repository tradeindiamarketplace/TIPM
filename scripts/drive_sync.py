"""Google Drive -> Shopify product photo sync (runs from .github/workflows/sync-product-images.yml).

Drive layout (the script creates the category folders on first run):

    TradeIndia Marketplace - Product Images/        <- root folder you share with the service account
      Cleaning/
        cover.jpg                                   <- optional: becomes the collection image
        MF-10 Microfiber cloths pack of 10/         <- product folder: SKU first, then any name
          1.jpg 2.jpg ...                           <- photos, in name order; 1.jpg is the main image
      Home storage/ ...

For every product folder the script finds the Shopify product whose variant SKU matches, uploads
photos it hasn't uploaded before (tracked by Drive file id in the product metafield
timp.drive_image_ids) and never deletes anything. Products are never created here: a folder
with no matching product is reported, because products go live only through owner approval.

Env: GOOGLE_SERVICE_ACCOUNT_JSON, DRIVE_ROOT_FOLDER_ID, SHOPIFY_STORE (xxx.myshopify.com),
     SHOPIFY_ADMIN_TOKEN (custom app: read/write_products, write_files). DRY_RUN=1 to only report.
"""
from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field

CATEGORY_FOLDERS = {
    "Cleaning": "cleaning-utility",
    "Home storage": "home-storage",
    "Kitchen": "kitchen-organisation",
    "Women's accessories": "womens-accessories",
    "Beauty": "beauty",
    "Kids": "kids",
    "Electronics accessories": "electronics-accessories",
    "Home appliances": "home-appliances",
    "Festive offers": "festive-offers",
}
IMAGE_MIME = {"image/jpeg", "image/png", "image/webp"}
SKU_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)\b")


@dataclass
class DriveImage:
    id: str
    name: str
    mime: str


@dataclass
class ProductFolder:
    category: str
    sku: str
    folder_name: str
    images: list[DriveImage] = field(default_factory=list)


@dataclass
class ShopifyProduct:
    id: str
    title: str
    synced_ids: set[str]


def plan(folders: list[ProductFolder], products_by_sku: dict[str, ShopifyProduct]) -> dict:
    """Pure planning step: what to upload where. Unit-tested in tests/test_drive_sync.py."""
    uploads, unmatched, up_to_date = [], [], []
    for f in folders:
        p = products_by_sku.get(f.sku.upper())
        if not p:
            unmatched.append(f"{f.category}/{f.folder_name}")
            continue
        new = [i for i in sorted(f.images, key=lambda i: _natural(i.name))
               if i.mime in IMAGE_MIME and i.id not in p.synced_ids]
        if new:
            uploads.append((p, f, new))
        else:
            up_to_date.append(p.title)
    return {"uploads": uploads, "unmatched": unmatched, "up_to_date": up_to_date}


def _natural(name: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", name)]


def parse_sku(folder_name: str) -> str | None:
    m = SKU_RE.match(folder_name.strip())
    return m.group(1).upper() if m else None


# ----------------------------------------------------------------------------- Google Drive
class Drive:
    API = "https://www.googleapis.com/drive/v3"

    def __init__(self, session):
        self.s = session

    @classmethod
    def from_env(cls):
        from google.oauth2 import service_account
        from google.auth.transport.requests import AuthorizedSession
        info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
        creds = service_account.Credentials.from_service_account_info(
            info, scopes=["https://www.googleapis.com/auth/drive"])
        return cls(AuthorizedSession(creds))

    def children(self, folder_id: str) -> list[dict]:
        out, token = [], None
        while True:
            r = self.s.get(f"{self.API}/files", params={
                "q": f"'{folder_id}' in parents and trashed = false",
                "fields": "nextPageToken, files(id, name, mimeType)", "pageSize": 1000,
                "supportsAllDrives": True, "includeItemsFromAllDrives": True, "pageToken": token})
            r.raise_for_status()
            j = r.json()
            out += j.get("files", [])
            token = j.get("nextPageToken")
            if not token:
                return out

    def ensure_folder(self, parent: str, name: str, existing: list[dict]) -> str:
        for f in existing:
            if f["mimeType"] == "application/vnd.google-apps.folder" and f["name"] == name:
                return f["id"]
        r = self.s.post(f"{self.API}/files", params={"supportsAllDrives": True},
                        json={"name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent]})
        r.raise_for_status()
        return r.json()["id"]

    def download(self, file_id: str) -> bytes:
        r = self.s.get(f"{self.API}/files/{file_id}", params={"alt": "media", "supportsAllDrives": True})
        r.raise_for_status()
        return r.content

    def scan(self, root: str, create_missing: bool) -> tuple[list[ProductFolder], dict[str, DriveImage]]:
        top = self.children(root)
        folders, covers = [], {}
        for cat in CATEGORY_FOLDERS:
            cid = self.ensure_folder(root, cat, top) if create_missing else next(
                (f["id"] for f in top if f["name"] == cat), None)
            if not cid:
                continue
            for item in self.children(cid):
                if item["mimeType"] == "application/vnd.google-apps.folder":
                    sku = parse_sku(item["name"])
                    if not sku:
                        continue
                    imgs = [DriveImage(i["id"], i["name"], i["mimeType"]) for i in self.children(item["id"])]
                    folders.append(ProductFolder(cat, sku, item["name"], imgs))
                elif item["name"].lower().startswith("cover.") and item["mimeType"] in IMAGE_MIME:
                    covers[cat] = DriveImage(item["id"], item["name"], item["mimeType"])
        return folders, covers


# ----------------------------------------------------------------------------- Shopify
class Shopify:
    VERSION = "2025-10"

    def __init__(self, store: str, token: str):
        import requests
        self.url = f"https://{store}/admin/api/{self.VERSION}/graphql.json"
        self.s = requests.Session()
        self.s.headers.update({"X-Shopify-Access-Token": token, "Content-Type": "application/json"})

    def gql(self, query: str, variables: dict | None = None) -> dict:
        r = self.s.post(self.url, json={"query": query, "variables": variables or {}}, timeout=60)
        r.raise_for_status()
        j = r.json()
        if j.get("errors"):
            raise RuntimeError(j["errors"])
        return j["data"]

    def product_by_sku(self, sku: str) -> ShopifyProduct | None:
        d = self.gql("""query($q: String!) { productVariants(first: 1, query: $q) { nodes { sku product { id title
            metafield(namespace: "timp", key: "drive_image_ids") { value } } } } }""", {"q": f"sku:{sku}"})
        nodes = [n for n in d["productVariants"]["nodes"] if (n["sku"] or "").upper() == sku.upper()]
        if not nodes:
            return None
        p = nodes[0]["product"]
        ids = set(json.loads(p["metafield"]["value"])) if p["metafield"] else set()
        return ShopifyProduct(p["id"], p["title"], ids)

    def staged_upload(self, filename: str, mime: str, data: bytes) -> str:
        d = self.gql("""mutation($input: [StagedUploadInput!]!) { stagedUploadsCreate(input: $input) {
            stagedTargets { url resourceUrl parameters { name value } } userErrors { field message } } }""",
                     {"input": [{"filename": filename, "mimeType": mime, "resource": "IMAGE", "httpMethod": "POST"}]})
        t = d["stagedUploadsCreate"]["stagedTargets"][0]
        import requests
        form = {p["name"]: p["value"] for p in t["parameters"]}
        r = requests.post(t["url"], data=form, files={"file": (filename, data, mime)}, timeout=120)
        r.raise_for_status()
        return t["resourceUrl"]

    def add_media(self, product_id: str, sources: list[tuple[str, str]]) -> None:
        d = self.gql("""mutation($product: ProductUpdateInput!, $media: [CreateMediaInput!]) {
            productUpdate(product: $product, media: $media) { product { id } userErrors { field message } } }""",
                     {"product": {"id": product_id},
                      "media": [{"originalSource": src, "mediaContentType": "IMAGE", "alt": alt} for src, alt in sources]})
        if d["productUpdate"]["userErrors"]:
            raise RuntimeError(d["productUpdate"]["userErrors"])

    def set_synced(self, product_id: str, ids: set[str]) -> None:
        d = self.gql("""mutation($m: [MetafieldsSetInput!]!) { metafieldsSet(metafields: $m) { userErrors { field message } } }""",
                     {"m": [{"ownerId": product_id, "namespace": "timp", "key": "drive_image_ids", "type": "json",
                             "value": json.dumps(sorted(ids))}]})
        if d["metafieldsSet"]["userErrors"]:
            raise RuntimeError(d["metafieldsSet"]["userErrors"])

    def set_collection_image(self, handle: str, src: str, alt: str) -> bool:
        d = self.gql("""query($h: String!) { collectionByIdentifier(identifier: {handle: $h}) { id image { url } } }""",
                     {"h": handle})
        c = d["collectionByIdentifier"]
        if not c or c["image"]:
            return False          # only fills an empty collection image; never overwrites
        self.gql("""mutation($i: CollectionInput!) { collectionUpdate(input: $i) { userErrors { message } } }""",
                 {"i": {"id": c["id"], "image": {"src": src, "altText": alt}}})
        return True


def main() -> int:
    dry = os.environ.get("DRY_RUN") == "1"
    drive = Drive.from_env()
    shop = Shopify(os.environ["SHOPIFY_STORE"], os.environ["SHOPIFY_ADMIN_TOKEN"])
    folders, covers = drive.scan(os.environ["DRIVE_ROOT_FOLDER_ID"], create_missing=not dry)
    products = {f.sku: p for f in folders if (p := shop.product_by_sku(f.sku))}
    pl = plan(folders, products)
    for p, f, new in pl["uploads"]:
        print(f"{'WOULD UPLOAD' if dry else 'UPLOAD'} {len(new)} photo(s) -> {p.title} ({f.sku})")
        if dry:
            continue
        srcs = [(shop.staged_upload(i.name, i.mime, drive.download(i.id)), f"{p.title} - photo {n}")
                for n, i in enumerate(new, 1 + len(p.synced_ids))]
        shop.add_media(p.id, srcs)
        shop.set_synced(p.id, p.synced_ids | {i.id for i in new})
    for cat, img in covers.items():
        if not dry:
            src = shop.staged_upload(img.name, img.mime, drive.download(img.id))
            if shop.set_collection_image(CATEGORY_FOLDERS[cat], src, cat):
                print(f"COLLECTION IMAGE set for {cat}")
    for u in pl["unmatched"]:
        print(f"NO PRODUCT for folder {u} (create and approve the product first; SKU must match)")
    print(f"done: {len(pl['uploads'])} updated, {len(pl['up_to_date'])} up to date, {len(pl['unmatched'])} unmatched")
    return 0


if __name__ == "__main__":
    sys.exit(main())
