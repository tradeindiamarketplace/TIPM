import json
import tempfile
import unittest
from decimal import Decimal as D
from pathlib import Path
from unittest import mock

import research.candidates as rc


class VerdictOverlay(unittest.TestCase):
    def test_overlay_sets_review_ca_and_confirmed_gst(self):
        c = {"id": "PC-X", "gst_pct": D("18")}
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "reviews").mkdir()
            (Path(d) / "reviews" / "PC-X.json").write_text(json.dumps(
                {"id": "PC-X", "review": {"verdict": "approve"}, "ca": {"verdict": "approve", "gst_pct_confirmed": 12}}))
            with mock.patch.object(rc, "CANDIDATES", [c]), mock.patch.object(rc, "__file__", str(Path(d) / "candidates.py")):
                rc._apply_verdicts()
        self.assertEqual(c["review"]["verdict"], "approve")
        self.assertEqual(c["gst_pct"], D("12"))

    def test_unknown_id_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "reviews").mkdir()
            (Path(d) / "reviews" / "x.json").write_text(json.dumps({"id": "NOPE", "review": {"verdict": "approve"}}))
            with mock.patch.object(rc, "CANDIDATES", []), mock.patch.object(rc, "__file__", str(Path(d) / "candidates.py")):
                rc._apply_verdicts()


if __name__ == "__main__":
    unittest.main()
