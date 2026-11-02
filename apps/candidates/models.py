import uuid

from django.db import models


class Candidate(models.Model):
    """
    متقاضی **بدون هیچ هویت تأییدشده** (اصل V نسخهٔ ۲.۰.۰). `mobile` فقط مقدار خوداظهاری فرم
    است که برای اعمال قاعدهٔ جلوگیری از ثبت تکراری (FR-008) یکتا نگه داشته می‌شود — صفر معنای
    احراز هویت دارد. تغییر `mobile` یک رکورد موجود فقط از طریق فرمان مدیریتی
    `transfer_candidate_mobile` (T025a، FR-064) مجاز است.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    mobile = models.CharField(max_length=15, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["mobile"])]

    def __str__(self) -> str:
        return self.mobile


class TrackingLookupRateCounter(models.Model):
    """شمارندهٔ اتمی نرخ‌محدودسازی جست‌وجوی کد پیگیری بر اساس IP (FR-043)."""

    ip_address = models.CharField(max_length=64)
    window_start = models.DateTimeField()
    count = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["ip_address", "window_start"], name="uniq_tracking_rate_window")
        ]
