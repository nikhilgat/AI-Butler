import httpx
import json

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:3b"

SYSTEM_PROMPT = """You are a home automation assistant. Convert user commands into JSON tool calls.

Always respond with ONLY a JSON object, no explanation, no markdown.

Supported actions: turn_on, turn_off, set_brightness, set_temperature, lock, unlock, set_volume

Examples:
User: "turn on the living room lights"
{"action": "turn_on", "device": "light", "area": "living_room"}

User: "set bedroom brightness to 50 percent"
{"action": "set_brightness", "device": "light", "area": "bedroom", "value": 50}

User: "I'm cold"
{"action": "set_temperature", "device": "thermostat", "area": "home", "value": 22}

User: "lock the front door"
{"action": "lock", "device": "door_lock", "area": "front"}

User: "turn off everything"
{"action": "turn_off", "device": "all", "area": "home"}
"""

def parse_intent(user_text: str) -> dict:
    payload = {
        "model": MODEL,
        "prompt": f"{SYSTEM_PROMPT}\n\nUser: \"{user_text}\"\n",
        "stream": False
    }

    response = httpx.post(OLLAMA_URL, json=payload, timeout=30)
    response.raise_for_status()

    raw = response.json()["response"].strip()

    # Strip markdown code fences if model adds them
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    return json.loads(raw)

if __name__ == "__main__":
    test_commands = [
        "turn on the kitchen lights",
        "set the bedroom brightness to 30 percent",
        "I'm feeling cold",
        "lock the front door",
        "turn off everything in the living room",
    ]

    for cmd in test_commands:
        print(f"Input:  {cmd}")
        result = parse_intent(cmd)
        print(f"Output: {json.dumps(result, indent=2)}\n")
