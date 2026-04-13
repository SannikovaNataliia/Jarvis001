import os
import json
import glob
import winreg

MEMORY_FILE = r"C:\Jarvis\memory\system_apps.json"

SKIP_EXE_FOLDERS = [
    "msys64", "Windows Kits", "Microsoft SDKs", "Microsoft SQL Server",
    "Common Files", "Windows NT", "Microsoft.NET", "WindowsPowerShell",
    "Microsoft Visual Studio", "dotnet", "dotnet\\sdk", "Extensions\\dump",
    "TestHostNetFramework", "DotnetTools", "AppHostTemplate",
    "Git", "Microsoft Office", "RStudio", "Windows Defender",
    "Windows Media Player", "Internet Explorer", "IIS", "IIS Express",
    "Windows Mail", "Windows Photo Viewer", "WindowsInstallationAssistant",
    "Microsoft Update Health Tools", "HP", "Intel", "Microsoft OneDrive"
]

SKIP_EXE_NAMES = [
    "uninstall", "setup", "install", "update", "crash", "helper",
    "service", "daemon", "agent", "repair", "migrate", "configure",
    "testhost", "datacollector", "dumpminitool", "apphost",
    "chrome_proxy", "chrome_pwa", "chrmstp", "maintenancetool",
    "unins000", "ikernel", "msdeploy", "imagingdevices", "wab", "wabmig",
    "getcurrentrollback", "uhssvc", "cltoast", "effectextractor",
    "gamesessionmonitor", "log-uploader", "vgc", "vgm", "vgtray",
    "appcmd", "iisexpress", "iisexpressadmincmd", "iisexpresstray",
    "openconsole", "vsce-sign", "code-tunnel", "rg",
    "qtwebengineprocess", "adsso", "senddmp", "vlc-cache-gen",
    "rar", "unrar", "battle.net launcher", "battlenet.overlay.runtime"
]

def get_apps_from_registry():
    apps = {}
    keys = [
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"
    ]
    for key_path in keys:
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
            for i in range(winreg.QueryInfoKey(key)[0]):
                try:
                    subkey = winreg.OpenKey(key, winreg.EnumKey(key, i))
                    name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                    try:
                        path = winreg.QueryValueEx(subkey, "InstallLocation")[0]
                    except:
                        path = ""
                    if name and name.strip() and path and path.strip() and os.path.exists(path.strip()):
                        apps[name.strip()] = path.strip()
                except:
                    pass
        except:
            pass
    return apps

def scan_executables():
    scan_paths = [
        r"C:\Program Files",
        r"C:\Program Files (x86)",
        r"D:\Programs",
    ]
    exes = {}
    for base_path in scan_paths:
        if not os.path.exists(base_path):
            continue
        for exe in glob.glob(f"{base_path}/**/*.exe", recursive=True):
            if any(skip in exe for skip in SKIP_EXE_FOLDERS):
                continue
            name = os.path.splitext(os.path.basename(exe))[0].lower()
            if any(skip in name for skip in SKIP_EXE_NAMES):
                continue
            exes[name] = exe
    return exes

def scan_and_save():
    print("Scanning registry...")
    registry_apps = get_apps_from_registry()
    print(f"Found {len(registry_apps)} apps in registry")

    print("Scanning executable files...")
    exe_apps = scan_executables()
    print(f"Found {len(exe_apps)} executables")

    result = {
        "registry": registry_apps,
        "executables": exe_apps
    }

    os.makedirs(r"C:\Jarvis\memory", exist_ok=True)
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"Saved to {MEMORY_FILE}")
    return result

if __name__ == "__main__":
    scan_and_save()
