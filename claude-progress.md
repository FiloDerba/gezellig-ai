# Progress Log

Repository-local session log for any coding agent. Read it at session start and update it
before handoff (see `AGENTS.md`).

## Current Verified State

- Repository root: `gezellig-ai/`
- Standard startup path: `uv run streamlit run streamlit_app.py` (or `RUN_START_COMMAND=1 ./init.sh`)
- Standard verification path: `./init.sh` (uv sync, ruff check, ruff format --check, pyright, pytest)
- Current highest-priority unfinished feature: none recorded; next idea is a RAG eval set + hybrid search (see session 002)
- Current blocker: none (`./init.sh` passes)

## Session Log

### Session 001

- Date: 2026-11-07
- Goal: Add the minimal agent harness (AGENTS.md workflow, init.sh, progress log, feature list).
- Completed: Added startup/working rules/definition of done/end-of-session sections to
  `AGENTS.md`; added `init.sh`, `claude-progress.md`, `feature_list.json`.
- Also fixed the pre-existing baseline failures (`baseline-001`): ruff import order, and pyright,
  which had been failing (django/ not on its path, no Django stubs, two type errors).
- Verification run: `./init.sh` (exit 0).
- Evidence captured: see `baseline-001` in `feature_list.json`.
- Commits: harness + baseline fix.
- Files or artifacts updated: harness files, `pyproject.toml`, `uv.lock` (django-types),
  `django/vocabulary/models.py`, `speaking.py`, `shared.py`, `tests/test_agent.py`.
- Known risk or unresolved issue: none known.
- Next best step: add the real backlog to `feature_list.json`.

### Session 002

- Date: 2026-11-10
- Goal: Add a RAG sandbox over the D&D campaign summary (`rag-001`), two-step and agentic,
  with pydantic-ai on local Ollama.
- Completed: `src/rag_playground/` (`loader.py`, `index.py`, `rag.py`, CLI in `__init__.py`),
  `tests/rag_playground/test_rag.py`, registration in `pyproject.toml` (+ explicit `numpy`),
  `.env.example`, `AGENTS.md` map row, `README.md` section.
- Verification run: `./init.sh` exit 0. ruff clean; 54 files formatted; pyright 0 errors;
  pytest 107 passed (6 new).
- Real run: `ollama pull bge-m3`; 657 chunks embedded in about a minute; both
  `uv run rag-playground` and `--agentic` answered and cited the expected chapters
  (details in `rag-001` evidence).
- Local-only state (git-ignored): `data/rag/setting-the-darkness-ablaze.docx` and its
  `.index.npz` cache. A fresh clone needs the document put back there.
- Known risk or unresolved issue: answers were not fact-checked by someone who knows the
  campaign. Agentic mode still has the playground's web search tool available.
- Next best step: write 10 questions with known answers as an eval set, then try hybrid
  (keyword + vector) search and compare.

### Session 002 (continued): PR flow and CI

- Goal: require pull requests into `main` and check them automatically (`ci-001`).
- Completed: GitHub ruleset `protect-main` (pull request required, no force push, no delete);
  `uv run pre-commit install` on this machine; `.github/workflows/ci.yml` running `./init.sh`;
  AGENTS.md now says to commit on a branch.
- Known risk: the pre-commit hook is per clone and has to be installed again after a fresh clone.
