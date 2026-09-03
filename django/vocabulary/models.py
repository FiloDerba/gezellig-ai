from datetime import date

from django.db import models

from vocabulary.srs import MATURE_INTERVAL_DAYS, RATING_CHOICES


class Word(models.Model):
    dutch = models.CharField(max_length=200)
    english = models.CharField(max_length=300)
    word_type = models.CharField(max_length=50, blank=True)
    audio_file = models.CharField(max_length=255, blank=True, null=True)
    tags = models.CharField(max_length=255, blank=True)
    chapter = models.CharField(max_length=100, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "words"
        ordering = ["dutch"]

    def __str__(self) -> str:
        return self.dutch


class SrsState(models.Model):
    """Scheduling state for a word. One row per word, keyed by the word itself."""

    word = models.OneToOneField(
        Word,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="srs",
        db_column="word_id",
    )
    interval = models.PositiveIntegerField(default=1)
    ease_factor = models.FloatField(default=2.5)
    due_date = models.DateField(default=date.today, db_index=True)
    reps = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "srs_state"
        ordering = ["due_date"]

    def __str__(self) -> str:
        return f"{self.word_id} due {self.due_date}"

    @property
    def is_new(self) -> bool:
        return self.reps == 0

    @property
    def maturity(self) -> str:
        if self.reps == 0:
            return "new"
        return "mature" if self.interval >= MATURE_INTERVAL_DAYS else "learning"


class ReviewLog(models.Model):
    """One row per rating, so activity and streaks can be reported."""

    word = models.ForeignKey(Word, on_delete=models.CASCADE, related_name="reviews")
    quality = models.PositiveSmallIntegerField(choices=RATING_CHOICES)
    reviewed_on = models.DateField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "review_log"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.word_id} rated {self.quality} on {self.reviewed_on}"
