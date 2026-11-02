from django.urls import path

from . import views

urlpatterns = [
    path("candidate/uploads", views.CandidateUploadView.as_view(), name="candidate-uploads"),
    path("candidate/uploads/<uuid:pk>", views.CandidateUploadStatusView.as_view(), name="candidate-upload-detail"),
]
