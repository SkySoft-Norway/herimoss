#!/usr/bin/env python3
"""
IFTTT/Zapier Facebook Automation Setup for Moss Events
Strategy #3: Automated Facebook monitoring using third-party services
"""

import json
import requests
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)

class IFTTTFacebookMonitor:
    def __init__(self):
        self.ifttt_webhook_key = "YOUR_IFTTT_WEBHOOK_KEY"  # Replace with actual key
        self.zapier_webhook_url = "YOUR_ZAPIER_WEBHOOK_URL"  # Replace with actual URL
        
    def setup_ifttt_triggers(self):
        """
        Setup guide for IFTTT Facebook monitoring
        """
        
        setup_guide = {
            "service": "IFTTT (If This Then That)",
            "url": "https://ifttt.com",
            "cost": "Free tier available, Pro $2.50/month",
            
            "facebook_applets": [
                {
                    "name": "Moss Kulturhus Facebook Monitor",
                    "trigger": "New post on Facebook page",
                    "page": "mosskulturhus",
                    "action": "Send webhook to our system",
                    "webhook_url": f"https://herimoss.no/api/facebook-event-webhook",
                    "setup_steps": [
                        "1. Go to https://ifttt.com/create",
                        "2. Choose 'Facebook Pages' as trigger",
                        "3. Select 'New post by page'", 
                        "4. Connect your Facebook account",
                        "5. Choose 'Moss Kulturhus' page (or enter URL)",
                        "6. Choose 'Webhooks' as action",
                        "7. Enter webhook URL and JSON format"
                    ]
                },
                {
                    "name": "Verket Scene Facebook Monitor", 
                    "trigger": "New post on Facebook page",
                    "page": "verketscene",
                    "action": "Send webhook to our system",
                    "webhook_url": f"https://herimoss.no/api/facebook-event-webhook"
                }
            ],
            
            "webhook_format": {
                "url": "https://herimoss.no/api/facebook-event-webhook",
                "method": "POST",
                "content_type": "application/json",
                "body": {
                    "page_name": "{{PageName}}",
                    "post_text": "{{Text}}",
                    "post_url": "{{LinkToPost}}",
                    "created_time": "{{CreatedAt}}",
                    "source": "ifttt-facebook"
                }
            }
        }
        
        return setup_guide
    
    def setup_zapier_integration(self):
        """
        Setup guide for Zapier Facebook monitoring
        """
        
        setup_guide = {
            "service": "Zapier",
            "url": "https://zapier.com",
            "cost": "Free tier: 100 tasks/month, Paid: $19.99+/month",
            
            "zaps": [
                {
                    "name": "Facebook Page to Moss Kalender",
                    "trigger": "Facebook Pages - New Post",
                    "filter": "Only posts containing 'event', 'arrangement', 'konsert', 'teater'",
                    "action": "Webhook POST to our system",
                    "setup_steps": [
                        "1. Create new Zap at https://zapier.com/app/zaps",
                        "2. Choose Facebook Pages as trigger app",
                        "3. Select 'New Post' trigger",
                        "4. Connect Facebook account",
                        "5. Choose specific pages to monitor",
                        "6. Add filter: Text contains event keywords",
                        "7. Choose Webhooks by Zapier as action",
                        "8. Configure POST webhook to our endpoint"
                    ]
                }
            ],
            
            "webhook_endpoint": {
                "url": "https://herimoss.no/api/zapier-facebook-webhook",
                "method": "POST",
                "headers": {
                    "Content-Type": "application/json",
                    "X-API-Key": "YOUR_API_KEY"
                },
                "payload": {
                    "page_id": "{{page__id}}",
                    "page_name": "{{page__name}}",
                    "message": "{{message}}",
                    "link": "{{link}}",
                    "created_time": "{{created_time}}",
                    "post_id": "{{id}}"
                }
            }
        }
        
        return setup_guide

def create_webhook_receiver():
    """
    Create webhook receiver for Facebook automation
    """
    
    webhook_code = '''
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
    title = text.split('\\n')[0][:100] if text else f"Event fra {page_name}"
    
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
    '''
    
    return webhook_code

def main():
    """Main setup function"""
    print("🔧 SETTING UP FACEBOOK AUTOMATION (Strategy #3)")
    print("=" * 55)
    
    monitor = IFTTTFacebookMonitor()
    
    # IFTTT Setup
    print("\n📱 IFTTT SETUP GUIDE:")
    ifttt_guide = monitor.setup_ifttt_triggers()
    
    print(f"Service: {ifttt_guide['service']}")
    print(f"URL: {ifttt_guide['url']}")
    print(f"Cost: {ifttt_guide['cost']}")
    
    print("\nFacebook Pages to Monitor:")
    for applet in ifttt_guide['facebook_applets']:
        print(f"  • {applet['name']} ({applet['page']})")
    
    print("\nSetup Steps for IFTTT:")
    for step in ifttt_guide['facebook_applets'][0]['setup_steps']:
        print(f"  {step}")
    
    # Zapier Setup  
    print(f"\n⚡ ZAPIER SETUP GUIDE:")
    zapier_guide = monitor.setup_zapier_integration()
    
    print(f"Service: {zapier_guide['service']}")
    print(f"URL: {zapier_guide['url']}")
    print(f"Cost: {zapier_guide['cost']}")
    
    print("\nSetup Steps for Zapier:")
    for step in zapier_guide['zaps'][0]['setup_steps']:
        print(f"  {step}")
    
    # Save webhook receiver code
    webhook_code = create_webhook_receiver()
    with open('/var/www/vhosts/herimoss.no/pythoncrawler/facebook_webhook_receiver.py', 'w') as f:
        f.write(webhook_code)
    
    print(f"\n✅ Setup files created:")
    print(f"  • facebook_automation_setup.py (this file)")
    print(f"  • facebook_webhook_receiver.py (webhook server)")
    
    print(f"\n🚀 NEXT STEPS:")
    print(f"1. Choose IFTTT or Zapier (or both)")
    print(f"2. Follow setup steps above") 
    print(f"3. Deploy webhook receiver: python3 facebook_webhook_receiver.py")
    print(f"4. Test with a Facebook post containing 'event'")

if __name__ == "__main__":
    main()
