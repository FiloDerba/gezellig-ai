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
    assert stats["total_reviews"] >= 0
    assert len(stats["by_chapter"]) == 1
    assert stats["by_chapter"][0]["chapter"] == "Thema01a"


def test_get_all_words_search_filter():
    conn = _conn()
    upsert_word(conn, _word(id=1, dutch="lezen", english="to read", chapter="Thema01a"))
    upsert_word(conn, _word(id=2, dutch="schrijven", english="to write", chapter="Thema01a"))
    upsert_srs_state(conn, _state(word_id=1))
    upsert_srs_state(conn, _state(word_id=2))
    result = get_all_words(conn, search="lez")
    assert len(result) == 1
    assert result[0][0].dutch == "lezen"


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
