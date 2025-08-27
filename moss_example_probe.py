#!/usr/bin/env python3
"""Example probe for a single Moss Kulturhus event.

Shows how current simple scraper parsed the first event and enumerates
candidate pieces so a human can map correct fields (start time, price etc.).

Usage:
  python3 moss_example_probe.py
  python3 moss_example_probe.py <event_url>
"""
import json, re, sys
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from datetime import datetime

ROOT = Path(__file__).parent
EVENTS_JSON = ROOT / 'mosskulturhus_events.json'
TIME_RE = re.compile(r'\b(\d{1,2}:\d{2})\b')
PRICE_RE = re.compile(r'kr\s*[0-9][0-9\s\.,-]{1,10}', re.I)
DATE_RE = re.compile(r'(\d{1,2})[\.]\s*([a-zA-ZæøåÆØÅ]{3,12})')

MONTH_MAP = {
    'jan':1,'jan.':1,'januar':1,'feb':2,'feb.':2,'februar':2,'mar':3,'mar.':3,'mars':3,'apr':4,'apr.':4,'april':4,'mai':5,
    'jun':6,'jun.':6,'juni':6,'jul':7,'jul.':7,'juli':7,'aug':8,'aug.':8,'august':8,'sep':9,'sep.':9,'sept':9,'sept.':9,'september':9,
    'okt':10,'okt.':10,'oktober':10,'nov':11,'nov.':11,'november':11,'des':12,'des.':12,'desember':12
}

def load_first_event():
    data = json.loads(EVENTS_JSON.read_text(encoding='utf-8'))
    ev = data['events'][0]
    return ev

def fetch(url):
    r = requests.get(url, timeout=25, headers={'User-Agent':'Mozilla/5.0 MossExampleProbe/1.0'})
    r.raise_for_status()
    return r.text

def enumerate_page(html: str):
    soup = BeautifulSoup(html, 'html.parser')
    title_tag = soup.find(['h1','h2'])
    paragraphs = []
    for p in soup.find_all('p'):
        txt = p.get_text(' ', strip=True)
        if txt:
            paragraphs.append(txt)
        if len(paragraphs) >= 8:
            break
    times = list(dict.fromkeys(TIME_RE.findall(html)))  # unique preserve order
    prices = list(dict.fromkeys(PRICE_RE.findall(html)))
    dates = list(dict.fromkeys(m.group(0) for m in DATE_RE.finditer(html)))
    meta_desc = None
    md = soup.find('meta', attrs={'name':'description'})
    if md and md.get('content'): meta_desc = md['content']
    return {
        'page_title': title_tag.get_text(strip=True) if title_tag else None,
        'meta_description': meta_desc,
        'paragraphs': paragraphs,
        'time_tokens': times,
        'price_tokens': prices,
        'date_tokens': dates
    }

def main():
    if not EVENTS_JSON.exists():
        print('No mosskulturhus_events.json found. Run the scraper first.')
        return
    ev = load_first_event()
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = ev['info_url']
    html = fetch(url)
    page_data = enumerate_page(html)
    print('=== Eksempel (første Moss-event) ===')
    print(f"URL: {url}\n")
    print('A. Nåværende parsed record:')
    print(f"   1) tittel      : {ev['title']}")
    print(f"   2) venue       : {ev['venue']}")
    print(f"   3) start (ISO) : {ev['start']}")
    print(f"   4) pris (nå)   : {ev['price']}")
    print(f"   5) raw-linje   : {ev['raw']}")
    print('\nB. Kandidater funnet på detaljsiden:')
    # Page title / meta
    print('  Tittel-kandidater:')
    i=1
    if page_data['page_title']:
        print(f"    T{i}. {page_data['page_title']}"); i+=1
    if page_data['meta_description']:
        print(f"    T{i}. {page_data['meta_description'][:140]}")
    print('  Avsnitt (første 8):')
    for idx, p in enumerate(page_data['paragraphs'], 1):
        print(f"    P{idx}. {p[:140]}")
    print('  Tidstokens:')
    if page_data['time_tokens']:
        for idx,t in enumerate(page_data['time_tokens'],1):
            print(f"    TT{idx}. {t}")
    else:
        print('    (ingen klokkeslett funnet)')
    print('  Pristokens:')
    if page_data['price_tokens']:
        for idx,pv in enumerate(page_data['price_tokens'],1):
            print(f"    PR{idx}. {pv}")
    else:
        print('    (ingen prisuttrykk funnet)')
    print('  Datotokens:')
    if page_data['date_tokens']:
        for idx,dt in enumerate(page_data['date_tokens'],1):
            print(f"    D{idx}. {dt}")
    else:
        print('    (ingen datouttrykk funnet)')
    print('\nSvar med hvilke nøkler vi skal bruke:')
    print('  - Starttid: angi TT-nummer hvis riktig tid dukker opp (ellers skriv "mangler")')
    print('  - Pris: angi PR-nummer hvis noen (ellers "mangler")')
    print('  - Beskrivelse: angi T#, P# eller skriv "kombiner T1 + P2" etc.')
    print('\nDeretter implementerer jeg utvidet henting basert på ditt svar.')

if __name__=='__main__':
    main()
