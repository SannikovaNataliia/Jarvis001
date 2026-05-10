import os

# Base paths
BASE_DIR = r"C:\Jarvis"
MEMORY_DIR = os.path.join(BASE_DIR, "memory")

# Memory files
USER_MEMORY_FILE = os.path.join(MEMORY_DIR, "user_memory.json")
PERSONALITY_FILE = os.path.join(MEMORY_DIR, "personality.json")
SYSTEM_APPS_FILE = os.path.join(MEMORY_DIR, "system_apps.json")
SYSTEM_INFO_FILE = os.path.join(MEMORY_DIR, "system_info.json")
MUSIC_LIBRARY_FILE = os.path.join(BASE_DIR, "data", "music_library.json")

# Browser paths
BRAVE_PATH = r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"
BRAVE_USER_DATA = r"C:\Users\User\AppData\Local\BraveSoftware\Brave-Browser\User Data"
BRAVE_PROFILE = "Profile 1"
BRAVE_DEBUG_URL = "http://localhost:9222"

# App paths
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CHROME_PROFILE = "Profile 1"
TEAMS_PATH = r"C:\Users\User\AppData\Local\Microsoft\WindowsApps\ms-teams.exe"
DISCORD_PATH = r"C:\Users\User\AppData\Local\Discord\app-1.0.9232\Discord.exe"

# Audio
BEEP_FILE = os.path.join(BASE_DIR, "audio", "beep.wav")
INPUT_WAV = os.path.join(BASE_DIR, "input.wav")
VOICE = "en-US-EricNeural"

# Google APIs
CREDENTIALS_FILE = os.path.join(BASE_DIR, "credentials.json")
CALENDAR_TOKEN_FILE = os.path.join(BASE_DIR, "token.json")
YOUTUBE_CLIENT_SECRET = os.path.join(BASE_DIR, "client_secret_88513857411-ct835f2pr2eomji31th8kddntt9uk339.apps.googleusercontent.com.json")
YOUTUBE_TOKEN_FILE = os.path.join(BASE_DIR, "youtube_token.json")
YOUTUBE_PLAYLIST_ID = "PLusZ2cIJXtuWbBWNZPDPu4UpeqzljtiWR"

# Teams
TEAMS_TENANT_ID = "1c2aa41e-5b92-4906-827e-0c10f9d73859"

# VAD settings
VOICE_THRESHOLD = 300
SILENCE_DURATION = 1.5
MAX_WAIT_SECONDS = 7
INTERRUPT_THRESHOLD = 800