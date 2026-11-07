# Progress Log

Repository-local session log for any coding agent. Read it at session start and update it
before handoff (see `AGENTS.md`).

## Current Verified State

- Repository root: `gezellig-ai/`
- Standard startup path: `uv run streamlit run streamlit_app.py` (or `RUN_START_COMMAND=1 ./init.sh`)
- Standard verification path: `./init.sh` (uv sync, ruff check, ruff format --check, pyright, pytest)
- Current highest-priority unfinished feature: none recorded; add the backlog to `feature_list.json`
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
