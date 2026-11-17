# gezellig-ai

My playground for learning to build with LLMs. It holds a few separate experiments:

| Folder | What it is |
|---|---|
| `src/ai_playground/` | A small chat agent (pydantic-ai, local Ollama) with date and web search tools |
| `src/rag_playground/` | Question answering over a long document: vector, keyword and grep search, a knowledge graph, an eval, and an MCP server |
| `src/dutch_learning/` + `django/` | A Dutch vocabulary trainer with spaced repetition and AI coaching |

What I learned along the way is in [`docs/ai-engineering-wiki.md`](docs/ai-engineering-wiki.md),
and what's left to learn is in [`docs/ai-learning-checklist.md`](docs/ai-learning-checklist.md).

*Gezellig* is the Dutch word for a warm, cosy, sociable feeling. Every Dutch course tells you
it can't be translated.

## Setup

```bash
uv sync
cp .env.example .env
ollama pull qwen3.6:35b-a3b
```

Everything runs on Ollama at `http://localhost:11434/v1` unless you say otherwise. The
settings in `.env`:

- `PLAYGROUND_MODEL`: any model you have pulled in Ollama
- `OLLAMA_BASE_URL`: if Ollama runs somewhere else
- `TAVILY_API_KEY`: turns on web search
- `GOOGLE_API_KEY`: the Dutch trainer's coach and pronunciation features use Gemini

## AI playground

A chat loop with your local model, which can look up the date and search the web.

```bash
uv run gezellig-ai
```

## RAG playground

Ask questions about a long document; mine is a 160k-word D&D campaign. Everything runs
locally. Put the `.docx` in `data/rag/` (git-ignored) and point `RAG_DOC` at it.

```bash
ollama pull bge-m3
uv run rag-playground                    # retrieve 5 passages, then answer
uv run rag-playground --agentic          # the model searches when and as often as it wants
uv run rag-playground --hybrid           # keyword search too (works with --agentic)
uv run rag-playground --agentic --grep   # add an exact regex search tool
uv run rag-playground --agentic --graph  # add a knowledge graph lookup tool
uv run rag-eval                          # score each search mode on a set of questions
uv run rag-mcp                           # serve the search tools over MCP
```

### How it works

- The document is split at its headings into passages of about 300 words, each starting
  with its chapter title. `loader.py` knows this document's heading styles (`SamKop`,
  `Samkop2`); change them there for another document.
- The first run embeds the passages, which takes a minute or two. Later runs reuse them
  until the document or `RAG_EMBED_MODEL` changes.
- Search runs in [LanceDB](https://lancedb.com). `RAG_STORE=numpy` does the same search in
  plain numpy instead, with the same results.
- Each answer shows which chapters were retrieved and how many tokens it used.
- The default mode answers every question on its own. `--agentic` keeps the conversation.

### The options

- **`--hybrid`** runs a keyword (BM25) search next to the vector search and merges the two.
  It finds invented names that the embedding model misses. Needs LanceDB.
- **`--grep`** gives the model a case-insensitive regex search over every paragraph. No
  index needed. It returns up to 30 hits, each with the text around the match.
- **`--graph`** has a local model (`RAG_GRAPH_MODEL`) read every passage once and note how
  the named characters, places and factions relate. That takes about two hours for this
  campaign, and it picks up where it stopped if interrupted. A relation is only kept if its
  passage contains both names and the sentence the model quotes. The model also drafts a
  list of names that mean the same person ("Cevan" and "Vecna"). Check that list and edit
  it; it is never overwritten.
- **`rag-eval`** reads a list of questions with the sections that answer them, and shows
  for each search mode how many it found, how much text it returned and how long it took.
  The file format is described at the top of `src/rag_playground/evaluate.py`.
- **`rag-mcp`** offers `search_campaign` and `grep_campaign` to any MCP client. For Claude
  Code: `claude mcp add campaign -- uv run --project /path/to/gezellig-ai rag-mcp --hybrid`.

Everything it creates lives next to the document in `data/rag/`:

| File | What it is |
|---|---|
| `<name>.index.npz` | The embedded passages |
| `<name>.lancedb` | The search table, rebuilt from the `.npz` on every start |
| `<name>.graph.json` | The knowledge graph |
| `<name>.aliases.json` | Names that mean the same thing; edit by hand |
| `<name>.eval.json` | Your eval questions |

## Dutch trainer

A vocabulary trainer: spaced repetition, an AI coach, and pronunciation scoring.

```bash
uv run streamlit run streamlit_app.py
```

There is no server. The app sets up Django inside itself and uses it only for the database,
so Django works as a library here. Run it from the repo root so it finds
`.streamlit/config.toml` and the audio in `data/media`.

| Page | What it does |
|---|---|
| Study | Today's cards. Flip, rate, and see the next interval on each button |
| Speaking | Record yourself saying the word; Gemini scores the pronunciation |
| Assistant | The playground agent, able to search the words you've studied |
| Progress | Reviews over time, upcoming load, and progress per chapter |
| Words | Search and filter the whole deck |
| Manage | Load the sample deck, add words, import from Anki |

**Cards per day** (under *Session*) caps each session, so a 3,000-word deck stays manageable.

### AI features

They need `GOOGLE_API_KEY`; without it they show a note instead. `DUTCH_MODEL` picks the
model.

- **Coach** (Study page): the meaning, an example sentence, a memory trick, and the mistake
  English speakers usually make with the word.
- **Ask** (Study page): ask anything about the current card. It won't give away the
  translation, since you're trying to remember it.
- **Speaking**: a score, what it heard, and what to fix, with attention to the sounds English
  speakers find hard (`g`/`ch`, `ui`, `eu`, `ij`/`ei`, the dropped final `n`).
- **Assistant**: the same agent as `uv run gezellig-ai`, plus two tools that read your deck:
  `search_my_vocabulary(query)` and `my_vocabulary_summary()`. It looks words up per
  question instead of getting the whole deck in its prompt, which would be 60-100k tokens
  every message. "Studied" means the word appears in your review history, so words you
  rated *Again* still count.

### Where things live

```
streamlit_app.py             page navigation
src/dutch_learning/
    data.py                  everything the pages read and write
    ai.py                    the AI agents and their output formats
    shared.py                cached agents and session helpers
    django_bootstrap.py      sets up Django inside the app
    app_pages/               one file per page
django/
    backend/                 settings, admin
    vocabulary/              models, scheduling (srs.py), reads (selectors.py), writes (services.py)
```

The pages hold no logic of their own; scheduling and queries live in `django/vocabulary/`.

### Database

SQLite by default (`django/db.sqlite3`). To use hosted Postgres, set `DATABASE_URL` in
`django/.env`. [Neon](https://neon.com) works well: its free tier doesn't pause idle projects.

1. Create a project at [console.neon.tech](https://console.neon.tech).
2. Copy the connection string from **Connect**, including the
   `?sslmode=require&channel_binding=require` part.
3. Put it in `django/.env` and create the tables:

```bash
cd django
uv run --project .. python manage.py migrate
```

To move an existing deck over, export it while still on SQLite, then load it into Postgres:

```bash
uv run --project .. python manage.py dumpdata vocabulary --indent 2 -o ../data/deck.json
uv run --project .. python manage.py loaddata ../data/deck.json
```

A remote database feels slower than SQLite. Tests always use SQLite.

### Importing words

```bash
cd django
uv run --project .. python manage.py import_anki /path/to/deck.apkg
uv run --project .. python manage.py import_legacy ../data/dutch_learning.db
```

Anki audio goes to `data/media` and is what the Speaking page plays as the native example.

### Admin

For bulk edits and checking schedules. This is the only time you run a server:

```bash
cd django
uv run --project .. python manage.py createsuperuser   # once
uv run --project .. python manage.py runserver         # http://127.0.0.1:8000/admin/
```

## Development

```bash
./init.sh                         # everything CI runs: sync, lint, format check, types, tests
uv run pytest
uv run ruff check . && uv run ruff format .
uv run pyright
uv run pre-commit install         # once per clone
```

The pre-commit hooks run ruff, catch the usual mistakes (whitespace, merge conflicts, large
files, private keys) and check that `uv.lock` matches `pyproject.toml`. They only see files
git knows about, so stage a new file before running them on it.

`main` only takes pull requests that pass CI.
