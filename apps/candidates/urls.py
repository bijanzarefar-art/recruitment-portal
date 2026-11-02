from django.urls import path

from . import views

urlpatterns = [
    path("", views.home_page, name="home-page"),
    path("jobs", views.jobs_list_page, name="candidate-jobs-list-page"),
    path("apply", views.apply_page, name="candidate-apply-page"),
    path("track", views.track_page, name="candidate-track-page"),
]
