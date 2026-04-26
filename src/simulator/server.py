from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pathlib import Path
import json
import asyncio

app = FastAPI()

# --- Device State ---
home_state = {
    "living_room": {
        "light":    {"on": False, "brightness": 100},
        "tv":       {"on": False},
        "blinds":   {"open": True},
    },
    "bedroom": {
        "light":    {"on": False, "brightness": 80},
        "blinds":   {"open": True},
    },
    "kitchen": {
        "light":    {"on": False, "brightness": 100},
    },
    "bathroom": {
        "light":    {"on": False, "brightness": 100},
    },
    "porch": {
        "light":    {"on": False, "brightness": 100},
    },
    "home": {
        "thermostat":   {"temperature": 21, "target": 21},
        "music_player": {"on": False, "track": "", "genre": ""},
        "door_lock":    {"locked": True},
    }
}

# --- WebSocket Manager ---
class ConnectionManager:
    def __init__(self):
        self.connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.connections.append(ws)

    def disconnect(self, ws: WebSocket):
        self.connections.remove(ws)

    async def broadcast(self, data: dict):
        for ws in self.connections:
            try:
                await ws.send_json(data)
            except:
                pass

manager = ConnectionManager()


def apply_action(action: dict) -> str:
    """Apply an action to home_state. Returns a human-readable result."""
    act = action.get("action", "")
    device = action.get("device", "")
    area = action.get("area", "home")

    # Normalize area
    area_map = {
        "living room": "living_room", "lounge": "living_room",
        "bed room": "bedroom", "bed": "bedroom",
        "bath room": "bathroom", "bath": "bathroom",
        "front": "porch", "outside": "porch",
    }
    area = area_map.get(area.lower(), area.lower().replace(" ", "_"))

    target = home_state.get(area) or home_state.get("home")

    if act in ("turn_on", "on"):
        if "light" in device and area in home_state:
            home_state[area]["light"]["on"] = True
            return f"Lights on in {area}"
        if "tv" in device and "tv" in home_state.get("living_room", {}):
            home_state["living_room"]["tv"]["on"] = True
            return "TV on"
        if "music" in device or "music_player" in device:
            home_state["home"]["music_player"]["on"] = True
            genre = action.get("genre", action.get("playlist", ""))
            home_state["home"]["music_player"]["genre"] = genre
            return f"Music on: {genre}"

    elif act in ("turn_off", "off"):
        if device == "all":
            for room in home_state:
                if "light" in home_state[room]:
                    home_state[room]["light"]["on"] = False
            home_state["living_room"]["tv"]["on"] = False
            home_state["home"]["music_player"]["on"] = False
            return "Everything turned off"
        if "light" in device and area in home_state:
            home_state[area]["light"]["on"] = False
            return f"Lights off in {area}"
        if "tv" in device:
            home_state["living_room"]["tv"]["on"] = False
            return "TV off"
        if "music" in device:
            home_state["home"]["music_player"]["on"] = False
            return "Music off"

    elif act == "set_brightness":
        val = int(action.get("value", action.get("brightness", 100)))
        if area in home_state and "light" in home_state[area]:
            home_state[area]["light"]["brightness"] = val
            home_state[area]["light"]["on"] = val > 0
            return f"Brightness set to {val}% in {area}"

    elif act in ("set_temperature", "adjust_temperature"):
        val = float(action.get("value", action.get("to", action.get("temperature", 21))))
        home_state["home"]["thermostat"]["target"] = val
        return f"Thermostat set to {val}°C"

    elif act == "lock":
        home_state["home"]["door_lock"]["locked"] = True
        return "Door locked"

    elif act == "unlock":
        home_state["home"]["door_lock"]["locked"] = False
        return "Door unlocked"

    elif act in ("open", "close"):
        if "blind" in device and area in home_state and "blinds" in home_state[area]:
            home_state[area]["blinds"]["open"] = (act == "open")
            return f"Blinds {act}ed in {area}"

    elif act == "play":
        home_state["home"]["music_player"]["on"] = True
        genre = action.get("genre", action.get("playlist", ""))
        track = action.get("track", "")
        home_state["home"]["music_player"]["genre"] = genre
        home_state["home"]["music_player"]["track"] = track
        return f"Playing: {genre or track}"

    return f"Action '{act}' on '{device}' in '{area}' — noted"


# --- Routes ---

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    html_path = Path(__file__).parent / "static" / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))

@app.get("/state")
async def get_state():
    return home_state

@app.post("/action")
async def receive_action(action: dict):
    result = apply_action(action)
    await manager.broadcast({"type": "state_update", "state": home_state, "result": result})
    return {"ok": True, "result": result}

@app.post("/action/batch")
async def receive_batch(actions: list):
    results = [apply_action(a) for a in actions]
    await manager.broadcast({"type": "state_update", "state": home_state, "result": ", ".join(results)})
    return {"ok": True, "results": results}

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    await ws.send_json({"type": "state_update", "state": home_state, "result": ""})
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.simulator.server:app", host="0.0.0.0", port=8000, reload=True)
