"""Offline regression tests: no Gemini calls or remote PDF downloads."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import gemini_enrich as mod


class TestGeminiSafety(unittest.TestCase):
    def test_official_pdf_allowlist(self):
        good = "https://www.city.sendai.jp/aoba-somu-somu/documents/example.pdf"
        self.assertTrue(mod.official_pdf(good))
        for bad in [
            "https://bad.example/doc.pdf",
            "https://www.city.sendai.jp.evil.example/file.pdf",
            "http://www.city.sendai.jp/file.pdf",
            "https://user:password@www.city.sendai.jp/file.pdf",
            "https://www.city.sendai.jp/../../doc.txt",
            "https://www.pref.yamagata.jp/file.pdf?private=1",
            "file:///etc/passwd"
        ]:
            with self.subTest(url=bad):
                self.assertFalse(mod.official_pdf(bad))

    def test_ai_response_validation_and_url_scrubbing(self):
        valid = {k: "資料で確認できず" for k in mod.FIELDS}
        valid["proposal_hint"] = "参照先 https://private.example/my-note は原典ではない"
        clean = mod.normalize_model_output(valid)
        self.assertNotIn("https://", clean["proposal_hint"])
        with self.assertRaises(ValueError):
            mod.normalize_model_output({"facility_use": "学校"})
        invalid = dict(valid)
        invalid["structure_type"] = ["RC"]
        with self.assertRaises(ValueError):
            mod.normalize_model_output(invalid)

    def test_no_api_key_keeps_public_ai_data_unmodified(self):
        with tempfile.TemporaryDirectory() as td:
            t = Path(td)
            docs, out, status = (t / x for x in ("official_documents.json", "ai_results.json", "ai_status.json"))
            docs.write_text("[]", encoding="utf-8")
            out.write_text("[]\n", encoding="utf-8")
            with patch.object(mod, "INPUT", docs), patch.object(mod, "OUT", out), patch.object(mod, "HEALTH", status), patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
                mod.main()
            self.assertEqual(json.loads(out.read_text(encoding="utf-8")), [])
            self.assertFalse(json.loads(status.read_text(encoding="utf-8"))["enabled"])

    def test_two_requests_max_and_manifest_owned_links(self):
        with tempfile.TemporaryDirectory() as td:
            t = Path(td)
            docs, out, status = (t / x for x in ("official_documents.json", "ai_results.json", "ai_status.json"))
            base = "https://www.city.sendai.jp/files/test"
            documents = [{"id": f"known-{n}", "pdf_url": f"{base}{n}.pdf"} for n in range(4)]
            docs.write_text(json.dumps(documents), encoding="utf-8")
            out.write_text("[]", encoding="utf-8")
            facts = {k: "資料で確認できず" for k in mod.FIELDS}
            with patch.object(mod, "INPUT", docs), patch.object(mod, "OUT", out), patch.object(mod, "HEALTH", status), patch.dict(os.environ, {"GEMINI_API_KEY": "unit-test-placeholder"}), patch.object(mod, "download_pdf", return_value=b"%PDF-test") as fetch, patch.object(mod, "generate", return_value=facts) as run:
                mod.main()
            contents = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(len(contents), 2)
            self.assertEqual(fetch.call_count, 2)
            self.assertEqual(run.call_count, 2)
            self.assertEqual(contents[0]["source_pdf_url"], documents[0]["pdf_url"])
            self.assertTrue(all(x["ai_state"] == "AI抽出・要原資料確認" for x in contents))


if __name__ == "__main__":
    unittest.main()
