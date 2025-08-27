#!/usr/bin/env python3
"""
Generate enhanced HTML calendar page with advanced features.
"""
import sqlite3
try:
    import mysql.connector  # type: ignore
    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False
import json
import time
import hashlib
from datetime import datetime, timedelta
import pytz
from pathlib import Path
import re
import os, sys
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

# --- Environment loader for .env (lightweight, no external dependency) ---
from pathlib import Path as _Path
ENV_LOADED = False
def load_env(env_path=None):
    """Load key=value pairs from a .env file into os.environ if not already set.
    Minimal implementation to avoid adding python-dotenv dependency."""
    global ENV_LOADED
    if ENV_LOADED:
        return
    try:
        if env_path is None:
            env_path = _Path(__file__).parent / '.env'
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                k, v = line.split('=', 1)
                k = k.strip(); v = v.strip()
                if k and v and k not in os.environ:
                    os.environ[k] = v
        ENV_LOADED = True
    except Exception:
        # Silently ignore; fallback to existing environment
        pass

load_env()

# --- Simple mode helpers (summary + AI stubs) ---
SENTENCE_END_RE = re.compile(r'(?<=[.!?])\s+(?=[A-ZÆØÅÄÖÉ])')

def summarize_text(text: str, max_sentences: int = 3) -> str:
    if not text:
        return ''
    # Strip excessive whitespace
    clean = re.sub(r'\s+', ' ', text).strip()
    # Split into sentences heuristically
    parts = SENTENCE_END_RE.split(clean)
    if len(parts) <= max_sentences:
        return clean
    return ' '.join(parts[:max_sentences])

def ai_available() -> bool:
    return os.getenv('AI_ENABLED', '0') in ('1', 'true', 'TRUE', 'yes', 'on') and (
        os.getenv('OPENAI_API_KEY') or os.getenv('AI_API_KEY')
    )

def ai_summarize_and_validate(title: str, original_desc: str) -> tuple[str, bool]:
    """Attempt AI summary + validation; fallback to heuristic.

    Returns (summary, valid). Validation fallback: overlap w/ title tokens & reasonable length.
    Enforces a hard cap of 280 visible characters for AI output.
    """
    base_summary = summarize_text(original_desc or '')
    if not ai_available():
        return base_summary, validate_event_basic(title, base_summary)
    api_key = os.getenv('OPENAI_API_KEY') or os.getenv('AI_API_KEY')
    model = os.getenv('AI_MODEL', 'gpt-4o-mini')
    timeout = float(os.getenv('AI_TIMEOUT', '15'))
    max_tokens = int(os.getenv('AI_MAX_TOKENS', '180'))
    prompt = (
        "Oppsummer dette kulturarrangementet i Moss i 2–3 korte setninger (maks 280 tegn). "
        "Ikke finn på detaljer. Unngå pris/tid med mindre eksplisitt i teksten. "
        f"Tittel: {title}\nRåtekst: {(original_desc or '')[:3000]}\nSvar kun med selve sammendraget."
    )
    summary = ''
    try:
        # Support both new (>=1.0) and legacy openai python clients
        try:
            from openai import OpenAI  # type: ignore
            client = OpenAI(api_key=api_key, timeout=timeout)
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=max_tokens
            )
            summary = resp.choices[0].message.content.strip()
        except Exception:
            import openai  # type: ignore
            openai.api_key = api_key
            resp = openai.ChatCompletion.create(
                model=model,
                messages=[{"role":"user","content":prompt}],
                temperature=0.2,
                max_tokens=max_tokens
            )
            summary = resp['choices'][0]['message']['content'].strip()
    except Exception:
        summary = ''
    if not summary:
        summary = base_summary
    # Enforce 280 char hard cap & clean whitespace
    summary = re.sub(r'\s+', ' ', summary).strip()[:280]
    valid = validate_event_basic(title, summary)
    return summary, valid

def validate_event_basic(title: str, summary: str) -> bool:
    if not summary:
        return False
    title_tokens = {t.lower() for t in re.findall(r"[\wøæåØÆÅ]+", title) if len(t) > 2}
    if not title_tokens:
        return len(summary) >= 20
    summary_tokens = {t.lower() for t in re.findall(r"[\wøæåØÆÅ]+", summary)}
    overlap = title_tokens & summary_tokens
    return bool(overlap) and 5 <= len(summary.split()) <= 70

def fetch_detail_description(url: str, timeout: int = 5) -> str:
    """Fetch a short description from the event detail page (meta desc or first substantial paragraph).

    Timeout lowered for fast batch generation. Returns empty string on any failure.
    """
    try:
        r = requests.get(url, timeout=timeout, headers={'User-Agent':'Mozilla/5.0 MossKulturBot detail'})
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        # Prefer meta description
        meta = soup.find('meta', attrs={'name':'description'})
        if meta and meta.get('content') and len(meta['content']) > 40:
            return meta['content'].strip()
        # Fallback: first substantial paragraph
        for p in soup.find_all('p'):
            txt = p.get_text(' ', strip=True)
            if len(txt) > 40 and not txt.lower().startswith('foto:'):
                return txt.strip()
    except Exception:
        return ''
    return ''

# -------------------- Lightweight description cache --------------------
_DESC_CACHE_PATH = '/var/www/vhosts/herimoss.no/pythoncrawler/cache/descriptions.json'
_DESC_CACHE_MAX_AGE_DAYS = 30

def _load_description_cache() -> dict:
    try:
        if os.path.exists(_DESC_CACHE_PATH):
            with open(_DESC_CACHE_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def _save_description_cache(cache: dict):
    try:
        os.makedirs(os.path.dirname(_DESC_CACHE_PATH), exist_ok=True)
        tmp_path = _DESC_CACHE_PATH + '.tmp'
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=0)
        os.replace(tmp_path, _DESC_CACHE_PATH)
    except Exception:
        pass


def _fetch_events_sqlite(limit=500):
    db_path = '/var/www/vhosts/herimoss.no/pythoncrawler/events.db'
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        SELECT title, venue, start_time, end_time, source_url, description, price_info, ticket_url
        FROM events
        WHERE status = 'active' AND start_time >= datetime('now')
        ORDER BY start_time ASC
        LIMIT ?
    """, (limit,))
    rows = cur.fetchall()
    conn.close()
    return rows


def _fetch_events_mariadb(limit=500):
    if not HAS_MYSQL:
        raise RuntimeError('mysql-connector-python not installed')
    cfg = dict(host='localhost', user='Terje_moss', password='Klokken!12!?!', database='Terje_moss')
    conn = mysql.connector.connect(**cfg)
    cur = conn.cursor()
    cur.execute("""
        SELECT title, venue, start_time, end_time, source_url, description, price_info, ticket_url
        FROM events
        WHERE status='active' AND start_time >= UTC_TIMESTAMP()
        ORDER BY start_time ASC
        LIMIT %s
    """, (limit,))
    rows = cur.fetchall()
    cur.close(); conn.close()
    return rows


def generate_enhanced_calendar_html(use_mariadb=True):
    """Generate HTML page with enhanced calendar features.

    Args:
        use_mariadb (bool): if True query MariaDB, else fall back to legacy SQLite.
    """
    try:
        if use_mariadb:
            raw = _fetch_events_mariadb()
        else:
            raw = _fetch_events_sqlite()
    except Exception as e:
        # Fallback to sqlite on error
        print(f"[WARN] Primary DB fetch failed ({e}); falling back to SQLite")
        raw = _fetch_events_sqlite()
    
    oslo_tz = pytz.timezone('Europe/Oslo')
    current_time = datetime.now(oslo_tz)
    
    # Process events and categorize
    processed_events = []
    venues = set()
    categories = set()
    
    for row in raw:
        # Unpack with ticket_url awareness
        if len(row) == 8:
            title, venue, start_time_val, end_time_val, info_url, description, price, ticket_url = row
        else:  # legacy
            title, venue, start_time_val, end_time_val, info_url, description, price = row
            ticket_url = None
        try:
            # Parse datetime
            # Normalize start datetime
            if isinstance(start_time_val, datetime):
                start_dt = start_time_val
            else:
                start_dt = datetime.fromisoformat(str(start_time_val).replace('Z', '+00:00'))
            if start_dt.tzinfo is None:
                # Treat naive as local Oslo time (not UTC) to avoid shifting by +2h
                start_dt = oslo_tz.localize(start_dt)
            local_time = start_dt.astimezone(oslo_tz)

            end_local = None
            if end_time_val:
                try:
                    if isinstance(end_time_val, datetime):
                        end_dt = end_time_val
                    else:
                        end_dt = datetime.fromisoformat(str(end_time_val).replace('Z', '+00:00'))
                    if end_dt.tzinfo is None:
                        end_dt = oslo_tz.localize(end_dt)
                    end_local = end_dt.astimezone(oslo_tz)
                except Exception:
                    end_local = None
            
            # Categorize events
            category = "arrangement"
            title_lower = title.lower()
            if any(word in title_lower for word in ['konsert', 'musikk', 'blues', 'jazz', 'band']):
                category = "musikk"
            elif any(word in title_lower for word in ['teater', 'forestilling', 'mussikal']):
                category = "teater"
            elif any(word in title_lower for word in ['familie', 'barn', 'barne']):
                category = "familie"
            elif any(word in title_lower for word in ['komedie', 'humor', 'show']):
                category = "komedie"
            elif any(word in title_lower for word in ['festival', 'fest']):
                category = "festival"
            
            # Determine ticket availability status
            availability = "available"  # Default
            if not info_url or info_url == "None":
                availability = "no-tickets"
            elif any(word in title_lower for word in ['utsolgt', 'sold out']):
                availability = "sold-out"
            
            # Price category
            price_category = "unknown"
            if price and price.lower() != 'none':
                if 'gratis' in price.lower() or '0' in price:
                    price_category = "free"
                elif any(char.isdigit() for char in price):
                    price_category = "paid"
            
            processed_events.append({
                'title': title,
                'venue': venue or 'Moss',
                'start_time': local_time,
                'end_time': end_local,
                'url': info_url if info_url and info_url != 'None' else None,
                'ticket_url': ticket_url if ticket_url and ticket_url not in ('None','') else None,
                'description': description,
                'price': price,
                'category': category,
                'availability': availability,
                'price_category': price_category
            })
            
            venues.add(venue or 'Moss')
            categories.add(category)
            
        except Exception as e:
            print(f"Error processing event {title}: {e}")
            continue
    
    # Generate events HTML
    events_html = ""
    
    for i, event in enumerate(processed_events):
        # Format date and time
        date_str = event['start_time'].strftime('%d. %B %Y')
        time_str = event['start_time'].strftime('%H:%M')
        if event.get('end_time') and event['end_time'].date() == event['start_time'].date():
            time_str = f"{time_str}–{event['end_time'].strftime('%H:%M')}"
        weekday = event['start_time'].strftime('%A')
        
        # Norwegian translations
        weekday_no = {
            'Monday': 'Mandag', 'Tuesday': 'Tirsdag', 'Wednesday': 'Onsdag',
            'Thursday': 'Torsdag', 'Friday': 'Fredag', 'Saturday': 'Lørdag', 'Sunday': 'Søndag'
        }.get(weekday, weekday)
        
        date_str_no = date_str
        for en_month, no_month in [
            ('January', 'januar'), ('February', 'februar'), ('March', 'mars'),
            ('April', 'april'), ('May', 'mai'), ('June', 'juni'),
            ('July', 'juli'), ('August', 'august'), ('September', 'september'),
            ('October', 'oktober'), ('November', 'november'), ('December', 'desember')
        ]:
            date_str_no = date_str_no.replace(en_month, no_month)
        
        # Availability status (remove ticket-related functionality)
        availability_html = ""
        # Simple status indicators without ticket references
        if event['availability'] == 'sold-out':
            availability_html = '<span class="status-indicator sold-out">🔴 Utsolgt</span>'
        elif event['availability'] == 'available':
            availability_html = '<span class="status-indicator available">🟢 Plass ledig</span>'
        elif event['availability'] == 'no-tickets':
            availability_html = '<span class="status-indicator no-tickets">ℹ️ Se arrangør</span>'
        
        # Description preview
        desc_preview = ""
        desc_full = ""
        desc_html = ""
        if event['description']:
            desc_full = event['description']
            if len(desc_full) > 150:
                desc_preview = desc_full[:150] + "..."
                read_more_btn = " <button class=\"read-more-btn\">Les mer</button>"
            else:
                desc_preview = desc_full
                read_more_btn = ""
            desc_html = f'<div class="event-description"><span class="desc-preview">{desc_preview}</span><span class="desc-full" style="display:none;">{desc_full}</span>{read_more_btn}</div>'
        
        # Price display
        price_display = ""
        if event['price'] and event['price'].lower() not in ['none', 'null', '']:
            price_display = f'<div class="event-price">💰 {event["price"]}</div>'
        
        # Determine info and purchase URLs.
        info_url = event.get('url')
        purchase_url = event.get('ticket_url')  # prefer dedicated field
        # Build event actions: include info link; buy button only if purchase_url present
        event_actions = ''
        if info_url or purchase_url:
            event_actions = '<div class="event-actions">'
            if info_url:
                event_actions += f'<a href="{info_url}" target="_blank" class="info-btn">\n                    ℹ️ Mer info\n                </a>'
            if purchase_url:
                event_actions += f'<a href="{purchase_url}" target="_blank" rel="noopener noreferrer" class="buy-btn">KJØP BILLETTER</a>'
            event_actions += f'<button class="reminder-btn" data-title="{event["title"]}" data-date="{event["start_time"].isoformat()}">\n                    🔔 Påminnelse\n                </button>'
            event_actions += '</div>'
        
        # QR code data
        qr_data = f"https://herimoss.no?event={i}"
        
        # Social sharing
        share_text = f"Sjekk ut: {event['title']} - {date_str_no} kl {time_str} på {event['venue']}"
        share_text_encoded = share_text.replace(' ', '%20').replace(':', '%3A')
        
        # prepare title_html with anchor if url exists (info page) ALWAYS prefer info page (not ticket)
        if event.get('url'):
            title_html = f'<a href="{event["url"]}" target="_blank" rel="noopener noreferrer">{event["title"]}</a>'
        else:
            title_html = event['title']

        # Show time range if end_time present in DB (later we can enrich processed_events to include end)
        # (for now we keep existing time_str; extension: attempt to parse end from description placeholder)

        events_html += f'''
        <div class="event-card" 
             data-category="{event['category']}" 
             data-venue="{event['venue']}" 
             data-price-category="{event['price_category']}"
             data-date="{event['start_time'].strftime('%Y-%m-%d')}">
            
            <div class="event-date">
                <div class="event-day">{event['start_time'].day}</div>
                <div class="event-month">{date_str_no.split()[1][:3].upper()}</div>
                <div class="event-weekday">{weekday_no[:3].upper()}</div>
            </div>
            
            <div class="event-info">
                <div class="event-header">
                    <h3 class="event-title">{title_html}</h3>
                    <div class="event-status">
                        {availability_html}
                        <span class="category-tag {event['category']}">{event['category'].title()}</span>
                    </div>
                </div>
                
                <div class="event-details">
                    <span class="event-time">🕒 {time_str}</span>
                    <span class="event-venue">📍 <a href="https://www.verketscene.no/" target="_blank" rel="noopener noreferrer">{event['venue']}</a></span>
                </div>
                
                
                {desc_html}
                
                {price_display}
                
                <div class="event-tools">
                    <button class="qr-btn" data-qr="{qr_data}">📱 QR</button>
                    <button class="share-btn" data-share="{share_text}" data-url="https://herimoss.no">📤 Del</button>
                    <div class="social-share" style="display:none;">
                        <a href="https://www.facebook.com/sharer/sharer.php?u=https://herimoss.no&quote={share_text}" target="_blank">📘 Facebook</a>
                        <a href="https://twitter.com/intent/tweet?text={share_text}&url=https://herimoss.no" target="_blank">🐦 Twitter</a>
                        <a href="https://wa.me/?text={share_text} https://herimoss.no" target="_blank">💬 WhatsApp</a>
                    </div>
                </div>
                
                {event_actions}
            </div>
        </div>
        '''
    
    # Generate filter options
    venue_options = ''.join([f'<label><input type="checkbox" value="{venue}" checked> {venue}</label>' for venue in sorted(venues)])
    category_options = ''.join([f'<label><input type="checkbox" value="{cat}" checked> {cat.title()}</label>' for cat in sorted(categories)])
    
    # Complete HTML page with all features
    html_content = f'''<!DOCTYPE html>
<html lang="no">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Moss Kulturkalender - Alle kulturarrangementer i Moss</title>
    <meta name="description" content="Komplett oversikt over kulturarrangementer i Moss kommune. Konserter, teater, utstillinger og mer fra Moss Kulturhus, Verket Scene og andre lokale arrangører.">
    <meta name="keywords" content="moss, kultur, kalender, arrangementer, konserter, teater, utstillinger, moss kulturhus, verket scene">
    <meta name="author" content="Moss Kulturkalender">
    
    <!-- QR Code library -->
    <script src="https://cdn.jsdelivr.net/npm/qrcode@1.5.3/build/qrcode.min.js"></script>
    
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }}
        
        header {{
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 30px;
            margin-bottom: 30px;
            text-align: center;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
        }}
        
        h1 {{
            color: #2c3e50;
            font-size: 2.5em;
            margin-bottom: 10px;
            font-weight: 300;
        }}
        
        .subtitle {{
            color: #7f8c8d;
            font-size: 1.2em;
            margin-bottom: 20px;
        }}
        
        .status {{
            background: rgba(52, 152, 219, 0.1);
            border: 1px solid #3498db;
            border-radius: 10px;
            padding: 15px;
            margin: 20px 0;
            text-align: center;
        }}
        
        .auto-update-status {{
            position: fixed;
            top: 20px;
            right: 20px;
            background: rgba(0, 0, 0, 0.8);
            color: white;
            padding: 10px 15px;
            border-radius: 20px;
            font-size: 0.9em;
            z-index: 1000;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        
        .update-indicator {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #27ae60;
            animation: pulse 2s infinite;
        }}
        
        @keyframes pulse {{
            0% {{ opacity: 1; }}
            50% {{ opacity: 0.5; }}
            100% {{ opacity: 1; }}
        }}
        
        .controls {{
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 25px;
            margin-bottom: 30px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
        }}
        
        .search-bar {{
            width: 100%;
            padding: 15px 20px;
            border: 2px solid #e0e0e0;
            border-radius: 25px;
            font-size: 1.1em;
            margin-bottom: 20px;
            transition: border-color 0.3s ease;
        }}
        
        .search-bar:focus {{
            outline: none;
            border-color: #3498db;
        }}
        
        .filter-row {{
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
            align-items: center;
            margin-bottom: 20px;
        }}
        
        .date-filters {{
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }}
        
        .date-filter-btn {{
            padding: 8px 16px;
            border: 2px solid #e0e0e0;
            background: white;
            border-radius: 20px;
            cursor: pointer;
            transition: all 0.3s ease;
        }}
        
        .date-filter-btn.active, .date-filter-btn:hover {{
            background: #3498db;
            color: white;
            border-color: #3498db;
        }}
        
        .filter-group {{
            display: flex;
            flex-direction: column;
            gap: 5px;
        }}
        
        .filter-group h4 {{
            color: #2c3e50;
            margin-bottom: 5px;
        }}
        
        .filter-group label {{
            display: flex;
            align-items: center;
            gap: 8px;
            cursor: pointer;
            padding: 5px;
        }}
        
        .view-toggle {{
            display: flex;
            gap: 10px;
            margin-left: auto;
        }}
        
        .view-btn {{
            padding: 10px 20px;
            border: 2px solid #e0e0e0;
            background: white;
            border-radius: 25px;
            cursor: pointer;
            transition: all 0.3s ease;
        }}
        
        .view-btn.active {{
            background: #3498db;
            color: white;
            border-color: #3498db;
        }}
        
        .events-section {{
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 30px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            margin-bottom: 30px;
        }}
        
        .events-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 25px;
        }}
        
        .events-section h2 {{
            color: #2c3e50;
            font-size: 2em;
        }}
        
        .event-count {{
            color: #7f8c8d;
            font-size: 1.1em;
        }}
        
        .events-grid {{
            display: grid;
            gap: 20px;
        }}
        
        .calendar-view {{
            display: grid;
            grid-template-columns: repeat(7, 1fr);
            gap: 1px;
            background: #e0e0e0;
            border-radius: 10px;
            overflow: hidden;
        }}
        
        .calendar-day {{
            background: white;
            min-height: 120px;
            padding: 10px;
            position: relative;
        }}
        
        .calendar-event {{
            font-size: 0.8em;
            background: #3498db;
            color: white;
            padding: 2px 5px;
            border-radius: 3px;
            margin: 1px 0;
            cursor: pointer;
        }}
        
        .event-card {{
            display: flex;
            background: #fff;
            border-radius: 15px;
            padding: 20px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
            border-left: 4px solid #3498db;
            transition: all 0.3s ease;
        }}
        
        .event-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15);
        }}
        
        .event-date {{
            background: linear-gradient(45deg, #667eea, #764ba2);
            color: white;
            border-radius: 10px;
            padding: 15px;
            text-align: center;
            margin-right: 20px;
            min-width: 80px;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }}
        
        .event-day {{
            font-size: 2em;
            font-weight: bold;
            line-height: 1;
        }}
        
        .event-month {{
            font-size: 0.9em;
            margin-top: 5px;
        }}
        
        .event-weekday {{
            font-size: 0.8em;
            opacity: 0.9;
            margin-top: 2px;
        }}
        
        .event-info {{
            flex: 1;
        }}
        
        .event-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 10px;
        }}
        
        .event-title {{
            color: #2c3e50;
            font-size: 1.3em;
            flex: 1;
            margin-right: 15px;
        }}
        
        .event-status {{
            display: flex;
            flex-direction: column;
            gap: 5px;
            align-items: flex-end;
        }}
        
        .status-indicator {{
            padding: 4px 8px;
            border-radius: 15px;
            font-size: 0.8em;
            font-weight: bold;
        }}
        
        .status-indicator.available {{
            background: rgba(39, 174, 96, 0.1);
            color: #27ae60;
        }}
        
        .status-indicator.sold-out {{
            background: rgba(231, 76, 60, 0.1);
            color: #e74c3c;
        }}
        
        .status-indicator.no-tickets {{
            background: rgba(149, 165, 166, 0.1);
            color: #95a5a6;
        }}
        
        .category-tag {{
            padding: 4px 8px;
            border-radius: 15px;
            font-size: 0.8em;
            font-weight: bold;
        }}
        
        .category-tag.musikk {{
            background: rgba(155, 89, 182, 0.1);
            color: #9b59b6;
        }}
        
        .category-tag.teater {{
            background: rgba(230, 126, 34, 0.1);
            color: #e67e22;
        }}
        
        .category-tag.familie {{
            background: rgba(46, 204, 113, 0.1);
            color: #2ecc71;
        }}
        
        .category-tag.komedie {{
            background: rgba(241, 196, 15, 0.1);
            color: #f1c40f;
        }}
        
        .category-tag.festival {{
            background: rgba(231, 76, 60, 0.1);
            color: #e74c3c;
        }}
        
        .category-tag.arrangement {{
            background: rgba(52, 152, 219, 0.1);
            color: #3498db;
        }}
        
        .event-details {{
            margin-bottom: 10px;
        }}
        
        .event-time, .event-venue {{
            display: inline-block;
            margin-right: 15px;
            color: #7f8c8d;
            font-size: 0.9em;
        }}
        
        .event-description {{
            color: #555;
            font-size: 0.9em;
            margin-bottom: 10px;
            line-height: 1.4;
        }}
        
        .read-more-btn {{
            background: none;
            border: none;
            color: #3498db;
            cursor: pointer;
            text-decoration: underline;
        }}
        
        .event-price {{
            color: #27ae60;
            font-weight: bold;
            margin-bottom: 10px;
        }}
        
        .event-tools {{
            display: flex;
            gap: 10px;
            margin-bottom: 10px;
            flex-wrap: wrap;
        }}
        
        .event-tools button {{
            padding: 6px 12px;
            border: 1px solid #e0e0e0;
            background: white;
            border-radius: 15px;
            cursor: pointer;
            font-size: 0.8em;
            transition: all 0.3s ease;
        }}
        
        .event-tools button:hover {{
            background: #f8f9fa;
            border-color: #3498db;
        }}
        
        .social-share {{
            display: flex;
            gap: 10px;
            margin-top: 10px;
        }}
        
        .social-share a {{
            padding: 6px 12px;
            border-radius: 15px;
            text-decoration: none;
            font-size: 0.8em;
            transition: all 0.3s ease;
        }}
        
        .event-actions {{
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }}
        
        .quick-buy-btn {{
            background: #27ae60;
            color: white;
            padding: 10px 20px;
            border-radius: 25px;
            text-decoration: none;
            font-weight: bold;
            transition: all 0.3s ease;
        }}
        
        .quick-buy-btn:hover {{
            background: #2ecc71;
            transform: translateY(-2px);
        }}
        
        .reminder-btn {{
            background: #f39c12;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 25px;
            cursor: pointer;
            font-weight: bold;
            transition: all 0.3s ease;
        }}
        
        .reminder-btn:hover {{
            background: #e67e22;
            transform: translateY(-2px);
        }}
        
        .weather-info {{
            background: rgba(52, 152, 219, 0.1);
            padding: 10px;
            border-radius: 10px;
            margin: 10px 0;
            font-size: 0.9em;
        }}
        
        .modal {{
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0,0,0,0.5);
        }}
        
        .modal-content {{
            background-color: white;
            margin: 15% auto;
            padding: 20px;
            border-radius: 15px;
            width: 80%;
            max-width: 500px;
            text-align: center;
        }}
        
        .close {{
            color: #aaa;
            float: right;
            font-size: 28px;
            font-weight: bold;
            cursor: pointer;
        }}
        
        .close:hover {{
            color: black;
        }}
        
        .hidden {{
            display: none !important;
        }}
        
        @media (max-width: 768px) {{
            .container {{
                padding: 10px;
            }}
            
            h1 {{
                font-size: 2em;
            }}
            
            .filter-row {{
                flex-direction: column;
                align-items: flex-start;
            }}
            
            .view-toggle {{
                margin-left: 0;
                margin-top: 10px;
            }}
            
            .event-card {{
                flex-direction: column;
            }}
            
            .event-date {{
                margin-right: 0;
                margin-bottom: 15px;
                min-width: auto;
                flex-direction: row;
                justify-content: space-around;
                padding: 10px;
            }}
            
            .event-day {{
                font-size: 1.5em;
            }}
            
            .event-header {{
                flex-direction: column;
                align-items: flex-start;
                gap: 10px;
            }}
            
            .event-status {{
                align-items: flex-start;
            }}
            
            .auto-update-status {{
                position: relative;
                top: 0;
                right: 0;
                margin-bottom: 20px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Auto-update status indicator (Feature 17) -->
        <div class="auto-update-status">
            <div class="update-indicator"></div>
            Live oppdatering aktiv
        </div>
        
        <header>
            <h1>🎭 Moss Kulturkalender</h1>
            <p class="subtitle">Din komplette guide til kulturarrangementer i Moss kommune</p>
            
            <div class="status">
                <span class="status-icon">🎉</span>
                <strong>System er aktivt med {len(processed_events)} arrangementer!</strong> Kulturkalenderen viser alle kommende arrangementer fra lokale kilder.
            </div>
        </header>
        
        <!-- Enhanced controls with filtering and search -->
        <div class="controls">
            <!-- Text search (Feature 15) -->
            <input type="text" class="search-bar" placeholder="🔍 Søk i arrangementer (tittel, beskrivelse, artist...)">
            
            <div class="filter-row">
                <!-- Date category filters (Feature 11) -->
                <div class="date-filters">
                    <button class="date-filter-btn active" data-filter="all">Alle</button>
                    <button class="date-filter-btn" data-filter="today">I dag</button>
                    <button class="date-filter-btn" data-filter="week">Denne uken</button>
                    <button class="date-filter-btn" data-filter="month">Neste måned</button>
                </div>
                
                <!-- Venue filter (Feature 12) -->
                <div class="filter-group">
                    <h4>Steder:</h4>
                    {venue_options}
                </div>
                
                <!-- Category filter (Feature 14) -->
                <div class="filter-group">
                    <h4>Kategorier:</h4>
                    {category_options}
                </div>
                
                <!-- Price filter (Feature 13) -->
                <div class="filter-group">
                    <h4>Pris:</h4>
                    <label><input type="checkbox" value="free" checked> Gratis</label>
                    <label><input type="checkbox" value="paid" checked> Betalt</label>
                    <label><input type="checkbox" value="unknown" checked> Ukjent</label>
                </div>
                
                <!-- View toggle (Feature 16) -->
                <div class="view-toggle">
                    <button class="view-btn active" data-view="list">📋 Liste</button>
                    <button class="view-btn" data-view="calendar">📅 Kalender</button>
                </div>
            </div>
        </div>
        
        <div class="events-section">
            <div class="events-header">
                <h2>📅 Kommende arrangementer</h2>
                <div class="event-count">
                    <span id="showing-count">{len(processed_events)}</span> av {len(processed_events)} arrangementer
                </div>
            </div>
            
            <!-- List view -->
            <div class="events-grid list-view">
                {events_html}
            </div>
            
            <!-- Calendar view (hidden by default) -->
            <div class="calendar-view hidden" id="calendar-view">
                <!-- Calendar will be generated by JavaScript -->
            </div>
        </div>
        
        <footer style="text-align: center; margin-top: 40px; padding: 20px; color: rgba(255, 255, 255, 0.8);">
            <p>🌍 <strong>Moss Kulturkalender</strong> - Skapt med ❤️ for Moss kommune</p>
            <p>Automatisk oppdatert fra Moss Kulturhus, Verket Scene og andre lokale kilder</p>
            <p>Besøk gjerne <a href="https://moss.kommune.no" style="color: rgba(255,255,255,0.9);">moss.kommune.no</a> for offisiell informasjon</p>
        </footer>
    </div>
    
    <!-- QR Code Modal (Feature 8) -->
    <div id="qrModal" class="modal">
        <div class="modal-content">
            <span class="close">&times;</span>
            <h3>📱 QR-kode for arrangement</h3>
            <div id="qrcode"></div>
            <p>Skann med mobilen for å dele arrangementet</p>
        </div>
    </div>
    
    <!-- Weather modal (Feature 19) -->
    <div id="weatherModal" class="modal">
        <div class="modal-content">
            <span class="close">&times;</span>
            <h3>🌤️ Værvarsel</h3>
            <div id="weather-content">Laster værdata...</div>
        </div>
    </div>
    
    <!-- Evening planner modal (Feature 20) -->
    <div id="plannerModal" class="modal">
        <div class="modal-content">
            <span class="close">&times;</span>
            <h3>🍽️ Planlegg kvelden</h3>
            <div id="planner-content">
                <p>Forslag til en perfekt kveld i Moss:</p>
                <div id="planner-suggestions"></div>
            </div>
        </div>
    </div>
    
    <script>
        // Global variables
        let allEvents = [];
        let filteredEvents = [];
        let currentView = 'list';
        
        // Initialize
        document.addEventListener('DOMContentLoaded', function() {{
            initializeEvents();
            initializeFilters();
            initializeModals();
            initializeReminders();
            startAutoUpdate();
        }});
        
        function initializeEvents() {{
            allEvents = Array.from(document.querySelectorAll('.event-card')).map(card => {{
                return {{
                    element: card,
                    title: card.querySelector('.event-title').textContent,
                    venue: card.dataset.venue,
                    category: card.dataset.category,
                    priceCategory: card.dataset.priceCategory,
                    date: new Date(card.dataset.date)
                }};
            }});
            filteredEvents = [...allEvents];
        }}
        
        // Search functionality (Feature 15)
        document.querySelector('.search-bar').addEventListener('input', function(e) {{
            const searchTerm = e.target.value.toLowerCase();
            filterEvents();
        }});
        
        // Date filters (Feature 11)
        document.querySelectorAll('.date-filter-btn').forEach(btn => {{
            btn.addEventListener('click', function() {{
                document.querySelectorAll('.date-filter-btn').forEach(b => b.classList.remove('active'));
                this.classList.add('active');
                filterEvents();
            }});
        }});
        
        // Venue and category filters (Features 12, 14)
        document.querySelectorAll('.filter-group input[type="checkbox"]').forEach(checkbox => {{
            checkbox.addEventListener('change', filterEvents);
        }});
        
        // View toggle (Feature 16)
        document.querySelectorAll('.view-btn').forEach(btn => {{
            btn.addEventListener('click', function() {{
                document.querySelectorAll('.view-btn').forEach(b => b.classList.remove('active'));
                this.classList.add('active');
                toggleView(this.dataset.view);
            }});
        }});
        
        function filterEvents() {{
            const searchTerm = document.querySelector('.search-bar').value.toLowerCase();
            const dateFilter = document.querySelector('.date-filter-btn.active').dataset.filter;
            const venueFilters = Array.from(document.querySelectorAll('.filter-group input[value]')).filter(cb => cb.checked && cb.closest('.filter-group').querySelector('h4').textContent.includes('Steder')).map(cb => cb.value);
            const categoryFilters = Array.from(document.querySelectorAll('.filter-group input[value]')).filter(cb => cb.checked && cb.closest('.filter-group').querySelector('h4').textContent.includes('Kategorier')).map(cb => cb.value);
            const priceFilters = Array.from(document.querySelectorAll('.filter-group input[value]')).filter(cb => cb.checked && cb.closest('.filter-group').querySelector('h4').textContent.includes('Pris')).map(cb => cb.value);
            
            const now = new Date();
            const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
            const weekFromNow = new Date(today.getTime() + 7 * 24 * 60 * 60 * 1000);
            const monthFromNow = new Date(today.getTime() + 30 * 24 * 60 * 60 * 1000);
            
            filteredEvents = allEvents.filter(event => {{
                // Search filter
                const matchesSearch = !searchTerm || 
                    event.title.toLowerCase().includes(searchTerm) ||
                    event.element.querySelector('.event-description')?.textContent.toLowerCase().includes(searchTerm) ||
                    event.venue.toLowerCase().includes(searchTerm);
                
                // Date filter
                let matchesDate = true;
                if (dateFilter === 'today') {{
                    matchesDate = event.date >= today && event.date < new Date(today.getTime() + 24 * 60 * 60 * 1000);
                }} else if (dateFilter === 'week') {{
                    matchesDate = event.date >= today && event.date <= weekFromNow;
                }} else if (dateFilter === 'month') {{
                    matchesDate = event.date >= today && event.date <= monthFromNow;
                }}
                
                // Venue filter
                const matchesVenue = venueFilters.length === 0 || venueFilters.includes(event.venue);
                
                // Category filter
                const matchesCategory = categoryFilters.length === 0 || categoryFilters.includes(event.category);
                
                // Price filter
                const matchesPrice = priceFilters.length === 0 || priceFilters.includes(event.priceCategory);
                
                return matchesSearch && matchesDate && matchesVenue && matchesCategory && matchesPrice;
            }});
            
            updateDisplay();
        }}
        
        function updateDisplay() {{
            // Hide all events
            allEvents.forEach(event => event.element.style.display = 'none');
            
            // Show filtered events
            filteredEvents.forEach(event => event.element.style.display = 'flex');
            
            // Update count
            document.getElementById('showing-count').textContent = filteredEvents.length;
        }}
        
        function toggleView(view) {{
            currentView = view;
            const listView = document.querySelector('.list-view');
            const calendarView = document.getElementById('calendar-view');
            
            if (view === 'calendar') {{
                listView.classList.add('hidden');
                calendarView.classList.remove('hidden');
                generateCalendarView();
            }} else {{
                listView.classList.remove('hidden');
                calendarView.classList.add('hidden');
            }}
        }}
        
        function generateCalendarView() {{
            // Simple calendar generation - would need more complex logic for full calendar
            const calendarView = document.getElementById('calendar-view');
            calendarView.innerHTML = '<p style="text-align: center; padding: 50px;">📅 Kalendervisning kommer snart!</p>';
        }}
        
        // Read more functionality (Feature 6)
        document.addEventListener('click', function(e) {{
            if (e.target.classList.contains('read-more-btn')) {{
                const description = e.target.closest('.event-description');
                const preview = description.querySelector('.desc-preview');
                const full = description.querySelector('.desc-full');
                
                if (preview.style.display === 'none') {{
                    preview.style.display = 'inline';
                    full.style.display = 'none';
                    e.target.textContent = 'Les mer';
                }} else {{
                    preview.style.display = 'none';
                    full.style.display = 'inline';
                    e.target.textContent = 'Les mindre';
                }}
            }}
        }});
        
        // QR Code functionality (Feature 8)
        document.addEventListener('click', function(e) {{
            if (e.target.classList.contains('qr-btn')) {{
                const qrData = e.target.dataset.qr;
                const modal = document.getElementById('qrModal');
                const qrDiv = document.getElementById('qrcode');
                qrDiv.innerHTML = '';
                
                QRCode.toCanvas(qrDiv, qrData, function (error) {{
                    if (error) console.error(error);
                }});
                
                modal.style.display = 'block';
            }}
        }});
        
        // Social sharing (Feature 9)
        document.addEventListener('click', function(e) {{
            if (e.target.classList.contains('share-btn')) {{
                const socialDiv = e.target.nextElementSibling;
                socialDiv.style.display = socialDiv.style.display === 'none' ? 'flex' : 'none';
            }}
        }});
        
        // Reminders (Feature 4)
        function initializeReminders() {{
            document.addEventListener('click', function(e) {{
                if (e.target.classList.contains('reminder-btn')) {{
                    const title = e.target.dataset.title;
                    const date = new Date(e.target.dataset.date);
                    
                    if (navigator.userAgent.includes('Mobile')) {{
                        // Try to create calendar event
                        const calendarUrl = `data:text/calendar;charset=utf8,BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
DTSTART:${{date.toISOString().replace(/[-:]/g, '').split('.')[0]}}Z
SUMMARY:${{title}}
DESCRIPTION:Arrangement i Moss - herimoss.no
LOCATION:Moss
END:VEVENT
END:VCALENDAR`;
                        
                        const link = document.createElement('a');
                        link.href = calendarUrl;
                        link.download = 'arrangement.ics';
                        link.click();
                    }} else {{
                        alert(`Påminnelse satt for: ${{title}}\\nDato: ${{date.toLocaleDateString('no-NO')}}`);
                    }}
                }}
            }});
        }}
        
        // Modal functionality
        function initializeModals() {{
            document.querySelectorAll('.close').forEach(closeBtn => {{
                closeBtn.addEventListener('click', function() {{
                    this.closest('.modal').style.display = 'none';
                }});
            }});
            
            window.addEventListener('click', function(e) {{
                if (e.target.classList.contains('modal')) {{
                    e.target.style.display = 'none';
                }}
            }});
        }}
        
        // Auto-update status (Feature 17)
        function startAutoUpdate() {{
            setInterval(() => {{
                // In a real implementation, this would check for new events
                console.log('Checking for updates...');
            }}, 60000); // Check every minute
            
            // Auto-refresh every 30 minutes
            setTimeout(() => {{
                window.location.reload();
            }}, 30 * 60 * 1000);
        }}
        
        // Weather integration (Feature 19)
        function showWeather(venue, date) {{
            const modal = document.getElementById('weatherModal');
            const content = document.getElementById('weather-content');
            
            // Simulated weather data
            content.innerHTML = `
                <div class="weather-info">
                    <h4>Værvarsel for ${{venue}} - ${{date.toLocaleDateString('no-NO')}}</h4>
                    <p>🌤️ Delvis skyet, 15°C</p>
                    <p>💧 10% sjanse for regn</p>
                    <p>💨 Svak vind fra vest</p>
                    <p><em>Perfekt vær for kulturopplevelser!</em></p>
                </div>
            `;
            
            modal.style.display = 'block';
        }}
        
        // Evening planner (Feature 20)
        function showEveningPlanner(venue, time) {{
            const modal = document.getElementById('plannerModal');
            const content = document.getElementById('planner-suggestions');
            
            const suggestions = [
                `🍽️ Middag før forestilling: Restaurant Refsnes Gods (10 min gange)`,
                `🚗 Parkering: Moss sentrum parkering (2 min gange til ${{venue}})`,
                `☕ Kaffe etterpå: Café Central (5 min gange)`,
                `🚌 Transport hjem: Buss linje 140 (avgår 22:45 fra Moss stasjon)`
            ];
            
            content.innerHTML = suggestions.map(s => `<p>${{s}}</p>`).join('');
            modal.style.display = 'block';
        }}
        
        // Initialize filters
        function initializeFilters() {{
            filterEvents();
        }}
        
        // Add click handlers for weather and planner
        document.addEventListener('click', function(e) {{
            if (e.target.textContent.includes('🌤️')) {{
                const eventCard = e.target.closest('.event-card');
                const venue = eventCard.dataset.venue;
                const date = new Date(eventCard.dataset.date);
                showWeather(venue, date);
            }}
            
            if (e.target.textContent.includes('🍽️')) {{
                const eventCard = e.target.closest('.event-card');
                const venue = eventCard.dataset.venue;
                const time = eventCard.querySelector('.event-time').textContent;
                showEveningPlanner(venue, time);
            }}
        }});
    </script>
</body>
</html>'''

    return html_content

def generate_simple_listing(use_mariadb=True):
    print('[DEBUG] generate_simple_listing invoked')
    # Fetch raw events via existing helper
    print('[DEBUG] starting DB fetch, use_mariadb=', use_mariadb, 'HAS_MYSQL=', HAS_MYSQL)
    try:
        raw = _fetch_events_mariadb() if (use_mariadb and HAS_MYSQL) else _fetch_events_sqlite()
    except Exception:
        raw = _fetch_events_sqlite()
    print('[DEBUG] DB fetch returned rows:', len(raw))
    oslo_tz = pytz.timezone('Europe/Oslo')
    events = []
    # Controlled enrichment settings
    enable_enrichment = os.getenv('ENRICH_DESCRIPTIONS', '0') == '1'
    max_enrich = int(os.getenv('ENRICH_MAX', '15'))  # cap per generation
    enrich_timeout = int(os.getenv('ENRICH_TIMEOUT', '5'))
    fetched_this_run = 0
    desc_cache = _load_description_cache() if enable_enrichment else {}
    cache_dirty = False
    now_ts = time.time()
    max_age = _DESC_CACHE_MAX_AGE_DAYS * 86400
    for row in raw:
        if len(row) == 8:
            title, venue, start_time_val, end_time_val, info_url, description, price, ticket_url = row
        else:
            title, venue, start_time_val, end_time_val, info_url, description, price = row
            ticket_url = None
        # Skip festival pass type umbrella events
        if title and 'festivalpass' in title.lower():
            continue
        try:
            if isinstance(start_time_val, datetime):
                start_dt = start_time_val
            else:
                start_dt = datetime.fromisoformat(str(start_time_val).replace('Z','+00:00'))
            if start_dt.tzinfo is None:
                start_dt = oslo_tz.localize(start_dt)
            local_start = start_dt.astimezone(oslo_tz)
        except Exception:
            continue
        # End time
        local_end = None
        if end_time_val:
            try:
                if isinstance(end_time_val, datetime):
                    end_dt = end_time_val
                else:
                    end_dt = datetime.fromisoformat(str(end_time_val).replace('Z','+00:00'))
                if end_dt.tzinfo is None:
                    end_dt = oslo_tz.localize(end_dt)
                local_end = end_dt.astimezone(oslo_tz)
            except Exception:
                local_end = None
        # Enrich description if missing & allowed
        if enable_enrichment and fetched_this_run < max_enrich and (not description or len(description.strip()) < 40) and info_url and info_url.startswith('http'):
            cache_entry = desc_cache.get(info_url)
            use_cached = False
            if cache_entry and isinstance(cache_entry, dict):
                ts = cache_entry.get('ts', 0)
                if now_ts - ts < max_age and cache_entry.get('text'):
                    description = cache_entry['text']
                    use_cached = True
            if not use_cached:
                try:
                    description_fetched = fetch_detail_description(info_url, timeout=enrich_timeout)
                except Exception:
                    description_fetched = ''
                if description_fetched:
                    description = description_fetched
                    desc_cache[info_url] = {'text': description_fetched, 'ts': now_ts}
                    cache_dirty = True
                fetched_this_run += 1
        summary, valid = ai_summarize_and_validate(title, description or '')
        # Provider classification (source-like) via URL / venue heuristics
        provider = 'Diverse'
        parsed_domain = None
        try:
            if info_url:
                parsed_domain = urlparse(info_url).netloc.lower()
        except Exception:
            parsed_domain = None
        if parsed_domain and 'verketscene' in parsed_domain:
            provider = 'Verket Scene'
        elif parsed_domain and 'mosskulturhus' in parsed_domain:
            provider = 'Moss Kulturhus'
        elif venue and any(v.lower() in venue.lower() for v in ['samfunnshuset','parkteatret','house of foundation']):
            provider = 'Moss Kulturhus'
        elif venue and any(v.lower() in venue.lower() for v in ['pub','bar','kro','cafe','privat']):
            provider = 'Privat'

        events.append({
            'title': title,
            'url': info_url if info_url and info_url != 'None' else None,
            'date': local_start.strftime('%Y-%m-%d'),
            'time': local_start.strftime('%H:%M'),
            'end_time': local_end.strftime('%H:%M') if local_end and local_end.date()==local_start.date() else None,
            'venue': venue or '',
            'summary': summary,
            'valid': valid,
            'price': price if price not in (None,'None','null','') else None,
            'provider': provider
        })
        if len(events) % 20 == 0:
            print(f"[DEBUG] processed events: {len(events)}")
    # Build minimal HTML (rows)
    rows = []
    for idx, ev in enumerate(events):
        time_range = ev['time'] + (f"–{ev['end_time']}" if ev.get('end_time') else '')
        date_line = f"{ev['date']} kl {time_range}{' – ' + ev['venue'] if ev.get('venue') else ''}"
        title_html = f"<a href='{ev['url']}' target='_blank' rel='noopener noreferrer'>{ev['title']}</a>" if ev['url'] else ev['title']
        badge = '' if ev['valid'] else "<span class='invalid'>⚠️</span>"
        summary_html = f"<p class='summary'>{ev['summary']}</p>" if ev['summary'] else ''
        price_html = f"<span class='price'>{ev['price']}</span>" if ev.get('price') else ''
        provider_tag = f"<span class='provider-tag'>{ev['provider']}</span>"
        search_blob = ' '.join([ev.get('title',''), ev.get('summary',''), ev.get('venue',''), ev.get('provider','')]).lower()
        rows.append(
            f"<div class='event-row provider-{ev['provider'].lower().replace(' ','-')}' data-provider='{ev['provider']}' data-search='{search_blob}' data-idx='{idx}'>"+
            f"<div class='when'>{date_line} {price_html} {provider_tag}</div><h3 class='title'>{title_html} {badge}</h3>{summary_html}<div class='actions'><button class='reminder' data-start='{ev['date']}T{ev['time']}' data-end='{ev['date']}T{ev['end_time']}' data-title='{ev['title']}'>🔔 Få påminnelse</button><button class='share' data-title='{ev['title']}' data-date='{ev['date']} {ev['time']}'>📤 Del</button></div></div>"
        )
    minimal_css = """
    body{font-family:system-ui,Segoe UI,Arial,sans-serif;margin:0;padding:0;background:#f1f5f9;color:#222}
    header{background:#0f172a;color:#fff;padding:18px 20px;display:flex;flex-direction:column;gap:6px}
    h1{font-weight:600;margin:0;font-size:1.6rem;letter-spacing:.5px}
    .topline{font-size:.7rem;opacity:.7;letter-spacing:1px;text-transform:uppercase}
    .searchbar{margin-top:4px;display:flex;gap:8px;flex-wrap:wrap;align-items:center}
    .searchbar input{flex:1;min-width:240px;padding:8px 12px;border:1px solid #334155;border-radius:10px;background:#1e293b;color:#fff;font-size:.85rem}
    .legend{display:flex;flex-wrap:wrap;gap:6px;font-size:.6rem;margin-top:6px}
    .legend span{padding:4px 10px;border-radius:20px;background:#1e293b;border:1px solid #334155;letter-spacing:.5px}
    .event-row{background:#fff;border:1px solid #e2e8f0;border-radius:14px;padding:18px;box-shadow:0 2px 4px rgba(0,0,0,0.05);} 
    .when{font-size:.9rem;color:#555;margin-bottom:4px;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
    .price{background:#eef6ff;color:#0b4a94;padding:2px 8px;border-radius:14px;font-size:.7rem;font-weight:600;letter-spacing:.5px}
    .provider-tag{background:#e2e8f0;color:#334155;padding:2px 8px;border-radius:14px;font-size:.55rem;font-weight:600;letter-spacing:.5px;text-transform:uppercase}
    .title{margin:.2rem 0 .5rem;font-size:1.05rem;line-height:1.3}
    .title a{text-decoration:none;color:#1a4c8f}
    .title a:hover{text-decoration:underline}
    .summary{margin:.4rem 0 0;font-size:.9rem;line-height:1.4;color:#333}
    .actions{margin-top:8px;display:flex;gap:8px}
    button{border:none;background:#1a4c8f;color:#fff;padding:6px 14px;border-radius:20px;cursor:pointer;font-size:.75rem;letter-spacing:.5px;font-weight:500}
    button.share{background:#2563eb}
    button:hover{opacity:.9}
    .invalid{color:#d97706;font-size:.9rem}
    main{padding:20px;max-width:920px;margin:0 auto}
    .meta{font-size:.7rem;text-transform:uppercase;letter-spacing:1px;color:#666;margin-top:2px}
    footer{margin-top:40px;font-size:.65rem;color:#475569;text-align:center;padding:30px 10px;background:#f8fafc;border-top:1px solid #e2e8f0}
    /* Provider diffuse backgrounds */
    .provider-moss-kulturhus{background:linear-gradient(135deg,#f6f3ff 0%,#ffffff 50%)}
    .provider-verket-scene{background:linear-gradient(135deg,#f0fdfa 0%,#ffffff 55%)}
    .provider-privat{background:linear-gradient(135deg,#fff7ed 0%,#ffffff 55%)}
    .provider-diverse{background:linear-gradient(135deg,#f1f5f9 0%,#ffffff 55%)}
    .provider-moss-kulturhus{border-left:5px solid #8b5cf6}
    .provider-verket-scene{border-left:5px solid #0d9488}
    .provider-privat{border-left:5px solid #d97706}
    .provider-diverse{border-left:5px solid #64748b}
    """
    script = """
      function buildICS(title, startDateTime, endDateTime){
            // Expect times in 'YYYY-MM-DDTHH:MM'; if end missing add +2h
            const dt = new Date(startDateTime+':00');
         const pad=n=>String(n).padStart(2,'0');
         const icsDate = dt.getFullYear()+pad(dt.getMonth()+1)+pad(dt.getDate())+'T'+pad(dt.getHours())+pad(dt.getMinutes())+'00';
            let dtEnd;
            if(endDateTime){
                dtEnd = new Date(endDateTime+':00');
            } else {
                dtEnd = new Date(dt.getTime()+2*60*60*1000); // +2h fallback
            }
         const icsEnd = dtEnd.getFullYear()+pad(dtEnd.getMonth()+1)+pad(dtEnd.getDate())+'T'+pad(dtEnd.getHours())+pad(dtEnd.getMinutes())+'00';
         const body = 'BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//Her i Moss//EN\nBEGIN:VEVENT\nDTSTAMP:'+icsDate+'Z\nDTSTART:'+icsDate+'Z\nDTEND:'+icsEnd+'Z\nSUMMARY:'+title.replace(/,/g,'')+'\nEND:VEVENT\nEND:VCALENDAR';
         const blob=new Blob([body],{type:'text/calendar'});return URL.createObjectURL(blob);
     }
    document.addEventListener('click',e=>{
       if(e.target.classList.contains('reminder')){
              const title=e.target.dataset.title;const start=e.target.dataset.start;const end=e.target.dataset.end;const url=buildICS(title,start,end && end.slice(0,16));
           const a=document.createElement('a');a.href=url;a.download=title.replace(/[^a-zA-Z0-9_-]+/g,'_')+'.ics';document.body.appendChild(a);a.click();a.remove();
       }
       if(e.target.classList.contains('share')){
           const t=e.target.dataset.title;const d=e.target.dataset.date;const text=t+' '+d;navigator.clipboard.writeText(text).then(()=>alert('Kopiert til utklippstavlen: '+text));
       }
    });
    """
    legend = "".join([
            "<span style='background:#f6f3ff;color:#4c1d95'>Moss Kulturhus</span>",
            "<span style='background:#f0fdfa;color:#065f46'>Verket Scene</span>",
            "<span style='background:#fff7ed;color:#9a3412'>Privat</span>",
            "<span style='background:#f1f5f9;color:#334155'>Diverse</span>"
    ])
    generated_ts = datetime.now().strftime('%Y-%m-%d %H:%M')
    total_events = len(events)
    moss_count = sum(1 for e in events if e['provider']== 'Moss Kulturhus')
    verket_count = sum(1 for e in events if e['provider']== 'Verket Scene')
    privat_count = sum(1 for e in events if e['provider']== 'Privat')
    diverse_count = sum(1 for e in events if e['provider']== 'Diverse')
    # Stats: upcoming per month & this week
    from collections import Counter
    month_counter = Counter()
    week_count = 0
    today = datetime.now().date()
    for e in events:
        try:
            d = datetime.strptime(e['date'], '%Y-%m-%d').date()
        except Exception:
            continue
        month_counter[d.strftime('%Y-%m')] += 1
        if 0 <= (d - today).days <= 7:
            week_count += 1
    month_stats_html = ''.join(f"<li><strong>{m}</strong>: {c}</li>" for m,c in sorted(month_counter.items()))
    # Additional design CSS (kept simple to avoid braces issues in f-string)
    extra_css = """
    nav{background:#1e293b;color:#fff;padding:10px 18px;display:flex;gap:18px;align-items:center;font-size:.8rem;flex-wrap:wrap}
    nav a{color:#cbd5e1;text-decoration:none;padding:6px 10px;border-radius:6px;font-weight:500}
    nav a:hover,nav a.active{background:#334155;color:#fff}
    .layout{max-width:1180px;margin:0 auto}
    .events-grid{margin-top:22px;display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:26px;margin-bottom:50px}
    .event-row{display:flex;flex-direction:column;height:100%;}
    .event-row .summary{flex-grow:1}
        .view-anchor{position:relative;top:-60px}
        section{scroll-margin-top:80px}
        #tips-form-wrapper{background:#ffffff;border:1px solid #e2e8f0;padding:20px 22px;border-radius:14px;margin-top:18px;max-width:760px}
        #tips-form-wrapper h2{margin:0 0 10px;font-size:1.2rem}
        form.tips-form label{display:block;font-size:.7rem;letter-spacing:.5px;font-weight:600;margin-top:14px;text-transform:uppercase;color:#475569}
        form.tips-form input,form.tips-form textarea,form.tips-form select{width:100%;padding:10px 12px;margin-top:4px;border:1px solid #cbd5e1;border-radius:10px;font:inherit;background:#f8fafc}
        form.tips-form textarea{min-height:140px;resize:vertical}
        .inline-fields{display:flex;gap:12px}
        .inline-fields .field{flex:1}
        .form-hint{font-size:.6rem;color:#64748b;margin-top:3px}
        .hp-field{position:absolute;left:-5000px;top:-5000px}
        .chips{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px}
        .chip{background:#e2e8f0;color:#334155;padding:4px 10px;border-radius:20px;font-size:.55rem;font-weight:600;letter-spacing:.5px}
        .stats-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px;margin-top:18px}
        .stat-card{background:#fff;border:1px solid #e2e8f0;padding:16px 14px;border-radius:14px;box-shadow:0 1px 2px rgba(0,0,0,.05)}
        .stat-card h3{margin:0 0 6px;font-size:.8rem;text-transform:uppercase;letter-spacing:.5px;color:#475569}
        .stat-big{font-size:1.8rem;font-weight:600;color:#0f172a}
        .month-list{columns:2;column-gap:30px;font-size:.75rem;margin:14px 0 0;padding:0;list-style:none}
        .month-list li{margin:2px 0;padding:2px 4px;border-radius:4px}
        .about{background:#ffffff;border:1px solid #e2e8f0;padding:22px 24px;border-radius:16px;line-height:1.55;margin-top:22px;max-width:860px}
        footer{margin-top:60px}
        .floating-top{position:fixed;bottom:18px;right:18px;background:#1e3a8a;color:#fff;border:none;border-radius:30px;padding:10px 16px;font-size:.7rem;cursor:pointer;box-shadow:0 4px 10px rgba(0,0,0,.25)}
        .floating-top:hover{opacity:.9}
        /* Hero video */
        .hero{position:relative;border-radius:18px;overflow:hidden;height:300px;margin-top:12px;background:linear-gradient(135deg,#1e293b,#0f172a);}
        .hero video{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;filter:brightness(.55);}
        .hero .hero-overlay{position:relative;z-index:2;display:flex;flex-direction:column;justify-content:center;height:100%;padding:38px 42px;color:#fff;}
        .hero h1{font-size:2.4rem;margin:0 0 10px;font-weight:600;letter-spacing:.5px;color:#fff}
        .hero-tagline{font-size:.9rem;max-width:520px;line-height:1.5;opacity:.9;margin:0}
        /* Pager */
        #pager{display:flex;align-items:center;gap:10px;font-size:.7rem;margin:18px 0 6px;flex-wrap:wrap}
        #pager button{background:#334155;padding:6px 12px;border-radius:8px;font-size:.65rem}
        #pager button[disabled]{opacity:.35;cursor:not-allowed}
        #pager .page-info{font-weight:600;letter-spacing:.5px;color:#475569}
        #pager .show-all{background:#1d4ed8}
    /* Fjorddis sidebakgrunn (stor skjerm) */
    @keyframes fjordDrift{0%{transform:translateY(0)}50%{transform:translateY(25px)}100%{transform:translateY(0)}}
    body::before,body::after{content:"";position:fixed;top:0;bottom:0;width:22vw;pointer-events:none;z-index:-1;filter:blur(40px) saturate(140%);opacity:.45;transition:opacity .8s ease}
    body::before{left:0;background:radial-gradient(circle at 60% 40%,rgba(18,54,92,.55),rgba(10,24,38,.1) 70%,transparent 100%),linear-gradient(180deg,rgba(12,53,92,.35),rgba(4,15,24,.8));animation:fjordDrift 38s ease-in-out infinite}
    body::after{right:0;background:radial-gradient(circle at 40% 60%,rgba(24,80,120,.5),rgba(6,20,34,.1) 70%,transparent 100%),linear-gradient(180deg,rgba(6,26,44,.55),rgba(2,10,18,.85));animation:fjordDrift 46s ease-in-out infinite reverse}
    @media (max-width:1280px){body::before,body::after{display:none}}
    @media (prefers-reduced-motion:reduce){body::before,body::after{animation:none}}
        """
    html = f"""<!DOCTYPE html><html lang='no'><head><meta charset='utf-8'><title>Moss Kulturkalender – enkel liste</title><meta name='viewport' content='width=device-width,initial-scale=1'>
        <meta name='description' content='Kompakt oversikt over kommende kulturarrangementer i Moss (konserter, teater, festivaler).'>
        <link rel='alternate' type='text/calendar' title='iCal feed' href='events.ics'>
        <link rel='alternate' type='application/rss+xml' title='RSS feed' href='rss.xml'>
        <style>{minimal_css}{extra_css}</style></head><body>
        <nav class='layout'>
            <a href='#oversikt' class='active'>Oversikt</a>
            <a href='#tips'>Tips</a>
            <a href='#statistikk'>Statistikk</a>
            <a href='#om'>Om oss</a>
        </nav>
        <header class='layout' style='border-bottom:1px solid #1e293b;padding-bottom:20px;'>
                <div class='hero'>
                    <video autoplay muted loop playsinline preload='metadata'>
                        <source src='2022395-hd_1920_1080_30fps.mp4' type='video/mp4'>
                    </video>
                    <div class='hero-overlay'>
                        <h1>🎭 Moss Kulturkalender</h1>
                        <p class='hero-tagline'>Fenomenbasert oversikt over konserter, forestillinger og kultur i Moss – samlet uten støy, trackers eller innlogging.</p>
                        <div class='statusbar' style='background:rgba(255,255,255,.15);color:#fff;padding:10px 14px;border-radius:12px;margin-top:16px;font-size:.78rem;border:1px solid rgba(255,255,255,.25)'>🎉 <strong>{total_events} aktive</strong> | Denne uken: {week_count} | Neste måned(er): {sum(c for m,c in month_counter.items())}</div>
                    </div>
                </div>
                <div class='searchbar' style='margin-top:14px'>
                         <input id='search' placeholder='Søk i arrangementer (tittel, tekst, sted)...' aria-label='Søk'>
                </div>
                <div class='legend' style='margin:10px 0 0'>{legend}</div>
        </header>
        <main class='layout'>
            <div id='oversikt' class='view-anchor'></div>
            <div class='meta'>Generert {generated_ts}</div>
            <div id='pager'>
                <button id='prevPage' disabled>◀ Forrige</button>
                <span class='page-info' id='pageInfo'>Side 1 av 1</span>
                <button id='nextPage'>Neste ▶</button>
                <button id='showAll' class='show-all'>Vis alle</button>
            </div>
            <div id='eventsContainer' class='events-grid'>{''.join(rows)}</div>
            <section id='tips'>
                <div id='tips-form-wrapper'>
                     <h2>Tipse om arrangement</h2>
                     <p style='font-size:.8rem;color:#475569;margin:0 0 10px'>Fyll inn detaljer så vi kan legge det inn. Krever manuell godkjenning. Alle felt unntatt pris er påkrevd.</p>
                     <form class='tips-form' id='tipsForm' novalidate>
                            <div class='hp-field'><label>La stå: <input type='text' name='website' value=''></label></div>
                            <input type='hidden' name='ts' id='form_ts'>
                            <input type='hidden' name='token' id='form_token'>
                            <label>Tittel<input name='title' required maxlength='160'></label>
                            <div class='inline-fields'>
                                <div class='field'><label>Dato<input type='date' name='date' required></label></div>
                                <div class='field'><label>Start (HH:MM)<input type='time' name='start' required></label></div>
                                <div class='field'><label>Slutt (valgfritt)<input type='time' name='end'></label></div>
                            </div>
                            <label>Sted / Venue<input name='venue' required maxlength='120'></label>
                            <label>Pris (valgfritt)<input name='price' maxlength='60' placeholder='f.eks. kr 250'></label>
                            <label>Lenke til mer info / billetter (https://)<input name='url' type='url' required></label>
                            <label>Beskrivelse<textarea name='description' required maxlength='1800' placeholder='Kort beskrivelse og evt. artistinfo'></textarea></label>
                            <div class='inline-fields'>
                                <div class='field'><label>Antispam: Hva er <span id='spamQ'></span>?<input name='spam_answer' required></label><div class='form-hint'>Enkelt regnestykke for å bekrefte at du er menneske.</div></div>
                            </div>
                            <button type='submit' style='margin-top:18px'>Send inn forslag</button>
                            <div id='tipsStatus' style='margin-top:10px;font-size:.75rem'></div>
                     </form>
                </div>
            </section>
            <section id='statistikk' style='margin-top:40px'>
                <h2 style='font-size:1.4rem;margin:0 0 10px'>Statistikk</h2>
                <div class='stats-cards'>
                     <div class='stat-card'><h3>Totalt</h3><div class='stat-big'>{total_events}</div><div style='font-size:.65rem'>Aktive kommende</div></div>
                     <div class='stat-card'><h3>Denne uken</h3><div class='stat-big'>{week_count}</div><div style='font-size:.65rem'>0-7 dager</div></div>
                     <div class='stat-card'><h3>Moss Kulturhus</h3><div class='stat-big'>{moss_count}</div></div>
                     <div class='stat-card'><h3>Verket Scene</h3><div class='stat-big'>{verket_count}</div></div>
                     <div class='stat-card'><h3>Privat</h3><div class='stat-big'>{privat_count}</div></div>
                     <div class='stat-card'><h3>Diverse</h3><div class='stat-big'>{diverse_count}</div></div>
                </div>
                <h3 style='margin:24px 0 6px;font-size:.85rem;text-transform:uppercase;letter-spacing:.5px;color:#475569'>Fordeling per måned</h3>
                <ul class='month-list'>{month_stats_html}</ul>
            </section>
            <section id='om' style='margin-top:50px'>
                <div class='about'>
                    <h2 style='margin-top:0'>Om Moss Kulturkalender</h2>
                    <p>Denne tjenesten er et uoffisielt, åpent prosjekt som samler kulturarrangementer i Moss i ett lettlest grensesnitt. Ingen trackers, ingen innlogging, bare rask oversikt. Data oppdateres ved kjøring av et Python-skript som henter og normaliserer offentlig tilgjengelig informasjon (kilder utvides gradvis).</p>
                    <p><strong>Mål:</strong> Gjøre det enklere å oppdage og planlegge lokale kulturopplevelser på tvers av scener og arrangører.</p>
                    <p><strong>Videre planer:</strong> Flere kilder, iCal feed, API-endepunkt, bedre datakvalitet (automatisk verifisering) og historikk.</p>
                    <p>Har du innspill eller ønsker bidrag? Bruk tips-skjemaet over eller ta kontakt.</p>
                </div>
            </section>
        </main>
    <footer>
                <div style='max-width:900px;margin:0 auto;line-height:1.5'>
                    Generert {generated_ts}. <a href='events.ics' style='color:#1d4ed8;text-decoration:none'>📅 iCal</a> | <a href='rss.xml' style='color:#1d4ed8;text-decoration:none'>📰 RSS</a>. Teknologi: Python, BeautifulSoup, MariaDB, statisk HTML. ICS-knapp lager kalenderfil lokalt.{' AI-sammendrag aktivert.' if ai_available() else ''}<br>
                    Dekning: Moss Kulturhus, Verket Scene og utvalgte andre kilder. Feil eller avlysninger kan forekomme – sjekk alltid original lenke.
                </div>
                <div style='margin-top:18px'>© {datetime.now().year} Moss Kulturkalender – åpen, ikke-offisiell oversikt.</div>
        </footer>
        <button class='floating-top' onclick="window.scrollTo({{top:0,behavior:'smooth'}})">TOPP</button>
        <script>{script}\n</script>
        <!--SEARCH_SCRIPT-->
        <!-- TIPS SCRIPT PLACEHOLDER -->
        </body></html>"""
    # Inject search filtering script separately to avoid f-string brace escapes
    search_script = ("<script>"+
        "(function(){var s=document.getElementById('search');if(!s)return;var pageSize=10;var showAll=false;"+
        "var rows=[].slice.call(document.querySelectorAll('.event-row'));var pageInfo=document.getElementById('pageInfo');"+
        "var prevB=document.getElementById('prevPage');var nextB=document.getElementById('nextPage');var showAllBtn=document.getElementById('showAll');"+
        "function totalPages(filtered){return Math.max(1,Math.ceil(filtered.length/pageSize));}"+
        "function applyFilter(){var q=s.value.toLowerCase();return rows.filter(function(r){return r.getAttribute('data-search').indexOf(q)>-1});}"+
        "function renderPage(p){var filtered=applyFilter();if(showAll||s.value.trim()){filtered.forEach(function(r){r.style.display=''});pageInfo.textContent= showAll? 'Alle ('+filtered.length+')' : (s.value?'Treff: '+filtered.length:'' );prevB.disabled=nextB.disabled=true;return;}"+
        "var pages=totalPages(filtered);if(p<1)p=1;if(p>pages)p=pages;prevB.disabled=p===1;nextB.disabled=p===pages;pageInfo.textContent='Side '+p+' av '+pages;filtered.forEach(function(r){r.style.display='none'});filtered.slice((p-1)*pageSize,p*pageSize).forEach(function(r){r.style.display=''});currentPage=p;}"+
        "var currentPage=1;renderPage(1);"+
        "s.addEventListener('input',function(){showAll=false;renderPage(1);});"+
        "prevB.addEventListener('click',function(){renderPage(currentPage-1);});"+
        "nextB.addEventListener('click',function(){renderPage(currentPage+1);});"+
        "showAllBtn.addEventListener('click',function(){showAll=true;renderPage(1);});"+
        "})();"+
        "</script>")
    html = html.replace('<!--SEARCH_SCRIPT-->', search_script)
    tips_script = ("<script>"+
            "(function(){var f=document.getElementById('tipsForm');if(!f)return;"+
            "var tsField=document.getElementById('form_ts');tsField.value=Date.now();"+
            "var tokenField=document.getElementById('form_token');tokenField.value=(Math.random().toString(36).slice(2));"+
            "var a=Math.floor(2+Math.random()*5),b=Math.floor(4+Math.random()*5);var spamQ=document.getElementById('spamQ');spamQ.textContent=a+'+'+b;var correct=a+b;"+
            "f.addEventListener('submit',function(ev){ev.preventDefault();var stat=document.getElementById('tipsStatus');"+
            "if(f.website && f.website.value){stat.textContent='Blokkert (honeypot).';stat.style.color='#b91c1c';return;}"+
            "if(Date.now()-parseInt(tsField.value,10)<3000){stat.textContent='For rask innsending – prøv igjen.';stat.style.color='#b91c1c';return;}"+
            "if(parseInt(f.spam_answer.value,10)!==correct){stat.textContent='Feil antispam-svar.';stat.style.color='#b91c1c';return;}"+
            "var data={title:f.title.value.trim(),date:f.date.value,start:f.start.value,end:f.end.value,venue:f.venue.value.trim(),price:f.price.value.trim(),url:f.url.value.trim(),description:f.description.value.trim(),token:tokenField.value};"+
            "if(!data.title||!data.date||!data.start||!data.venue||!data.url||!data.description){stat.textContent='Manglende påkrevde felt.';stat.style.color='#b91c1c';return;}"+
            "var store=JSON.parse(localStorage.getItem('tips_queue')||'[]');store.push({submitted:new Date().toISOString(),data:data});localStorage.setItem('tips_queue',JSON.stringify(store));"+
            "f.reset();stat.textContent='Takk! Forslaget er lagret lokalt og må manuelt hentes ut (server-endepunkt ikke aktivert ennå).';stat.style.color='#065f46';"+
            "});})();"+
            "</script>")
    html = html.replace('<!-- TIPS SCRIPT PLACEHOLDER -->', tips_script)
    print('[DEBUG] generate_simple_listing completed, length', len(html))
    if enable_enrichment and cache_dirty:
        _save_description_cache(desc_cache)
    return html

def generate_ical_feed(use_mariadb=True):
    """Generate an iCal (.ics) feed string for upcoming events.
    Uses UTC times and adds a fallback 2h end if missing. Limits can be set with ICS_LIMIT env var."""
    try:
        raw = _fetch_events_mariadb() if (use_mariadb and HAS_MYSQL) else _fetch_events_sqlite()
    except Exception:
        raw = _fetch_events_sqlite()
    oslo_tz = pytz.timezone('Europe/Oslo')
    now = datetime.now(oslo_tz) - timedelta(hours=2)  # include events started very recently
    limit = int(os.getenv('ICS_LIMIT', '500'))
    lines = [
        'BEGIN:VCALENDAR',
        'PRODID:-//Moss Kulturkalender//NO',
        'VERSION:2.0',
        'CALSCALE:GREGORIAN',
        'METHOD:PUBLISH',
        'X-WR-CALNAME:Moss Kulturkalender',
    ]
    count = 0
    for row in raw:
        if len(row) >= 7:
            title, venue, start_val, end_val, info_url, description, price = row[:7]
        else:
            continue
        try:
            if isinstance(start_val, datetime):
                start_dt = start_val
            else:
                start_dt = datetime.fromisoformat(str(start_val).replace('Z','+00:00'))
            if start_dt.tzinfo is None:
                start_dt = oslo_tz.localize(start_dt)
            if start_dt < now:
                continue
        except Exception:
            continue
        # End time fallback + timezone normalization
        if end_val:
            try:
                if isinstance(end_val, datetime):
                    end_dt = end_val
                else:
                    end_dt = datetime.fromisoformat(str(end_val).replace('Z','+00:00'))
                if end_dt.tzinfo is None:
                    end_dt = oslo_tz.localize(end_dt)
            except Exception:
                end_dt = start_dt + timedelta(hours=2)
        else:
            end_dt = start_dt + timedelta(hours=2)
        start_utc = start_dt.astimezone(pytz.utc)
        end_utc = end_dt.astimezone(pytz.utc)
        # ICS formatting
        def fmt(dt):
            return dt.strftime('%Y%m%dT%H%M%SZ')
        clean_title = (title or 'Uten tittel').replace('\n',' ').strip()
        desc_base = description or ''
        if price and price not in ('None','null',''):
            if price not in desc_base:
                desc_base = f"{desc_base}\nPris: {price}" if desc_base else f"Pris: {price}"
        desc = re.sub(r'\s+', ' ', desc_base).strip()[:900]
        def ics_escape(s: str) -> str:
            return s.replace('\\','\\\\').replace('\n','\\n').replace('\r','').replace(',','\\,').replace(';','\\;')
        uid_source = (info_url or '') + clean_title + fmt(start_utc)
        uid = hashlib.sha1(uid_source.encode('utf-8')).hexdigest() + '@mosskultur'
        lines.extend([
            'BEGIN:VEVENT',
            f'UID:{uid}',
            f'DTSTAMP:{fmt(datetime.utcnow())}',
            f'DTSTART:{fmt(start_utc)}',
            f'DTEND:{fmt(end_utc)}',
            f'SUMMARY:{ics_escape(clean_title)}',
            *( [f'LOCATION:{ics_escape(venue.strip())}'] if venue else [] ),
            *( [f'DESCRIPTION:{ics_escape(desc)}'] if desc else [] ),
            *( [f'URL:{ics_escape(info_url.strip())}'] if info_url and info_url != 'None' else [] ),
            'END:VEVENT'
        ])
        count += 1
        if count >= limit:
            break
    lines.append('END:VCALENDAR')
    # Return CRLF per spec
    return '\r\n'.join(lines) + '\r\n'

def generate_rss_feed(use_mariadb=True):
    """Generate RSS 2.0 feed for upcoming events. Writes items sorted by start_time ascending (limit RSS_LIMIT)."""
    try:
        raw = _fetch_events_mariadb() if (use_mariadb and HAS_MYSQL) else _fetch_events_sqlite()
    except Exception:
        raw = _fetch_events_sqlite()
    limit = int(os.getenv('RSS_LIMIT','100'))
    # Transform into dicts resembling generate_simple_listing logic (reuse AI summary for quality if possible)
    items = []
    oslo_tz = pytz.timezone('Europe/Oslo')
    now = datetime.now(oslo_tz) - timedelta(hours=2)
    for row in raw:
        # Row schema may differ; attempt flexible extraction
        # We know DB schema has: title, description, start_time, end_time, venue, source_url, price_info
        try:
            # Using named indices via description if needed would require a cursor; here we rely on order from our fetch helpers
            if len(row) >= 7:
                title = row[0]; venue = row[1]; start_val = row[2]; end_val = row[3]; info_url = row[4]; description = row[5]; price = row[6]
            else:
                continue
            if not title:
                continue
            # Parse start time
            if isinstance(start_val, datetime):
                start_dt = start_val
            else:
                start_dt = datetime.fromisoformat(str(start_val).replace('Z','+00:00'))
            if start_dt.tzinfo is None:
                start_dt = oslo_tz.localize(start_dt)
            if start_dt < now:
                continue
            desc_text = description or ''
            # Price injection
            if price and price not in ('None','null','') and price not in desc_text:
                if desc_text:
                    desc_text = desc_text + f"\nPris: {price}"
                else:
                    desc_text = f"Pris: {price}"
            # Basic cleanup & truncate
            desc_text = re.sub(r'\s+',' ', desc_text).strip()[:800]
            items.append({
                'title': title.strip(),
                'link': info_url if info_url and info_url != 'None' else '',
                'description': desc_text,
                'start': start_dt,
                'venue': venue or ''
            })
        except Exception:
            continue
    # Sort by start time
    items.sort(key=lambda x: x['start'])
    items = items[:limit]
    # Build RSS XML
    def x(s):
        if s is None:
            return ''
        return (s.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;'))
    now_rfc = datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0">',
        '<channel>',
        '<title>Moss Kulturkalender</title>',
        '<link>https://herimoss.no/</link>',
        '<description>Kommende kulturarrangementer i Moss</description>',
        f'<lastBuildDate>{now_rfc}</lastBuildDate>',
        '<language>no</language>'
    ]
    for it in items:
        pub_rfc = it["start"].astimezone(pytz.utc).strftime('%a, %d %b %Y %H:%M:%S GMT')
        guid = hashlib.sha1((it.get('link','')+it.get('title','')+it['start'].isoformat()).encode('utf-8')).hexdigest()
        desc_blocks = []
        if it.get('venue'):
            desc_blocks.append(f"Sted: {x(it['venue'])}")
        if it.get('description'):
            desc_blocks.append(x(it['description']))
        full_desc = ' | '.join(desc_blocks) if desc_blocks else ''
        lines.extend([
            '<item>',
            f"<title>{x(it.get('title',''))}</title>",
            f"<link>{x(it.get('link',''))}</link>" if it.get('link') else '<link>https://herimoss.no/</link>',
            f'<guid isPermaLink="false">{guid}</guid>',
            f'<pubDate>{pub_rfc}</pubDate>',
            f'<description>{full_desc}</description>',
            '</item>'
        ])
    lines.extend(['</channel>', '</rss>'])
    return '\n'.join(lines)

if __name__ == "__main__":
    simple = '--simple' in sys.argv or os.getenv('SIMPLE_MODE') == '1'
    only_ics = '--ics' in sys.argv
    only_rss = '--rss' in sys.argv
    try:
        if only_ics:
            ics = generate_ical_feed(use_mariadb=HAS_MYSQL)
            ics_path = '/var/www/vhosts/herimoss.no/httpdocs/events.ics'
            with open(ics_path, 'w', encoding='utf-8') as f:
                f.write(ics)
            print(f"✅ iCal feed generated: {ics_path}")
        elif only_rss:
            rss = generate_rss_feed(use_mariadb=HAS_MYSQL)
            rss_path = '/var/www/vhosts/herimoss.no/httpdocs/rss.xml'
            with open(rss_path, 'w', encoding='utf-8') as f:
                f.write(rss)
            print(f"✅ RSS feed generated: {rss_path}")
        else:
            if simple:
                html = generate_simple_listing(use_mariadb=HAS_MYSQL)
            else:
                html = generate_enhanced_calendar_html(use_mariadb=HAS_MYSQL)
            output_path = '/var/www/vhosts/herimoss.no/httpdocs/index.html'
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html)
            # Always also (re)generate ICS unless disabled
            if os.getenv('SKIP_ICS','0') != '1':
                ics = generate_ical_feed(use_mariadb=HAS_MYSQL)
                with open('/var/www/vhosts/herimoss.no/httpdocs/events.ics','w', encoding='utf-8') as f:
                    f.write(ics)
            # Always also (re)generate RSS unless disabled
            if os.getenv('SKIP_RSS','0') != '1':
                rss = generate_rss_feed(use_mariadb=HAS_MYSQL)
                with open('/var/www/vhosts/herimoss.no/httpdocs/rss.xml','w', encoding='utf-8') as f:
                    f.write(rss)
            if simple:
                print("✅ Simple listing generated.")
            else:
                print("✅ Enhanced calendar with 15 features generated successfully!")
                print(f"📄 Saved to: {output_path}")
            print("📅 ICS feed updated (events.ics)")
            print("📰 RSS feed updated (rss.xml)")
    except Exception as e:
        print(f"❌ Error generating calendar or feed: {e}")
