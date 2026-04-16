import os
import json
import threading
from groq import Groq
from dotenv import load_dotenv
import anthropic


def load_personality():
    with open(r"C:\Jarvis\memory\personality.json", "r", encoding="utf-8") as f:
        p = json.load(f)
    with open(r"C:\Jarvis\memory\user_memory.json", "r", encoding="utf-8") as f:
        m = json.load(f)

    facts_str = ""
    if m.get("facts"):
        facts_str = "\nLearned facts:\n" + "\n".join(f"- {fact}" for fact in m["facts"])

    return f"""You are Jarvis, a personal AI assistant.

Core traits: {p["core_traits"]}

Speech rules:
{chr(10).join(f"- {rule}" for rule in p["speech_rules"])}

User info:
- Name: {m["name"]}
- Location: {m["location"]}
- Timezone: {m["timezone"]}
- Interests: {", ".join(m["interests"])}
- Apps used: {", ".join(m["apps"])}
- Preferences: {", ".join(m["preferences"])}
{facts_str}"""


def add_to_memory(fact):
    try:
        with open(r"C:\Jarvis\memory\user_memory.json", "r", encoding="utf-8") as f:
            memory = json.load(f)
        if fact not in memory["facts"]:
            memory["facts"].append(fact)
            with open(r"C:\Jarvis\memory\user_memory.json", "w", encoding="utf-8") as f:
                json.dump(memory, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"memory update error: {e}")

load_dotenv()

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

claude_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

ROUTER_SYSTEM_PROMPT = '''You are a routing assistant for a voice assistant named Jarvis.
Analyze the user request and return ONLY a JSON object or JSON array, no other text.

For a single action, return a JSON object:
{"action": "answer" | "web_search" | "command" | "open_app" | "close_app" | "browser_search" | "ask_claude", "has_question": true | false, "app_name": "app name (only for open_app and close_app)", "query": "search query (only for browser_search)"}

For multiple actions, return a JSON array:
[{"action": "open_app", "app_name": "chrome", "has_question": false}, {"action": "open_app", "app_name": "telegram", "has_question": false}]

Rules — be conservative, prefer "answer" when possible:
- "answer": conversation, general knowledge, facts, advice, follow-ups
- "web_search": ONLY for current/live data: today weather, live scores, breaking news, prices
- "command": ONLY these exact: play_music, update_music, open_chrome, open_discord, open_teams, open_claude, good_morning, stop, go_offline
- "open_app": user wants to open/launch an application that is NOT in the command list above. Return the app name as "app_name"
- "close_app": user wants to close/quit/exit an application. Return app name as "app_name"
- "browser_search": user wants to find and open something online (video, website, article, song). Return search query as "query"
- "ask_claude": ONLY for very complex technical analysis or long document writing

Examples:
"open telegram" → {"action": "open_app", "app_name": "telegram", "has_question": false}
"open chrome and telegram" → [{"action": "open_app", "app_name": "chrome", "has_question": false}, {"action": "open_app", "app_name": "telegram", "has_question": false}]
"close telegram" → {"action": "close_app", "app_name": "telegram", "has_question": false}
"find and play new BTS MV" → {"action": "browser_search", "query": "BTS new MV", "has_question": false}
"open weather forecast for Lviv" → {"action": "browser_search", "query": "Lviv weather forecast", "has_question": false}
"find minecraft gameplay video" → {"action": "browser_search", "query": "minecraft gameplay video", "has_question": false}

Always respond with valid JSON only. No markdown, no explanation.'''


def route_request(text):
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
                {"role": "user", "content": text}
            ],
            max_tokens=300,
            temperature=0.1
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()
        parsed = json.loads(raw)
        # always return a list
        if isinstance(parsed, dict):
            return [parsed]
        return parsed
    except Exception as e:
        print(f"router error: {e}")
        return [{"action": "ask_claude", "has_question": False}]


PRIORITY_EXES = {
    "visualstudio": "devenv",
    "vscode": "code",
    "rstudio": "rstudio",
    "wordpad": "wordpad",
}

def find_and_open_app(app_name):
    import subprocess, os, glob
    try:
        with open(r"C:\Jarvis\memory\system_apps.json", "r", encoding="utf-8") as f:
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


def browser_find_and_open(query):
    try:
        response = claude_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            system="You are a URL finder. Given a search query, return ONLY the best direct URL to open. No explanation, just the URL. For videos prefer YouTube. For music prefer YouTube Music.",
            messages=[{"role": "user", "content": f"Find the best URL for: {query}"}],
            tools=[{"type": "web_search_20250305", "name": "web_search"}]
        )
        url = ""
        for block in response.content:
            if hasattr(block, "text"):
                url += block.text.strip()

        # якщо не знайшов URL — робимо YouTube пошук
        if not url or "http" not in url:
            url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"

        print(f"🌐 Opening: {url}")

        from browser_agent import open_url, is_brave_debug_available
        if not is_brave_debug_available():
            return False, "Brave is not running in debug mode. Please open it via brave_debug.bat"

        success, result = open_url(url)
        return success, url
    except Exception as e:
        print(f"browser_find_and_open error: {e}")
        return False, str(e)


def extract_and_save_facts(user_text, assistant_text):
    try:
        with open(r"C:\Jarvis\memory\user_memory.json", "r", encoding="utf-8") as f:
            memory = json.load(f)

        existing_facts = memory.get("facts", [])

        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": """Extract new personal facts about the user from this conversation.
Rules:
- Only extract specific, concrete, useful facts
- Skip vague or obvious things
- Skip duplicates or things already covered by existing facts
- Merge/update if new info contradicts existing fact
- Return ONLY a JSON object: {"add": ["new fact"], "remove": ["old fact to replace"]}
- Return {"add": [], "remove": []} if nothing new
No explanation, just JSON."""},
                {"role": "user", "content": f"Existing facts: {json.dumps(existing_facts)}\n\nUser said: {user_text}\nAssistant replied: {assistant_text}"}
            ],
            max_tokens=300,
            temperature=0.1
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        result = json.loads(raw.strip())

        facts = existing_facts.copy()
        for old in result.get("remove", []):
            if old in facts:
                facts.remove(old)
        for new in result.get("add", []):
            if new not in facts:
                facts.append(new)

        memory["facts"] = facts
        with open(r"C:\Jarvis\memory\user_memory.json", "w", encoding="utf-8") as f:
            json.dump(memory, f, ensure_ascii=False, indent=2)

    except Exception as e:
        print(f"fact extraction error: {e}")


def groq_answer(question, history=[]):
    try:
        messages = [{"role": "system", "content": load_personality()}]
        for h in history:
            messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": question})

        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            max_tokens=512,
            temperature=0.7
        )
        print(f"🤖 Groq (Llama 70B)")
        result = response.choices[0].message.content.strip()
        threading.Thread(
            target=extract_and_save_facts,
            args=(question, result),
            daemon=True
        ).start()
        has_q = result.strip().endswith("?") or "?" in result[-50:]
        return {"text": result, "has_question": has_q}
    except Exception as e:
        print(f"groq_answer error: {e}")
        return {"text": "Something went wrong.", "has_question": False}


def groq_wrap(raw_answer, original_question):
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": load_personality()},
                {"role": "user", "content": f"Rephrase this answer naturally for voice, staying in character. Question was: {original_question}\n\nAnswer: {raw_answer}"}
            ],
            max_tokens=300,
            temperature=0.5
        )
        result = response.choices[0].message.content.strip()
        has_q = result.strip().endswith("?") or result.count("?") > 0
        return {"text": result, "has_question": has_q}
    except Exception as e:
        print(f"groq_wrap error: {e}")
        return {"text": raw_answer, "has_question": False}


def claude_web_search(question):
    try:
        print(f"🔍 Claude Haiku (web search)")
        response = claude_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            system=load_personality(),
            messages=[{"role": "user", "content": question}],
            tools=[{"type": "web_search_20250305", "name": "web_search"}]
        )
        reply = ""
        for block in response.content:
            if hasattr(block, "text"):
                reply += block.text
        has_q = "?" in reply
        return {"text": reply or "I couldn't find that.", "has_question": has_q}
    except Exception as e:
        print(f"claude_web_search error: {e}")
        return {"text": "I couldn't find that.", "has_question": False}


def claude_answer(question, history=[]):
    try:
        print(f"💎 Claude Sonnet")
        messages = history + [{"role": "user", "content": question}]
        response = claude_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=load_personality(),
            messages=messages,
            tools=[{"type": "web_search_20250305", "name": "web_search"}]
        )
        reply = ""
        for block in response.content:
            if hasattr(block, "text"):
                reply += block.text
        has_q = "?" in reply
        return {"text": reply or "I couldn't find that.", "has_question": has_q}
    except Exception as e:
        print(f"claude_answer error: {e}")
        return {"text": "Something went wrong.", "has_question": False}
