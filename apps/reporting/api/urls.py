from django.urls import path

from . import views

urlpatterns = [
    path("staff/exports", views.StaffExportView.as_view(), name="staff-exports"),
]
