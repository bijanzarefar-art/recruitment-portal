from django.urls import path

from . import views

urlpatterns = [
    path("staff/login", views.staff_login_page, name="staff-login-page"),
    path("staff/dashboard", views.staff_dashboard_page, name="staff-dashboard-page"),
    path(
        "staff/applications/<uuid:pk>",
        views.staff_application_detail_page,
        name="staff-application-detail-page",
    ),
    path("staff/exports", views.staff_export_page, name="staff-export-page"),
    path("staff/jobs", views.staff_jobs_page, name="staff-jobs-page"),
    path("staff/pipeline", views.staff_pipeline_page, name="staff-pipeline-page"),
    path("staff/account", views.staff_account_page, name="staff-account-page"),
    path("staff/users", views.staff_users_page, name="staff-users-page"),
]
