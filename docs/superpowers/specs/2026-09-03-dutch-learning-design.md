# Dutch Learning App — Design Spec

**Date:** 2026-09-03  
**Status:** Approved

## Overview

Streamlit app for learning Dutch vocabulary using SM-2 spaced repetition and AI-powered conversational hints. Word data imported from an Anki `.apkg` file (De Opmaat / De Sprong course, 2957 notes).

## Architecture

```
apkg file → importer → SQLite (words + SRS state)
                            ↓
                Streamlit UI (session_state for card flow)
                            ↓
                AI hint layer (pydantic-ai, Claude/Gemini)
```

- Local app, run with `uv run streamlit run src/dutch_learning/app.py`
- Data stored in `data/dutch_learning.db`
- Audio media stored in `data/media/`
- One-time import CLI: `uv run python -m dutch_learning.importer /path/to/deck.apkg`

## Data Model

### `words` table

| column     | type    | notes                              |
|------------|---------|------------------------------------|
| id         | int PK  | Anki note id                       |
| dutch      | text    | e.g. `lezen`                       |
| english    | text    | e.g. `to read`                     |
| word_type  | text    | N / V / Pron / Adj / etc           |
| audio_file | text    | filename in `data/media/`          |
| tags       | text    | raw Anki tags                      |
| chapter    | text    | extracted from tags (e.g. Thema01) |

### `srs_state` table

| column      | type    | notes                          |
|-------------|---------|--------------------------------|
| word_id     | int FK  | references words.id            |
| interval    | int     | days until next review         |
| ease_factor | float   | SM-2 EF, starts at 2.5         |
| due_date    | date    | next review date               |
| reps        | int     | total reviews completed        |

SM-2 rating scale: Again=0, Hard=1, Good=3, Easy=5 (standard Anki).

## UI

Three pages via sidebar navigation:

### Study (main)

```
┌─────────────────────────────────────┐
│  📚 De Opmaat — 12 cards due today  │
│                                     │
│         [ lezen ]                   │
│         verb • Thema 01             │
│                                     │
│         🔊 Play audio               │
│                                     │
│      [ Show answer ]                │
│                                     │
│  ─── after flip ───                 │
│         to read                     │
│                                     │
│  💬 Ask AI for a hint  (expander)   │
│                                     │
│  [Again] [Hard] [Good] [Easy]       │
└─────────────────────────────────────┘
```

- Cards shown = words with `due_date <= today`, ordered by due date
- AI hint expander only visible after answer is revealed
- Rating buttons trigger SM-2 update and advance to next card

### Browse

- Searchable, filterable table of all words
- Filter by chapter
- Shows Dutch, English, word type, chapter, next due date

### Stats

- Cards due today
- Total cards reviewed (all time)
- Cards per chapter with review counts

## AI Hints

- Provider: reuse existing pydantic-ai setup; Claude or Gemini via `.env` keys
- Trigger: user opens expander and types a question
- Streaming response via `st.write_stream`
- System prompt:

```
You are a Dutch language tutor. The user is studying the word '{dutch}'
({word_type}, meaning '{english}'). Answer concisely in English.
Give hints, etymology, mnemonics, or example sentences as requested.
Do not directly give away the answer if the user is still trying to recall it.
```

## File Structure

```
src/dutch_learning/
├── app.py              # Streamlit entry point, sidebar nav
├── db.py               # SQLite setup, all queries
├── srs.py              # SM-2 algorithm implementation
├── importer.py         # .apkg → SQLite + media extraction
├── ai.py               # AI hint client, streaming
└── pages/
    ├── study.py        # Study page logic + UI
    ├── browse.py       # Browse page
    └── stats.py        # Stats page
data/
├── dutch_learning.db   # SQLite database (gitignored)
└── media/              # Audio files from apkg (gitignored)
```

## Out of Scope (MVP)

- User accounts / multi-user
- Mnemonic generation (AI auto-generates memory aids)
- Typed answer scoring
- Mobile layout optimization
- Export / sync back to Anki
