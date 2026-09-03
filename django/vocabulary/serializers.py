from rest_framework import serializers

from vocabulary.models import ReviewLog, SrsState, Word
from vocabulary.srs import RATING_CHOICES, preview_intervals


class SrsStateSerializer(serializers.ModelSerializer):
    maturity = serializers.CharField(read_only=True)

    class Meta:
        model = SrsState
        fields = ["interval", "ease_factor", "due_date", "reps", "maturity"]
        read_only_fields = fields


class WordSerializer(serializers.ModelSerializer):
    srs = SrsStateSerializer(read_only=True)

    class Meta:
        model = Word
        fields = [
            "id",
            "dutch",
            "english",
            "word_type",
            "audio_file",
            "tags",
            "chapter",
            "srs",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "srs", "created_at", "updated_at"]


class StudyCardSerializer(serializers.Serializer):
    """A due card plus what each rating would schedule, so the client needs no SM-2."""

    word = WordSerializer(read_only=True)
    interval = serializers.IntegerField(read_only=True)
    ease_factor = serializers.FloatField(read_only=True)
    reps = serializers.IntegerField(read_only=True)
    due_date = serializers.DateField(read_only=True)
    previews = serializers.SerializerMethodField()

    @staticmethod
    def get_previews(state: SrsState) -> dict[str, int]:
        return preview_intervals(state.interval, state.ease_factor, state.reps)


class ReviewRequestSerializer(serializers.Serializer):
    quality = serializers.ChoiceField(choices=RATING_CHOICES)


class ReviewLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReviewLog
        fields = ["id", "word", "quality", "reviewed_on", "created_at"]
        read_only_fields = fields


class OverviewSerializer(serializers.Serializer):
    total_words = serializers.IntegerField()
    due_today = serializers.IntegerField()
    new = serializers.IntegerField()
    learning = serializers.IntegerField()
    mature = serializers.IntegerField()
    total_reviews = serializers.IntegerField()
    reviewed_today = serializers.IntegerField()
    streak = serializers.IntegerField()


class ActivityPointSerializer(serializers.Serializer):
    date = serializers.DateField()
    reviews = serializers.IntegerField()


class ForecastPointSerializer(serializers.Serializer):
    date = serializers.DateField()
    cards = serializers.IntegerField()


class ChapterStatSerializer(serializers.Serializer):
    chapter = serializers.CharField()
    words = serializers.IntegerField()
    reviews = serializers.IntegerField(allow_null=True)
