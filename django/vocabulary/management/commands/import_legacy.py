"""Copy the pre-Django SQLite deck (words, schedule and review log) into Django."""

import sqlite3
from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from vocabulary.models import ReviewLog, SrsState, Word

DEFAULT_SOURCE = Path("../data/dutch_learning.db")


class Command(BaseCommand):
    help = "Import words, SRS state and review history from the standalone SQLite database."

    def add_arguments(self, parser) -> None:
        parser.add_argument("source", nargs="?", default=str(DEFAULT_SOURCE))
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete existing vocabulary rows before importing.",
        )

    def handle(self, *args, **options) -> None:
        source = Path(options["source"]).expanduser()
        if not source.exists():
            raise CommandError(f"No SQLite database at {source}")

        conn = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            words = conn.execute("SELECT * FROM words").fetchall()
            states = {
                row["word_id"]: row for row in conn.execute("SELECT * FROM srs_state").fetchall()
            }
            reviews = self._read_reviews(conn)
        finally:
            conn.close()

        if options["flush"]:
            ReviewLog.objects.all().delete()
            SrsState.objects.all().delete()
            Word.objects.all().delete()

        existing = set(Word.objects.values_list("id", flat=True))
        with transaction.atomic():
            new_words = [
                Word(
                    id=row["id"],
                    dutch=row["dutch"],
                    english=row["english"],
                    word_type=row["word_type"] or "",
                    audio_file=row["audio_file"],
                    tags=row["tags"] or "",
                    chapter=row["chapter"] or "",
                )
                for row in words
                if row["id"] not in existing
            ]
            Word.objects.bulk_create(new_words, batch_size=500)

            imported_ids = {word.id for word in new_words}
            SrsState.objects.bulk_create(
                [
                    SrsState(
                        word_id=word_id,
                        interval=state["interval"],
                        ease_factor=state["ease_factor"],
                        reps=state["reps"],
                        due_date=date.fromisoformat(state["due_date"]),
                    )
                    for word_id, state in states.items()
                    if word_id in imported_ids
                ],
                batch_size=500,
            )

            known_ids = existing | imported_ids
            logged = ReviewLog.objects.bulk_create(
                [
                    ReviewLog(
                        word_id=row["word_id"],
                        quality=row["quality"],
                        reviewed_on=date.fromisoformat(row["reviewed_on"]),
                    )
                    for row in reviews
                    if row["word_id"] in known_ids
                ],
                batch_size=500,
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {len(new_words)} word(s), "
                f"{len(new_words)} schedule row(s), {len(logged)} review(s). "
                f"Skipped {len(words) - len(new_words)} already present."
            )
        )

    @staticmethod
    def _read_reviews(conn: sqlite3.Connection) -> list[sqlite3.Row]:
        """The review log only exists in databases used after that feature landed."""
        tables = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master")}
        if "review_log" not in tables:
            return []
        return conn.execute("SELECT word_id, quality, reviewed_on FROM review_log").fetchall()
