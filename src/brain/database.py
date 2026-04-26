import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "data" / "butler.db"

def get_connection():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    c = conn.cursor()

    # Household members
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            persona_name TEXT NOT NULL,       -- name user gives the butler
            is_active   INTEGER DEFAULT 1,
            created_at  TEXT DEFAULT (datetime('now'))
        )
    """)

    # Flexible key/value facts about each user
    # category: schedule | preference | hobby | vocabulary | personality
    c.execute("""
        CREATE TABLE IF NOT EXISTS user_profile (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id),
            category    TEXT NOT NULL,
            key         TEXT NOT NULL,
            value       TEXT NOT NULL,
            confidence  REAL DEFAULT 1.0,     -- 0.0 to 1.0
            source      TEXT DEFAULT 'onboarding', -- onboarding | observed | inferred
            updated_at  TEXT DEFAULT (datetime('now')),
            UNIQUE(user_id, category, key)
        )
    """)

    # Everything that happened — full world context snapshot
    c.execute("""
        CREATE TABLE IF NOT EXISTS episodes (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL REFERENCES users(id),
            timestamp       TEXT DEFAULT (datetime('now')),
            day_of_week     TEXT,
            context_json    TEXT,             -- {time, weather, devices_on, presence}
            user_input      TEXT,             -- what the user said (if anything)
            action_taken    TEXT,             -- what the butler did
            outcome         TEXT,             -- accepted | rejected | ignored
            source          TEXT DEFAULT 'user' -- user | proactive | automated
        )
    """)

    # Learned patterns extracted from episodes
    c.execute("""
        CREATE TABLE IF NOT EXISTS patterns (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id             INTEGER NOT NULL REFERENCES users(id),
            trigger_context     TEXT NOT NULL,  -- JSON describing when this fires
            predicted_action    TEXT NOT NULL,  -- what to do
            confidence          REAL DEFAULT 0.5,
            occurrences         INTEGER DEFAULT 1,
            last_seen           TEXT,
            created_at          TEXT DEFAULT (datetime('now'))
        )
    """)

    # Per-session conversation memory
    c.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id),
            session_id  TEXT NOT NULL,
            role        TEXT NOT NULL,         -- user | assistant
            message     TEXT NOT NULL,
            timestamp   TEXT DEFAULT (datetime('now'))
        )
    """)

    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH}")

# --- User helpers ---

def create_user(name: str, persona_name: str) -> int:
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO users (name, persona_name) VALUES (?, ?)", (name, persona_name))
    user_id = c.lastrowid
    conn.commit()
    conn.close()
    return user_id

def get_all_users() -> list:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE is_active = 1")
    users = [dict(row) for row in c.fetchall()]
    conn.close()
    return users

# --- Profile helpers ---

def upsert_profile(user_id: int, category: str, key: str, value: str,
                   confidence: float = 1.0, source: str = "onboarding"):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO user_profile (user_id, category, key, value, confidence, source, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(user_id, category, key)
        DO UPDATE SET value=excluded.value, confidence=excluded.confidence,
                      source=excluded.source, updated_at=excluded.updated_at
    """, (user_id, category, key, value, confidence, source))
    conn.commit()
    conn.close()

def get_profile(user_id: int) -> dict:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT category, key, value, confidence FROM user_profile WHERE user_id = ?", (user_id,))
    rows = c.fetchall()
    conn.close()
    profile = {}
    for row in rows:
        profile.setdefault(row["category"], {})[row["key"]] = {
            "value": row["value"],
            "confidence": row["confidence"]
        }
    return profile

# --- Episode helpers ---

def log_episode(user_id: int, context: dict, user_input: str = None,
                action_taken: str = None, outcome: str = None, source: str = "user"):
    conn = get_connection()
    c = conn.cursor()
    now = datetime.now()
    c.execute("""
        INSERT INTO episodes (user_id, timestamp, day_of_week, context_json, user_input, action_taken, outcome, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, now.isoformat(), now.strftime("%A"),
          json.dumps(context), user_input, action_taken, outcome, source))
    conn.commit()
    conn.close()

# --- Conversation helpers ---

def add_message(user_id: int, session_id: str, role: str, message: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO conversations (user_id, session_id, role, message)
        VALUES (?, ?, ?, ?)
    """, (user_id, session_id, role, message))
    conn.commit()
    conn.close()

def get_conversation(user_id: int, session_id: str, last_n: int = 10) -> list:
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT role, message FROM conversations
        WHERE user_id = ? AND session_id = ?
        ORDER BY timestamp DESC LIMIT ?
    """, (user_id, session_id, last_n))
    rows = [dict(row) for row in c.fetchall()]
    conn.close()
    return list(reversed(rows))


if __name__ == "__main__":
    init_db()

    # Test: create a user
    uid = create_user("Nikhil", "Jarvis")
    print(f"Created user id={uid}")

    # Test: seed some profile facts
    upsert_profile(uid, "schedule", "wake_time", "07:00")
    upsert_profile(uid, "preference", "temperature", "21")
    upsert_profile(uid, "hobby", "gaming", "true")
    upsert_profile(uid, "vocabulary", "kill the lights", "turn_off/lights")

    # Test: log an episode
    log_episode(uid,
        context={"time": "22:05", "weather": "clear", "devices_on": ["tv"]},
        user_input="I'm tired",
        action_taken="dim_lights/bedroom",
        outcome="accepted"
    )

    # Test: add conversation turns
    log_episode
    add_message(uid, "session_001", "user", "I'm tired")
    add_message(uid, "session_001", "assistant", "I've dimmed the bedroom lights. Sleep well, Nikhil.")

    # Print profile
    print("\nUser profile:")
    print(json.dumps(get_profile(uid), indent=2))

    # Print conversation
    print("\nConversation:")
    for msg in get_conversation(uid, "session_001"):
        print(f"  {msg['role']}: {msg['message']}")

    print("\nAll good — Brain schema working.")
