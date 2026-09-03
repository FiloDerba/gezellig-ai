from datetime import date

from django.contrib import admin

from vocabulary.models import ReviewLog, SrsState, Word
from vocabulary.srs import initial_schedule


class SrsStateInline(admin.StackedInline):
    model = SrsState
    can_delete = False
    extra = 0


@admin.register(Word)
class WordAdmin(admin.ModelAdmin):
    list_display = ["dutch", "english", "word_type", "chapter", "due_date", "reps", "maturity"]
    list_filter = ["chapter", "word_type"]
    search_fields = ["dutch", "english"]
    ordering = ["dutch"]
    inlines = [SrsStateInline]
    list_select_related = ["srs"]
    actions = ["reset_schedule"]

    @admin.display(description="Due", ordering="srs__due_date")
    def due_date(self, word: Word):
        return getattr(word.srs, "due_date", None)

    @admin.display(description="Reviews", ordering="srs__reps")
    def reps(self, word: Word):
        return getattr(word.srs, "reps", None)

    @admin.display(description="Status")
    def maturity(self, word: Word):
        return getattr(word.srs, "maturity", "—")

    @admin.action(description="Reset schedule (back to a new card, due today)")
    def reset_schedule(self, request, queryset):
        schedule = initial_schedule()
        updated = SrsState.objects.filter(word__in=queryset).update(
            interval=schedule.interval,
            ease_factor=schedule.ease_factor,
            reps=schedule.reps,
            due_date=schedule.due_date,
        )
        self.message_user(request, f"Reset {updated} card(s).")


@admin.register(SrsState)
class SrsStateAdmin(admin.ModelAdmin):
    list_display = ["word", "due_date", "interval", "ease_factor", "reps", "maturity"]
    list_filter = ["due_date"]
    search_fields = ["word__dutch", "word__english"]
    list_select_related = ["word"]
    ordering = ["due_date"]

    @admin.display(description="Status")
    def maturity(self, state: SrsState):
        return state.maturity


@admin.register(ReviewLog)
class ReviewLogAdmin(admin.ModelAdmin):
    list_display = ["word", "quality", "reviewed_on", "created_at"]
    list_filter = ["reviewed_on", "quality"]
    search_fields = ["word__dutch", "word__english"]
    list_select_related = ["word"]
    date_hierarchy = "reviewed_on"

    def has_add_permission(self, request) -> bool:
        """Reviews are written by the study endpoint, not by hand."""
        return False


admin.site.site_header = "Dutch Vocabulary"
admin.site.site_title = "Dutch Vocabulary"
admin.site.index_title = f"Deck administration — {date.today():%d %b %Y}"
