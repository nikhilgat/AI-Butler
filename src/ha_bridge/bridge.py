import httpx

SIMULATOR_URL = "http://localhost:8000"

DEVICE_MAP = {
    "light": "light", "lights": "light", "lighting": "light",
    "lamp": "light", "lamps": "light",
    "tv": "tv", "television": "tv",
    "music": "music_player", "speaker": "music_player", "speakers": "music_player",
    "thermostat": "thermostat", "heater": "thermostat", "ac": "thermostat",
    "temperature": "thermostat",
    "lock": "door_lock", "door": "door_lock",
    "blind": "blinds", "blinds": "blinds", "curtain": "blinds",
}

AREA_MAP = {
    "living": "living_room", "lounge": "living_room",
    "bedroom": "bedroom", "bed": "bedroom",
    "kitchen": "kitchen",
    "bathroom": "bathroom", "bath": "bathroom",
    "porch": "porch", "front": "porch", "entrance": "porch",
    "all": "all", "entire": "all", "whole": "all", "everywhere": "all",
    "home": "home", "house": "home",
}


def _normalize_verb(raw: str) -> str:
    r = raw.lower()
    if any(x in r for x in ("turn off", "switch off", "disable", "off", "kill", "stop")):
        return "turn_off"
    if any(x in r for x in ("turn on", "switch on", "enable", "on", "start")):
        return "turn_on"
    if any(x in r for x in ("dim", "lower", "decrease", "reduce", "darken")):
        return "set_brightness"
    if any(x in r for x in ("brighten", "increase brightness", "brighter")):
        return "set_brightness"
    if any(x in r for x in ("set temperature", "adjust temperature", "set temp", "change temp", "heat", "cool")):
        return "set_temperature"
    if any(x in r for x in ("lock",)):
        return "lock"
    if any(x in r for x in ("unlock",)):
        return "unlock"
    if any(x in r for x in ("play", "music on")):
        return "play"
    if any(x in r for x in ("open",)):
        return "open"
    if any(x in r for x in ("close",)):
        return "close"
    return raw.lower().replace(" ", "_")


def _normalize_device(raw: str) -> str:
    r = raw.lower()
    for k, v in DEVICE_MAP.items():
        if k in r:
            return v
    return raw.lower().replace(" ", "_")


def _normalize_area(raw: str) -> str:
    r = raw.lower()
    for k, v in AREA_MAP.items():
        if k in r:
            return v
    return r.replace(" ", "_")


def normalize_action(action: dict) -> dict:
    n = dict(action)

    # Combine action + device + area into one big string for verb detection
    full_text = f"{action.get('action','')} {action.get('device','')} {action.get('area','')}".lower()

    n["action"] = _normalize_verb(action.get("action", ""))
    n["device"] = _normalize_device(action.get("device", ""))
    n["area"]   = _normalize_area(action.get("area", ""))

    # "all" area + turn_off → turn off everything
    if n["area"] == "all" and n["action"] == "turn_off":
        n["device"] = "all"

    # dim with no value → 30%
    if n["action"] == "set_brightness" and "value" not in n:
        n["value"] = 30

    return n


def send_action(action: dict) -> str:
    normalized = normalize_action(action)
    try:
        r = httpx.post(f"{SIMULATOR_URL}/action", json=normalized, timeout=5)
        r.raise_for_status()
        return r.json().get("result", "")
    except Exception as e:
        return f"[simulator offline: {e}]"


def get_home_state() -> dict:
    try:
        r = httpx.get(f"{SIMULATOR_URL}/state", timeout=5)
        return r.json()
    except:
        return {}
