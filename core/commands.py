import subprocess
import time
import psutil
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import os
from datetime import datetime
import sys
from modules.calendar_helper import find_current_or_next_event
from modules.teams_links import open_teams_for_subject
from modules.music_library import update_music_library, get_random_track
from core.config import BRAVE_PATH, BRAVE_USER_DATA, CHROME_PATH, CHROME_PROFILE, TEAMS_PATH, DISCORD_PATH

def open_chrome():
    subprocess.Popen([CHROME_PATH, f"--profile-directory={CHROME_PROFILE}"])

def open_teams():
    event = find_current_or_next_event()
    if event:
        event_name = event.get("summary", "")
        subject_name = open_teams_for_subject(event_name)
        if subject_name:
            return True, "Opening your current class in Teams."
    subprocess.Popen([TEAMS_PATH])
    return True, "No classes found today. Opening Teams."

def open_discord():
    subprocess.Popen(
        [DISCORD_PATH],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

def open_claude_app():
    subprocess.Popen(["explorer.exe", "shell:AppsFolder\\Claude_pzs8sxrjxfjjc!Claude"])

def startup_setup():
    print("🚀 Starting setup...")
    print("⏳ Opening Teams...")
    open_teams()  # tuple return intentionally ignored here
    time.sleep(8)
    print("⏳ Opening Chrome...")
    open_chrome()
    time.sleep(5)
    print("✅ Startup complete!")

def good_morning():
    now = datetime.now()
    day = now.weekday()  # 0=Пн, 6=Нд
    time_str = now.strftime("%I:%M %p")
    if day < 5:
        return "workday", time_str
    else:
        return "weekend", time_str

BTS_RESPONSE = """BTS is a South Korean boy band formed in 2013 under HYBE Corporation. 
The group consists of seven members: RM, Jin, Suga, J-Hope, Jimin, V, and Jungkook. 
They are one of the most successful musical acts in history, breaking numerous records worldwide. 
Their music spans multiple genres including K-pop, hip-hop, and R&B. 
BTS has won countless awards and sold out stadiums across the globe. 
They are known for their powerful performances and meaningful lyrics about self-love and mental health. 
In 2022, the members began fulfilling their mandatory military service in South Korea. 
They are expected to reunite and resume group activities in 2025."""

def tell_me_about_bts():
    return BTS_RESPONSE


def is_brave_running():
    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'] == 'brave.exe':
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return False


def play_youtube_music():
    try:
        track = get_random_track()
        if not track:
            return False, "Music library is empty. Say update music first."

        options = Options()
        options.binary_location = BRAVE_PATH
        options.debugger_address = "127.0.0.1:9222"

        try:
            driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=options
            )
        except Exception:
            # Brave not running with debug port — launch it
            subprocess.Popen([
                BRAVE_PATH,
                "--remote-debugging-port=9222",
                f"--user-data-dir={BRAVE_USER_DATA}",
                "--profile-directory=Profile 1",
            ])
            time.sleep(3)
            driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=options
            )

        # find existing YouTube Music tab
        yt_tab = None
        for handle in driver.window_handles:
            driver.switch_to.window(handle)
            if "music.youtube.com" in driver.current_url:
                yt_tab = handle
                break

        if yt_tab:
            driver.get(track["url"])
        else:
            driver.switch_to.new_window("tab")
            driver.get(track["url"])

        print(f"🎵 Playing: {track['title']}")
        return True, f"Playing {track['title']}"
    except Exception as e:
        print(f"play_youtube_music error: {e}")
        return False, f"Could not start music: {e}"

def fast_play_music():
    try:
        track = get_random_track()
        if not track:
            return False, "Music library is empty. Say update music first."

        if is_brave_running():
            subprocess.Popen([BRAVE_PATH, track["url"]])
        else:
            subprocess.Popen([
                BRAVE_PATH,
                "--profile-directory=Profile 1",
                f"--user-data-dir={BRAVE_USER_DATA}",
                track["url"],
            ])

        print(f"🎵 Playing: {track['title']}")
        return True, f"Playing {track['title']}"
    except Exception as e:
        return False, f"Could not start music: {e}"

COMMANDS = {
    "update music": update_music_library,
    "update library": update_music_library,
    "play music": play_youtube_music,
    "open chrome": open_chrome,
    "open browser": open_chrome,
    "open teams": open_teams,
    "open microsoft teams": open_teams,
    "open discord": open_discord,
    "open claude": open_claude_app,
    "start setup": startup_setup,
    "startup": startup_setup,
    "morning setup": startup_setup,
    "discord": open_discord,
    "fast music": fast_play_music,
    "quick music": fast_play_music,
    "music": play_youtube_music,
}
print(f"DEBUG COMMANDS keys: {list(COMMANDS.keys())}")

def handle_command(text):
    text_lower = text.lower()
    print(f"DEBUG handle_command: '{text_lower}'")
    for keyword, action in COMMANDS.items():
        if keyword in text_lower:
            print(f"DEBUG matched: '{keyword}'")
            result = action()
            if isinstance(result, tuple):
                return result  # (success, message)
            return True, "Done!"
    print(f"DEBUG no match found")
    return False, None