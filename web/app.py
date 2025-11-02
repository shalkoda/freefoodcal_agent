"""
Flask web application for Free Food Calendar Agent
Provides web interface for managing scans and viewing events
"""

from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from flask_session import Session
import os
import sys
import threading
import time
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import Config
from src.agent import FoodEventAgent
from src.google_calendar_client import GoogleCalendarClient
from src.outlook_client import OutlookClient
from src.database import Database

app = Flask(__name__)
app.config['SECRET_KEY'] = Config.FLASK_SECRET_KEY
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

# Initialize components
agent = None  # Lazy initialization - only when needed
db = Database()

# Background scanning thread
scanning_thread = None
scanning_active = False


def get_agent():
    """Get or initialize FoodEventAgent (lazy initialization)"""
    global agent
    if agent is None:
        try:
            agent = FoodEventAgent()
        except Exception as e:
            raise ValueError(f"Failed to initialize FoodEventAgent: {e}. Please ensure COHERE_API_KEY and GOOGLE_API_KEY are set in .env file.")
    return agent


def run_automatic_scan():
    """Run an automatic scan with calendar integration if enabled"""
    try:
        # Check if auto-calendar is enabled
        auto_calendar_enabled = db.get_auto_calendar_enabled()
        
        calendar_client = None
        if auto_calendar_enabled:
            try:
                calendar_client = GoogleCalendarClient()
                calendar_client.authenticate()
                print(f"[{datetime.now()}] ✅ Calendar authenticated for auto-scan")
            except Exception as e:
                print(f"[{datetime.now()}] ⚠️  Calendar authentication failed: {e}")
                print(f"[{datetime.now()}] 📧 Continuing scan without calendar...")
                # Continue without calendar if auth fails
        
        print(f"[{datetime.now()}] 🔍 Starting automatic scan...")
        try:
            agent = get_agent()
        except ValueError as e:
            print(f"[{datetime.now()}] ❌ Cannot scan: {e}")
            return
        
        results = agent.scan_emails(calendar_client)
        print(f"[{datetime.now()}] ✅ Auto-scan complete: {results['events_found']} events found, {results['events_added']} added to calendar")
        
    except Exception as e:
        print(f"[{datetime.now()}] ❌ Auto-scan error: {e}")


def background_scanner():
    """Background thread that runs periodic scans"""
    global scanning_active
    scan_interval_hours = float(db.get_setting('scan_interval_hours', '6'))
    scan_interval_seconds = scan_interval_hours * 3600
    
    while scanning_active:
        if db.get_auto_scan_enabled():
            run_automatic_scan()
        else:
            print(f"[{datetime.now()}] ℹ️  Auto-scan is disabled, skipping...")
        
        # Sleep for the scan interval
        time.sleep(scan_interval_seconds)


def start_background_scanner():
    """Start the background scanning thread"""
    global scanning_thread, scanning_active
    
    if scanning_thread is None or not scanning_thread.is_alive():
        scanning_active = True
        scanning_thread = threading.Thread(target=background_scanner, daemon=True)
        scanning_thread.start()
        print(f"[{datetime.now()}] 🚀 Background scanner started")


def stop_background_scanner():
    """Stop the background scanning thread"""
    global scanning_active
    scanning_active = False
    print(f"[{datetime.now()}] 🛑 Background scanner stopped")


@app.route('/')
def index():
    """Dashboard homepage"""
    stats = db.get_stats()
    recent_events = db.get_recent_events(limit=10)
    food_stats = db.get_food_type_stats()
    auto_calendar_enabled = db.get_auto_calendar_enabled()
    google_authenticated = session.get('google_authenticated', False)

    return render_template('index.html',
                          stats=stats,
                          recent_events=recent_events,
                          food_stats=food_stats,
                          auto_calendar_enabled=auto_calendar_enabled,
                          google_authenticated=google_authenticated)


@app.route('/scan', methods=['POST'])
def scan():
    """Trigger manual email scan"""
    try:
        # Check if auto-calendar is enabled and if calendar is authenticated
        calendar_client = None
        auto_calendar_enabled = db.get_auto_calendar_enabled()
        
        if auto_calendar_enabled:
            if session.get('google_authenticated'):
                try:
                    calendar_client = GoogleCalendarClient()
                    calendar_client.authenticate()
                except Exception as e:
                    print(f"⚠️  Calendar authentication error: {e}")
                    # Continue without calendar if auth fails
            else:
                # Auto-calendar is enabled but not authenticated
                return jsonify({
                    'success': False,
                    'error': 'Auto-calendar is enabled but Google Calendar is not authenticated. Please authenticate first.',
                    'requires_auth': True
                }), 400

        # Get agent (lazy initialization)
        try:
            agent = get_agent()
        except ValueError as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 400
        
        # Run scan
        results = agent.scan_emails(calendar_client)

        return jsonify({
            'success': True,
            'results': results
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/events')
def events():
    """Get all events as JSON"""
    limit = request.args.get('limit', 50, type=int)
    events = db.get_recent_events(limit=limit)
    return jsonify(events)


@app.route('/stats')
def stats():
    """Get statistics"""
    overall_stats = db.get_stats()
    llm_stats = db.get_llm_stats(days=30)
    filter_perf = db.get_filter_performance(days=30)

    return jsonify({
        'overall': overall_stats,
        'llm_usage': llm_stats,
        'filter_performance': filter_perf
    })


@app.route('/auth/status')
def auth_status():
    """Check authentication status"""
    return jsonify({
        'google_authenticated': session.get('google_authenticated', False),
        'microsoft_authenticated': session.get('microsoft_authenticated', False)
    })


@app.route('/auth/google/login')
def google_login():
    """Initiate Google OAuth"""
    try:
        calendar_client = GoogleCalendarClient()
        auth_url = calendar_client.get_auth_url()
        return redirect(auth_url)
    except Exception as e:
        return f"Error: {e}", 500


@app.route('/auth/google/callback')
def google_callback():
    """Google OAuth callback"""
    code = request.args.get('code')
    if code:
        try:
            calendar_client = GoogleCalendarClient()
            calendar_client.authenticate(auth_code=code)
            session['google_authenticated'] = True
            return render_template('oauth_callback.html',
                                 service='Google Calendar',
                                 success=True)
        except Exception as e:
            return render_template('oauth_callback.html',
                                 service='Google Calendar',
                                 success=False,
                                 error=str(e))
    return "No authorization code provided", 400


@app.route('/auth/microsoft/login')
def microsoft_login():
    """Initiate Microsoft OAuth"""
    try:
        outlook_client = OutlookClient()
        auth_url = outlook_client.get_auth_url()
        return redirect(auth_url)
    except Exception as e:
        return f"Error: {e}", 500


@app.route('/auth/microsoft/callback')
def microsoft_callback():
    """Microsoft OAuth callback"""
    code = request.args.get('code')
    if code:
        try:
            outlook_client = OutlookClient()
            outlook_client.authenticate(code)
            session['microsoft_authenticated'] = True
            return render_template('oauth_callback.html',
                                 service='Microsoft Outlook',
                                 success=True)
        except Exception as e:
            return render_template('oauth_callback.html',
                                 service='Microsoft Outlook',
                                 success=False,
                                 error=str(e))
    return "No authorization code provided", 400


@app.route('/analytics')
def analytics():
    """Analytics page"""
    llm_stats = db.get_llm_stats(days=30)
    filter_perf = db.get_filter_performance(days=30)
    food_stats = db.get_food_type_stats()

    return render_template('analytics.html',
                          llm_stats=llm_stats,
                          filter_perf=filter_perf,
                          food_stats=food_stats)


@app.route('/settings', methods=['GET'])
def get_settings():
    """Get current settings"""
    try:
        return jsonify({
            'success': True,
            'settings': {
                'auto_calendar_enabled': db.get_auto_calendar_enabled(),
                'auto_scan_enabled': db.get_auto_scan_enabled(),
                'google_authenticated': session.get('google_authenticated', False)
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/settings', methods=['POST'])
def update_settings():
    """Update settings"""
    try:
        data = request.get_json()
        
        if 'auto_calendar_enabled' in data:
            db.set_auto_calendar_enabled(data['auto_calendar_enabled'])
        
        if 'auto_scan_enabled' in data:
            auto_scan_enabled = data['auto_scan_enabled']
            db.set_auto_scan_enabled(auto_scan_enabled)
            
            # Start/stop background scanner based on setting
            if auto_scan_enabled:
                start_background_scanner()
            else:
                stop_background_scanner()
        
        return jsonify({
            'success': True,
            'settings': {
                'auto_calendar_enabled': db.get_auto_calendar_enabled(),
                'auto_scan_enabled': db.get_auto_scan_enabled()
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


if __name__ == '__main__':
    # Don't validate config on startup - allow server to start without API keys
    # Config validation will happen when agent is initialized
    print("⚠️  Note: API keys (COHERE_API_KEY, GOOGLE_API_KEY) are optional for UI access")
    print("   Scans will require API keys to be configured in .env file")
    
    # Start background scanner if auto-scan is enabled (but don't fail if agent can't init)
    try:
        if db.get_auto_scan_enabled():
            # Check if we can initialize agent
            get_agent()
            start_background_scanner()
    except Exception as e:
        print(f"⚠️  Background scanner not started: {e}")

    # Run app
    app.run(
        host='0.0.0.0',
        port=Config.FLASK_PORT,
        debug=(Config.FLASK_ENV == 'development')
    )
