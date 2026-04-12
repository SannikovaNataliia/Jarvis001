import os
import json
from groq import Groq
from dotenv import load_dotenv
import anthropic
from personality import JARVIS_PERSONALITY

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


def groq_answer(question, history=[]):
    try:
        messages = [{"role": "system", "content": JARVIS_PERSONALITY}]
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
                {"role": "system", "content": JARVIS_PERSONALITY},
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
            system=JARVIS_PERSONALITY,
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
            system=JARVIS_PERSONALITY,
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
