#!/usr/bin/env python3
"""
Generate HTML calendar page with events from database.
"""
import sqlite3
import json
from datetime import datetime, timedelta
import pytz
from pathlib import Path

def generate_calendar_html():
    """Generate HTML page with calendar of events."""
    
    # Connect to database
    db_path = '/var/www/vhosts/herimoss.no/pythoncrawler/events.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get upcoming events
    cursor.execute("""
        SELECT title, venue, start_time, source_url, description, price_info
        FROM events 
        WHERE status = 'active' AND start_time >= datetime('now')
        ORDER BY start_time ASC
        LIMIT 50
    """)
    
    events = cursor.fetchall()
    conn.close()
    
    oslo_tz = pytz.timezone('Europe/Oslo')
    current_time = datetime.now(oslo_tz)
    
    # Generate event cards HTML
    events_html = ""
    
    if events:
        for title, venue, start_time_str, url, description, price in events:
            try:
                # Parse datetime
                start_dt = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                if start_dt.tzinfo is None:
                    start_dt = start_dt.replace(tzinfo=pytz.UTC)
                local_time = start_dt.astimezone(oslo_tz)
                
                # Format date and time
                date_str = local_time.strftime('%d. %B %Y')
                time_str = local_time.strftime('%H:%M')
                weekday = local_time.strftime('%A')
                
                # Norwegian weekdays
                weekday_no = {
                    'Monday': 'Mandag', 'Tuesday': 'Tirsdag', 'Wednesday': 'Onsdag',
                    'Thursday': 'Torsdag', 'Friday': 'Fredag', 'Saturday': 'Lørdag', 'Sunday': 'Søndag'
                }.get(weekday, weekday)
                
                # Norwegian months
                date_str_no = date_str
                for en_month, no_month in [
                    ('January', 'januar'), ('February', 'februar'), ('March', 'mars'),
                    ('April', 'april'), ('May', 'mai'), ('June', 'juni'),
                    ('July', 'juli'), ('August', 'august'), ('September', 'september'),
                    ('October', 'oktober'), ('November', 'november'), ('December', 'desember')
                ]:
                    date_str_no = date_str_no.replace(en_month, no_month)
                
                # Clean description
                desc_preview = ""
                if description:
                    desc_preview = description[:100] + "..." if len(description) > 100 else description
                
                # Price info
                price_display = ""
                if price and price.lower() not in ['none', 'null', '']:
                    price_display = f'<div class="event-price">💰 {price}</div>'
                
                # URL link
                url_link = ""
                if url and url.startswith('http'):
                    url_link = f'<a href="{url}" target="_blank" class="event-link">🎫 Billett/info</a>'
                
                events_html += f"""
                <div class="event-card">
                    <div class="event-date">
                        <div class="event-day">{local_time.day}</div>
                        <div class="event-month">{date_str_no.split()[1][:3].upper()}</div>
                        <div class="event-weekday">{weekday_no[:3].upper()}</div>
                    </div>
                    <div class="event-info">
                        <h3 class="event-title">{title}</h3>
                        <div class="event-details">
                            <span class="event-time">🕒 {time_str}</span>
                            <span class="event-venue">📍 {venue or 'Moss'}</span>
                        </div>
                        {f'<p class="event-description">{desc_preview}</p>' if desc_preview else ''}
                        {price_display}
                        {url_link}
                    </div>
                </div>
                """
                
            except Exception as e:
                print(f"Error processing event {title}: {e}")
                continue
    else:
        events_html = """
        <div class="no-events">
            <h3>🔍 Ingen arrangementer funnet</h3>
            <p>Systemet jobber med å hente arrangementer fra lokale kilder.</p>
        </div>
        """
    
    # Complete HTML page
    html_content = f"""<!DOCTYPE html>
<html lang="no">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Moss Kulturkalender - Alle kulturarrangementer i Moss</title>
    <meta name="description" content="Komplett oversikt over kulturarrangementer i Moss kommune. Konserter, teater, utstillinger og mer fra Moss Kulturhus, Verket Scene og andre lokale arrangører.">
    <meta name="keywords" content="moss, kultur, kalender, arrangementer, konserter, teater, utstillinger, moss kulturhus, verket scene">
    <meta name="author" content="Moss Kulturkalender">
    
    <!-- Open Graph / Facebook -->
    <meta property="og:type" content="website">
    <meta property="og:url" content="https://herimoss.no/">
    <meta property="og:title" content="Moss Kulturkalender">
    <meta property="og:description" content="Komplett oversikt over kulturarrangementer i Moss kommune">
    
    <!-- Twitter -->
    <meta property="twitter:card" content="summary_large_image">
    <meta property="twitter:url" content="https://herimoss.no/">
    <meta property="twitter:title" content="Moss Kulturkalender">
    <meta property="twitter:description" content="Komplett oversikt over kulturarrangementer i Moss kommune">
    
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
            max-width: 1200px;
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
        
        .status-icon {{
            font-size: 1.5em;
            margin-right: 10px;
        }}
        
        .events-section {{
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 30px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            margin-bottom: 30px;
        }}
        
        .events-section h2 {{
            color: #2c3e50;
            margin-bottom: 25px;
            font-size: 2em;
            text-align: center;
        }}
        
        .events-grid {{
            display: grid;
            gap: 20px;
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
        
        .event-title {{
            color: #2c3e50;
            margin-bottom: 10px;
            font-size: 1.3em;
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
        
        .event-price {{
            color: #27ae60;
            font-weight: bold;
            margin-bottom: 10px;
        }}
        
        .event-link {{
            display: inline-block;
            background: #3498db;
            color: white;
            padding: 8px 15px;
            border-radius: 20px;
            text-decoration: none;
            font-size: 0.9em;
            transition: background 0.3s ease;
        }}
        
        .event-link:hover {{
            background: #2980b9;
        }}
        
        .no-events {{
            text-align: center;
            padding: 50px;
            color: #7f8c8d;
        }}
        
        .update-info {{
            background: rgba(52, 152, 219, 0.1);
            border-radius: 10px;
            padding: 20px;
            margin: 20px 0;
            text-align: center;
            font-size: 0.9em;
            color: #34495e;
        }}
        
        footer {{
            text-align: center;
            margin-top: 40px;
            padding: 20px;
            color: rgba(255, 255, 255, 0.8);
        }}
        
        @media (max-width: 768px) {{
            .container {{
                padding: 10px;
            }}
            
            h1 {{
                font-size: 2em;
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
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🎭 Moss Kulturkalender</h1>
            <p class="subtitle">Din komplette guide til kulturarrangementer i Moss kommune</p>
            
            <div class="status">
                <span class="status-icon">🎉</span>
                <strong>System er aktivt med {len(events)} arrangementer!</strong> Kulturkalenderen viser alle kommende arrangementer fra lokale kilder.
            </div>
        </header>
        
        <div class="events-section">
            <h2>📅 Kommende arrangementer</h2>
            
            <div class="update-info">
                <strong>Sist oppdatert:</strong> {current_time.strftime('%d. %B %Y kl. %H:%M')} | 
                <strong>Antall arrangementer:</strong> {len(events)} kommende
            </div>
            
            <div class="events-grid">
                {events_html}
            </div>
        </div>
        
        <footer>
            <p>🌍 <strong>Moss Kulturkalender</strong> - Skapt med ❤️ for Moss kommune</p>
            <p>Automatisk oppdatert fra Moss Kulturhus, Verket Scene og andre lokale kilder</p>
            <p>Besøk gjerne <a href="https://moss.kommune.no" style="color: rgba(255,255,255,0.9);">moss.kommune.no</a> for offisiell informasjon</p>
        </footer>
    </div>
    
    <script>
        // Add some interactive elements
        document.querySelectorAll('.event-card').forEach(card => {{
            card.addEventListener('mouseenter', () => {{
                card.style.borderLeftColor = '#e74c3c';
            }});
            
            card.addEventListener('mouseleave', () => {{
                card.style.borderLeftColor = '#3498db';
            }});
        }});
        
        // Auto-refresh every 30 minutes
        setTimeout(() => {{
            window.location.reload();
        }}, 30 * 60 * 1000);
    </script>
</body>
</html>"""

    return html_content

if __name__ == "__main__":
    try:
        html = generate_calendar_html()
        
        # Write to file
        output_path = '/var/www/vhosts/herimoss.no/httpdocs/index.html'
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        
        print("✅ Calendar HTML generated successfully!")
        print(f"📄 Saved to: {output_path}")
        
    except Exception as e:
        print(f"❌ Error generating calendar: {e}")
