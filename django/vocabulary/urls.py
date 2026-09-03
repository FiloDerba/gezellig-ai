from django.urls import include, path
from rest_framework.routers import DefaultRouter

from vocabulary.views import StatsViewSet, StudyViewSet, WordViewSet

router = DefaultRouter()
router.register(r"words", WordViewSet)
router.register(r"study", StudyViewSet, basename="study")
router.register(r"stats", StatsViewSet, basename="stats")

urlpatterns = [path("", include(router.urls))]
