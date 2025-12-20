"""URL patterns for the demo app."""

from demo.views import ConfigView, HealthView, IndexView, ItemsView, UploadView
from django.urls import path

urlpatterns = [
    path("", IndexView.as_view(), name="index"),
    path("api/items/", ItemsView.as_view(), name="items"),
    path("api/upload/", UploadView.as_view(), name="upload"),
    path("api/config/", ConfigView.as_view(), name="config"),
    path("health/", HealthView.as_view(), name="health"),
]
