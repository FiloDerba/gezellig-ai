# AGENTS.md

Orientation for AI agents. Read this first; `README.md` has the user-facing detail.

## What this repo is

A personal **monorepo of experiments**. Each top-level area is an independent sandbox for
trying an idea. When one outgrows the repo it is moved to its own repository, so keep areas
loosely coupled: no imports between sandboxes except through a documented seam (see below).

Python 3.14, managed with `uv` (one `pyproject.toml`, one `uv.lock`, one `.venv`).

## Map

| Area | Path | What it is | Entry point |
|---|---|---|---|
| AI playground | `src/ai_playground/` | pydantic-ai chat agent (local Ollama by default) with `date` + Tavily `web_search` tools. Accepts `extra_context` / `extra_tools` so hosts can extend it. | `uv run gezellig-ai` |
| Dutch trainer UI | `src/dutch_learning/` | Streamlit app: spaced-repetition study, AI coach, pronunciation scoring (Gemini), assistant page. No business logic here. | `uv run streamlit run streamlit_app.py` |
| Dutch trainer backend | `django/` | Django used **as a library** (ORM + admin), not a server. `vocabulary/` holds models, SM-2 (`srs.py`), reads (`selectors.py`), writes (`services.py`), Anki import. | `django/manage.py` |
| Tests | `tests/` (app/agent), `django/**/test_*.py` | pytest | `uv run pytest` |

Seams between areas:
- `dutch_learning` -> `ai_playground`: the Assistant page passes `extra_context`/`extra_tools`
  (`dutch_learning/vocab_tools.py`) into `ai_playground.Agent`. The playground knows nothing
  about Dutch.
- `dutch_learning` -> `django`: `django_bootstrap.py` configures Django in-process;
  `data.py` is the only adapter the pages use.

## Where logic belongs (Dutch trainer)

- Scheduling rules: `django/vocabulary/srs.py`
- Reads: `selectors.py`; writes: `services.py`
- UI adapter: `src/dutch_learning/data.py`
- Agents and structured outputs: `src/dutch_learning/ai.py`; cached agents/session: `shared.py`
- Pages: `src/dutch_learning/app_pages/*.py` (one script per page, registered in `streamlit_app.py`)

## Config

Root `.env` (see `.env.example`): `PLAYGROUND_MODEL`, `OLLAMA_BASE_URL`, `GOOGLE_API_KEY`
(Dutch AI features; they degrade gracefully without it), `TAVILY_API_KEY`, `DUTCH_MODEL`.
`django/.env` (see `django/example.env`): `DATABASE_URL` (Postgres/Neon) or default SQLite
`django/db.sqlite3`. Tests always use SQLite. Run the app from the repo root (it needs
`.streamlit/config.toml` and `data/media`).

## Commands

```bash
uv sync
uv run pytest
uv run ruff check . && uv run ruff format .   # line length 100
uv run pyright                                # checks src/ and tests/
cd django && uv run --project .. python manage.py <cmd>   # migrate, import_anki, runserver...
```

Pre-commit runs ruff + `uv lock --check`; keep `pyproject.toml` and `uv.lock` in sync.

## Conventions

- Match surrounding style; keep changes small. No dependencies for a few lines of code.
- `pytest` has `pythonpath = ["src", "django"]`, so import `ai_playground`, `dutch_learning`,
  `vocabulary`, `backend` directly.
- New packages under `src/` must be added to `module-name` in `[tool.uv.build-backend]` and to
  ruff's `known-first-party`.

## Adding a new sandbox

1. Create a new folder: `src/<name>/` for Python code (or a top-level folder for a non-Python
   or self-contained project).
2. Register it as above if it is a package; add its deps to `pyproject.toml` and run `uv lock`.
3. Add a row to the **Map** table here and a short section in `README.md`.
4. Put its tests in `tests/<name>/`.
5. When it gets too big, move it to its own repo and delete the row.
