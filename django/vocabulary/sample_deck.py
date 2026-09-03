"""A small built-in deck so the app is usable before importing an Anki export."""

from vocabulary.models import SrsState, Word
from vocabulary.srs import initial_schedule

SAMPLE_WORDS: list[tuple[str, str, str, str]] = [
    ("de man", "the man", "noun", "Basics 1"),
    ("de vrouw", "the woman", "noun", "Basics 1"),
    ("het kind", "the child", "noun", "Basics 1"),
    ("het huis", "the house", "noun", "Basics 1"),
    ("de stad", "the city", "noun", "Basics 1"),
    ("het brood", "the bread", "noun", "Food"),
    ("de kaas", "the cheese", "noun", "Food"),
    ("het water", "the water", "noun", "Food"),
    ("de appel", "the apple", "noun", "Food"),
    ("het ontbijt", "the breakfast", "noun", "Food"),
    ("zijn", "to be", "verb", "Verbs 1"),
    ("hebben", "to have", "verb", "Verbs 1"),
    ("gaan", "to go", "verb", "Verbs 1"),
    ("komen", "to come", "verb", "Verbs 1"),
    ("weten", "to know (a fact)", "verb", "Verbs 1"),
    ("kennen", "to know (a person)", "verb", "Verbs 1"),
    ("werken", "to work", "verb", "Verbs 1"),
    ("spreken", "to speak", "verb", "Verbs 1"),
    ("begrijpen", "to understand", "verb", "Verbs 1"),
    ("leren", "to learn", "verb", "Verbs 1"),
    ("groot", "big", "adjective", "Adjectives"),
    ("klein", "small", "adjective", "Adjectives"),
    ("mooi", "beautiful", "adjective", "Adjectives"),
    ("moeilijk", "difficult", "adjective", "Adjectives"),
    ("gezellig", "cosy, convivial", "adjective", "Adjectives"),
    ("altijd", "always", "adverb", "Time"),
    ("nooit", "never", "adverb", "Time"),
    ("vandaag", "today", "adverb", "Time"),
    ("morgen", "tomorrow", "adverb", "Time"),
    ("gisteren", "yesterday", "adverb", "Time"),
]


def load_sample_words() -> int:
    """Add sample words that are not in the database yet. Returns how many were added."""
    existing = {dutch.casefold() for dutch in Word.objects.values_list("dutch", flat=True)}
    schedule = initial_schedule()
    added = []
    for dutch, english, word_type, chapter in SAMPLE_WORDS:
        if dutch.casefold() in existing:
            continue
        added.append(
            Word(dutch=dutch, english=english, word_type=word_type, chapter=chapter, tags="sample")
        )
    Word.objects.bulk_create(added)
    SrsState.objects.bulk_create(
        [
            SrsState(
                word_id=word.id,
                interval=schedule.interval,
                ease_factor=schedule.ease_factor,
                reps=schedule.reps,
                due_date=schedule.due_date,
            )
            for word in added
        ]
    )
    return len(added)
