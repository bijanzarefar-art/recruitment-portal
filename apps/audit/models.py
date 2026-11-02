import uuid

from django.conf import settings
from django.db import models


class AuditEvent(models.Model):
    """
    رویداد حسابرسی برای عملیات حساس (FR-055، اصل VIII). فقط‌افزودنی: نقش برنامه در
    دیتابیس باید فقط حق INSERT روی این جدول داشته باشد (بدون UPDATE/DELETE) — این محدودیت
    در سطح نقش دیتابیس تولید اعمال می‌شود، نه در این مدل.
    هرگز حاوی OTP خام، رمز عبور یا محتوای فایل رزومه نیست.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    staff_actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    candidate_actor = models.ForeignKey(
        "candidates.Candidate", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    action = models.CharField(max_length=100)
    object_type = models.CharField(max_length=100, blank=True)
    object_id = models.CharField(max_length=64, blank=True)
    http_request_id = models.CharField(max_length=64, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["action", "created_at"])]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.action} @ {self.created_at:%Y-%m-%d %H:%M}"
