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
    conn = sqlite3.connect(path, check_same_thread=False)
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
    cursor = conn.execute(
        """UPDATE srs_state SET interval=?, ease_factor=?, due_date=?, reps=?
           WHERE word_id=?""",
        (state.interval, state.ease_factor, state.due_date.isoformat(),
         state.reps, state.word_id),
    )
    if cursor.rowcount == 0:
        raise ValueError(f"no srs_state row for word_id={state.word_id}")
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
        """SELECT w.chapter, COUNT(*) as count, COALESCE(SUM(s.reps), 0) as reviews
           FROM words w LEFT JOIN srs_state s ON w.id = s.word_id
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
