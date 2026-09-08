"""Read-side queries for the study queue and the stats endpoints."""

from datetime import date, timedelta

from django.db.models import Case, Count, IntegerField, Max, Q, Sum, When

from vocabulary.models import ReviewLog, SrsState, Word
from vocabulary.srs import MATURE_INTERVAL_DAYS


def due_queue(today: date, limit: int | None = None):
    """Cards due on or before `today`, started cards ahead of brand-new ones."""
    queryset = (
        SrsState.objects.select_related("word")
        .filter(due_date__lte=today)
        # Started cards (reps > 0) sort ahead of brand-new ones on the same due date.
        .annotate(queue_rank=Case(When(reps=0, then=1), default=0, output_field=IntegerField()))
        .order_by("due_date", "queue_rank", "word_id")
    )
    return queryset[:limit] if limit else queryset


def words(
    chapter: str | None = None,
    search: str | None = None,
    maturity: str | None = None,
    today: date | None = None,
):
    """The word list behind both `GET /api/words/` and the Streamlit browse page."""
    queryset = Word.objects.select_related("srs").all()
    if chapter:
        queryset = queryset.filter(chapter=chapter)
    if search:
        queryset = queryset.filter(Q(dutch__icontains=search) | Q(english__icontains=search))
    if maturity == "new":
        queryset = queryset.filter(srs__reps=0)
    elif maturity == "due":
        queryset = queryset.filter(srs__due_date__lte=today or date.today())
    return queryset


def encountered(search: str | None = None, limit: int | None = None):
    """Words the learner has actually rated at least once, most recent first.

    Driven by the review log rather than `reps`, because an "Again" rating resets reps to
    zero — which would hide precisely the words that turned out to be hard.
    """
    queryset = (
        Word.objects.select_related("srs")
        .annotate(times_reviewed=Count("reviews"), last_seen=Max("reviews__reviewed_on"))
        .filter(times_reviewed__gt=0)
        .order_by("-last_seen", "dutch")
    )
    if search:
        queryset = queryset.filter(Q(dutch__icontains=search) | Q(english__icontains=search))
    return queryset[:limit] if limit else queryset


def speaking_pool(today: date, limit: int = 30):
    """Words with a native recording, due ones first, then shuffled.

    Pronunciation practice is only useful where there is a reference recording to
    compare against, which the Anki import provides for most of the deck.
    """
    return (
        Word.objects.select_related("srs")
        .exclude(audio_file__isnull=True)
        .exclude(audio_file="")
        .annotate(
            queue_rank=Case(
                When(srs__due_date__lte=today, then=0), default=1, output_field=IntegerField()
            )
        )
        .order_by("queue_rank", "?")[:limit]
    )


def overview(today: date) -> dict:
    counts = SrsState.objects.aggregate(
        due_today=Count("pk", filter=Q(due_date__lte=today)),
        new=Count("pk", filter=Q(reps=0)),
        learning=Count("pk", filter=Q(reps__gt=0, interval__lt=MATURE_INTERVAL_DAYS)),
        mature=Count("pk", filter=Q(reps__gt=0, interval__gte=MATURE_INTERVAL_DAYS)),
        total_reviews=Sum("reps"),
    )
    return {
        "total_words": Word.objects.count(),
        "due_today": counts["due_today"],
        "new": counts["new"],
        "learning": counts["learning"],
        "mature": counts["mature"],
        "total_reviews": counts["total_reviews"] or 0,
        "reviewed_today": ReviewLog.objects.filter(reviewed_on=today).count(),
        "streak": streak(today),
    }


def activity(today: date, days: int = 21) -> list[dict]:
    """Reviews per day for the last `days` days, oldest first, including empty days."""
    start = today - timedelta(days=days - 1)
    rows = (
        ReviewLog.objects.filter(reviewed_on__range=(start, today))
        .values("reviewed_on")
        .annotate(reviews=Count("id"))
    )
    counts = {row["reviewed_on"]: row["reviews"] for row in rows}
    return [
        {"date": day, "reviews": counts.get(day, 0)}
        for day in (start + timedelta(days=offset) for offset in range(days))
    ]


def forecast(today: date, days: int = 14) -> list[dict]:
    """Cards scheduled per day for the next `days` days. Overdue cards land on day 0."""
    horizon = today + timedelta(days=days - 1)
    rows = (
        SrsState.objects.filter(due_date__lte=horizon)
        .values("due_date")
        .annotate(cards=Count("pk"))
    )
    counts = dict.fromkeys(range(days), 0)
    for row in rows:
        offset = (row["due_date"] - today).days
        counts[max(offset, 0)] += row["cards"]
    return [
        {"date": today + timedelta(days=offset), "cards": count}
        for offset, count in sorted(counts.items())
    ]


def streak(today: date) -> int:
    """Consecutive days with at least one review, ending today or yesterday."""
    days = set(ReviewLog.objects.values_list("reviewed_on", flat=True).distinct())
    if not days:
        return 0
    cursor = today if today in days else today - timedelta(days=1)
    count = 0
    while cursor in days:
        count += 1
        cursor -= timedelta(days=1)
    return count


def chapter_breakdown() -> list[dict]:
    return list(
        Word.objects.values("chapter")
        .annotate(words=Count("id"), reviews=Sum("srs__reps"))
        .order_by("chapter")
    )
