#!/usr/bin/env python3
"""Detail field probe utility.

Fetches one or more event detail pages and enumerates candidate values for:
 1. Meta tags (title/description/og/twitter)
 2. JSON-LD Event fields (dates, times, price, location)
 3. Time tokens (HH:MM)
 4. Price tokens (kr ...)
 5. Date tokens (dd. mon [yyyy])
 6. Headings (h1/h2/h3)
 7. Paragraph candidates (first 3 > 40 chars)
 8. Purchase / ticket links (anchor text + href)

Usage:
  python3 detail_field_probe.py               # auto-picks first 3 moss + first 3 verket events
  python3 detail_field_probe.py URL1 URL2 ...  # probe specific URLs

Goal: Let a human map which enumerated candidates correspond to canonical fields (start time, price, etc.).
"""
from __future__ import annotations
import sys, json, re, time
from pathlib import Path
from typing import List, Dict, Any
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).parent
MOSS_JSON = ROOT / 'mosskulturhus_events.json'
VERKET_JSON = ROOT / 'verketscene_events.json'

TIME_RE = re.compile(r'\b(\d{1,2}:\d{2})\b')
PRICE_RE = re.compile(r'kr\s*[0-9][0-9\s\.,-]{1,10}', re.I)
DATE_RE = re.compile(r'\b(\d{1,2})[\.]\s*([a-zA-ZæøåÆØÅ]{3,12})(?:\s*(\d{4}))?')
PURCHASE_WORDS = ['kjøp','billett','billetter','ticket','tickets']

MONTH_MAP = {
    'jan':1,'jan.':1,'januar':1,'feb':2,'feb.':2,'februar':2,'mar':3,'mar.':3,'mars':3,'apr':4,'apr.':4,'april':4,'mai':5,
    'jun':6,'jun.':6,'juni':6,'jul':7,'jul.':7,'juli':7,'aug':8,'aug.':8,'august':8,'sep':9,'sep.':9,'sept':9,'sept.':9,'september':9,
    'okt':10,'okt.':10,'oktober':10,'nov':11,'nov.':11,'november':11,'des':12,'des.':12,'desember':12
}

def load_event_urls(limit_each=3) -> List[str]:
    urls = []
    if MOSS_JSON.exists():
        try:
            data = json.loads(MOSS_JSON.read_text(encoding='utf-8'))
            evs = data.get('events', data)
            for r in evs[:limit_each]:
                u = r.get('info_url') or r.get('url');
                if u: urls.append(u)
        except Exception:
            pass
    if VERKET_JSON.exists():
        try:
            data = json.loads(VERKET_JSON.read_text(encoding='utf-8'))
            evs = data.get('events', data)
            for r in evs[:limit_each]:
                u = r.get('info_url') or r.get('url');
                if u: urls.append(u)
        except Exception:
            pass
    return urls

def fetch(url: str) -> str:
    r = requests.get(url, timeout=25, headers={'User-Agent':'Mozilla/5.0 FieldProbe/1.0'})
    r.raise_for_status()
    return r.text

def extract_json_ld(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    out = []
    for tag in soup.find_all('script', type='application/ld+json'):
        try:
            txt = tag.string or tag.text
            if not txt: continue
            data = json.loads(txt)
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        out.append(item)
            elif isinstance(data, dict):
                out.append(data)
        except Exception:
            continue
    return out

def collect_candidates(url: str) -> Dict[str, Any]:
    html = fetch(url)
    soup = BeautifulSoup(html, 'html.parser')
    meta = {}
    for m in soup.find_all('meta'):
        name = m.get('name') or m.get('property')
        if name and any(name.lower().startswith(p) for p in ['og:','twitter:','description']):
            meta[name] = m.get('content')
    if soup.title and soup.title.string:
        meta['<title>'] = soup.title.string.strip()

    json_ld = extract_json_ld(soup)
    events_ld = [j for j in json_ld if isinstance(j, dict) and (j.get('@type') == 'Event' or 'startDate' in j or 'endDate' in j)]

    text = soup.get_text('\n', strip=True)
    times = sorted(set(TIME_RE.findall(text)))
    prices = sorted(set(PRICE_RE.findall(text)))
    dates = sorted(set(match[0]+'. '+match[1]+(' '+match[2] if match[2] else '') for match in DATE_RE.findall(text)))
    headings = []
    for tag in soup.find_all(['h1','h2','h3']):
        t = tag.get_text(' ', strip=True)
        if t and t not in headings:
            headings.append(t)
    paragraphs = []
    for p in soup.find_all('p'):
        pt = p.get_text(' ', strip=True)
        if len(pt) > 40 and pt not in paragraphs:
            paragraphs.append(pt)
        if len(paragraphs) >= 3:
            break
    ticket_links = []
    for a in soup.find_all('a', href=True):
        txt = a.get_text(' ', strip=True)
        if any(w in txt.lower() for w in PURCHASE_WORDS) or any(w in a['href'].lower() for w in PURCHASE_WORDS):
            ticket_links.append({'text': txt, 'href': a['href']})
    return {
        'url': url,
        'meta': meta,
        'jsonld_events': events_ld,
        'time_tokens': times,
        'price_tokens': prices,
        'date_tokens': dates,
        'headings': headings,
        'paragraphs': paragraphs,
        'ticket_links': ticket_links,
    }

def main(urls: List[str]):
    results = []
    for i, u in enumerate(urls, 1):
        try:
            print(f"[Probe {i}/{len(urls)}] {u}")
            res = collect_candidates(u)
            results.append(res)
            time.sleep(0.8)
        except Exception as e:
            print(f"  ERROR: {e}")
    # Pretty print enumerated candidates per URL
    for res in results:
        print("\n==============================")
        print(f"URL: {res['url']}")
        def enum(lst):
            return '\n'.join(f"  {i+1}. {v if not isinstance(v, dict) else json.dumps(v, ensure_ascii=False)[:300]}" for i,v in enumerate(lst)) or '  (none)'
        # Meta
        print("Meta candidates:")
        for idx,(k,v) in enumerate(res['meta'].items(),1):
            print(f"  {idx}. {k} = {v[:160]}")
        print("JSON-LD Event objects:")
        print(enum(res['jsonld_events']))
        print("Time tokens:")
        print(enum(res['time_tokens']))
        print("Price tokens:")
        print(enum(res['price_tokens']))
        print("Date tokens:")
        print(enum(res['date_tokens']))
        print("Headings:")
        print(enum(res['headings']))
        print("Paragraph candidates:")
        print(enum(res['paragraphs']))
        print("Ticket link candidates:")
        print(enum(res['ticket_links']))
    # JSON output path for programmatic follow-up
    out_path = ROOT / 'detail_field_probe_output.json'
    with open(out_path,'w',encoding='utf-8') as f:
        json.dump(results,f,ensure_ascii=False,indent=2)
    print(f"\nSaved raw probe data to {out_path}")

if __name__ == '__main__':
    if len(sys.argv) > 1:
        main(sys.argv[1:])
    else:
        main(load_event_urls())
