import os
import json
import threading
from groq import Groq
from dotenv import load_dotenv
import anthropic
from modules.memory_manager import load_personality, extract_and_save_facts
from modules.app_manager import find_and_open_app, find_and_close_app
from modules.browser_agent import open_url, is_brave_debug_available

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

        if not is_brave_debug_available():
            return False, "Brave is not running in debug mode. Please open it via brave_debug.bat"

        success, result = open_url(url)
        return success, url
    except Exception as e:
        print(f"browser_find_and_open error: {e}")
        return False, str(e)


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
