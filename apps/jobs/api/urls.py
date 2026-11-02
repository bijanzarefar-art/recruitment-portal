from django.urls import path

from . import views

urlpatterns = [
    path("jobs", views.PublicJobListView.as_view(), name="job-list"),
    path("staff/jobs", views.StaffJobListCreateView.as_view(), name="staff-job-list-create"),
    path("staff/jobs/<uuid:pk>", views.StaffJobDetailView.as_view(), name="staff-job-detail"),
    path("staff/jobs/<uuid:pk>/status", views.StaffJobStatusView.as_view(), name="staff-job-status"),
]
