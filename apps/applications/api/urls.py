from django.urls import path

from . import views

urlpatterns = [
    path("privacy-notice", views.CurrentPrivacyNoticeView.as_view(), name="privacy-notice"),
    path("candidate/applications", views.CandidateApplicationCreateView.as_view(), name="candidate-applications"),
    path("track/<str:tracking_code>", views.TrackApplicationView.as_view(), name="track-application"),
    path(
        "staff/applications/<uuid:pk>/assignments",
        views.StaffApplicationAssignmentView.as_view(),
        name="staff-application-assignments",
    ),
    path("staff/applications", views.StaffApplicationListView.as_view(), name="staff-application-list"),
    path(
        "staff/applications/metrics",
        views.StaffApplicationMetricsView.as_view(),
        name="staff-application-metrics",
    ),
    path("staff/applications/<uuid:pk>", views.StaffApplicationDetailView.as_view(), name="staff-application-detail"),
    path(
        "staff/applications/<uuid:pk>/resume",
        views.StaffResumeDownloadView.as_view(),
        name="staff-application-resume",
    ),
    path(
        "staff/applications/<uuid:pk>/notes",
        views.StaffApplicationNoteCreateView.as_view(),
        name="staff-application-notes",
    ),
    path(
        "staff/applications/<uuid:pk>/status",
        views.StaffApplicationStatusView.as_view(),
        name="staff-application-status",
    ),
]
