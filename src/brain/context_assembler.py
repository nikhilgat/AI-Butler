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

    prefs = profile.get("preference", {})
    if "temperature" in prefs:
        lines.append(f"- Preferred temperature: {prefs['temperature']['value']}°C")
    if "music_genre" in prefs:
        lines.append(f"- Music taste: {prefs['music_genre']['value']}")

    hobbies = profile.get("hobby", {})
    if hobbies:
        items = [k for k in hobbies]
        lines.append(f"- Hobbies/interests: {', '.join(items)}")

    household = profile.get("household", {})
    if "other_members" in household:
        lines.append(f"- Household: {household['other_members']['value']}")

    vocab = profile.get("vocabulary", {})
    if vocab:
        mappings = [f'"{k}" means "{v["value"]}"' for k, v in vocab.items()]
        lines.append(f"- Custom vocabulary: {'; '.join(mappings)}")

    return "\n".join(lines) if lines else "No profile data yet."

def assemble_context(user_id: int, session_id: str, persona_name: str, user_name: str) -> str:
    ctx = get_current_context()
    profile = get_profile(user_id)
    history = get_conversation(user_id, session_id, last_n=10)
    patterns = get_relevant_patterns(user_id, ctx)

    profile_summary = build_profile_summary(profile)

    # Format conversation history
    history_text = ""
    if history:
        lines = [f"{m['role'].capitalize()}: {m['message']}" for m in history]
        history_text = "\n".join(lines)
    else:
        history_text = "No conversation history yet."

    # Format patterns
    pattern_text = ""
    if patterns:
        lines = []
        for p in patterns:
            lines.append(f"- When {p['trigger_context']} → {p['predicted_action']} (confidence: {p['confidence']:.0%})")
        pattern_text = "\n".join(lines)
    else:
        pattern_text = "Still learning patterns."

    system_prompt = f"""You are {persona_name}, a warm, witty, and highly intelligent home AI butler.
You are speaking with {user_name}. You know them well and care about their comfort and wellbeing.

CURRENT CONTEXT:
- Time: {ctx['time']} ({ctx['period']}) on {ctx['day']}, {ctx['date']}

WHAT YOU KNOW ABOUT {user_name.upper()}:
{profile_summary}

LEARNED PATTERNS:
{pattern_text}

RECENT CONVERSATION:
{history_text}

INSTRUCTIONS:
- Respond naturally and conversationally, like a trusted butler who knows the household well.
- If the user's request involves a device action, include it at the end of your response as a JSON block like: <action>{{"action": "turn_on", "device": "lights", "area": "bedroom"}}</action>
- If nothing actionable is needed, just respond warmly in plain text.
- Be concise. Never be robotic or stiff.
- Use the user's name occasionally but not every message.
- If you notice something relevant from their profile or patterns, reference it naturally.
- Never mention that you are an AI or a language model."""

    return system_prompt


if __name__ == "__main__":
    # Quick test — assumes onboarding has been run
    from src.brain.database import get_all_users
    users = get_all_users()
    if not users:
        print("Run onboarding first.")
    else:
        u = users[0]
        prompt = assemble_context(u["id"], "test_session", u["persona_name"], u["name"])
        print(prompt)
