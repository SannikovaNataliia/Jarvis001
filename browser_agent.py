import requests
import json
import json as json_module
import time
import websocket
from pywinauto import Application
from pywinauto import keyboard

BRAVE_DEBUG_URL = "http://localhost:9222"

def focus_brave():
    try:
        app = Application(backend='uia').connect(title_re='.*Brave.*')
        window = app.top_window()
        window.restore()
        window.set_focus()
        return True
    except Exception as e:
        print(f"focus_brave error: {e}")
        return False

def is_brave_debug_available():
    try:
        requests.get(f"{BRAVE_DEBUG_URL}/json", timeout=2)
        return True
    except:
        return False

def open_url(url):
    try:
        new_tab = requests.put(f"{BRAVE_DEBUG_URL}/json/new").json()
        time.sleep(1)
        tab_id = new_tab['id']
        ws_url = new_tab['webSocketDebuggerUrl']
        requests.get(f"{BRAVE_DEBUG_URL}/json/activate/{tab_id}")
        time.sleep(0.5)
        focus_brave()
        time.sleep(0.3)

        ws = websocket.create_connection(ws_url)
        ws.send(json_module.dumps({
            "id": 1,
            "method": "Page.navigate",
            "params": {"url": url}
        }))
        time.sleep(4)

        # check if login required
        success, message = check_and_handle_login(ws, tab_id, url)
        ws.close()
        return success, message
    except Exception as e:
        print(f"browser_agent error: {e}")
        return False, str(e)


def check_and_handle_login(ws, tab_id, target_url):
    """Check if redirected to login page and handle autofill if needed"""
    try:
        # get current URL
        ws.send(json_module.dumps({
            "id": 20,
            "method": "Runtime.evaluate",
            "params": {"expression": "window.location.href"}
        }))
        time.sleep(0.5)
        result = ws.recv()
        current_url = json_module.loads(result).get("result", {}).get("value", "")

        print(f"📍 Current URL: {current_url}")

        # check if on login page
        if any(x in current_url.lower() for x in ["login", "auth", "signin", "sign-in"]):
            print("🔐 Login page detected, attempting autofill...")

            # find site key from target URL
            site_key = None
            for key in ["mystat", "github", "google"]:
                if key in target_url.lower():
                    site_key = key
                    break

            # click email/login field
            ws.send(json_module.dumps({
                "id": 21,
                "method": "Runtime.evaluate",
                "params": {
                    "expression": """
                    var input = document.querySelector('input[type=email], input[type=text], input[name=login]');
                    if (input) { input.click(); input.focus(); 'focused'; } else { 'not found'; }
                    """
                }
            }))
            time.sleep(1)

            # handle autofill
            success, message = handle_autofill(ws, 'input[type=email], input[type=text]', site_key)

            if success:
                time.sleep(2)
                # click login button
                ws.send(json_module.dumps({
                    "id": 22,
                    "method": "Runtime.evaluate",
                    "params": {
                        "expression": """
                        var btn = document.querySelector('button[type=submit], input[type=submit], .login-btn, button.btn');
                        if (btn) { btn.click(); 'clicked'; } else { 'not found'; }
                        """
                    }
                }))
                time.sleep(3)

                # navigate to original target
                ws.send(json_module.dumps({
                    "id": 23,
                    "method": "Page.navigate",
                    "params": {"url": target_url}
                }))
                time.sleep(3)
                return True, "Logged in and navigated to target."
            else:
                return False, message

        return True, "Already on target page."

    except Exception as e:
        print(f"check_and_handle_login error: {e}")
        return False, str(e)

def click_first_result(tab_id, ws_url, selector):
    try:
        ws = websocket.create_connection(ws_url)
        requests.get(f"{BRAVE_DEBUG_URL}/json/activate/{tab_id}")
        time.sleep(1)

        ws.send(json.dumps({
            "id": 1,
            "method": "Runtime.evaluate",
            "params": {
                "expression": f"""
                var el = document.querySelector('{selector}');
                if (el) {{ el.click(); 'clicked'; }} else {{ 'not found'; }}
                """
            }
        }))
        time.sleep(1)
        result = ws.recv()
        ws.close()
        return 'clicked' in result
    except Exception as e:
        print(f"click error: {e}")
        return False


def handle_autofill(ws, input_selector, site_key=None):
    """
    Click input field, handle autofill suggestions.
    site_key: key to look up in memory for preferred account
    """
    try:
        # click the input field
        ws.send(json_module.dumps({
            "id": 10,
            "method": "Runtime.evaluate",
            "params": {
                "expression": f"document.querySelector('{input_selector}').click();"
            }
        }))
        time.sleep(1)

        # press arrow down to trigger autofill dropdown
        keyboard.send_keys('{DOWN}')
        time.sleep(0.5)

        # check how many autofill items appeared via accessibility
        ws.send(json_module.dumps({
            "id": 11,
            "method": "Runtime.evaluate",
            "params": {
                "expression": """
                (function() {
                    var items = document.querySelectorAll('[role=option], [role=listitem], .autofill-suggestion');
                    return JSON.stringify({count: items.length, texts: [...items].map(i => i.innerText?.slice(0,50))});
                })()
                """
            }
        }))
        time.sleep(0.5)
        result = ws.recv()

        # try to load preferred account from memory
        preferred = None
        try:
            with open(r"C:\Jarvis\memory\system_info.json", "r", encoding="utf-8") as f:
                sys_info = json_module.load(f)
            if site_key and site_key in sys_info.get("autofill", {}):
                preferred = sys_info["autofill"][site_key]
        except:
            pass

        # parse autofill options
        try:
            data = json_module.loads(json_module.loads(result)["result"]["value"])
            count = data.get("count", 0)
            texts = data.get("texts", [])
        except:
            count = 0
            texts = []

        if count == 0:
            # no autofill shown, just press Enter on first suggestion
            keyboard.send_keys('{ENTER}')
            return True, "Used first autofill option."

        elif count == 1:
            # only one option — select it
            keyboard.send_keys('{ENTER}')
            return True, f"Selected autofill: {texts[0] if texts else 'option 1'}"

        else:
            # multiple options
            if preferred:
                # find matching option
                for i, text in enumerate(texts):
                    if preferred.lower() in text.lower():
                        # navigate to correct option
                        for _ in range(i):
                            keyboard.send_keys('{DOWN}')
                            time.sleep(0.2)
                        keyboard.send_keys('{ENTER}')
                        return True, f"Selected preferred autofill: {preferred}"
                # preferred not found
                keyboard.send_keys('{ESCAPE}')
                return False, f"Preferred account '{preferred}' not found in autofill options: {texts}"
            else:
                # no preference in memory — stop and ask
                keyboard.send_keys('{ESCAPE}')
                return False, f"Multiple autofill options found: {texts}. Please specify which account to use."

    except Exception as e:
        print(f"handle_autofill error: {e}")
        return False, str(e)
