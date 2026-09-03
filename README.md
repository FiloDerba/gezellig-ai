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

## Dev

```bash
uv run pytest
uv run ruff check .
uv run pyright
```
