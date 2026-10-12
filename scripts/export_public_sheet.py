"""Export only public procurement records to a Google Sheets-compatible UTF-8 CSV.
No company PDF, staff assignment, visit notes, or credentials are read.
Run: python scripts/export_public_sheet.py --output /tmp/pc_radar_public.csv
"""
import argparse
import csv
import json
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
COLUMNS = [
    "案件ID", "案件名", "都道府県・所在地", "発注者", "設計事務所",
    "事業段階", "公表日", "落札価格(円)", "工期", "施設用途",
    "延床面積(㎡)", "構造形式", "PC関連記述", "公式掲載URL",
    "公式PDF URL", "情報区分", "確認状態",
]
ALLOWED_KEYS = {
    "id", "title", "place", "issuer", "designer_office", "phase",
    "published", "award_price_yen", "period", "facility_type",
    "floor_area_sqm", "structure_type", "pc_evidence",
    "source_page_url", "pdf_url", "pdf_documents", "url", "source_type",
}

def safe_url(value):
    if not isinstance(value, str):
        return ""
    p = urlparse(value)
    return value if p.scheme == "https" and p.netloc and not p.username else ""

def clean(value):
    if value is None:
        return ""
    if not isinstance(value, (str, int, float)):
        return ""
    value = str(value).strip()
    # Avoid CSV formula execution when imported into Sheets or Excel.
    return "'" + value if value.startswith(("=", "+", "-", "@", "\t", "\r")) else value

def rows_from_public(official, discoveries):
    records = {}
    for item in official:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        key = str(item["id"])
        records[key] = {
            "案件ID": key, "案件名": item.get("title", ""),
            "都道府県・所在地": item.get("place", ""),
            "発注者": item.get("issuer", ""),
            "設計事務所": item.get("designer_office", ""),
            "事業段階": item.get("phase", ""),
            "公表日": item.get("published", ""),
            "落札価格(円)": item.get("award_price_yen", ""),
            "工期": item.get("period", ""),
            "施設用途": item.get("facility_type", ""),
            "延床面積(㎡)": item.get("floor_area_sqm", ""),
            "構造形式": item.get("structure_type", ""),
            "PC関連記述": item.get("pc_evidence", ""),
            "公式掲載URL": safe_url(item.get("source_page_url", "")),
            "公式PDF URL": safe_url(item.get("pdf_url", "")),
            "情報区分": "公式資料登録",
            "確認状態": "原典との照合が必要",
        }
    for item in discoveries:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        key = str(item["id"])
        if key in records:
            continue
        pdfs = item.get("pdf_documents") or []
        pdf_url = pdfs[0].get("url", "") if pdfs and isinstance(pdfs[0], dict) else ""
        records[key] = {
            "案件ID": key, "案件名": item.get("title", ""),
            "都道府県・所在地": item.get("place", ""),
            "発注者": item.get("issuer", ""),
            "設計事務所": "", "事業段階": "",
            "公表日": item.get("published", ""),
            "落札価格(円)": "", "工期": "", "施設用途": "",
            "延床面積(㎡)": "", "構造形式": "", "PC関連記述": "",
            "公式掲載URL": safe_url(item.get("source_page_url", item.get("url", ""))),
            "公式PDF URL": safe_url(pdf_url),
            "情報区分": "公開ニュース候補（未検証）",
            "確認状態": "公式原典の確認前",
        }
    return [{col: clean(record.get(col, "")) for col in COLUMNS} for record in records.values()]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, help="Output path; use a private local folder")
    args = parser.parse_args()
    official = json.loads((ROOT / "official_documents.json").read_text(encoding="utf-8"))
    discoveries = json.loads((ROOT / "data.json").read_text(encoding="utf-8"))
    rows = rows_from_public(official, discoveries)
    dest = Path(args.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Public records exported: {len(rows)}. Private company files were not accessed.")

if __name__ == "__main__":
    main()
