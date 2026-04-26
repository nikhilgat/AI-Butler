import httpx
import json
import uuid
from src.brain.database import (
    init_db, create_user, upsert_profile,
    add_message, get_conversation, get_all_users
)

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:3b"

# Questions to cover during onboarding
ONBOARDING_STEPS = [
    {
        "key": ("schedule", "wake_time"),
        "question": "What time do you usually wake up on weekdays?",
        "extract_prompt": "Extract the wake time from this response as HH:MM (24hr). Return ONLY the time string, nothing else."
    },
    {
        "key": ("schedule", "sleep_time"),
        "question": "And what time do you usually go to bed?",
        "extract_prompt": "Extract the sleep/bedtime from this response as HH:MM (24hr). Return ONLY the time string, nothing else."
    },
    {
        "key": ("preference", "temperature"),
        "question": "What's your preferred room temperature? (in °C)",
        "extract_prompt": "Extract the temperature number from this response. Return ONLY the number, nothing else."
    },
    {
        "key": ("schedule", "work_schedule"),
        "question": "Do you work from home, go to an office, or something else?",
        "extract_prompt": "Summarize the work situation in 3 words max (e.g. 'work from home', 'office weekdays'). Return ONLY that, nothing else."
    },
    {
        "key": ("hobby", "interests"),
        "question": "What are some of your hobbies or interests? (e.g. gaming, cooking, music — whatever comes to mind)",
        "extract_prompt": "Extract a comma-separated list of hobbies/interests from this response. Return ONLY the list, nothing else."
    },
    {
        "key": ("preference", "music_genre"),
        "question": "Do you enjoy music at home? If so, what kind?",
        "extract_prompt": "Extract music genre or preference. If they don't listen to music, return 'none'. Return ONLY the value, nothing else."
    },
    {
        "key": ("household", "other_members"),
        "question": "Who else lives with you at home? (family, partner, roommates — or just you?)",
        "extract_prompt": "Summarize household members briefly (e.g. 'partner', 'partner and 2 kids', 'alone'). Return ONLY that, nothing else."
    },
]


def llm(prompt: str) -> str:
    response = httpx.post(OLLAMA_URL, json={
        "model": MODEL,
        "prompt": prompt,
        "stream": False
    }, timeout=30)
    response.raise_for_status()
    return response.json()["response"].strip()


def extract_value(user_response: str, extract_prompt: str) -> str:
    prompt = f"{extract_prompt}\n\nUser said: \"{user_response}\""
    return llm(prompt).strip()


def butler_say(text: str, persona_name: str = "Butler"):
    print(f"\n{persona_name}: {text}\n")


def user_input_text(prompt: str = "") -> str:
    return input(f"You: ").strip()


def run_onboarding():
    init_db()

    # Check if any users exist already
    existing = get_all_users()
    if existing:
        print("\nOnboarding already complete. Users found:")
        for u in existing:
            print(f"  - {u['name']} (Butler name: {u['persona_name']})")
        return existing[0]["id"]

    print("\n" + "="*50)
    print("  Welcome to The Butler — First Time Setup")
    print("="*50)

    # Step 1: Get user's name
    butler_say("Hello! I'm your new home assistant. Before we get started, I'd love to know a bit about you.")
    butler_say("What's your name?")
    user_name = user_input_text()

    # Step 2: Pick butler's persona name
    butler_say(f"Great to meet you, {user_name}! What would you like to call me? (e.g. Jarvis, Nova, Max — anything you like)")
    persona_name = user_input_text()
    if not persona_name:
        persona_name = "Jarvis"

    # Create user in DB
    user_id = create_user(user_name, persona_name)
    session_id = str(uuid.uuid4())

    butler_say(f"Perfect — I'm {persona_name}. I'll be learning about you and your home over time, but first let me ask you a few quick questions to get started.", persona_name)

    # Step 3: Walk through onboarding questions
    for step in ONBOARDING_STEPS:
        category, key = step["key"]
        butler_say(step["question"], persona_name)

        add_message(user_id, session_id, "assistant", step["question"])
        response = user_input_text()
        add_message(user_id, session_id, "user", response)

        # Extract structured value from natural response
        value = extract_value(response, step["extract_prompt"])
        upsert_profile(user_id, category, key, value, confidence=1.0, source="onboarding")
        print(f"  [saved: {category}/{key} = {value}]")

    # Step 4: Warm close
    closing = llm(
        f"You are {persona_name}, a warm and witty home AI butler. "
        f"The user's name is {user_name}. "
        f"You just finished onboarding them. "
        f"Write a short, warm, personalised welcome message (2-3 sentences max). "
        f"Tell them you'll be learning more about them over time and you're here whenever they need you."
    )
    butler_say(closing, persona_name)
    add_message(user_id, session_id, "assistant", closing)

    print("\n" + "="*50)
    print(f"  Setup complete. User ID: {user_id}")
    print("="*50 + "\n")

    return user_id


if __name__ == "__main__":
    run_onboarding()
