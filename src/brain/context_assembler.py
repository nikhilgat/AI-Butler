import json
from datetime import datetime
from src.brain.database import get_connection, get_profile, get_conversation

def get_current_context() -> dict:
    now = datetime.now()
    return {
        "time": now.strftime("%H:%M"),
        "day": now.strftime("%A"),
        "date": now.strftime("%Y-%m-%d"),
        "period": _time_period(now.hour)
    }

def _time_period(hour: int) -> str:
    if 5 <= hour < 12:  return "morning"
    if 12 <= hour < 17: return "afternoon"
    if 17 <= hour < 21: return "evening"
    return "night"

def get_relevant_patterns(user_id: int, context: dict, limit: int = 3) -> list:
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT trigger_context, predicted_action, confidence, occurrences
        FROM patterns
        WHERE user_id = ? AND confidence >= 0.6
        ORDER BY confidence DESC, occurrences DESC
        LIMIT ?
    """, (user_id, limit))
    rows = [dict(row) for row in c.fetchall()]
    conn.close()
    return rows

def build_profile_summary(profile: dict) -> str:
    lines = []

    schedule = profile.get("schedule", {})
    if "wake_time" in schedule:
        lines.append(f"- Usually wakes at {schedule['wake_time']['value']}")
    if "sleep_time" in schedule:
        lines.append(f"- Usually sleeps at {schedule['sleep_time']['value']}")
    if "work_schedule" in schedule:
        lines.append(f"- Work: {schedule['work_schedule']['value']}")
    # Show all other schedule items dynamically
    for k, v in schedule.items():
        if k not in ("wake_time", "sleep_time", "work_schedule"):
            lines.append(f"- {k.replace('_', ' ').capitalize()}: {v['value']}")

    prefs = profile.get("preference", {})
    for k, v in prefs.items():
        lines.append(f"- {k.replace('_', ' ').capitalize()}: {v['value']}")

    hobbies = profile.get("hobby", {})
    for k, v in hobbies.items():
        lines.append(f"- Hobby/interest: {v['value']}")

    household = profile.get("household", {})
    for k, v in household.items():
        lines.append(f"- Household ({k.replace('_', ' ')}): {v['value']}")

    vocab = profile.get("vocabulary", {})
    if vocab:
        mappings = [f'"{k}" means "{v["value"]}"' for k, v in vocab.items()]
        lines.append(f"- Custom vocabulary: {'; '.join(mappings)}")

    personality = profile.get("personality", {})
    for k, v in personality.items():
        lines.append(f"- Personality ({k.replace('_', ' ')}): {v['value']}")

    return "\n".join(lines) if lines else "No profile data yet."

def assemble_context(user_id: int, session_id: str, persona_name: str, user_name: str) -> str:
    ctx = get_current_context()
    profile = get_profile(user_id)
    history = get_conversation(user_id, session_id, last_n=10)
    patterns = get_relevant_patterns(user_id, ctx)

    profile_summary = build_profile_summary(profile)

    history_text = "\n".join(
        [f"{m['role'].capitalize()}: {m['message']}" for m in history]
    ) if history else "No conversation history yet."

    pattern_text = "\n".join(
        [f"- When {p['trigger_context']} → {p['predicted_action']} (confidence: {p['confidence']:.0%})"
         for p in patterns]
    ) if patterns else "Still learning patterns."

    system_prompt = f"""You are {persona_name}, a warm, witty, and highly personal home AI butler.
You are speaking with {user_name}.

CURRENT TIME: {ctx['time']} — it is {ctx['period']} on {ctx['day']}, {ctx['date']}.
You MUST use the current time context in all responses. Never say good morning if it is evening or night.

WHAT YOU KNOW ABOUT {user_name.upper()}:
{profile_summary}

LEARNED PATTERNS:
{pattern_text}

RECENT CONVERSATION:
{history_text}

STRICT INSTRUCTIONS:
- Always be aware of the current time period ({ctx['period']}) and respond accordingly.
- Only reference devices or states you have been explicitly told about. Do not invent device states.
- If the user asks about something you don't know (e.g. device state, to-do list), say you don't have that information yet.
- If the user's request involves a device action, append it at the END of your response as: <action>{{"action": "...", "device": "...", "area": "..."}}</action>
- Respond naturally and concisely. Never be robotic.
- Use the user's name occasionally but not every message.
- Never claim to be an AI or language model."""

    return system_prompt


if __name__ == "__main__":
    from src.brain.database import get_all_users
    users = get_all_users()
    if not users:
        print("Run onboarding first.")
    else:
        u = users[0]
        prompt = assemble_context(u["id"], "test_session", u["persona_name"], u["name"])
        print(prompt)
