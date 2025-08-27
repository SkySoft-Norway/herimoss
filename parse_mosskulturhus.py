#!/usr/bin/env python3
"""Parse saved mosskulturhus HTML (from debug_pages/mosskulturhus_curl.html)
and extract events with clickable links.

Writes results to mosskulturhus_events.json in the same folder.
"""
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qsl, urlunparse, urlencode

from bs4 import BeautifulSoup
from datetime import datetime
from date_utils import normalize_date_to_iso, parse_price, detect_venue

BASE = "https://www.mosskulturhus.no"
ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "debug_pages" / "mosskulturhus_curl.html"
OUTPUT = ROOT / "mosskulturhus_events.json"


def normalize_url(u: str) -> str:
    if not u:
        return u
    u = urljoin(BASE, u)
    p = urlparse(u)
    # remove common tracking params
    qs = [(k, v) for k, v in parse_qsl(p.query) if not k.lower().startswith("utm_")]
    newq = urlencode(qs)
    clean = urlunparse((p.scheme, p.netloc, p.path, p.params, newq, ""))
    return clean


def likely_ticket_link(href: str) -> bool:
    if not href:
        return False
    href = href.lower()
    keywords = ["ticket", "tix", "billet", "billetter", "billett", "tickets", "ticketmaster", "tix.no"]
    return any(k in href for k in keywords)


def extract_title_from_context(a):
    # Prefer anchor text if meaningful
    text = (a.get_text(" ", strip=True) or "").strip()
    if text and len(text) > 2 and not text.lower().startswith("les mer"):
        return text

    # look for nearby headings
    parent = a.find_parent()
    for tag in ("h3", "h2", "h4", "h5", "strong"):
        candidate = parent.find_previous(tag) if parent else None
        if candidate and candidate.get_text(strip=True):
            return candidate.get_text(strip=True)

    # fallback to parent/article text
    if parent:
        t = parent.get_text(" ", strip=True)
        if t:
            return (t[:200] + "...") if len(t) > 200 else t

    return text or ""


def main():
    if not INPUT.exists():
        print(f"Input snapshot not found: {INPUT}")
        return

    html = INPUT.read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(html, "lxml")

    anchors = []

    # 1) Anchors inside program grid if present
    containers = soup.select("#program, .program, .grid, .events, .evcal_list, .event, .event-item")
    for c in containers:
        for a in c.find_all("a", href=True):
            anchors.append(a)

    # 2) Anchors that look like ticket links anywhere on the page
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if likely_ticket_link(href):
            anchors.append(a)

    # 3) de-dup by normalized href
    seen = {}
    for a in anchors:
        raw = a.get("href")
        href = normalize_url(raw)
        if not href:
            continue
        if href in seen:
            continue
        title = extract_title_from_context(a)
        # extract surrounding text for metadata
        parent = a.find_parent()
        ptext = parent.get_text(' ', strip=True) if parent else ''

        # datetime
        dt = None
        time_tag = a.find_previous('time') or (parent.find('time') if parent else None)
        if time_tag and time_tag.has_attr('datetime'):
            dt = time_tag['datetime']
        else:
            dt = normalize_date_to_iso(ptext)

        # venue & price via helpers
        venue = detect_venue(ptext)
        price = parse_price(ptext)

        # external id
        ext_id = None
        m = re.search(r"ticketmaster\.no/(?:event/)?(\d+)", href)
        if m:
            ext_id = m.group(1)
        else:
            m2 = re.search(r"tix\.no/.*/(\d+)", href)
            if m2:
                ext_id = m2.group(1)

        seen[href] = {
            "title": title,
            "url": href,
            "source": "mosskulturhus",
            "extracted_from": str(INPUT.name),
            "datetime": dt,
            "venue": venue,
            "price": price or 'Ukjent',
            "external_id": ext_id,
        }

    events = list(seen.values())
    # sort by url for stable output
    events.sort(key=lambda x: x.get("url"))

    OUTPUT.write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(events)} events to {OUTPUT}")
    if events:
        print("Sample:")
        for e in events[:10]:
            print(f" - {e['title'][:80]} -> {e['url']}")


if __name__ == "__main__":
    main()
