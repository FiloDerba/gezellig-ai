# Dutch Learning App — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Streamlit flashcard app that imports a Dutch Anki deck, runs SM-2 spaced repetition, and provides AI-powered hints via pydantic-ai.

**Architecture:** One-time CLI import converts `.apkg` → SQLite + media files. Streamlit app reads that DB, runs SM-2 on each card rating, and calls pydantic-ai (Claude or Gemini) for on-demand hints. Three pages (Study, Browse, Stats) via sidebar radio button stored in `st.session_state`.

**Tech Stack:** Python 3.14, Streamlit, SQLite (stdlib), pydantic-ai, uv

## Global Constraints

- Python ≥ 3.14 (enforced by `.python-version`)
- All commands run with `uv run` prefix (never bare `python`)
- DB path: `data/dutch_learning.db` (relative to project root, gitignored)
- Media path: `data/media/` (gitignored)
- Anki `.apkg` field layout: `flds[0]=dutch`, `flds[4]=english`, `flds[7]=word_type`, `flds[9]=[sound:file.mp3]`
- SM-2 rating scale: Again=0, Hard=1, Good=3, Easy=5
- No user accounts, no multi-user, no export back to Anki

---

## File Map

| Path | Responsibility |
|---|---|
| `src/dutch_learning/__init__.py` | Empty package marker |
| `src/dutch_learning/srs.py` | SM-2 algorithm — pure functions, no I/O |
| `src/dutch_learning/db.py` | SQLite schema + all queries |
| `src/dutch_learning/importer.py` | `.apkg` → SQLite + media extraction CLI |
| `src/dutch_learning/ai.py` | AI hint client (pydantic-ai) |
| `src/dutch_learning/app.py` | Streamlit entry point, sidebar nav |
| `src/dutch_learning/pages/study.py` | Study page UI + card flow logic |
| `src/dutch_learning/pages/browse.py` | Browse page (searchable word table) |
| `src/dutch_learning/pages/stats.py` | Stats page |
| `tests/dutch_learning/test_srs.py` | SM-2 unit tests |
| `tests/dutch_learning/test_db.py` | DB layer tests (in-memory SQLite) |
| `tests/dutch_learning/test_importer.py` | Importer integration test |
| `data/dutch_learning.db` | SQLite DB (gitignored — created at import time) |
| `data/media/` | Audio files (gitignored) |

---

### Task 1: Project Scaffold + Dependencies

**Files:**
- Modify: `pyproject.toml`
- Create: `src/dutch_learning/__init__.py`
- Create: `src/dutch_learning/pages/__init__.py`
- Create: `tests/dutch_learning/__init__.py`

**Interfaces:**
- Produces: `uv run streamlit run src/dutch_learning/app.py` as the launch command
- Produces: `uv run python -m dutch_learning.importer` as the import CLI

- [ ] **Step 1: Add dependencies to pyproject.toml**

Open `pyproject.toml` and add to the `dependencies` list:
```toml
[project]
dependencies = [
    "logfire>=4.40.0",
    "pydantic-ai-slim[anthropic,google,openai]>=2.32.1",
    "python-dotenv>=1.2.3",
    "streamlit>=1.40.0",
    "tavily-python>=0.7.27",
]

[project.scripts]
ai-playground = "ai_playground:main"
dutch-learning = "dutch_learning.importer:main"
```

- [ ] **Step 2: Install dependencies**

```bash
uv sync
```

Expected: resolves without error, `streamlit` now in `.venv`.

- [ ] **Step 3: Create package init files**

Create `src/dutch_learning/__init__.py` — empty file.
Create `src/dutch_learning/pages/__init__.py` — empty file.
Create `tests/dutch_learning/__init__.py` — empty file.

- [ ] **Step 4: Add data/ to .gitignore**

Open `.gitignore` and add at the end:
```
data/
```

- [ ] **Step 5: Verify streamlit is importable**

```bash
uv run python -c "import streamlit; print(streamlit.__version__)"
```

Expected: prints a version number (≥1.40.0).

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock src/dutch_learning/ tests/dutch_learning/ .gitignore
git commit -m "feat: scaffold dutch_learning package with streamlit dependency"
```

---

### Task 2: SM-2 Algorithm

**Files:**
- Create: `src/dutch_learning/srs.py`
- Create: `tests/dutch_learning/test_srs.py`

**Interfaces:**
- Produces:
  ```python
  from dataclasses import dataclass
  from datetime import date

  @dataclass
  class SRSState:
      word_id: int
      interval: int        # days until next review
      ease_factor: float   # starts at 2.5
      due_date: date
      reps: int            # total successful reviews

  def update_sm2(state: SRSState, quality: int) -> SRSState:
      """quality: 0=Again, 1=Hard, 3=Good, 5=Easy. Returns new state."""
  
  def new_state(word_id: int) -> SRSState:
      """Create a fresh SRS state for a new word (due today)."""
  ```

- [ ] **Step 1: Write the failing tests**

Create `tests/dutch_learning/test_srs.py`:
```python
from datetime import date, timedelta
from dutch_learning.srs import SRSState, update_sm2, new_state


def _state(interval=1, ease_factor=2.5, reps=0, due=None):
    return SRSState(
        word_id=1,
        interval=interval,
        ease_factor=ease_factor,
        due_date=due or date.today(),
        reps=reps,
    )


def test_new_state_due_today():
    s = new_state(word_id=42)
    assert s.word_id == 42
    assert s.due_date == date.today()
    assert s.interval == 1
    assert s.ease_factor == 2.5
    assert s.reps == 0


def test_again_resets_reps_and_short_interval():
    s = _state(interval=10, ease_factor=2.5, reps=5)
    new = update_sm2(s, quality=0)
    assert new.reps == 0
    assert new.interval == 1
    assert new.due_date == date.today() + timedelta(days=1)


def test_hard_resets_reps():
    s = _state(interval=10, ease_factor=2.5, reps=5)
    new = update_sm2(s, quality=1)
    assert new.reps == 0
    assert new.interval == 1


def test_good_first_rep_gives_interval_1():
    s = _state(reps=0)
    new = update_sm2(s, quality=3)
    assert new.interval == 1
    assert new.reps == 1


def test_good_second_rep_gives_interval_6():
    s = _state(reps=1, interval=1)
    new = update_sm2(s, quality=3)
    assert new.interval == 6
    assert new.reps == 2


def test_good_third_rep_multiplies_by_ease():
    s = _state(reps=2, interval=6, ease_factor=2.5)
    new = update_sm2(s, quality=3)
    assert new.interval == round(6 * 2.5)
    assert new.reps == 3


def test_easy_increases_ease_factor():
    s = _state(reps=2, interval=6, ease_factor=2.5)
    new = update_sm2(s, quality=5)
    assert new.ease_factor > s.ease_factor


def test_again_decreases_ease_factor():
    s = _state(ease_factor=2.5)
    new = update_sm2(s, quality=0)
    assert new.ease_factor < s.ease_factor


def test_ease_factor_floor_is_1_3():
    s = _state(ease_factor=1.3)
    new = update_sm2(s, quality=0)
    assert new.ease_factor >= 1.3


def test_due_date_set_correctly_after_good():
    s = _state(reps=2, interval=6, ease_factor=2.5)
    new = update_sm2(s, quality=3)
    assert new.due_date == date.today() + timedelta(days=new.interval)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/dutch_learning/test_srs.py -v
```

Expected: `ModuleNotFoundError: No module named 'dutch_learning'` or similar — confirms tests exist and run.

- [ ] **Step 3: Implement srs.py**

Create `src/dutch_learning/srs.py`:
```python
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass
class SRSState:
    word_id: int
    interval: int
    ease_factor: float
    due_date: date
    reps: int


def new_state(word_id: int) -> SRSState:
    return SRSState(
        word_id=word_id,
        interval=1,
        ease_factor=2.5,
        due_date=date.today(),
        reps=0,
    )


def update_sm2(state: SRSState, quality: int) -> SRSState:
    ease = state.ease_factor + 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)
    ease = max(1.3, ease)

    if quality < 3:
        reps = 0
        interval = 1
    else:
        reps = state.reps + 1
        if state.reps == 0:
            interval = 1
        elif state.reps == 1:
            interval = 6
        else:
            interval = round(state.interval * state.ease_factor)

    return SRSState(
        word_id=state.word_id,
        interval=interval,
        ease_factor=ease,
        due_date=date.today() + timedelta(days=interval),
        reps=reps,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/dutch_learning/test_srs.py -v
```

Expected: all 10 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dutch_learning/srs.py tests/dutch_learning/test_srs.py
git commit -m "feat: implement SM-2 spaced repetition algorithm"
```

---

### Task 3: Database Layer

**Files:**
- Create: `src/dutch_learning/db.py`
- Create: `tests/dutch_learning/test_db.py`

**Interfaces:**
- Consumes: `SRSState` from `dutch_learning.srs`
- Produces:
  ```python
  import sqlite3
  from dataclasses import dataclass
  from datetime import date
  from pathlib import Path

  @dataclass
  class Word:
      id: int
      dutch: str
      english: str
      word_type: str
      audio_file: str | None
      tags: str
      chapter: str

  DB_PATH: Path  # = Path("data/dutch_learning.db")

  def get_conn(path: Path = DB_PATH) -> sqlite3.Connection: ...
  def init_db(conn: sqlite3.Connection) -> None: ...
  def upsert_word(conn: sqlite3.Connection, word: Word) -> None: ...
  def upsert_srs_state(conn: sqlite3.Connection, state: SRSState) -> None: ...
  def get_due_cards(conn: sqlite3.Connection, today: date) -> list[tuple[Word, SRSState]]: ...
  def get_all_words(conn: sqlite3.Connection, chapter: str | None = None, search: str | None = None) -> list[tuple[Word, SRSState]]: ...
  def get_chapters(conn: sqlite3.Connection) -> list[str]: ...
  def get_stats(conn: sqlite3.Connection, today: date) -> dict: ...
  def update_srs_state(conn: sqlite3.Connection, state: SRSState) -> None: ...
  ```

- [ ] **Step 1: Write the failing tests**

Create `tests/dutch_learning/test_db.py`:
```python
import sqlite3
from datetime import date, timedelta
from dutch_learning.db import (
    Word, init_db, upsert_word, upsert_srs_state,
    get_due_cards, get_all_words, get_chapters, get_stats, update_srs_state,
)
from dutch_learning.srs import SRSState


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _word(id=1, dutch="lezen", english="to read", word_type="V",
          audio_file="test.mp3", tags="Dutch::DeOpmaat::Thema01a", chapter="Thema01a"):
    return Word(id=id, dutch=dutch, english=english, word_type=word_type,
                audio_file=audio_file, tags=tags, chapter=chapter)


def _state(word_id=1, interval=1, ease_factor=2.5, due_date=None, reps=0):
    return SRSState(word_id=word_id, interval=interval, ease_factor=ease_factor,
                    due_date=due_date or date.today(), reps=reps)


def test_init_db_creates_tables():
    conn = _conn()
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {r[0] for r in c.fetchall()}
    assert "words" in tables
    assert "srs_state" in tables


def test_upsert_word_inserts_and_is_idempotent():
    conn = _conn()
    w = _word()
    upsert_word(conn, w)
    upsert_word(conn, w)  # idempotent
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM words")
    assert c.fetchone()[0] == 1


def test_upsert_srs_state():
    conn = _conn()
    upsert_word(conn, _word())
    s = _state()
    upsert_srs_state(conn, s)
    c = conn.cursor()
    c.execute("SELECT interval FROM srs_state WHERE word_id=1")
    assert c.fetchone()[0] == 1


def test_get_due_cards_returns_overdue():
    conn = _conn()
    upsert_word(conn, _word())
    upsert_srs_state(conn, _state(due_date=date.today()))
    due = get_due_cards(conn, date.today())
    assert len(due) == 1
    word, state = due[0]
    assert word.dutch == "lezen"


def test_get_due_cards_excludes_future():
    conn = _conn()
    upsert_word(conn, _word())
    upsert_srs_state(conn, _state(due_date=date.today() + timedelta(days=5)))
    assert get_due_cards(conn, date.today()) == []


def test_get_all_words_no_filter():
    conn = _conn()
    upsert_word(conn, _word(id=1, chapter="Thema01a"))
    upsert_word(conn, _word(id=2, dutch="schrijven", english="to write", chapter="Thema02"))
    upsert_srs_state(conn, _state(word_id=1))
    upsert_srs_state(conn, _state(word_id=2))
    assert len(get_all_words(conn)) == 2


def test_get_all_words_chapter_filter():
    conn = _conn()
    upsert_word(conn, _word(id=1, chapter="Thema01a"))
    upsert_word(conn, _word(id=2, dutch="schrijven", english="to write", chapter="Thema02"))
    upsert_srs_state(conn, _state(word_id=1))
    upsert_srs_state(conn, _state(word_id=2))
    result = get_all_words(conn, chapter="Thema01a")
    assert len(result) == 1
    assert result[0][0].chapter == "Thema01a"


def test_get_chapters():
    conn = _conn()
    upsert_word(conn, _word(id=1, chapter="Thema01a"))
    upsert_word(conn, _word(id=2, dutch="schrijven", english="to write", chapter="Thema02"))
    upsert_srs_state(conn, _state(word_id=1))
    upsert_srs_state(conn, _state(word_id=2))
    chapters = get_chapters(conn)
    assert set(chapters) == {"Thema01a", "Thema02"}


def test_get_stats():
    conn = _conn()
    upsert_word(conn, _word())
    upsert_srs_state(conn, _state(due_date=date.today(), reps=3))
    stats = get_stats(conn, date.today())
    assert stats["due_today"] == 1
    assert stats["total_words"] == 1


def test_update_srs_state():
    conn = _conn()
    upsert_word(conn, _word())
    upsert_srs_state(conn, _state(interval=1))
    new = _state(interval=6, ease_factor=2.6, reps=1)
    update_srs_state(conn, new)
    c = conn.cursor()
    c.execute("SELECT interval, ease_factor, reps FROM srs_state WHERE word_id=1")
    row = c.fetchone()
    assert row[0] == 6
    assert abs(row[1] - 2.6) < 0.001
    assert row[2] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/dutch_learning/test_db.py -v
```

Expected: `ModuleNotFoundError: No module named 'dutch_learning.db'`

- [ ] **Step 3: Implement db.py**

Create `src/dutch_learning/db.py`:
```python
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from dutch_learning.srs import SRSState

DB_PATH = Path("data/dutch_learning.db")


@dataclass
class Word:
    id: int
    dutch: str
    english: str
    word_type: str
    audio_file: str | None
    tags: str
    chapter: str


def get_conn(path: Path = DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS words (
            id          INTEGER PRIMARY KEY,
            dutch       TEXT NOT NULL,
            english     TEXT NOT NULL,
            word_type   TEXT,
            audio_file  TEXT,
            tags        TEXT,
            chapter     TEXT
        );
        CREATE TABLE IF NOT EXISTS srs_state (
            word_id      INTEGER PRIMARY KEY REFERENCES words(id),
            interval     INTEGER NOT NULL DEFAULT 1,
            ease_factor  REAL    NOT NULL DEFAULT 2.5,
            due_date     TEXT    NOT NULL,
            reps         INTEGER NOT NULL DEFAULT 0
        );
    """)
    conn.commit()


def upsert_word(conn: sqlite3.Connection, word: Word) -> None:
    conn.execute(
        """INSERT OR IGNORE INTO words (id, dutch, english, word_type, audio_file, tags, chapter)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (word.id, word.dutch, word.english, word.word_type,
         word.audio_file, word.tags, word.chapter),
    )
    conn.commit()


def upsert_srs_state(conn: sqlite3.Connection, state: SRSState) -> None:
    conn.execute(
        """INSERT OR IGNORE INTO srs_state (word_id, interval, ease_factor, due_date, reps)
           VALUES (?, ?, ?, ?, ?)""",
        (state.word_id, state.interval, state.ease_factor,
         state.due_date.isoformat(), state.reps),
    )
    conn.commit()


def update_srs_state(conn: sqlite3.Connection, state: SRSState) -> None:
    conn.execute(
        """UPDATE srs_state SET interval=?, ease_factor=?, due_date=?, reps=?
           WHERE word_id=?""",
        (state.interval, state.ease_factor, state.due_date.isoformat(),
         state.reps, state.word_id),
    )
    conn.commit()


def _row_to_word(row: sqlite3.Row) -> Word:
    return Word(
        id=row["id"],
        dutch=row["dutch"],
        english=row["english"],
        word_type=row["word_type"],
        audio_file=row["audio_file"],
        tags=row["tags"],
        chapter=row["chapter"],
    )


def _row_to_state(row: sqlite3.Row) -> SRSState:
    return SRSState(
        word_id=row["word_id"],
        interval=row["interval"],
        ease_factor=row["ease_factor"],
        due_date=date.fromisoformat(row["due_date"]),
        reps=row["reps"],
    )


def get_due_cards(conn: sqlite3.Connection, today: date) -> list[tuple[Word, SRSState]]:
    rows = conn.execute(
        """SELECT w.*, s.word_id, s.interval, s.ease_factor, s.due_date, s.reps
           FROM words w JOIN srs_state s ON w.id = s.word_id
           WHERE s.due_date <= ?
           ORDER BY s.due_date""",
        (today.isoformat(),),
    ).fetchall()
    return [(_row_to_word(r), _row_to_state(r)) for r in rows]


def get_all_words(
    conn: sqlite3.Connection,
    chapter: str | None = None,
    search: str | None = None,
) -> list[tuple[Word, SRSState]]:
    query = """SELECT w.*, s.word_id, s.interval, s.ease_factor, s.due_date, s.reps
               FROM words w JOIN srs_state s ON w.id = s.word_id"""
    params: list = []
    conditions = []
    if chapter:
        conditions.append("w.chapter = ?")
        params.append(chapter)
    if search:
        conditions.append("(w.dutch LIKE ? OR w.english LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY w.dutch"
    rows = conn.execute(query, params).fetchall()
    return [(_row_to_word(r), _row_to_state(r)) for r in rows]


def get_chapters(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT DISTINCT chapter FROM words ORDER BY chapter"
    ).fetchall()
    return [r["chapter"] for r in rows]


def get_stats(conn: sqlite3.Connection, today: date) -> dict:
    due_today = conn.execute(
        "SELECT COUNT(*) FROM srs_state WHERE due_date <= ?",
        (today.isoformat(),),
    ).fetchone()[0]
    total_words = conn.execute("SELECT COUNT(*) FROM words").fetchone()[0]
    total_reviews = conn.execute("SELECT SUM(reps) FROM srs_state").fetchone()[0] or 0
    chapter_rows = conn.execute(
        """SELECT w.chapter, COUNT(*) as count, SUM(s.reps) as reviews
           FROM words w JOIN srs_state s ON w.id = s.word_id
           GROUP BY w.chapter ORDER BY w.chapter"""
    ).fetchall()
    return {
        "due_today": due_today,
        "total_words": total_words,
        "total_reviews": total_reviews,
        "by_chapter": [
            {"chapter": r["chapter"], "count": r["count"], "reviews": r["reviews"] or 0}
            for r in chapter_rows
        ],
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/dutch_learning/test_db.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dutch_learning/db.py tests/dutch_learning/test_db.py
git commit -m "feat: add SQLite database layer for words and SRS state"
```

---

### Task 4: Anki Importer

**Files:**
- Create: `src/dutch_learning/importer.py`
- Create: `tests/dutch_learning/test_importer.py`

**Interfaces:**
- Consumes: `Word`, `get_conn`, `init_db`, `upsert_word`, `upsert_srs_state`, `new_state` from previous tasks
- Produces:
  ```python
  def import_deck(apkg_path: str, db_path: Path = DB_PATH, media_dir: Path = MEDIA_DIR) -> int:
      """Import .apkg into SQLite + extract audio. Returns count of words imported."""

  def main() -> None:
      """CLI entry point: python -m dutch_learning.importer /path/to/deck.apkg"""
  ```

- [ ] **Step 1: Write the failing test**

Create `tests/dutch_learning/test_importer.py`:
```python
import io
import json
import sqlite3
import zipfile
from pathlib import Path
import pytest
from dutch_learning.db import get_conn, init_db, get_all_words
from dutch_learning.importer import import_deck


def _make_apkg(tmp_path: Path) -> Path:
    """Build a minimal .apkg with 2 notes."""
    db_path = tmp_path / "collection.anki2"
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE notes (
            id INTEGER PRIMARY KEY,
            guid TEXT,
            mid INTEGER,
            mod INTEGER,
            usn INTEGER,
            tags TEXT,
            flds TEXT,
            sfld TEXT,
            csum INTEGER,
            flags INTEGER,
            data TEXT
        );
    """)
    # field layout: flds[0]=dutch \x1f[1]\x1f[2]\x1f[3]\x1f[4]=english \x1f[5]\x1f[6]\x1f[7]=type \x1f[8]\x1f[9]=audio
    notes = [
        (1, "guid1", 1, 0, 0, " Dutch::DeOpmaat::Thema01a ",
         "lezen\x1f\x1f\x1f\x1fto read\x1f\x1f\x1fV\x1f\x1f[sound:test.mp3]",
         "lezen", 0, 0, ""),
        (2, "guid2", 1, 0, 0, " Dutch::DeOpmaat::Thema02 ",
         "schrijven\x1f\x1f\x1f\x1fto write\x1f\x1f\x1fV\x1f\x1f[sound:test2.mp3]",
         "schrijven", 0, 0, ""),
    ]
    conn.executemany(
        "INSERT INTO notes VALUES (?,?,?,?,?,?,?,?,?,?,?)", notes
    )
    conn.commit()
    conn.close()

    apkg_path = tmp_path / "test.apkg"
    media_manifest = {"0": "test.mp3", "1": "test2.mp3"}
    with zipfile.ZipFile(apkg_path, "w") as z:
        z.write(db_path, "collection.anki2")
        z.writestr("media", json.dumps(media_manifest))
        z.writestr("0", b"fake_audio_data_1")
        z.writestr("1", b"fake_audio_data_2")

    return apkg_path


def test_import_deck_imports_words(tmp_path):
    apkg = _make_apkg(tmp_path)
    out_db = tmp_path / "test.db"
    media_dir = tmp_path / "media"

    count = import_deck(str(apkg), db_path=out_db, media_dir=media_dir)

    assert count == 2
    conn = get_conn(out_db)
    words = get_all_words(conn)
    dutches = {w.dutch for w, _ in words}
    assert dutches == {"lezen", "schrijven"}


def test_import_deck_extracts_media(tmp_path):
    apkg = _make_apkg(tmp_path)
    out_db = tmp_path / "test.db"
    media_dir = tmp_path / "media"

    import_deck(str(apkg), db_path=out_db, media_dir=media_dir)

    assert (media_dir / "test.mp3").exists()
    assert (media_dir / "test2.mp3").exists()


def test_import_deck_sets_chapter(tmp_path):
    apkg = _make_apkg(tmp_path)
    out_db = tmp_path / "test.db"
    media_dir = tmp_path / "media"

    import_deck(str(apkg), db_path=out_db, media_dir=media_dir)

    conn = get_conn(out_db)
    words = get_all_words(conn)
    chapters = {w.chapter for w, _ in words}
    assert chapters == {"Thema01a", "Thema02"}


def test_import_deck_is_idempotent(tmp_path):
    apkg = _make_apkg(tmp_path)
    out_db = tmp_path / "test.db"
    media_dir = tmp_path / "media"

    import_deck(str(apkg), db_path=out_db, media_dir=media_dir)
    count2 = import_deck(str(apkg), db_path=out_db, media_dir=media_dir)

    conn = get_conn(out_db)
    assert len(get_all_words(conn)) == 2  # no duplicates
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/dutch_learning/test_importer.py -v
```

Expected: `ModuleNotFoundError: No module named 'dutch_learning.importer'`

- [ ] **Step 3: Implement importer.py**

Create `src/dutch_learning/importer.py`:
```python
import json
import re
import sqlite3
import sys
import zipfile
from pathlib import Path

from dutch_learning.db import DB_PATH, Word, get_conn, init_db, upsert_srs_state, upsert_word
from dutch_learning.srs import new_state

MEDIA_DIR = Path("data/media")


def _parse_audio(field: str) -> str | None:
    m = re.match(r"\[sound:(.+?)\]", field)
    return m.group(1) if m else None


def _extract_chapter(tags: str) -> str:
    for tag in tags.strip().split():
        parts = tag.split("::")
        if len(parts) >= 2:
            return parts[-1]
    return "Unknown"


def import_deck(
    apkg_path: str,
    db_path: Path = DB_PATH,
    media_dir: Path = MEDIA_DIR,
) -> int:
    media_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(apkg_path) as zf:
        # Build media filename map: numbered_file → actual_filename
        media_map: dict[str, str] = {}
        if "media" in zf.namelist():
            media_map = json.loads(zf.read("media").decode())

        # Extract audio files
        for numbered, filename in media_map.items():
            if numbered in zf.namelist():
                data = zf.read(numbered)
                (media_dir / filename).write_bytes(data)

        # Read notes from embedded SQLite
        raw_db = zf.read("collection.anki2")

    tmp_db = Path("/tmp/anki_import_collection.anki2")
    tmp_db.write_bytes(raw_db)

    anki_conn = sqlite3.connect(tmp_db)
    anki_conn.row_factory = sqlite3.Row
    notes = anki_conn.execute(
        "SELECT id, tags, flds FROM notes"
    ).fetchall()
    anki_conn.close()

    app_conn = get_conn(db_path)
    init_db(app_conn)

    count = 0
    for note in notes:
        fields = note["flds"].split("\x1f")
        if len(fields) < 10:
            continue
        dutch = fields[0].strip()
        english = fields[4].strip()
        word_type = fields[7].strip()
        audio_file = _parse_audio(fields[9].strip())
        if not dutch or not english:
            continue

        word = Word(
            id=note["id"],
            dutch=dutch,
            english=english,
            word_type=word_type,
            audio_file=audio_file,
            tags=note["tags"].strip(),
            chapter=_extract_chapter(note["tags"]),
        )
        upsert_word(app_conn, word)
        upsert_srs_state(app_conn, new_state(word.id))
        count += 1

    app_conn.close()
    tmp_db.unlink(missing_ok=True)
    return count


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: uv run python -m dutch_learning.importer /path/to/deck.apkg")
        sys.exit(1)
    apkg_path = sys.argv[1]
    print(f"Importing {apkg_path} ...")
    count = import_deck(apkg_path)
    print(f"Done. Imported {count} words.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/dutch_learning/test_importer.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Run the actual import**

```bash
uv run python -m dutch_learning.importer /Users/admin/Downloads/Dutch_courses_De_Opmaat__De_Sprong.apkg
```

Expected: `Done. Imported 2957 words.`

- [ ] **Step 6: Commit**

```bash
git add src/dutch_learning/importer.py tests/dutch_learning/test_importer.py
git commit -m "feat: add Anki .apkg importer with media extraction"
```

---

### Task 5: AI Hints

**Files:**
- Create: `src/dutch_learning/ai.py`

No unit tests — pydantic-ai calls need real API keys; tested manually in Task 9.

**Interfaces:**
- Produces:
  ```python
  from pydantic_ai import Agent

  SYSTEM_PROMPT: str

  def make_hint_agent(model: str = "google-gla:gemini-2.0-flash") -> Agent:
      """Create a pydantic-ai Agent configured as a Dutch tutor."""

  def get_hint(agent: Agent, dutch: str, word_type: str, english: str, question: str) -> str:
      """Run agent synchronously; return text response."""
  ```

- [ ] **Step 1: Create ai.py**

Create `src/dutch_learning/ai.py`:
```python
from pydantic_ai import Agent

SYSTEM_PROMPT = (
    "You are a Dutch language tutor. Answer concisely in English. "
    "Give hints, etymology, mnemonics, or example sentences as requested. "
    "Do not directly give away the translation if the user is still trying to recall it."
)


def make_hint_agent(model: str = "google-gla:gemini-2.0-flash") -> Agent:
    return Agent(model, system_prompt=SYSTEM_PROMPT)


def get_hint(agent: Agent, dutch: str, word_type: str, english: str, question: str) -> str:
    prompt = (
        f"The user is studying the Dutch word '{dutch}' ({word_type}, meaning '{english}'). "
        f"Their question: {question}"
    )
    result = agent.run_sync(prompt)
    return result.output
```

- [ ] **Step 2: Verify import works**

```bash
uv run python -c "from dutch_learning.ai import make_hint_agent; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/dutch_learning/ai.py
git commit -m "feat: add pydantic-ai hint client for Dutch tutor"
```

---

### Task 6: Study Page

**Files:**
- Create: `src/dutch_learning/pages/study.py`

**Interfaces:**
- Consumes: `Word`, `SRSState`, `get_due_cards`, `update_srs_state` from db; `update_sm2` from srs; `get_hint` from ai
- Produces: `def render(conn, agent) -> None` — full Streamlit page

- [ ] **Step 1: Create study.py**

Create `src/dutch_learning/pages/study.py`:
```python
from datetime import date
from pathlib import Path

import streamlit as st

from dutch_learning import ai as ai_mod
from dutch_learning.db import get_due_cards, update_srs_state
from dutch_learning.srs import update_sm2

MEDIA_DIR = Path("data/media")
RATINGS = {"Again": 0, "Hard": 1, "Good": 3, "Easy": 5}


def _load_due(conn):
    """Load due cards into session_state if not already loaded."""
    if "due_cards" not in st.session_state:
        st.session_state.due_cards = get_due_cards(conn, date.today())
        st.session_state.card_idx = 0
        st.session_state.flipped = False


def _current_card(conn):
    _load_due(conn)
    cards = st.session_state.due_cards
    idx = st.session_state.card_idx
    if idx >= len(cards):
        return None, None
    return cards[idx]


def _advance(conn):
    st.session_state.card_idx += 1
    st.session_state.flipped = False
    # Reload if we've gone through all cards
    if st.session_state.card_idx >= len(st.session_state.due_cards):
        del st.session_state["due_cards"]


def render(conn, agent) -> None:
    st.title("Study")
    _load_due(conn)
    total_due = len(st.session_state.due_cards)
    remaining = total_due - st.session_state.card_idx

    if remaining <= 0:
        st.success(f"All {total_due} cards done for today!")
        if st.button("Reset session"):
            del st.session_state["due_cards"]
            st.rerun()
        return

    st.caption(f"{remaining} card(s) remaining today")

    word, srs = _current_card(conn)

    st.markdown(f"## {word.dutch}")
    st.caption(f"{word.word_type} · {word.chapter}")

    audio_path = MEDIA_DIR / word.audio_file if word.audio_file else None
    if audio_path and audio_path.exists():
        st.audio(str(audio_path))

    if not st.session_state.flipped:
        if st.button("Show answer"):
            st.session_state.flipped = True
            st.rerun()
        return

    st.markdown(f"**{word.english}**")

    with st.expander("Ask AI for a hint"):
        question = st.text_input("Your question", key=f"hint_q_{st.session_state.card_idx}")
        if question:
            with st.spinner("Thinking..."):
                hint = ai_mod.get_hint(agent, word.dutch, word.word_type, word.english, question)
            st.markdown(hint)

    st.write("---")
    cols = st.columns(4)
    for col, (label, quality) in zip(cols, RATINGS.items()):
        if col.button(label, use_container_width=True):
            new_state = update_sm2(srs, quality)
            update_srs_state(conn, new_state)
            _advance(conn)
            st.rerun()
```

- [ ] **Step 2: Commit**

```bash
git add src/dutch_learning/pages/study.py
git commit -m "feat: add Study page with SM-2 card flow and AI hints"
```

---

### Task 7: Browse Page

**Files:**
- Create: `src/dutch_learning/pages/browse.py`

**Interfaces:**
- Consumes: `get_all_words`, `get_chapters` from db
- Produces: `def render(conn) -> None`

- [ ] **Step 1: Create browse.py**

Create `src/dutch_learning/pages/browse.py`:
```python
import streamlit as st

from dutch_learning.db import get_all_words, get_chapters


def render(conn) -> None:
    st.title("Browse")

    chapters = ["All"] + get_chapters(conn)
    chapter_filter = st.selectbox("Chapter", chapters)
    search = st.text_input("Search (Dutch or English)")

    chapter = None if chapter_filter == "All" else chapter_filter
    search_str = search.strip() or None

    rows = get_all_words(conn, chapter=chapter, search=search_str)

    st.caption(f"{len(rows)} word(s)")

    if not rows:
        st.info("No words match the filter.")
        return

    table_data = [
        {
            "Dutch": w.dutch,
            "English": w.english,
            "Type": w.word_type,
            "Chapter": w.chapter,
            "Due": s.due_date.isoformat(),
            "Reviews": s.reps,
        }
        for w, s in rows
    ]
    st.dataframe(table_data, use_container_width=True)
```

- [ ] **Step 2: Commit**

```bash
git add src/dutch_learning/pages/browse.py
git commit -m "feat: add Browse page with chapter and search filters"
```

---

### Task 8: Stats Page

**Files:**
- Create: `src/dutch_learning/pages/stats.py`

**Interfaces:**
- Consumes: `get_stats` from db
- Produces: `def render(conn) -> None`

- [ ] **Step 1: Create stats.py**

Create `src/dutch_learning/pages/stats.py`:
```python
from datetime import date

import streamlit as st

from dutch_learning.db import get_stats


def render(conn) -> None:
    st.title("Stats")
    stats = get_stats(conn, date.today())

    col1, col2, col3 = st.columns(3)
    col1.metric("Due today", stats["due_today"])
    col2.metric("Total words", stats["total_words"])
    col3.metric("Total reviews", stats["total_reviews"])

    st.write("---")
    st.subheader("By chapter")

    if not stats["by_chapter"]:
        st.info("No data yet.")
        return

    chapter_data = [
        {"Chapter": r["chapter"], "Words": r["count"], "Reviews": r["reviews"]}
        for r in stats["by_chapter"]
    ]
    st.dataframe(chapter_data, use_container_width=True)
```

- [ ] **Step 2: Commit**

```bash
git add src/dutch_learning/pages/stats.py
git commit -m "feat: add Stats page with metrics and per-chapter breakdown"
```

---

### Task 9: App Entry Point + End-to-End Smoke Test

**Files:**
- Create: `src/dutch_learning/app.py`

**Interfaces:**
- Consumes: `get_conn`, `init_db` from db; `make_hint_agent` from ai; `render` from all three pages
- Produces: runnable Streamlit app via `uv run streamlit run src/dutch_learning/app.py`

- [ ] **Step 1: Create app.py**

Create `src/dutch_learning/app.py`:
```python
import os

import streamlit as st
from dotenv import load_dotenv

from dutch_learning.ai import make_hint_agent
from dutch_learning.db import get_conn, init_db
from dutch_learning.pages import browse, stats, study

load_dotenv()

st.set_page_config(page_title="Dutch Learning", page_icon="🇳🇱", layout="centered")


@st.cache_resource
def _get_conn():
    conn = get_conn()
    init_db(conn)
    return conn


@st.cache_resource
def _get_agent():
    model = os.getenv("DUTCH_MODEL", "google-gla:gemini-2.0-flash")
    return make_hint_agent(model)


def main():
    conn = _get_conn()
    agent = _get_agent()

    page = st.sidebar.radio("Navigate", ["Study", "Browse", "Stats"])

    if page == "Study":
        study.render(conn, agent)
    elif page == "Browse":
        browse.render(conn)
    elif page == "Stats":
        stats.render(conn)


main()
```

- [ ] **Step 2: Verify data is imported (or import now if not done)**

```bash
ls data/dutch_learning.db 2>/dev/null && echo "DB exists" || uv run python -m dutch_learning.importer /Users/admin/Downloads/Dutch_courses_De_Opmaat__De_Sprong.apkg
```

- [ ] **Step 3: Launch the app**

```bash
uv run streamlit run src/dutch_learning/app.py
```

Expected: browser opens at `http://localhost:8501`. Study page shows cards due today (all 2957 on first run since due_date = today for all).

- [ ] **Step 4: Smoke test — Study page**

- Word shows (Dutch text visible)
- "Show answer" reveals English translation
- Audio plays (if GOOGLE_API_KEY not set, audio files are present from import)
- Rating buttons (Again/Hard/Good/Easy) advance to next card

- [ ] **Step 5: Smoke test — Browse page**

- Table shows all 2957 words
- Chapter filter narrows the list
- Search finds matching words

- [ ] **Step 6: Smoke test — Stats page**

- Three metric tiles show numbers
- Chapter table renders

- [ ] **Step 7: Smoke test — AI hints (if GOOGLE_API_KEY set in .env)**

- Open AI hint expander on Study page
- Type a question like "Give me an example sentence"
- Response appears

- [ ] **Step 8: Commit**

```bash
git add src/dutch_learning/app.py
git commit -m "feat: add Streamlit app entry point, wire Study/Browse/Stats pages"
```

---

## Running the App

```bash
# One-time import (already done in Task 4 step 5):
uv run python -m dutch_learning.importer /Users/admin/Downloads/Dutch_courses_De_Opmaat__De_Sprong.apkg

# Start the app:
uv run streamlit run src/dutch_learning/app.py
```

Visit `http://localhost:8501`.

## Adding .env for AI

```
GOOGLE_API_KEY=your_key_here   # Gemini (free tier at aistudio.google.com)
# OR
ANTHROPIC_API_KEY=your_key     # Then set DUTCH_MODEL=anthropic:claude-haiku-4-5-20251001 in .env
```
