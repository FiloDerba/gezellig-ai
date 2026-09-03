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

A spaced-repetition vocabulary trainer in two parts: a **Django + DRF backend** that owns the
data and the scheduling, and a **Streamlit frontend** that is purely a client of its API.

### Backend

All Django code lives under `django/`: `backend/` is the project package, `vocabulary/` is the
single domain app.

```bash
cd django
cp example.env .env                                   # optional, all values have defaults
uv run --project .. python manage.py migrate
uv run --project .. python manage.py runserver        # http://127.0.0.1:8000
```

Interactive API docs are at `/api/docs/`, the OpenAPI schema at `/api/schema/`. The Django
admin is at `/admin/` — create a login with `manage.py createsuperuser`, or use `admin`/`admin`
if the stack was started through Docker. It lists words with their schedule, filters by chapter
and word type, and can bulk-reset cards; the review log is read-only there.

| Endpoint | Purpose |
|---|---|
| `GET /api/words/` | List/search words (`?chapter=`, `?search=`, `?maturity=`) |
| `POST /api/words/` | Add a word; its schedule row is created too |
| `POST /api/words/load-sample/` | Load the built-in starter deck |
| `GET /api/study/queue/?limit=20` | Today's due cards, each with per-rating interval previews |
| `POST /api/study/{id}/review/` | Record a rating (`{"quality": 0\|1\|3\|5}`) and reschedule |
| `GET /api/stats/overview/` | Totals, maturity split, reviews today, streak |
| `GET /api/stats/activity/`, `/forecast/`, `/chapters/` | Data behind the Progress tab |

Getting words in:

```bash
uv run --project .. python manage.py import_anki /path/to/deck.apkg   # Anki export
uv run --project .. python manage.py import_legacy ../data/dutch_learning.db   # pre-Django SQLite
```

### Frontend

**Vocabulary** is the landing page: today's session on the *Study* tab, charts and maturity on
the *Progress* tab. `Word list` and `Manage` are secondary pages in the sidebar. Sessions are
capped by the **Cards per day** slider, so a large deck stays finite.

```bash
uv run streamlit run src/dutch_learning/app.py   # from the repo root, with the backend running
```

Run it from the repo root so `.streamlit/config.toml` (dark theme, orange accent) applies.
Set `VOCAB_API_URL` if the backend is not on `http://127.0.0.1:8000/api`.

### Docker

`django/docker-compose.yaml` runs the whole thing — Postgres, the backend and the frontend —
so nothing but Docker is needed:

```bash
cd django
docker compose up -d --build
```

| Service | URL | Notes |
|---|---|---|
| `web` | http://127.0.0.1:8000 | Django on `runserver`, auto-migrated |
| `streamlit` | http://127.0.0.1:8501 | Waits for `web` to report healthy |
| `db` | `127.0.0.1:5433` | Postgres 17.7, published off 5432 to avoid clashes |

On first boot `entrypoint.sh` waits for Postgres, migrates, creates an **`admin` / `admin`**
superuser, and loads the sample deck if the database is empty. The repo is bind-mounted, so
edits reload live.

The compose project is pinned to `name: dutch-learning`. Without that, Compose names the
project after this directory (`django`) and collides with every other repo whose Django app
also lives in a `django/` folder — sharing their volumes and deleting their containers.

```bash
docker compose logs -f web            # follow the backend
docker compose run --rm web bash entrypoint.sh test    # run pytest in the container
docker compose down                   # stop; add -v to also drop the Postgres volume
```

### Using hosted Postgres instead of SQLite

The backend defaults to `django/db.sqlite3`. It switches to Postgres when either
`DATABASE_URL` (a connection string, which is what [Neon](https://neon.com) hands you) or
`DATABASE_NAME` (discrete `DATABASE_*` variables, which is how compose passes them) is set.

Neon's free tier does not pause idle projects, unlike [Supabase](https://supabase.com):

1. Create a project at [console.neon.tech](https://console.neon.tech), any region near you.
2. Copy the connection string from **Connect** → *Connection string*, and keep the
   `?sslmode=require&channel_binding=require` suffix; both are forwarded to the driver.
3. Put it in `django/.env` (gitignored) as `DATABASE_URL=...`, then create the schema:

```bash
cd django
uv run --project .. python manage.py migrate
```

To carry an existing deck over, dump it while still on SQLite and load it once `DATABASE_URL`
points at Neon. `loaddata` resets the Postgres sequences afterwards, so new words still get
usable ids:

```bash
uv run --project .. python manage.py dumpdata vocabulary --indent 2 -o ../data/deck.json
uv run --project .. python manage.py loaddata ../data/deck.json
```

Use the **pooled** host (`-pooler` in the hostname) for serverless deploys. `CONN_MAX_AGE`
defaults to 600s so a remote database is not redialled on every request.

## Dev

```bash
uv run pytest
uv run ruff check .
uv run pyright
```
