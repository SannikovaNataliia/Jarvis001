import json
import os
import threading
from groq import Groq
from dotenv import load_dotenv
from core.config import USER_MEMORY_FILE, PERSONALITY_FILE

load_dotenv()
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def load_personality():
    with open(PERSONALITY_FILE, "r", encoding="utf-8") as f:
        p = json.load(f)
    with open(USER_MEMORY_FILE, "r", encoding="utf-8") as f:
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
        with open(USER_MEMORY_FILE, "r", encoding="utf-8") as f:
            memory = json.load(f)
        if fact not in memory["facts"]:
            memory["facts"].append(fact)
            with open(USER_MEMORY_FILE, "w", encoding="utf-8") as f:
                json.dump(memory, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"memory update error: {e}")


def extract_and_save_facts(user_text, assistant_text):
    try:
        with open(USER_MEMORY_FILE, "r", encoding="utf-8") as f:
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
        with open(USER_MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(memory, f, ensure_ascii=False, indent=2)

    except Exception as e:
        print(f"fact extraction error: {e}")
