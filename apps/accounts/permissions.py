from rest_framework.permissions import BasePermission

from .models import StaffUser


class IsStaff(BasePermission):
    """
    هر کارمند احرازهویت‌شده (نشست staff_sessionid با MFA کامل) و هنوز فعال. بررسی `is_active`
    اینجا الزامی است: Django پیش‌فرض `request.user` را از `user_id` ذخیره‌شده در نشست بازمی‌سازد
    بدون بررسی مجدد `is_active` در هر درخواست؛ بدون این بررسی، غیرفعال‌کردن حساب یک کارمند
    نمی‌توانست نشست از‌پیش‌ساخته‌شده او را فوراً باطل کند (رفع یافته M3 در تحلیل، FR-045).
    """

    def has_permission(self, request, view) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and isinstance(request.user, StaffUser)
            and request.user.is_active
        )


class IsHrManager(IsStaff):
    def has_permission(self, request, view) -> bool:
        return super().has_permission(request, view) and request.user.role == StaffUser.Role.HR_MANAGER
