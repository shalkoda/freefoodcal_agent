"""
Google Calendar Client
Handles calendar event creation via Google Calendar API
"""

import os
import pickle
from datetime import datetime, timedelta
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


class GoogleCalendarClient:
    """
    Google Calendar client for event creation

    Handles:
    - OAuth authentication
    - Event creation
    - Duplicate detection
    - Event listing
    """

    SCOPES = ['https://www.googleapis.com/auth/calendar']

    def __init__(self, credentials_file='credentials.json', token_file='token.pickle'):
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.creds = None
        self.service = None

    def get_auth_url(self):
        """
        Get authorization URL for OAuth flow

        Returns:
            str: Authorization URL
        """
        flow = InstalledAppFlow.from_client_secrets_file(
            self.credentials_file,
            self.SCOPES,
            redirect_uri=os.getenv('GOOGLE_REDIRECT_URI', 'http://localhost:5050/auth/google/callback')
        )

        auth_url, _ = flow.authorization_url(prompt='consent')
        return auth_url

    def authenticate(self, auth_code=None):
        """
        Authenticate with Google Calendar

        Args:
            auth_code: Authorization code from OAuth callback (optional)

        Returns:
            bool: True if authenticated successfully
        """
        # Try to load existing credentials
        if os.path.exists(self.token_file):
            with open(self.token_file, 'rb') as token:
                self.creds = pickle.load(token)

        # If no valid credentials, authenticate
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                try:
                    self.creds.refresh(Request())
                except Exception as e:
                    print(f"⚠️  Error refreshing token: {e}")
                    self.creds = None

            if not self.creds:
                if auth_code:
                    # Use provided auth code
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_file,
                        self.SCOPES,
                        redirect_uri=os.getenv('GOOGLE_REDIRECT_URI')
                    )
                    flow.fetch_token(code=auth_code)
                    self.creds = flow.credentials
                else:
                    # Interactive flow
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_file,
                        self.SCOPES
                    )
                    self.creds = flow.run_local_server(port=0)

            # Save credentials
            with open(self.token_file, 'wb') as token:
                pickle.dump(self.creds, token)

        # Build service
        self.service = build('calendar', 'v3', credentials=self.creds)
        return True

    def get_credentials(self):
        """Get current credentials"""
        if not self.creds:
            self.authenticate()
        return self.creds

    def create_event(self, event_name, date, time, end_time=None, location='TBD',
                    food_type='food', description='', timezone='America/New_York'):
        """
        Create calendar event

        Args:
            event_name: Event title
            date: Event date (YYYY-MM-DD)
            time: Start time (HH:MM)
            end_time: End time (HH:MM, optional)
            location: Event location
            food_type: Type of food
            description: Event description
            timezone: Timezone

        Returns:
            dict: Created event with 'event_id' and 'html_link'
        """
        if not self.service:
            self.authenticate()

        # Format datetime
        start_datetime = self._format_datetime(date, time, timezone)

        if end_time and end_time != 'unknown':
            end_datetime = self._format_datetime(date, end_time, timezone)
        else:
            # Default 1 hour duration
            start_dt = datetime.fromisoformat(start_datetime)
            end_dt = start_dt + timedelta(hours=1)
            end_datetime = end_dt.isoformat()

        # Build event
        event = {
            'summary': f"🍕 {event_name}",
            'location': location,
            'description': f"{description}\n\n🍴 Food Type: {food_type}",
            'start': {
                'dateTime': start_datetime,
                'timeZone': timezone,
            },
            'end': {
                'dateTime': end_datetime,
                'timeZone': timezone,
            },
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'popup', 'minutes': 30},
                ],
            },
        }

        try:
            created_event = self.service.events().insert(calendarId='primary', body=event).execute()
            return {
                'event_id': created_event['id'],
                'html_link': created_event.get('htmlLink', '')
            }
        except HttpError as error:
            print(f"❌ Error creating calendar event: {error}")
            raise

    def check_duplicate(self, event_name, date):
        """
        Check if event already exists on this date

        Args:
            event_name: Event name to check
            date: Event date (YYYY-MM-DD)

        Returns:
            bool: True if duplicate exists
        """
        if not self.service:
            self.authenticate()

        try:
            # Get events for this day
            start_of_day = f"{date}T00:00:00Z"
            end_of_day = f"{date}T23:59:59Z"

            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=start_of_day,
                timeMax=end_of_day,
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])

            # Check if any event has similar name
            for event in events:
                existing_name = event.get('summary', '').lower()
                if event_name.lower() in existing_name or existing_name in event_name.lower():
                    return True

            return False

        except HttpError as error:
            print(f"⚠️  Error checking duplicates: {error}")
            return False

    def list_upcoming_events(self, days=7):
        """
        List upcoming events

        Args:
            days: Number of days to look ahead

        Returns:
            List[dict]: List of upcoming events
        """
        if not self.service:
            self.authenticate()

        try:
            now = datetime.utcnow().isoformat() + 'Z'
            future = (datetime.utcnow() + timedelta(days=days)).isoformat() + 'Z'

            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=now,
                timeMax=future,
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])
            return events

        except HttpError as error:
            print(f"❌ Error listing events: {error}")
            return []

    def _format_datetime(self, date, time, timezone):
        """
        Format date and time into RFC3339 timestamp

        Args:
            date: Date string (YYYY-MM-DD)
            time: Time string (HH:MM)
            timezone: Timezone string

        Returns:
            str: RFC3339 formatted datetime
        """
        if date == 'unknown' or time == 'unknown':
            # Default to tomorrow at noon
            dt = datetime.now() + timedelta(days=1)
            dt = dt.replace(hour=12, minute=0, second=0, microsecond=0)
            return dt.isoformat()

        try:
            dt_str = f"{date}T{time}:00"
            dt = datetime.fromisoformat(dt_str)
            return dt.isoformat()
        except ValueError as e:
            print(f"⚠️  Error formatting datetime: {e}")
            # Fallback
            dt = datetime.now() + timedelta(days=1)
            dt = dt.replace(hour=12, minute=0, second=0, microsecond=0)
            return dt.isoformat()
