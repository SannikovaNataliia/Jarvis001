import json
import random
import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from core.config import MUSIC_LIBRARY_FILE, YOUTUBE_CLIENT_SECRET, YOUTUBE_TOKEN_FILE, YOUTUBE_PLAYLIST_ID

SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]


def _get_service():
    creds = None
    if os.path.exists(YOUTUBE_TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(YOUTUBE_TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(YOUTUBE_CLIENT_SECRET, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(YOUTUBE_TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    return build("youtube", "v3", credentials=creds)


def update_music_library():
    try:
        service = _get_service()
        tracks = []
        next_page_token = None

        while True:
            response = service.playlistItems().list(
                playlistId=YOUTUBE_PLAYLIST_ID,
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

        with open(MUSIC_LIBRARY_FILE, "w", encoding="utf-8") as f:
            json.dump(tracks, f, ensure_ascii=False, indent=2)

        return True, f"Library updated: {len(tracks)} tracks"
    except Exception as e:
        return False, f"Update failed: {e}"


def get_random_track():
    try:
        with open(MUSIC_LIBRARY_FILE, "r", encoding="utf-8") as f:
            tracks = json.load(f)
        if not tracks:
            return None
        return random.choice(tracks)
    except Exception:
        return None
