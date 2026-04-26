# The Butler — AI Home OS

## Vision
A locally-run, privacy-first AI butler that knows your home, your life, and your patterns.
Not a voice assistant. A persistent, living AI that acts proactively, explains its reasoning, and gets smarter every day — entirely on your own hardware, zero cloud dependency.

---

## What Makes This Different

| Feature | Alexa/Google | HA + LLM | The Butler |
|---|---|---|---|
| Natural conversation | Partial | Yes | Yes |
| Device control | Yes | Yes | Yes |
| Learns routines | Basic | No | Yes |
| Knows interests/hobbies | No | No | Yes |
| Proactive suggestions | Minimal | No | Yes |
| Explains its reasoning | No | No | Yes |
| Household knowledge graph | No | No | Yes |
| 100% local | No | Yes | Yes |
| Persistent personality/persona | No | No | Yes |
| Multi-user household profiles | Partial | No | Yes |

---

## Architecture

```
┌─────────────────────────────────────────┐
│            ONBOARDING ENGINE            │
│  Conversational first-run profile setup │
│  Persona name selection                 │
│  Household member registration          │
└──────────────────┬──────────────────────┘
                   ↓
┌─────────────────────────────────────────┐
│             PERCEPTION LAYER            │
│  STT (Whisper) │ Wake word              │
│  Time │ Weather │ Calendar │ Presence   │
│  Device states (via Home Assistant)     │
└──────────────────┬──────────────────────┘
                   ↓
┌─────────────────────────────────────────┐
│               BRAIN LAYER               │
│  Short-term : conversation buffer       │
│  Episodic   : SQLite event log          │
│  Semantic   : user profile + facts      │
│  Graph      : pattern relationships     │
└──────────────────┬──────────────────────┘
                   ↓
┌─────────────────────────────────────────┐
│            REASONING LAYER              │
│  Context assembler                      │
│  LLM — Qwen2.5:3b via Ollama           │
│  Response parser (text + action)        │
│  Proactive suggestion engine            │
└──────────────────┬──────────────────────┘
                   ↓
┌─────────────────────────────────────────┐
│              ACTION LAYER               │
│  Device control (HA bridge)             │
│  TTS response (Piper)                   │
│  Profile updater (async)                │
│  Pattern learner (async)                │
└─────────────────────────────────────────┘
```

---

## Brain — Database Schema

**Multi-user from day one.** All tables are user-scoped.

```
users               — household members, each with their own profile + persona
user_profile        — flexible key/value facts with confidence scores
                      categories: schedule, preference, hobby, vocabulary, personality
episodes            — timestamped log of everything that happened + full world context
patterns            — learned correlations extracted from episodes over time
conversations       — per-session short-term memory (role, message, timestamp)
```

---

## Proactive Engine Logic

| Confidence | Context | Behaviour |
|---|---|---|
| > 85% | Routine, non-intrusive | Act silently, notify after |
| 60–85% | Uncertain | Ask first |
| < 60% | Still learning | Stay silent, collect data |

Context sensitivity:
- No interruptions when TV/music at high volume
- More proactive in mornings, less at night
- Matches verbosity to user's reply style

---

## Persona Design
- Named by user during onboarding
- Warm, witty, concise default tone
- Adapts formality to detected user mood
- Remembers personal details, references them naturally

---

## Key Design Decisions

| Decision | Chose | Over | Why |
|---|---|---|---|
| LLM runtime | Ollama | llama.cpp direct | Easier model management, API-first |
| LLM model | Qwen2.5:3b | Phi-3.5, LLaMA 3.2 | Best instruction following at 3B scale |
| STT | Whisper base | Faster-Whisper | Simplicity for MVP, upgrade path clear |
| Memory store | SQLite | ChromaDB, Postgres | Zero-dependency, local, fast enough |
| Device layer | Home Assistant | Direct protocol | Massive device support, open source |
| Multi-user | From day one | Add later | Schema is harder to migrate than build right |
| Proactive logic | Confidence tiers | Always ask / never ask | Balances helpfulness vs annoyance |

---

## Module Status

| # | Module | Status |
|---|--------|--------|
| 1 | STT — Whisper | ✅ Complete |
| 2 | Brain — SQLite schema | 🔧 In Progress |
| 3 | Onboarding engine | 🔲 Queued |
| 4 | Context assembler | 🔲 Queued |
| 5 | Reasoning layer (LLM + parser) | 🔲 Queued |
| 6 | Home Assistant bridge | 🔲 Queued |
| 7 | TTS — Piper | 🔲 Queued |
| 8 | Proactive engine | 🔲 Queued |
| 9 | Wake word — OpenWakeWord | 🔲 Queued |
| 10 | Web dashboard | 🔲 Queued |

---

## Roadmap (Post-MVP)
- Multi-user voice identification
- Presence detection (BLE / phone ping)
- Anomaly detection (unusual power draw, door left open)
- Calendar + weather integration
- Circadian lighting (auto colour temp by time)
- Energy reports in plain English
- Guest mode with restricted access
- Vacation mode (simulated occupancy)
- Appliance health monitoring
- Visual automation builder (LLM-assisted)
- White-label for property managers / short-term rentals

---

## Tech Stack

| Component | Technology |
|---|---|
| LLM | Qwen2.5:3b via Ollama |
| STT | OpenAI Whisper (local) |
| TTS | Piper (local) |
| Wake Word | OpenWakeWord |
| Device Layer | Home Assistant |
| Backend | FastAPI (Python 3.12) |
| Memory | SQLite |
| Patterns | NetworkX + SQLite |
| Dev Hardware | RTX 4070, 32GB RAM, Windows 11 |
