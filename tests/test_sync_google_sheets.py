import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from sync_google_sheets import plan, matrix, AUTO_OFFICIAL, AUTO_CANDIDATES, AUTO_LOG, quoted_range
from export_public_sheet import COLUMNS

class SheetsSyncTest(unittest.TestCase):
    def test_separate_tabs_and_header(self):
        official = [{"案件ID": "a", "案件名": "学校", "情報区分": "公式資料登録"}]
        candidates = [{"案件ID": "b", "案件名": "候補", "情報区分": "公開ニュース候補（未検証）"}]
        p = plan(official, candidates, "2026-10-12T00:00:00Z")
        self.assertEqual(set(p), {AUTO_OFFICIAL, AUTO_CANDIDATES, AUTO_LOG})
        self.assertEqual(p[AUTO_OFFICIAL][0], COLUMNS)
        self.assertEqual(p[AUTO_OFFICIAL][1][0], "a")
        self.assertEqual(p[AUTO_CANDIDATES][1][0], "b")
        self.assertEqual(p[AUTO_LOG][1][1:3], [1, 1])

    def test_empty_data_preserves_header(self):
        self.assertEqual(matrix([]), [COLUMNS])

    def test_quoted_range(self):
        self.assertIn("%21A1", quoted_range("公開案件_自動"))

if __name__ == "__main__":
    unittest.main()
