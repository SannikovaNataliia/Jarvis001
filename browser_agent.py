import requests
import json
import time
import websocket
from pywinauto import Application

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
        # відкрити нову вкладку
        new_tab = requests.put(f"{BRAVE_DEBUG_URL}/json/new").json()
        time.sleep(1)

        tab_id = new_tab['id']
        ws_url = new_tab['webSocketDebuggerUrl']

        # активуємо вкладку
        requests.get(f"{BRAVE_DEBUG_URL}/json/activate/{tab_id}")
        time.sleep(0.5)
        focus_brave()
        time.sleep(0.3)

        ws = websocket.create_connection(ws_url)

        # навігація
        ws.send(json.dumps({
            "id": 1,
            "method": "Page.navigate",
            "params": {"url": url}
        }))
        time.sleep(4)
        ws.close()
        return True, url
    except Exception as e:
        print(f"browser_agent error: {e}")
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
