"""Public-only procurement discovery. Never reads or publishes corporate PDFs."""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import hashlib
import json
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
FEEDS = ROOT / "sources.json"
OUT = ROOT / "data.json"
STATUS = ROOT / "status.json"
AREAS = ["東京都", "茨城県", "群馬県", "新潟県", "宮城県", "山形県"]
TARGET = ("建築", "新築", "改築", "学校", "消防", "体育館", "庁舎", "施設", "研究棟", "物流", "プレキャスト", "PC梁")
ACTION = ("設計", "基本計画", "基本構想", "入札", "発注", "落札", "プロポーザル", "整備", "建替", "新築", "改築", "工事", "委託")
CUTOFF = datetime.now(timezone.utc) - timedelta(days=90)

def local(tag):
    return tag.split("}", 1)[-1].split(":")[-1]

def plain(text):
    value = re.sub(r"<[^>]*>", " ", unescape(text or ""))
    return re.sub(r"\s+", " ", value).strip()

def https(url):
    try:
        p = urlparse(url or "")
        return p.scheme == "https" and bool(p.hostname) and not p.username and not p.password
    except ValueError:
        return False

def fetch(url):
    if not https(url):
        raise ValueError("HTTPS URL only")
    req = Request(url, headers={"User-Agent": "PCSalesRadar/1.0 (public RSS reader)", "Accept": "application/rss+xml,application/atom+xml,application/xml,text/xml,*/*"})
    with urlopen(req, timeout=22) as resp:
        if not https(resp.geturl()):
            raise ValueError("Non-HTTPS redirect")
        data = resp.read(1_500_001)
        if len(data) > 1_500_000:
            raise ValueError("Feed exceeds limit")
        return data

def child(node, names):
    for e in list(node):
        if local(e.tag) in names:
            return plain("".join(e.itertext()))
    return ""

def published(raw):
    if not raw:
        return ""
    try:
        return parsedate_to_datetime(raw).date().isoformat()
    except (TypeError, ValueError, IndexError):
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            return ""

def decode_xml(raw):
    """Normalize Japanese RSS encodings before ElementTree parsing."""
    mark = re.search(br'<\?xml[^>]*\bencoding\s*=\s*["\']([^"\']+)["\']', raw[:300], re.I)
    if not mark:
        return raw
    charset = mark.group(1).decode("ascii", "replace")
    if charset.lower().replace("-", "").replace("_", "") in ("utf8", "usascii"):
        return raw
    decoded = raw.decode(charset, errors="replace")
    decoded = re.sub(r'(<\?xml[^>]*\bencoding\s*=\s*)["\'][^"\']+["\']',
                     r'\1"UTF-8"', decoded, count=1, flags=re.I)
    return decoded.encode("utf-8")

def entries(raw):
    doc = ET.fromstring(decode_xml(raw))
    result = []
    for node in doc.iter():
        kind = local(node.tag)
        if kind not in ("item", "entry"):
            continue
        title = child(node, ("title",))[:180]
        href = child(node, ("link",))
        if kind == "entry":
            for c in node:
                if local(c.tag) == "link" and (c.get("rel", "alternate") == "alternate" or not href):
                    href = c.get("href", href)
                    if c.get("rel", "alternate") == "alternate":
                        break
        result.append({
            "title": title,
            "url": href,
            "summary": child(node, ("description", "summary", "content"))[:450],
            "published": published(child(node, ("pubDate", "published", "updated", "date")))
        })
    return result

def canonical(s):
    return re.sub(r"[\s\W_]+", "", (s or "").casefold())

def appropriate(e):
    text = e["title"] + " " + e["summary"]
    if not any(w in text for w in TARGET) or not any(w in text for w in ACTION):
        return False
    # Skip generic national news with no grounded location, unless it is a directly
    # published procurement announcement. Nothing here is advertised as confirmed award.
    return True

def main():
    now = datetime.now(timezone.utc)
    existing = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else []
    old = {e["id"]: e for e in existing if isinstance(e, dict) and e.get("id")}
    found = {}
    ok, errors = [], []
    for source in json.loads(FEEDS.read_text(encoding="utf-8")):
        try:
            results = entries(fetch(source["url"]))
            ok.append({"name": source["label"], "entries": len(results)})
        except Exception as ex:
            errors.append({"name": source["label"], "error": str(ex)[:180]})
            continue
        for entry in results[:250]:
            if len(entry["title"]) < 8 or not https(entry["url"]) or not appropriate(entry):
                continue
            date = entry["published"]
            # Only recent announcements; initial historic reference cases are
            # embedded separately in index.html.
            if date and date < CUTOFF.date().isoformat():
                continue
            title = entry["title"]
            key = hashlib.sha256((canonical(title) + "\x00" + entry["url"]).encode()).hexdigest()[:18]
            previous = old.get(key, {})
            content = title + " " + entry["summary"]
            area = next((a for a in AREAS if a in content), "")
            if not area:
                continue # Other areas are not part of the current six-area watch
            is_pdf = urlparse(entry["url"]).path.lower().endswith(".pdf")
            row = {
                "id": key, "title": title, "summary": entry["summary"][:360],
                "source": source["label"], "issuer": source["label"],
                "source_type": source["category"], "document_type": "公開情報候補",
                "published": date, "first_seen": previous.get("first_seen", now.date().isoformat()),
                "place": area, "designer_office": "", "assignee": "",
                "initial_reference": False, "url": entry["url"],
                "source_page_url": entry["url"],
                "pdf_documents": [{"label": "原典PDF", "url": entry["url"]}] if is_pdf else [],
                "status": "社内PDF照合なし（要原典確認）"
            }
            found[key] = row
    # Preserve prior discoveries temporarily if RSS endpoints are unavailable.
    cutoff = CUTOFF.date().isoformat()
    merged = {k: v for k, v in old.items() if v.get("first_seen", "") >= cutoff and v.get("place") in AREAS}
    merged.update(found)
    # De-duplicate equivalent normalized headlines across separate RSS feeds.
    unique = {}
    for x in sorted(merged.values(), key=lambda v: (v.get("published", ""), v.get("first_seen", "")), reverse=True):
        title_key = canonical(x.get("title"))
        if title_key and title_key not in unique:
            unique[title_key] = x
    output = list(unique.values())[:200]
    # Print and publish collection errors; never claim the crawler is exhaustive.
    OUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    STATUS.write_text(json.dumps({
        "checked_at": now.isoformat(timespec="seconds"),
        "collection_status": "取得完了" if ok and not errors else "一部取得失敗" if ok else "取得失敗・保持データを表示",
        "sources_ok": ok, "sources_errors": errors,
        "visible": len(output) + 3,
        "baseline_status": "社内月次PDF照合は未接続。公開RSSの参考候補のみ"
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Success:", len(ok), "Errors:", len(errors), "Additional candidates:", len(output))
    for err in errors:
        print("Source error:", err["name"], err["error"])

if __name__ == "__main__":
    main()
