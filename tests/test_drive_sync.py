import unittest

from scripts.drive_sync import DriveImage, ProductFolder, ShopifyProduct, parse_sku, plan
from scripts.recommend import POLICY, policy_problems
from decimal import Decimal as D


class DriveSyncPlan(unittest.TestCase):
    def test_sku_parsing(self):
        self.assertEqual(parse_sku("MF-10 Microfiber cloths pack of 10"), "MF-10")
        self.assertEqual(parse_sku("brush13"), "BRUSH13")
        self.assertIsNone(parse_sku("  (old photos)"))

    def test_only_new_images_in_natural_order(self):
        f = ProductFolder("Cleaning", "MF-10", "MF-10 cloths", [
            DriveImage("a", "10.jpg", "image/jpeg"), DriveImage("b", "2.jpg", "image/jpeg"),
            DriveImage("c", "1.jpg", "image/jpeg"), DriveImage("d", "notes.txt", "text/plain")])
        p = ShopifyProduct("gid://shopify/Product/1", "Cloths", {"b"})
        pl = plan([f], {"MF-10": p})
        (_, _, new), = pl["uploads"]
        self.assertEqual([i.name for i in new], ["1.jpg", "10.jpg"])      # b already synced, txt ignored

    def test_unmatched_folder_is_reported_not_created(self):
        pl = plan([ProductFolder("Kids", "LB-3", "LB-3 lunch box", [DriveImage("x", "1.jpg", "image/jpeg")])], {})
        self.assertEqual(pl["unmatched"], ["Kids/LB-3 lunch box"])
        self.assertEqual(pl["uploads"], [])

    def test_up_to_date(self):
        f = ProductFolder("Cleaning", "MF-10", "MF-10", [DriveImage("a", "1.jpg", "image/jpeg")])
        pl = plan([f], {"MF-10": ShopifyProduct("p", "Cloths", {"a"})})
        self.assertEqual(pl["up_to_date"], ["Cloths"])


class ProductPolicy(unittest.TestCase):
    base = dict(category="cleaning_utility", weight="le_500g", price=D("699"), supplier_cost=D("225"))

    def test_good_candidate_has_no_problems(self):
        self.assertEqual(policy_problems(self.base), [])

    def test_blocked_categories(self):
        for cat in ("apparel", "power_banks", "supplements", "electrical_appliances"):
            self.assertTrue(policy_problems(dict(self.base, category=cat)), cat)

    def test_electrical_needs_bis_documents(self):
        c = dict(self.base, category="kitchen_organisation", electrical=True)
        self.assertTrue(any("electrical" in p for p in policy_problems(c)))
        c["documents"] = POLICY["exception"]["electrical"]["required_documents"]
        self.assertEqual(policy_problems(c), [])

    def test_needs_info_is_its_own_stage(self):
        from scripts.recommend import evaluate
        c = dict(self.base, id="T1", name="t", gst_pct=D("18"), review={"verdict": "needs_info", "notes": "quote needed"})
        r = evaluate(c)
        self.assertEqual(r["stage"], "NEEDS_INFO")
        self.assertIn("quote needed", r["reason"])

    def test_website_only_tax_path_limits_channels(self):
        from scripts.recommend import evaluate
        c = dict(self.base, id="T2", name="t", gst_pct=D("18"), review={"verdict": "approve"},
                 ca={"verdict": "approve", "tax_path": "bill_to_ship_to_website_only"})
        r = evaluate(c)
        self.assertEqual(set(r["channels"]), {"shopify"})
        self.assertIn(r["best_channel"], ("shopify", None))

    def test_price_and_weight_limits(self):
        self.assertTrue(policy_problems(dict(self.base, price=D("299"))))
        self.assertTrue(policy_problems(dict(self.base, weight="le_5kg")))


if __name__ == "__main__":
    unittest.main()
