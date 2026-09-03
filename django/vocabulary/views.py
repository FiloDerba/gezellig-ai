from datetime import date

from django.db import transaction
from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from vocabulary import selectors
from vocabulary.models import ReviewLog, SrsState, Word
from vocabulary.sample_deck import load_sample_words
from vocabulary.serializers import (
    ActivityPointSerializer,
    ChapterStatSerializer,
    ForecastPointSerializer,
    OverviewSerializer,
    ReviewRequestSerializer,
    SrsStateSerializer,
    StudyCardSerializer,
    WordSerializer,
)
from vocabulary.srs import initial_schedule
from vocabulary.srs import review as apply_review

DEFAULT_QUEUE_LIMIT = 20
MAX_QUEUE_LIMIT = 500


def _int_param(request, name: str, default: int, maximum: int) -> int:
    """Read a positive integer query parameter, falling back to `default` when unusable."""
    try:
        value = int(request.query_params.get(name, default))
    except (TypeError, ValueError):
        return default
    return max(1, min(value, maximum))


class WordViewSet(viewsets.ModelViewSet):
    """CRUD for vocabulary. Creating a word also creates its scheduling row."""

    queryset = Word.objects.select_related("srs").all()
    serializer_class = WordSerializer
    filterset_fields = ["chapter", "word_type"]

    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(Q(dutch__icontains=search) | Q(english__icontains=search))
        maturity = self.request.query_params.get("maturity")
        if maturity == "new":
            queryset = queryset.filter(srs__reps=0)
        elif maturity == "due":
            queryset = queryset.filter(srs__due_date__lte=date.today())
        return queryset

    @extend_schema(
        parameters=[
            OpenApiParameter("search", str, description="Match Dutch or English text"),
            OpenApiParameter("maturity", str, enum=["new", "due"]),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def perform_create(self, serializer) -> None:
        with transaction.atomic():
            word = serializer.save()
            schedule = initial_schedule()
            SrsState.objects.create(
                word=word,
                interval=schedule.interval,
                ease_factor=schedule.ease_factor,
                reps=schedule.reps,
                due_date=schedule.due_date,
            )

    @extend_schema(request=None, responses={201: None})
    @action(detail=False, methods=["post"], url_path="load-sample")
    def load_sample(self, request):
        """Add the built-in starter deck, skipping words that already exist."""
        added = load_sample_words()
        return Response({"added": added}, status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses={200: WordSerializer})
    @action(detail=True, methods=["post"])
    def reset(self, request, pk=None):
        """Send a word back to the start of the schedule."""
        word = self.get_object()
        schedule = initial_schedule()
        SrsState.objects.update_or_create(
            word=word,
            defaults={
                "interval": schedule.interval,
                "ease_factor": schedule.ease_factor,
                "reps": schedule.reps,
                "due_date": schedule.due_date,
            },
        )
        word.refresh_from_db()
        return Response(WordSerializer(word).data)


class StudyViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """The study queue and the endpoint that records a rating."""

    queryset = SrsState.objects.select_related("word").all()
    serializer_class = StudyCardSerializer

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "limit",
                int,
                description=(
                    f"Cards to return (default {DEFAULT_QUEUE_LIMIT}, max {MAX_QUEUE_LIMIT})"
                ),
            )
        ],
        responses={200: StudyCardSerializer(many=True)},
    )
    @action(detail=False, methods=["get"])
    def queue(self, request):
        limit = _int_param(request, "limit", DEFAULT_QUEUE_LIMIT, MAX_QUEUE_LIMIT)
        today = date.today()
        cards = selectors.due_queue(today, limit=limit)
        return Response(
            {
                "due_total": SrsState.objects.filter(due_date__lte=today).count(),
                "limit": limit,
                "results": StudyCardSerializer(cards, many=True).data,
            }
        )

    @extend_schema(
        request=ReviewRequestSerializer,
        responses={200: SrsStateSerializer},
    )
    @action(detail=True, methods=["post"])
    def review(self, request, pk=None):
        """Apply a rating: reschedule the card and append to the review log."""
        state = self.get_object()
        payload = ReviewRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        quality = payload.validated_data["quality"]
        today = date.today()

        schedule = apply_review(state.interval, state.ease_factor, state.reps, quality, today)
        with transaction.atomic():
            state.interval = schedule.interval
            state.ease_factor = schedule.ease_factor
            state.reps = schedule.reps
            state.due_date = schedule.due_date
            state.save(update_fields=["interval", "ease_factor", "reps", "due_date", "updated_at"])
            ReviewLog.objects.create(word_id=state.word_id, quality=quality, reviewed_on=today)

        return Response(SrsStateSerializer(state).data, status=status.HTTP_200_OK)


class StatsViewSet(viewsets.ViewSet):
    """Aggregates behind the Progress tab."""

    @extend_schema(responses={200: OverviewSerializer})
    @action(detail=False, methods=["get"])
    def overview(self, request):
        return Response(OverviewSerializer(selectors.overview(date.today())).data)

    @extend_schema(
        parameters=[OpenApiParameter("days", int, description="Window size, default 21")],
        responses={200: ActivityPointSerializer(many=True)},
    )
    @action(detail=False, methods=["get"])
    def activity(self, request):
        days = _int_param(request, "days", 21, 365)
        data = selectors.activity(date.today(), days=days)
        return Response(ActivityPointSerializer(data, many=True).data)

    @extend_schema(
        parameters=[OpenApiParameter("days", int, description="Window size, default 14")],
        responses={200: ForecastPointSerializer(many=True)},
    )
    @action(detail=False, methods=["get"])
    def forecast(self, request):
        days = _int_param(request, "days", 14, 365)
        data = selectors.forecast(date.today(), days=days)
        return Response(ForecastPointSerializer(data, many=True).data)

    @extend_schema(responses={200: ChapterStatSerializer(many=True)})
    @action(detail=False, methods=["get"])
    def chapters(self, request):
        return Response(ChapterStatSerializer(selectors.chapter_breakdown(), many=True).data)
