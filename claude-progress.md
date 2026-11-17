# Progress Log

Repository-local session log for any coding agent. Read it at session start and update it
before handoff (see `AGENTS.md`).

## Current Verified State

- Repository root: `gezellig-ai/`
- Standard startup path: `uv run streamlit run streamlit_app.py` (or `RUN_START_COMMAND=1 ./init.sh`)
- Standard verification path: `./init.sh` (uv sync, ruff check, ruff format --check, pyright, pytest)
- Current highest-priority unfinished feature: none recorded; next idea is a RAG eval set (see session 004)
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

### Session 002 (continued): learning notes

- Added `docs/ai-learning-checklist.md` (moved from a Google Doc, with added points marked)
  and `docs/ai-engineering-wiki.md` (notes on RAG, embeddings, tool calling, RAG vs
  fine-tuning, and the model timing comparison). Docs only, no code change.
- Local-only: `.env` now sets `PLAYGROUND_MODEL=gemma4:e4b`.

### Session 002 (continued): LanceDB

- Goal: put the RAG vectors in a vector database, keeping numpy as a fallback (`rag-002`).
- Completed: `lancedb` dependency; `rag_playground/index.py` builds a LanceDB table from the
  `.npz` cache and searches it; `RAG_STORE=numpy` keeps the old path; startup line names the
  store; README, AGENTS.md, `.env.example` updated.
- Verification run: `./init.sh` exit 0, pytest 110 passed. Both stores return identical
  chunks on the real index (see `rag-002` evidence).
- Local-only state: `data/rag/*.lancedb` folder (git-ignored); `.env` sets
  `PLAYGROUND_MODEL=gemma4:e4b`.
- Both this work and the `docs/` notes are on branch `add-lancedb`, in one pull request.
- Next best step: an eval set of ~10 campaign questions, then hybrid search using LanceDB's
  built-in keyword index.

### Session 003

- Date: 2026-11-11
- Goal: hybrid (keyword + vector) search in the RAG playground (`rag-003`).
- Completed: `lance_table` builds a LanceDB keyword index on `text`; `Index(hybrid=True)` runs
  LanceDB's hybrid query (merged by reciprocal rank fusion); `--hybrid` CLI flag, off by
  default; startup line names the search type. README, AGENTS.md map row and the wiki updated.
- Verification run: `./init.sh` exit 0, pytest 112 passed (2 new).
- Real run: on 14 rare-name questions the name was in the top 5 for 11/14 with vector search
  and 14/14 with hybrid; common questions unchanged (details in `rag-003` evidence).
- Known risk or unresolved issue: the eval set was skipped, so "better" is only measured as
  "the name appears in a retrieved chunk". Hybrid is opt-in until an eval set says otherwise.
- Branch `rag-hybrid-search`, committed locally, not pushed.
- Next best step: the eval set of ~10 questions with known answers, then decide whether
  hybrid becomes the default; after that, reranking.

### Session 003 (continued): reranking notes

- Docs only. `docs/ai-engineering-wiki.md` now explains how hybrid search and reranking work.
- Decision: reranking is skipped for now. Ollama 0.40.16 has no rerank endpoint (404 on
  `/api/rerank` and `/v1/rerank`); the local options and their trade-offs are in the wiki.
- Next best step is unchanged: the eval set, which also tells whether reranking is worth it.

### Session 004

- Date: 2026-11-11
- Goal: a knowledge graph for the RAG playground (`rag-004`).
- Completed: `rag_playground/graph.py` (extraction agent, resumable build, JSON cache, lookup
  by name); `campaign_relations` tool and `graph=` argument on `rag.agentic`; `--graph` CLI
  flag (needs `--agentic`); `RAG_GRAPH_MODEL` setting; `doc_path` helper in `index.py`.
  README, AGENTS.md, `.env.example`, wiki section "Knowledge graphs", checklist updated.
- Verification run: `./init.sh` exit 0, pytest 118 passed (6 new).
- Real run: graph built in 118 min with `qwen3.6:35b-a3b` (1,251 relations, 23 chunks
  skipped); the model called `campaign_relations` on connection questions with both
  `gemma4:e4b` and `qwen3.6:35b-a3b` (details in `rag-004` evidence).
- Local-only state (git-ignored): `data/rag/setting-the-darkness-ablaze.graph.json`. A fresh
  clone, a changed document or a changed `RAG_GRAPH_MODEL` means a two-hour rebuild.
- Known risk or unresolved issue: aliases are not merged, some extracted relations are
  wrong, skipped chunks are not retried, and nothing was fact-checked by a human.
- Branch `rag-knowledge-graph`, stacked on `rag-hybrid-search`; committed locally, not pushed.
- Next best step: the eval set, including two or three connection questions, to measure
  whether hybrid search and the graph improve answers.

### Session 005

- Date: 2026-11-11
- Goal: fix the two graph problems found in Session 004: one character under several names,
  and wrong relations (`rag-005`).
- Completed (code): the extractor returns the sentence that states each relation; `stated`
  drops a relation when that sentence or a name is not in the chunk, when an end has no
  capital letter, or when it names the narrator in text with no first person. The cache key
  includes the prompt. `draft_aliases` / `load_aliases` write `data/rag/<name>.aliases.json`
  once (model draft, then hand-edited, never overwritten); `Graph.about` follows the groups
  and `campaign_relations` shows the quote and the alias names.
- Verification run: `./init.sh` exit 0, pytest 121 passed (3 new).
- NOT DONE: the real rebuild, so `rag-005` is `in_progress`. It was started, stopped at 13 of
  657 chunks, and put on hold at the user's request. Until it runs, `--graph` starts the
  two-hour build on first use. The old graph is kept as `…graph-v1.json` (git-ignored).
- Measured so far (details in `rag-005` evidence): in a sample of 49 old relations, 18 were
  clearly stated relations between named things and 23 were junk or wrong.
- Known risk: the checks do not judge meaning, so a relation with a real but unrelated quote
  still passes. The alias draft makes mistakes ("Rayl" grouped with Cevan) and needs review.
- Next best step: run the rebuild (`uv run rag-playground --agentic --graph`), review the
  alias file, judge a sample of 50 new relations, then update the wiki with the numbers.

### Session 006

- Date: 2026-11-17
- Goal: a grep tool for agentic RAG (`rag-006`), next to vector and hybrid search.
- Completed: `grep_tool` in `rag.py` (case-insensitive regex per paragraph, 200-character
  snippets, max 30 hits), `--grep` flag (needs `--agentic`), 4 tests, README/AGENTS rows.
- Verification run: `./init.sh` exit 0, pytest 125 passed. Real-document check and one real
  question recorded under `rag-006` in `feature_list.json`.
- Known risk or unresolved issue: grep not yet compared with hybrid on the 14 name questions.
  `rag-005` graph rebuild still on hold (user's choice, too slow for now).
- Then (plan approved by the user: eval, reranker, MCP, context-engineering write-up):
  `rag-007` retrieval eval, `uv run rag-eval`, 16 questions in git-ignored
  `data/rag/<name>.eval.json`. vector 15/16, hybrid 16/16, grep 15/16 (numbers under
  `rag-007`). Checklist and wiki "Next experiments" updated.
- Next best step: user reviews the eval questions and adds harder ones (multi-chapter,
  paraphrased); then `rag-008`, a reranker behind `--rerank`, kept only if the eval improves.
