import os
from datetime import datetime, timezone, timedelta
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), "credentials.json")
TOKEN_FILE = os.path.join(os.path.dirname(__file__), "token.json")
UNIVERSITY_CALENDAR_NAME = "UNIVERSITY"


def _get_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    return build("calendar", "v3", credentials=creds)


def _find_university_calendar_id(service):
    calendars = service.calendarList().list().execute().get("items", [])
    for cal in calendars:
        if cal.get("summary", "").upper() == UNIVERSITY_CALENDAR_NAME:
            return cal["id"]
    raise ValueError(f"No calendar named '{UNIVERSITY_CALENDAR_NAME}' found in your Google account.")


def _parse_event_time(event, key):
    """Return a timezone-aware datetime from event start or end dict."""
    dt_str = event[key].get("dateTime")
    if dt_str:
        return datetime.fromisoformat(dt_str)
    # All-day event — treat as midnight local time (no tz info needed for comparison)
    date_str = event[key].get("date")
    return datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)


def get_todays_university_events():
    """Return all UNIVERSITY calendar events for today, sorted by start time."""
    service = _get_service()
    cal_id = _find_university_calendar_id(service)

    local_tz = datetime.now().astimezone().tzinfo
    now_local = datetime.now(tz=local_tz)
    day_start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)

    result = service.events().list(
        calendarId=cal_id,
        timeMin=day_start.isoformat(),
        timeMax=day_end.isoformat(),
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    return result.get("items", [])


def find_current_or_next_event():
    """
    Returns:
      - The currently happening event, if any.
      - Otherwise the next upcoming event today.
      - Otherwise the last event of the day (already finished).
      - None if there are no events today at all.
    """
    events = get_todays_university_events()
    if not events:
        return None

    now = datetime.now().astimezone()

    current = None
    upcoming = None

    for event in events:  # already sorted by start time
        start = _parse_event_time(event, "start")
        end = _parse_event_time(event, "end")

        if start <= now < end:
            current = event
            break  # no need to look further

        if now < start and upcoming is None:
            upcoming = event

    if current:
        return current
    if upcoming:
        return upcoming
    # All events finished — return the last one
    return events[-1]
