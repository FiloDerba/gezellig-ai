"""Reading vocabulary out of an Anki `.apkg` export."""

import json
import os
import re
import sqlite3
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

MIN_FIELDS = 10
FIELD_SEPARATOR = "\x1f"


@dataclass
class AnkiNote:
    id: int
    dutch: str
    english: str
    word_type: str
    audio_file: str | None
    tags: str
    chapter: str


def parse_audio(field: str) -> str | None:
    # re.search so [sound:...] is found even when wrapped in HTML
    match = re.search(r"\[sound:(.+?)\]", field)
    return match.group(1) if match else None


def extract_chapter(tags: str) -> str:
    for tag in tags.strip().split():
        parts = tag.split("::")
        if len(parts) >= 2:
            return parts[-1]
    return "Unknown"


def extract_media(archive: zipfile.ZipFile, media_dir: Path) -> int:
    """Write the deck's audio files out under their original names."""
    if "media" not in archive.namelist():
        return 0
    media_map: dict[str, str] = json.loads(archive.read("media").decode())
    media_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for numbered, filename in media_map.items():
        if numbered in archive.namelist():
            (media_dir / Path(filename).name).write_bytes(archive.read(numbered))
            written += 1
    return written


def read_notes(apkg_path: Path) -> list[AnkiNote]:
    """Notes from the collection database embedded in the archive."""
    with zipfile.ZipFile(apkg_path) as archive:
        raw_db = archive.read("collection.anki2")

    handle, tmp_name = tempfile.mkstemp(suffix=".anki2")
    os.close(handle)
    tmp_db = Path(tmp_name)
    try:
        tmp_db.write_bytes(raw_db)
        with sqlite3.connect(tmp_db) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT id, tags, flds FROM notes").fetchall()
    finally:
        tmp_db.unlink(missing_ok=True)

    notes = []
    for row in rows:
        fields = row["flds"].split(FIELD_SEPARATOR)
        if len(fields) < MIN_FIELDS:
            continue
        dutch, english = fields[0].strip(), fields[4].strip()
        if not dutch or not english:
            continue
        notes.append(
            AnkiNote(
                id=row["id"],
                dutch=dutch,
                english=english,
                word_type=fields[7].strip(),
                audio_file=parse_audio(fields[9].strip()),
                tags=row["tags"].strip(),
                chapter=extract_chapter(row["tags"]),
            )
        )
    return notes
