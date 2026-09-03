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

    assert count2 == 2  # processes same notes; INSERT OR IGNORE prevents duplicates
    conn = get_conn(out_db)
    assert len(get_all_words(conn)) == 2  # no duplicates
