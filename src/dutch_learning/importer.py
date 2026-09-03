import json
import os
import re
import sqlite3
import sys
import tempfile
import zipfile
from pathlib import Path

from dutch_learning.db import DB_PATH, Word, get_conn, init_db, upsert_srs_state, upsert_word
from dutch_learning.srs import new_state

MEDIA_DIR = Path("data/media")


def _parse_audio(field: str) -> str | None:
    # re.search so [sound:...] is found even when wrapped in HTML
    m = re.search(r"\[sound:(.+?)\]", field)
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

    # Use a unique temp file to avoid collisions under concurrent imports
    fd, tmp_path_str = tempfile.mkstemp(suffix=".anki2")
    os.close(fd)
    tmp_db = Path(tmp_path_str)

    # Ensure temp file is always removed, even on exception
    try:
        tmp_db.write_bytes(raw_db)

        # Context manager closes anki_conn on exit (including exception)
        with sqlite3.connect(tmp_db) as anki_conn:
            anki_conn.row_factory = sqlite3.Row
            notes = anki_conn.execute(
                "SELECT id, tags, flds FROM notes"
            ).fetchall()
    finally:
        tmp_db.unlink(missing_ok=True)

    app_conn = get_conn(db_path)
    # Ensure app_conn is always closed, even on exception
    try:
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
    finally:
        app_conn.close()

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
