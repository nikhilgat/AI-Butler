import httpx
import json
import re
import uuid
from datetime import datetime
from src.brain.context_assembler import assemble_context
from src.brain.database import init_db, get_all_users, add_message, log_episode
from src.brain.memory_updater import update_memory, update_patterns
from src.ha_bridge.bridge import send_action

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:3b"


def llm_chat(system_prompt: str, user_message: str) -> str:
    response = httpx.post(OLLAMA_URL, json={
        "model": MODEL,
        "prompt": f"{system_prompt}\n\nUser: {user_message}\nAssistant:",
        "stream": False
    }, timeout=60)
    response.raise_for_status()
    return response.json()["response"].strip()


def parse_response(raw: str) -> tuple[str, dict | None]:
    action = None
    text = raw
    match = re.search(r"<action>(.*?)</action>", raw, re.DOTALL | re.IGNORECASE)
    if not match:
        match = re.search(r"<action>(\{.*?\})", raw, re.DOTALL)
    if match:
        try:
            action = json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass
        text = raw[:match.start()].strip()
    return text, action


def _time_period(hour: int) -> str:
    if 5 <= hour < 12:  return "morning"
    if 12 <= hour < 17: return "afternoon"
    if 17 <= hour < 21: return "evening"
    return "night"


def run_conversation(user_id: int, persona_name: str, user_name: str):
    session_id = str(uuid.uuid4())
    print(f"\n{'='*50}")
    print(f"  {persona_name} is ready. Say something.")
    print(f"  (type 'quit' to exit)")
    print(f"{'='*50}\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{persona_name}: Goodbye, {user_name}. I'll be here when you need me.")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "bye"):
            print(f"\n{persona_name}: Take care, {user_name}. I'll keep an eye on things.")
            break

        system_prompt = assemble_context(user_id, session_id, persona_name, user_name)
        raw = llm_chat(system_prompt, user_input)
        text_reply, action = parse_response(raw)

        add_message(user_id, session_id, "user", user_input)
        add_message(user_id, session_id, "assistant", text_reply)

        now = datetime.now()
        context = {
            "time": now.strftime("%H:%M"),
            "day": now.strftime("%A"),
            "period": _time_period(now.hour)
        }

        # Send action to simulator if present
        sim_result = ""
        if action:
            sim_result = send_action(action)
            print(f"\n  [Action]: {json.dumps(action)}")
            print(f"  [Simulator]: {sim_result}")

        log_episode(
            user_id=user_id,
            context=context,
            user_input=user_input,
            action_taken=json.dumps(action) if action else None,
            outcome="accepted" if action else "none",
            source="user"
        )

        update_memory(user_id, user_input)
        if action:
            update_patterns(user_id, context, json.dumps(action))

        print(f"\n{persona_name}: {text_reply}\n")


if __name__ == "__main__":
    init_db()
    users = get_all_users()
    if not users:
        print("No users found. Run onboarding first:")
        print("  python -m src.brain.onboarding")
    else:
        u = users[0]
        run_conversation(u["id"], u["persona_name"], u["name"])
