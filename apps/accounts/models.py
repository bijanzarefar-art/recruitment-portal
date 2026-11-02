import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class StaffUser(AbstractUser):
    """
    کاربر کارمند (FR-017 تا FR-021). نقش تجاری مجزا از اپراتور سامانه؛ ساخت فقط از طریق
    فرمان مدیریتی محدود یا رابط مدیریت کاربران (FR-020). ورود فقط نام‌کاربری/رمز عبور است؛
    هیچ عامل دومی وجود ندارد (اصل V نسخهٔ ۳.۰.۰).
    """

    class Role(models.TextChoices):
        RECRUITER = "recruiter", "کارشناس جذب"
        HIRING_MANAGER = "hiring_manager", "مدیر استخدام"
        HR_MANAGER = "hr_manager", "مدیر HR"
        SYSTEM_OPERATOR = "system_operator", "اپراتور سامانه"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.CharField(max_length=20, choices=Role.choices)
    created_by = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="created_accounts"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["role"])]

    def __str__(self) -> str:
        return f"{self.username} ({self.get_role_display()})"


class StaffLoginRateCounter(models.Model):
    """
    شمارنده نرخ اتمی برای تلاش‌های ورود کارمند (FR-047). الگوی `OtpRateCounter` در
    `apps/candidates/models.py` را تکرار می‌کند: پنجره ثابت در دیتابیس (نه حافظه محلی یک
    process) تا میان چند worker سازگار بماند. کلیدها **حساب** و **IP** جداگانه شمارش می‌شوند.
    """

    class Scope(models.TextChoices):
        ACCOUNT = "account", "حساب"
        IP = "ip", "آدرس IP"

    scope = models.CharField(max_length=10, choices=Scope.choices)
    key = models.CharField(max_length=128)
    window_start = models.DateTimeField()
    count = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["scope", "key", "window_start"], name="uniq_staff_login_rate_window"
            )
        ]
