"""URL configuration for Replane example project."""

from django.urls import include, path

urlpatterns = [
    path("", include("demo.urls")),
]
