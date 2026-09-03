from datetime import date, timedelta

import pytest
from rest_framework import status

from vocabulary.models import ReviewLog, SrsState, Word
from vocabulary.srs import AGAIN, EASY, GOOD, HARD


@pytest.mark.django_db
class WordApiTests:
    def test_list_words(self, api_client, word):
        response = api_client.get("/api/words/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["dutch"] == "lezen"

    def test_list_embeds_schedule(self, api_client, word):
        response = api_client.get("/api/words/")
        srs = response.data["results"][0]["srs"]
        assert srs["reps"] == 0
        assert srs["maturity"] == "new"

    def test_create_word_also_creates_schedule(self, api_client):
        response = api_client.post(
            "/api/words/",
            {"dutch": "de fiets", "english": "the bicycle", "word_type": "noun"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        created = Word.objects.get(dutch="de fiets")
        assert created.srs.due_date == date.today()
        assert created.srs.reps == 0

    def test_filter_by_chapter(self, api_client, make_card):
        make_card(dutch="een", chapter="Thema01a")
        make_card(dutch="twee", chapter="Thema02")
        response = api_client.get("/api/words/", {"chapter": "Thema02"})
        assert response.data["count"] == 1
        assert response.data["results"][0]["dutch"] == "twee"

    def test_search_matches_dutch_or_english(self, api_client, make_card):
        make_card(dutch="lezen", english="to read")
        make_card(dutch="schrijven", english="to write")
        assert api_client.get("/api/words/", {"search": "lez"}).data["count"] == 1
        assert api_client.get("/api/words/", {"search": "write"}).data["count"] == 1

    def test_delete_word_removes_schedule(self, api_client, word):
        response = api_client.delete(f"/api/words/{word.id}/")
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert SrsState.objects.count() == 0

    def test_reset_returns_card_to_the_start(self, api_client, word):
        SrsState.objects.filter(word=word).update(
            reps=6, interval=90, due_date=date.today() + timedelta(days=90)
        )
        response = api_client.post(f"/api/words/{word.id}/reset/")
        assert response.status_code == status.HTTP_200_OK
        state = SrsState.objects.get(word=word)
        assert (state.reps, state.interval, state.due_date) == (0, 1, date.today())


@pytest.mark.django_db
class StudyQueueTests:
    def test_queue_returns_due_cards_with_previews(self, api_client, word):
        response = api_client.get("/api/study/queue/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["due_total"] == 1
        card = response.data["results"][0]
        assert card["word"]["dutch"] == "lezen"
        assert card["previews"] == {"again": 1, "hard": 1, "good": 1, "easy": 4}

    def test_queue_excludes_future_cards(self, api_client, make_card):
        make_card(dutch="later", due_offset=5)
        response = api_client.get("/api/study/queue/")
        assert response.data["due_total"] == 0
        assert response.data["results"] == []

    def test_queue_respects_limit(self, api_client, make_card):
        for index in range(5):
            make_card(dutch=f"woord{index}")
        response = api_client.get("/api/study/queue/", {"limit": 2})
        assert response.data["due_total"] == 5
        assert len(response.data["results"]) == 2

    def test_queue_puts_started_cards_first(self, api_client, make_card):
        make_card(dutch="nieuw", reps=0)
        make_card(dutch="bekend", reps=3)
        response = api_client.get("/api/study/queue/")
        assert [c["word"]["dutch"] for c in response.data["results"]] == ["bekend", "nieuw"]

    def test_bad_limit_falls_back_to_default(self, api_client, word):
        response = api_client.get("/api/study/queue/", {"limit": "banana"})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["limit"] == 20


def rate(api_client, word_id: int, quality: int):
    return api_client.post(f"/api/study/{word_id}/review/", {"quality": quality}, format="json")


@pytest.mark.django_db
class ReviewTests:
    def test_good_review_reschedules_and_logs(self, api_client, word):
        response = rate(api_client, word.id, GOOD)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["reps"] == 1
        assert response.data["interval"] == 1
        assert response.data["due_date"] == (date.today() + timedelta(days=1)).isoformat()
        assert ReviewLog.objects.filter(word=word, quality=GOOD).count() == 1

    def test_easy_graduates_new_card(self, api_client, word):
        assert rate(api_client, word.id, EASY).data["interval"] == 4

    def test_again_lapses_card_without_losing_it(self, api_client, word):
        SrsState.objects.filter(word=word).update(reps=5, interval=40)
        response = rate(api_client, word.id, AGAIN)
        assert response.data["reps"] == 0
        assert response.data["interval"] == 1
        assert Word.objects.filter(id=word.id).exists()

    def test_hard_keeps_progress(self, api_client, word):
        SrsState.objects.filter(word=word).update(reps=5, interval=10)
        response = rate(api_client, word.id, HARD)
        assert response.data["reps"] == 6
        assert response.data["interval"] == 12

    def test_invalid_quality_is_rejected(self, api_client, word):
        assert rate(api_client, word.id, 9).status_code == status.HTTP_400_BAD_REQUEST
        assert ReviewLog.objects.count() == 0

    def test_review_of_unknown_card_is_404(self, api_client, db):
        assert rate(api_client, 123456, GOOD).status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class StatsTests:
    def test_overview_counts(self, api_client, make_card):
        make_card(dutch="nieuw", reps=0)
        make_card(dutch="lerend", reps=2, interval=6)
        make_card(dutch="volwassen", reps=9, interval=40, due_offset=10)
        response = api_client.get("/api/stats/overview/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["total_words"] == 3
        assert response.data["due_today"] == 2
        assert (response.data["new"], response.data["learning"], response.data["mature"]) == (
            1,
            1,
            1,
        )
        assert response.data["total_reviews"] == 11

    def test_overview_tracks_today_and_streak(self, api_client, word):
        api_client.post(f"/api/study/{word.id}/review/", {"quality": GOOD}, format="json")
        response = api_client.get("/api/stats/overview/")
        assert response.data["reviewed_today"] == 1
        assert response.data["streak"] == 1

    def test_activity_window_includes_empty_days(self, api_client, word):
        api_client.post(f"/api/study/{word.id}/review/", {"quality": GOOD}, format="json")
        response = api_client.get("/api/stats/activity/", {"days": 3})
        assert len(response.data) == 3
        assert response.data[-1]["date"] == date.today().isoformat()
        assert [row["reviews"] for row in response.data] == [0, 0, 1]

    def test_forecast_buckets_overdue_on_day_zero(self, api_client, make_card):
        make_card(dutch="achterstand", due_offset=-4)
        make_card(dutch="vandaag", due_offset=0)
        make_card(dutch="later", due_offset=2)
        response = api_client.get("/api/stats/forecast/", {"days": 5})
        assert len(response.data) == 5
        assert response.data[0]["cards"] == 2
        assert response.data[2]["cards"] == 1

    def test_chapters_breakdown(self, api_client, make_card):
        make_card(dutch="een", chapter="Thema01a", reps=3)
        make_card(dutch="twee", chapter="Thema01a")
        make_card(dutch="drie", chapter="Thema02")
        response = api_client.get("/api/stats/chapters/")
        rows = {row["chapter"]: row for row in response.data}
        assert rows["Thema01a"]["words"] == 2
        assert rows["Thema01a"]["reviews"] == 3
        assert rows["Thema02"]["words"] == 1


@pytest.mark.django_db
class SchemaTests:
    def test_openapi_schema_is_generated(self, api_client):
        response = api_client.get("/api/schema/")
        assert response.status_code == status.HTTP_200_OK

    def test_health_endpoint(self, api_client):
        assert api_client.get("/health/").json() == {"status": "ok"}
