import json
import subprocess
import psutil
from core.config import SYSTEM_APPS_FILE

PRIORITY_EXES = {
    "visualstudio": "devenv",
    "vscode": "code",
    "rstudio": "rstudio",
    "wordpad": "wordpad",
}

def find_and_open_app(app_name):
    import subprocess, os, glob
    try:
        with open(SYSTEM_APPS_FILE, "r", encoding="utf-8") as f:
            apps = json.load(f)

        name_lower = app_name.lower().strip().replace(" ", "")
        executables = apps.get("executables", {})

        print(f"🔎 Looking for: {app_name}")

        # check priority exe names first
        for app_key, exe_name in PRIORITY_EXES.items():
            if app_key in name_lower or name_lower in app_key:
                if exe_name in executables:
                    path = executables[exe_name]
                    print(f"✅ Found: {path}")
                    subprocess.Popen([path])
                    return True, f"Opening {app_name}."

        # exact match
        if name_lower in executables:
            path = executables[name_lower]
            print(f"✅ Found: {path}")
            subprocess.Popen([path])
            return True, f"Opening {app_name}."

        # normalized match
        for key, path in executables.items():
            key_normalized = key.lower().replace(" ", "").replace("-", "")
            if key_normalized == name_lower or key_normalized.startswith(name_lower) or name_lower.startswith(key_normalized):
                if len(key) > 2:
                    print(f"✅ Found: {path}")
                    subprocess.Popen([path])
                    return True, f"Opening {app_name}."

        return False, f"I couldn't find {app_name} on your system."
    except Exception as e:
        print(f"find_and_open_app error: {e}")
        return False, f"Could not open {app_name}."


def find_and_close_app(app_name):
    import psutil
    name_lower = app_name.lower().replace(" ", "")
    found = False
    try:
        for proc in psutil.process_iter(['name', 'exe']):
            try:
                proc_name = proc.info['name'].lower().replace(".exe", "").replace(" ", "")
                if name_lower in proc_name or proc_name in name_lower:
                    if len(proc_name) > 2:
                        proc.terminate()
                        found = True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        if found:
            return True, f"Closed {app_name}."
        return False, f"{app_name} is not running."
    except Exception as e:
        return False, f"Could not close {app_name}: {e}"
