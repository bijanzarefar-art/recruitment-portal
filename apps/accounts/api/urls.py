from django.urls import path

from . import views

urlpatterns = [
    path("auth/staff/login", views.StaffLoginView.as_view(), name="staff-login"),
    path("auth/staff/logout", views.StaffLogoutView.as_view(), name="staff-logout"),
    path("staff/users", views.StaffUserListCreateView.as_view(), name="staff-user-list-create"),
    path("staff/users/<uuid:pk>", views.StaffUserDetailView.as_view(), name="staff-user-detail"),
]
