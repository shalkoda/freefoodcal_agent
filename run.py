"""
Application entry point
Runs the Free Food Calendar Agent
"""

import sys
import argparse
from config import Config

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Free Food Calendar Agent')
    parser.add_argument('mode', choices=['web', 'scan', 'setup'],
                       help='Mode to run: web (Flask app), scan (one-time scan), setup (initialize database)')
    parser.add_argument('--no-calendar', action='store_true',
                       help='Scan emails without creating calendar events')

    args = parser.parse_args()

    # Validate configuration
    if not Config.validate() and args.mode != 'setup':
        print("\n❌ Please configure your API keys in .env file first!")
        print("   Copy .env.example to .env and fill in your keys.\n")
        return 1

    if args.mode == 'setup':
        print("🔧 Setting up database...")
        from src.database import Database
        db = Database()
        db.init_db()
        print("✅ Database initialized!")
        return 0

    elif args.mode == 'scan':
        print("🔍 Starting one-time email scan...")
        from src.agent import FoodEventAgent
        from src.google_calendar_client import GoogleCalendarClient

        agent = FoodEventAgent()

        # Setup calendar client if needed
        calendar_client = None
        if not args.no_calendar:
            try:
                calendar_client = GoogleCalendarClient()
                calendar_client.authenticate()
                print("✅ Google Calendar authenticated")
            except Exception as e:
                print(f"⚠️  Could not authenticate with Google Calendar: {e}")
                print("   Running without calendar integration...")

        # Run scan
        results = agent.scan_emails(calendar_client)

        print(f"\n✅ Scan complete!")
        print(f"   Events found: {results['events_found']}")
        print(f"   Events added to calendar: {results['events_added']}")

        return 0

    elif args.mode == 'web':
        print("🌐 Starting Flask web application...")
        from web.app import app
        app.run(
            host='0.0.0.0',
            port=Config.FLASK_PORT,
            debug=(Config.FLASK_ENV == 'development')
        )
        return 0

if __name__ == '__main__':
    sys.exit(main())
