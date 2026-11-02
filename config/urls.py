from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("apps.jobs.api.urls")),
    path("api/v1/", include("apps.candidates.api.urls")),
    path("api/v1/", include("apps.applications.api.urls")),
    path("api/v1/", include("apps.attachments.api.urls")),
    path("api/v1/", include("apps.accounts.api.urls")),
    path("api/v1/", include("apps.reporting.api.urls")),
    path("", include("apps.candidates.urls")),
    path("", include("apps.accounts.urls")),
]
