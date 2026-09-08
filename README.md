# ai-playground

Playground for testing agentic frameworks, primarily [pydantic-ai](https://ai.pydantic.dev).

## Setup

```bash
uv sync
cp .env.example .env   # fill in GOOGLE_API_KEY (free tier: https://aistudio.google.com/apikey) and TAVILY_API_KEY
```

## Run

Starts an interactive chat loop backed by Gemini (`gemini-2.0-flash`, free tier),
with `date` and `web_search` (Tavily) tools wired in.

```bash
uv run ai-playground
```

## Dutch learning app

A spaced-repetition vocabulary trainer with AI coaching and pronunciation scoring.

```bash
uv run streamlit run streamlit_app.py
```

That is the whole thing — one process, no server. The app configures Django inside itself and
uses the ORM to reach the database named in `django/.env`, so Django is a library here rather
than a service. Run it from the repo root so `.streamlit/config.toml` (dark theme, orange
accent) and `data/media` (the deck's audio) resolve.

### Pages

| Page | What it does |
|---|---|
| Study | Today's session. Flip, rate, and get intervals previewed on each answer button |
| Speaking | Say the word, record it, and have Gemini score the pronunciation |
| Assistant | The ai-playground agent, able to search the words you have actually studied |
| Progress | Review activity, upcoming load, maturity split, per-chapter breakdown |
| Words | Filter and search the whole deck |
| Manage | Load the sample deck, add words, see how to import Anki |

Sessions are capped by **Cards per day** under *Session*, so a 3000-word deck stays finite.

### AI

`GOOGLE_API_KEY` in the root `.env` powers three things, all of which degrade to a caption if
the key is missing:

- **Coach** on the Study page returns a structured breakdown — meaning, an example sentence
  with translation, a mnemonic, and the mistake English speakers make with that word.
- **Ask** takes a free-form question about the current card and deliberately withholds the
  translation, since you are mid-recall.
- **Speaking** sends your recording to Gemini and gets back a score, what it heard, and
  concrete fixes, tuned for the sounds English speakers find hard in Dutch (`g`/`ch`, `ui`,
  `eu`, `ij`/`ei`, dropped final `n`).

Override the model with `DUTCH_MODEL`.

### Assistant

The **Assistant** page runs the `ai_playground` agent — the same one behind `uv run
ai-playground`, keeping its date and web search tools — with two extra tools that read this
deck, so answers are grounded in your own vocabulary instead of Dutch in general:

| Tool | Returns |
|---|---|
| `search_my_vocabulary(query)` | Studied words matching a Dutch or English substring, with review counts and recency |
| `my_vocabulary_summary()` | Coverage, maturity split, streak, and chapters touched |

"Studied" means *appears in the review log*, not `reps > 0`. An `Again` rating resets `reps`
to zero, so the simpler definition would hide exactly the words you found hardest.

Retrieval happens per turn through tools rather than by pasting the deck into the prompt,
which keeps each turn cheap and always current — the full deck would be roughly 60-100k tokens
every message. The agent is cached on the model alone, so it can never hold a stale copy.
Expect tool-using turns to take noticeably longer than plain ones, since they are two model
round trips plus a database query.

`ai_playground.Agent` gained `extra_context` and `extra_tools` for this, so the host
application injects its own knowledge without the agent package knowing anything about Dutch.
Set `PLAYGROUND_MODEL` to change its model.

### Layout

```
streamlit_app.py             navigation only
src/dutch_learning/
    data.py                  everything the pages read and write
    ai.py                    agents and their structured outputs
    shared.py                cached agents, session handling, formatters
    django_bootstrap.py      configures Django in-process
    app_pages/               one script per page
django/
    backend/                 settings, admin urls
    vocabulary/              models, migrations, selectors, services, SM-2, admin
```

Scheduling rules and queries live on the Django side: `vocabulary/srs.py` holds the
Anki-flavoured SM-2, `selectors.py` the reads, `services.py` the writes. `data.py` only adapts
them for the UI, so no business logic sits in the Streamlit layer.

### Database

Defaults to `django/db.sqlite3`. Set `DATABASE_URL` in `django/.env` to use hosted Postgres —
[Neon](https://neon.com) is a good fit because its free tier does not pause idle projects,
unlike [Supabase](https://supabase.com).

1. Create a project at [console.neon.tech](https://console.neon.tech).
2. Copy the connection string from **Connect**, keeping the
   `?sslmode=require&channel_binding=require` suffix; both are forwarded to the driver.
3. Put it in `django/.env` (gitignored), then create the schema:

```bash
cd django
uv run --project .. python manage.py migrate
```

To carry an existing deck across, dump it while still on SQLite and load it once `DATABASE_URL`
points at Neon. `loaddata` resets the Postgres sequences, so new words still get usable ids:

```bash
uv run --project .. python manage.py dumpdata vocabulary --indent 2 -o ../data/deck.json
uv run --project .. python manage.py loaddata ../data/deck.json
```

Expect a remote database to feel slower than SQLite; `CONN_MAX_AGE` is 600s so connections are
reused rather than redialled. Blank values in `.env` are treated as unset, so the defaults still
apply. The test suite always uses SQLite, whatever `DATABASE_URL` says.

### Getting words in

```bash
cd django
uv run --project .. python manage.py import_anki /path/to/deck.apkg
uv run --project .. python manage.py import_legacy ../data/dutch_learning.db
```

Anki audio lands in `data/media` and is what the Speaking page plays as the native reference.

### Admin

The only reason to run a server. Useful for bulk edits and for inspecting schedules:

```bash
cd django
uv run --project .. python manage.py runserver     # http://127.0.0.1:8000/admin/
```

Create a login with `manage.py createsuperuser`. Words list with their schedule, filter by
chapter and word type, and can be bulk-reset; the review log is read-only, since those rows are
written by the study flow.

## Dev

```bash
uv run pytest
uv run ruff check .
uv run pyright
```
