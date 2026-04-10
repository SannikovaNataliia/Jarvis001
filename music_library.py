import json
import random
import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

CLIENT_SECRET_FILE = r"C:\Jarvis\client_secret_88513857411-ct835f2pr2eomji31th8kddntt9uk339.apps.googleusercontent.com.json"
PLAYLIST_ID = "PLusZ2cIJXtuWbBWNZPDPu4UpeqzljtiWR"
LIBRARY_FILE = r"C:\Jarvis\music_library.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]
TOKEN_FILE = r"C:\Jarvis\youtube_token.json"


def _get_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    return build("youtube", "v3", credentials=creds)


def update_music_library():
    try:
        service = _get_service()
        tracks = []
        next_page_token = None

        while True:
            response = service.playlistItems().list(
                playlistId=PLAYLIST_ID,
                part="snippet",
                maxResults=50,
                pageToken=next_page_token,
            ).execute()

            for item in response.get("items", []):
                snippet = item["snippet"]
                video_id = snippet["resourceId"]["videoId"]
                tracks.append({
                    "title": snippet["title"],
                    "video_id": video_id,
                    "url": f"https://music.youtube.com/watch?v={video_id}",
                })

            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break

        with open(LIBRARY_FILE, "w", encoding="utf-8") as f:
            json.dump(tracks, f, ensure_ascii=False, indent=2)

        return True, f"Library updated: {len(tracks)} tracks"
    except Exception as e:
        return False, f"Update failed: {e}"


def get_random_track():
    try:
        with open(LIBRARY_FILE, "r", encoding="utf-8") as f:
            tracks = json.load(f)
        if not tracks:
            return None
        return random.choice(tracks)
    except Exception:
        return None
