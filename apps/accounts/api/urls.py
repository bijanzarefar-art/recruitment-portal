from django.urls import path

from . import views

urlpatterns = [
    path("auth/staff/login", views.StaffLoginView.as_view(), name="staff-login"),
    path("auth/staff/logout", views.StaffLogoutView.as_view(), name="staff-logout"),
    path("auth/staff/change-password", views.ChangeOwnPasswordView.as_view(), name="staff-change-password"),
    path("staff/users", views.StaffUserListCreateView.as_view(), name="staff-user-list-create"),
    path("staff/users/<uuid:pk>", views.StaffUserDetailView.as_view(), name="staff-user-detail"),
    path("staff/users/<uuid:pk>/password", views.AdminResetPasswordView.as_view(), name="staff-user-password"),
]
