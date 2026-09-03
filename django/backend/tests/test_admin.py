import pytest
from vocabulary.models import ReviewLog, SrsState


@pytest.mark.django_db
class AdminTests:
    def test_index_lists_vocabulary_models(self, admin_client):
        response = admin_client.get("/admin/")
        assert response.status_code == 200
        assert b"Dutch Vocabulary" in response.content

    @pytest.mark.parametrize(
        "path",
        ["/admin/vocabulary/word/", "/admin/vocabulary/srsstate/", "/admin/vocabulary/reviewlog/"],
    )
    def test_changelists_render(self, admin_client, word, path):
        assert admin_client.get(path).status_code == 200

    def test_word_changelist_shows_schedule_columns(self, admin_client, word):
        response = admin_client.get("/admin/vocabulary/word/")
        assert response.context["cl"].result_count == 1
        assert b"lezen" in response.content

    def test_word_search(self, admin_client, make_card):
        make_card(dutch="lezen", english="to read")
        make_card(dutch="schrijven", english="to write")
        response = admin_client.get("/admin/vocabulary/word/", {"q": "lez"})
        assert response.context["cl"].result_count == 1

    def test_word_detail_includes_srs_inline(self, admin_client, word):
        response = admin_client.get(f"/admin/vocabulary/word/{word.id}/change/")
        assert response.status_code == 200
        assert b"ease_factor" in response.content

    def test_reset_schedule_action(self, admin_client, word):
        SrsState.objects.filter(word=word).update(reps=7, interval=120)
        response = admin_client.post(
            "/admin/vocabulary/word/",
            {"action": "reset_schedule", "_selected_action": [str(word.id)]},
            follow=True,
        )
        assert response.status_code == 200
        state = SrsState.objects.get(word=word)
        assert (state.reps, state.interval) == (0, 1)

    def test_review_log_is_read_only(self, admin_client, word):
        ReviewLog.objects.create(word=word, quality=3, reviewed_on="2026-09-03")
        response = admin_client.get("/admin/vocabulary/reviewlog/add/")
        assert response.status_code == 403

    def test_admin_requires_login(self, client):
        response = client.get("/admin/vocabulary/word/")
        assert response.status_code == 302
        assert "/admin/login/" in response.url


@pytest.mark.django_db
class ApiStillWorksWithAdminMiddlewareTests:
    def test_api_post_is_not_blocked_by_csrf(self, client, word):
        """DRF views are CSRF-exempt, so adding CsrfViewMiddleware must not break them."""
        response = client.post(
            f"/api/study/{word.id}/review/",
            data={"quality": 3},
            content_type="application/json",
        )
        assert response.status_code == 200
