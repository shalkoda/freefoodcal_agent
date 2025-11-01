from __future__ import annotations
import os, pickle, pathlib, datetime as dt
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

TOKEN_PATH = pathlib.Path(".tokens/google_token.pickle")
CREDENTIALS_FILE = "credentials.json"
SCOPES = ["https://www.googleapis.com/auth/calendar"]

class GoogleCalendarClient:
    def __init__(self, redirect_uri: str):
        self.redirect_uri = redirect_uri
        self.creds: Credentials | None = None
        self.service = None
        TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Step 1: send user to Google
    def get_auth_url(self) -> str:
        flow = Flow.from_client_secrets_file(
            CREDENTIALS_FILE, scopes=SCOPES, redirect_uri=self.redirect_uri
        )
        auth_url, _ = flow.authorization_url(
            access_type="offline", include_granted_scopes="true", prompt="consent"
        )
        return auth_url

    # Step 2: exchange code for tokens and persist
    def authenticate(self, auth_code: str) -> None:
        flow = Flow.from_client_secrets_file(
            CREDENTIALS_FILE, scopes=SCOPES, redirect_uri=self.redirect_uri
        )
        flow.fetch_token(code=auth_code)
        self.creds = flow.credentials
        with open(TOKEN_PATH, "wb") as f:
            pickle.dump(self.creds, f)
        self.service = build("calendar", "v3", credentials=self.creds)

    # Load/refresh creds for later calls
    def get_credentials(self) -> Credentials:
        if not self.creds and TOKEN_PATH.exists():
            self.creds = pickle.load(open(TOKEN_PATH, "rb"))
        if self.creds and self.creds.expired and self.creds.refresh_token:
            self.creds.refresh(Request())
        if not self.service and self.creds:
            self.service = build("calendar", "v3", credentials=self.creds)
        return self.creds

    def list_upcoming_events(self, days: int = 30):
        self.get_credentials()
        now = dt.datetime.utcnow().isoformat() + "Z"
        time_max = (dt.datetime.utcnow() + dt.timedelta(days=days)).isoformat() + "Z"
        resp = self.service.events().list(
            calendarId="primary",
            timeMin=now,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
            maxResults=20,
        ).execute()
        return resp.get("items", [])

    def create_event(self, summary, date, start_time, end_time, location="", description=""):
        self.get_credentials()
        start = self._rfc3339(date, start_time)
        end = self._rfc3339(date, end_time)
        body = {
            "summary": summary,
            "location": location,
            "description": description,
            "start": {"dateTime": start},
            "end": {"dateTime": end},
        }
        event = self.service.events().insert(calendarId="primary", body=body).execute()
        return {"event_id": event.get("id"), "html_link": event.get("htmlLink")}

    def check_duplicate(self, summary, date):
        self.get_credentials()
        start = self._rfc3339(date, "00:00")
        end = self._rfc3339(date, "23:59")
        resp = self.service.events().list(
            calendarId="primary",
            timeMin=start, timeMax=end, singleEvents=True, orderBy="startTime"
        ).execute()
        return any(e.get("summary","").strip().lower() == summary.strip().lower()
                   for e in resp.get("items", []))

    def _rfc3339(self, date_str, time_str, tz="America/Chicago"):
        # date: YYYY-MM-DD, time: HH:MM (24h)
        dt_local = dt.datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        # naive local → RFC3339 with timezone offset; keep it simple for dev
        return dt_local.isoformat()  # Google accepts naive local if calendar tz is set
