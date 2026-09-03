import zipfile
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from vocabulary.anki import extract_media, read_notes
from vocabulary.models import SrsState, Word
from vocabulary.srs import initial_schedule

DEFAULT_MEDIA_DIR = Path("../data/media")


class Command(BaseCommand):
    help = "Import words from an Anki .apkg export."

    def add_arguments(self, parser) -> None:
        parser.add_argument("apkg")
        parser.add_argument("--media-dir", default=str(DEFAULT_MEDIA_DIR))

    def handle(self, *args, **options) -> None:
        apkg = Path(options["apkg"]).expanduser()
        if not apkg.exists():
            raise CommandError(f"No such file: {apkg}")

        media_dir = Path(options["media_dir"])
        with zipfile.ZipFile(apkg) as archive:
            media_count = extract_media(archive, media_dir)
        notes = read_notes(apkg)

        existing = set(Word.objects.values_list("id", flat=True))
        schedule = initial_schedule()
        with transaction.atomic():
            new_words = [
                Word(
                    id=note.id,
                    dutch=note.dutch,
                    english=note.english,
                    word_type=note.word_type,
                    audio_file=note.audio_file,
                    tags=note.tags,
                    chapter=note.chapter,
                )
                for note in notes
                if note.id not in existing
            ]
            Word.objects.bulk_create(new_words, batch_size=500)
            SrsState.objects.bulk_create(
                [
                    SrsState(
                        word_id=word.id,
                        interval=schedule.interval,
                        ease_factor=schedule.ease_factor,
                        reps=schedule.reps,
                        due_date=schedule.due_date,
                    )
                    for word in new_words
                ],
                batch_size=500,
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {len(new_words)} word(s) and {media_count} audio file(s). "
                f"Skipped {len(notes) - len(new_words)} already present."
            )
        )
