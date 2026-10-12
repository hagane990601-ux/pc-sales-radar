import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from export_public_sheet import rows_from_public, COLUMNS

class PublicSheetExportTest(unittest.TestCase):
    def test_official_and_candidate_separated(self):
        official = [{"id":"a", "title":"庁舎建替", "place":"宮城県", "pdf_url":"https://city.example.jp/a.pdf", "assignee":"非公開"}]
        candidate = [{"id":"b", "title":"学校設計", "place":"茨城県", "designer_office":"未検証設計", "url":"https://news.example.jp/1", "memo":"非公開"}]
        rows = rows_from_public(official, candidate)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["公式PDF URL"], "https://city.example.jp/a.pdf")
        self.assertEqual(rows[1]["設計事務所"], "")
        self.assertEqual(rows[1]["情報区分"], "公開ニュース候補（未検証）")
        self.assertNotIn("assignee", COLUMNS)
        self.assertNotIn("memo", COLUMNS)

    def test_duplicate_id_and_formula_safety(self):
        official = [{"id":"x","title":"=IMPORTXML(1)"}]
        rows = rows_from_public(official, [{"id":"x","title":"duplicate"}])
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["案件名"].startswith("'="))

if __name__ == "__main__":
    unittest.main()
