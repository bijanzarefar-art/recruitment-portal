from django.contrib import admin

from .models import StaffUser


@admin.register(StaffUser)
class StaffUserAdmin(admin.ModelAdmin):
    list_display = ("username", "role", "is_active", "created_at")
    list_filter = ("role", "is_active")
    search_fields = ("username",)
