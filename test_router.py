
from router import route_request, claude_web_search, claude_answer

print('=== ROUTING ===')
tests = ['what is the weather in Lviv today', 'tell me about black holes', 'open discord']
for t in tests:
    r = route_request(t)
print('Q:', t, '-> action:', r.get('action', 'unknown'))

print()
print('=== WEB SEARCH ===')
r = claude_web_search('what is the weather in Lviv today')
print(r['text'][:200])

print()
print('=== CLAUDE SONNET ===')
r = claude_answer('tell me something interesting about space')
print(r['text'][:200])