import httpx
import json
from src.brain.database import upsert_profile, get_connection

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:3b"

EXTRACT_PROMPT = """You are analyzing a single user message to extract memorable personal facts.

Return ONLY a JSON array. Each item must have:
- category: one of [schedule, preference, hobby, vocabulary, household, personality]
- key: short snake_case identifier (e.g. favourite_artist, morning_run_time, night_lighting)
- value: the extracted value as a string
- confidence: float 0.0 to 1.0

Rules:
- Only extract clear, personal facts worth remembering long-term.
- Vague filler like "sounds good", "ok", "yes" = return []
- Preferences about people, music, food, habits are always worth saving.

Examples:
"I love Louis Armstrong" → [{"category": "preference", "key": "favourite_artist", "value": "Louis Armstrong", "confidence": 0.95}]
"I usually go for a run at 6am" → [{"category": "schedule", "key": "morning_run_time", "value": "06:00", "confidence": 0.9}]
"I hate bright lights at night" → [{"category": "preference", "key": "night_lighting", "value": "dim", "confidence": 0.9}]
"my sister is visiting next week" → [{"category": "household", "key": "sister_visit", "value": "next week", "confidence": 0.7}]
"I love spicy food" → [{"category": "preference", "key": "food_preference", "value": "spicy", "confidence": 0.9}]
"sounds good" → []
"ok" → []

ONLY return the JSON array. No explanation, no markdown, no extra text.
"""


def extract_facts(user_message: str) -> list[dict]:
    prompt = f"{EXTRACT_PROMPT}\n\nUser message: \"{user_message}\"\nResult:"
    try:
        response = httpx.post(OLLAMA_URL, json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False
        }, timeout=30)
        response.raise_for_status()
        raw = response.json()["response"].strip()

        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        facts = json.loads(raw)
        return facts if isinstance(facts, list) else []
    except Exception as e:
        print(f"  [memory] extraction failed: {e}")
        return []


def update_memory(user_id: int, user_message: str, verbose: bool = True):
    facts = extract_facts(user_message)
    if not facts:
        return

    for fact in facts:
        try:
            upsert_profile(
                user_id=user_id,
                category=fact["category"],
                key=fact["key"],
                value=fact["value"],
                confidence=float(fact.get("confidence", 0.8)),
                source="observed"
            )
            if verbose:
                print(f"  [memory] learned: {fact['category']}/{fact['key']} = {fact['value']} ({fact.get('confidence', 0.8):.0%})")
        except Exception as e:
            print(f"  [memory] failed to save fact: {e}")


def update_patterns(user_id: int, context: dict, action_taken: str):
    if not action_taken:
        return

    trigger = json.dumps({
        "day": context.get("day"),
        "period": context.get("period"),
        "time_approx": context.get("time", "")[:2] + ":00"
    })

    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT id, occurrences FROM patterns
        WHERE user_id = ? AND trigger_context = ? AND predicted_action = ?
    """, (user_id, trigger, action_taken))
    row = c.fetchone()

    if row:
        new_occ = row["occurrences"] + 1
        new_conf = min(0.95, 0.5 + (new_occ * 0.05))
        c.execute("""
            UPDATE patterns SET occurrences = ?, confidence = ?, last_seen = datetime('now')
            WHERE id = ?
        """, (new_occ, new_conf, row["id"]))
    else:
        c.execute("""
            INSERT INTO patterns (user_id, trigger_context, predicted_action, confidence, occurrences, last_seen)
            VALUES (?, ?, ?, 0.5, 1, datetime('now'))
        """, (user_id, trigger, action_taken))

    conn.commit()
    conn.close()


if __name__ == "__main__":
    from src.brain.database import init_db, get_all_users, get_profile
    init_db()
    users = get_all_users()
    if not users:
        print("Run onboarding first.")
    else:
        uid = users[0]["id"]
        test_messages = [
            "I love Louis Armstrong",
            "I usually go for a run at 6am on weekdays",
            "I hate bright lights at night",
            "sounds good",
            "my sister is visiting next week",
            "I love spicy food",
        ]
        for msg in test_messages:
            print(f"\nInput: \"{msg}\"")
            update_memory(uid, msg)

        print("\nUpdated profile:")
        print(json.dumps(get_profile(uid), indent=2))
