import os
import json
import threading
from groq import Groq
from dotenv import load_dotenv
import anthropic


def load_personality():
    with open(r"C:\Jarvis\personality.json", "r", encoding="utf-8") as f:
        p = json.load(f)
    with open(r"C:\Jarvis\user_memory.json", "r", encoding="utf-8") as f:
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
        with open(r"C:\Jarvis\user_memory.json", "r", encoding="utf-8") as f:
            memory = json.load(f)
        if fact not in memory["facts"]:
            memory["facts"].append(fact)
            with open(r"C:\Jarvis\user_memory.json", "w", encoding="utf-8") as f:
                json.dump(memory, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"memory update error: {e}")

load_dotenv()

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

claude_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

ROUTER_SYSTEM_PROMPT = '''You are a routing assistant for a voice assistant named Jarvis.
Analyze the user request and return ONLY a JSON object, no other text.

JSON structure:
{
  "action": "answer" | "web_search" | "command" | "ask_claude",
  "text": "your answer here (only for action=answer)",
  "query": "search query (only for action=web_search)",
  "command": "command name (only for action=command)",
  "reason": "why claude needed (only for action=ask_claude)",
  "has_question": true | false
}

Rules:
- "answer": you can answer directly from your knowledge. Set has_question=true if your answer contains a question.
- "web_search": request needs current/real-time info (weather, news, scores, prices, current events)
- "command": request is clearly one of these commands: play_music, update_music, open_chrome, open_discord, open_teams, open_claude, good_morning, stop, go_offline
- "ask_claude": request is complex, sensitive, requires deep reasoning or long analysis

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
        # strip markdown if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except Exception as e:
        print(f"router error: {e}")
        return {"action": "ask_claude", "has_question": False, "reason": "router failed"}


def extract_and_save_facts(user_text, assistant_text):
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "Extract any new personal facts about the user from this conversation. Return ONLY a JSON array of short fact strings, or empty array [] if nothing new. Example: [\"Nata likes coffee\", \"Nata has a cat\"]. No explanation, just JSON."},
                {"role": "user", "content": f"User said: {user_text}\nAssistant replied: {assistant_text}"}
            ],
            max_tokens=200,
            temperature=0.1
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        facts = json.loads(raw.strip())
        for fact in facts:
            add_to_memory(fact)
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
        result = response.choices[0].message.content.strip()
        threading.Thread(
            target=extract_and_save_facts,
            args=(question, result),
            daemon=True
        ).start()
        has_q = "?" in result
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
        has_q = "?" in result
        return {"text": result, "has_question": has_q}
    except Exception as e:
        print(f"groq_wrap error: {e}")
        return {"text": raw_answer, "has_question": False}


def claude_web_search(question):
    try:
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
