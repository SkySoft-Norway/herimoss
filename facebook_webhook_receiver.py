
from flask import Flask, request, jsonify
import sqlite3
import json
import re
from datetime import datetime

app = Flask(__name__)

@app.route('/api/facebook-event-webhook', methods=['POST'])
def receive_facebook_event():
    """Receive Facebook events from IFTTT/Zapier"""
    try:
        data = request.get_json()
        
        # Extract event information from Facebook post
        page_name = data.get('page_name', '')
        post_text = data.get('post_text', '')
        post_url = data.get('post_url', '')
        
        # Simple event detection
        event_keywords = ['event', 'arrangement', 'konsert', 'teater', 'utstilling', 'forestilling']
        
        if any(keyword in post_text.lower() for keyword in event_keywords):
            # Try to extract event details
            event_data = extract_event_details(post_text, page_name, post_url)
            
            if event_data:
                save_facebook_event(event_data)
                return jsonify({"status": "success", "message": "Event saved"})
        
        return jsonify({"status": "ignored", "message": "Not an event post"})
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

def extract_event_details(text, page_name, url):
    """Extract event details from Facebook post text"""
    
    # Basic pattern matching for dates and times
    date_patterns = [
        r'(\d{1,2})\.\s?(\d{1,2})\.\s?(\d{4})',  # DD.MM.YYYY
        r'(\d{1,2})/(\d{1,2})/(\d{4})',          # DD/MM/YYYY
    ]
    
    time_patterns = [
        r'kl\.?\s?(\d{1,2})[:\.](\d{2})',        # kl 19:30
        r'(\d{1,2})[:\.](\d{2})',                # 19:30
    ]
    
    # Extract date
    event_date = None
    for pattern in date_patterns:
        match = re.search(pattern, text)
        if match:
            day, month, year = match.groups()
            event_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            break
    
    # Extract time
    event_time = None
    for pattern in time_patterns:
        match = re.search(pattern, text)
        if match:
            hour, minute = match.groups()
            event_time = f"{hour.zfill(2)}:{minute.zfill(2)}"
            break
    
    # Extract title (first line or sentence)
    title = text.split('\n')[0][:100] if text else f"Event fra {page_name}"
    
    return {
        "title": title,
        "description": text[:500],
        "venue": page_name,
        "start_date": event_date,
        "start_time": event_time,
        "source_url": url,
        "source": "facebook-automation"
    }

def save_facebook_event(event_data):
    """Save Facebook event to database"""
    conn = sqlite3.connect('/var/www/vhosts/herimoss.no/pythoncrawler/events.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT OR REPLACE INTO events 
        (title, venue, description, start_time, source_url, category, status)
        VALUES (?, ?, ?, ?, ?, 'facebook-event', 'active')
    """, (
        event_data['title'],
        event_data['venue'],
        event_data['description'],
        f"{event_data['start_date']} {event_data['start_time']}" if event_data['start_date'] and event_data['start_time'] else None,
        event_data['source_url']
    ))
    
    conn.commit()
    conn.close()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
    