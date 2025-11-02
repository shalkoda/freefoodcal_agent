"""
Flask web application for Free Food Calendar Agent
Provides web interface for managing scans and viewing events
"""

from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from flask_session import Session
import os
import sys

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
agent = FoodEventAgent()
db = Database()


@app.route('/')
def index():
    """Dashboard homepage"""
    stats = db.get_stats()
    recent_events = db.get_recent_events(limit=10)
    food_stats = db.get_food_type_stats()

    return render_template('index.html',
                          stats=stats,
                          recent_events=recent_events,
                          food_stats=food_stats,
                          google_authenticated=session.get('google_authenticated', False),
                          microsoft_authenticated=session.get('microsoft_authenticated', False))


@app.route('/scan', methods=['POST'])
def scan():
    """Trigger manual email scan"""
    try:
        # Check if calendar is authenticated
        calendar_client = None
        if session.get('google_authenticated'):
            try:
                calendar_client = GoogleCalendarClient()
                calendar_client.authenticate()
            except:
                pass

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
    except FileNotFoundError:
        return render_template('oauth_callback.html',
                             service='Google Calendar',
                             success=False,
                             error='credentials.json file not found or empty. Please add your Google OAuth credentials.'),
    except Exception as e:
        return render_template('oauth_callback.html',
                             service='Google Calendar',
                             success=False,
                             error=f'Error: {str(e)}'), 500


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


if __name__ == '__main__':
    # Validate config
    Config.validate()

    # Run app
    app.run(
        host='0.0.0.0',
        port=Config.FLASK_PORT,
        debug=(Config.FLASK_ENV == 'development')
    )
