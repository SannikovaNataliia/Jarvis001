from router import route_request, groq_answer, groq_wrap, claude_web_search

print("=== GROQ ANSWER з personality ===")
r = groq_answer("tell me something interesting")
print(r['text'])

print()
print("=== WEB SEARCH + GROQ WRAP ===")
raw = claude_web_search("what is the weather in Lviv today")
wrapped = groq_wrap(raw['text'], "what is the weather in Lviv today")
print(wrapped['text'])

print()
print("=== ROUTING ===")
tests = ["play music", "what is the weather", "tell me about quantum physics", "open discord"]
for t in tests:
    r = route_request(t)
    print(f"{t} -> {r.get('action')}")