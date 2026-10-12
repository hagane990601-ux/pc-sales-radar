"""Sync ONLY public procurement information to private Google Sheets.

Uses GOOGLE_SERVICE_ACCOUNT_JSON (GitHub Actions secret) and GOOGLE_SHEET_ID.
Does not read internal company PDFs, contacts or sales notes.
Only auto-owned tabs are modified; user-maintained tabs are untouched.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from export_public_sheet import COLUMNS, ROOT, rows_from_public

AUTO_OFFICIAL = "公開案件_自動"
AUTO_CANDIDATES = "候補_自動"
AUTO_LOG = "収集ログ_自動"
AUTO_TABS = (AUTO_OFFICIAL, AUTO_CANDIDATES, AUTO_LOG)
BASE = "https://sheets.googleapis.com/v4/spreadsheets/"

def load_rows():
    official = json.loads((ROOT / "official_documents.json").read_text(encoding="utf-8"))
    discoveries = json.loads((ROOT / "data.json").read_text(encoding="utf-8"))
    rows = rows_from_public(official, discoveries)
    verified = [r for r in rows if r["情報区分"] == "公式資料登録"]
    candidates = [r for r in rows if r["情報区分"] != "公式資料登録"]
    return verified, candidates

def matrix(rows):
    return [COLUMNS] + [[r.get(col, "") for col in COLUMNS] for r in rows]

def plan(official, candidates, stamp):
    """Pure, testable plan. Never include private fields."""
    return {
        AUTO_OFFICIAL: matrix(official),
        AUTO_CANDIDATES: matrix(candidates),
        AUTO_LOG: [
            ["同期日時(UTC)", "公開案件数", "未検証候補数", "注記"],
            [stamp, len(official), len(candidates), "公開情報のみ。社内月次PDFとは未照合"],
        ],
    }

def access_token():
    # Import only for live sync, allowing pure logic tests without cloud packages.
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    if not raw:
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON is not configured")
    info = json.loads(raw)
    if info.get("type") != "service_account":
        raise ValueError("Invalid service account credentials type")
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    creds.refresh(Request())
    return creds.token

def api(method, url, token, payload=None):
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Authorization": "Bearer " + token, "Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json; charset=utf-8"
    for attempt in range(3):
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=35) as response:
                body = response.read()
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504) and attempt < 2:
                time.sleep(2 ** attempt)
                continue
            # Never print the raw error body (it may contain sensitive data).
            raise RuntimeError(f"Google Sheets API returned HTTP {exc.code}") from None
    raise RuntimeError("Google Sheets API request failed")

def quoted_range(title):
    return urllib.parse.quote("'" + title.replace("'", "''") + "'!A1", safe="")

def sync(sheet_id, token, payload):
    root = BASE + urllib.parse.quote(sheet_id, safe="")
    meta = api("GET", root + "?fields=sheets.properties.title", token)
    existing = {s["properties"]["title"] for s in meta.get("sheets", [])}
    missing = [name for name in AUTO_TABS if name not in existing]
    if missing:
        api("POST", root + ":batchUpdate", token, {
            "requests": [{"addSheet": {"properties": {"title": name}}} for name in missing]
        })
    # Only clear our three dedicated tabs. Do not touch user-owned tabs.
    for title in AUTO_TABS:
        tab_url = root + "/values/" + quoted_range(title)
        api("POST", tab_url + ":clear", token, {})
        api("PUT", tab_url + "?valueInputOption=RAW", token, {
            "range": "'" + title + "'!A1",
            "majorDimension": "ROWS",
            "values": payload[title],
        })

def main():
    sheet_id = os.environ.get("GOOGLE_SHEET_ID", "").strip()
    if not sheet_id:
        raise RuntimeError("GOOGLE_SHEET_ID is missing")
    if not all(ch.isascii() and (ch.isalnum() or ch in "-_") for ch in sheet_id):
        raise ValueError("Invalid GOOGLE_SHEET_ID")
    official, candidates = load_rows()
    payload = plan(official, candidates, datetime.now(timezone.utc).isoformat())
    sync(sheet_id, access_token(), payload)
    print(f"Google Sheets sync completed: {len(official)} official, {len(candidates)} unverified candidates; private records excluded")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Avoid printing stack traces or secret-bearing API responses.
        print(f"Google Sheets sync failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
