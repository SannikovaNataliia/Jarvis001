import requests
import json
import time
import websocket

# крок 1: відкрити нову вкладку з YouTube пошуком
new_tab = requests.put('http://localhost:9222/json/new').json()
time.sleep(1)

tab_id = new_tab['id']
ws_url = new_tab['webSocketDebuggerUrl']

# активуємо вкладку
requests.get(f'http://localhost:9222/json/activate/{tab_id}')
time.sleep(0.5)

ws = websocket.create_connection(ws_url)

# крок 2: навігація на YouTube пошук
ws.send(json.dumps({
    "id": 1,
    "method": "Page.navigate",
    "params": {"url": "https://www.youtube.com/results?search_query=BTS+ARIRANG+MV"}
}))
print("Navigating...")
time.sleep(5)  # чекаємо завантаження

# очищаємо буфер відповідей
ws.settimeout(1)
try:
    while True:
        ws.recv()
except:
    pass
ws.settimeout(None)

# крок 3: клікаємо на перше відео
ws.send(json.dumps({
    "id": 2,
    "method": "Runtime.evaluate",
    "params": {
        "expression": """
        var videos = document.querySelectorAll('ytd-video-renderer a#thumbnail');
        if (videos.length > 0) {
            videos[0].click();
            'clicked: ' + videos[0].href;
        } else {
            'not found, total elements: ' + document.querySelectorAll('a').length;
        }
        """
    }
}))
time.sleep(1)
result = ws.recv()
print(result)

ws.close()
print("Done!")