import uuid

from django.db import models


class BackgroundJob(models.Model):
    """صف کار داخلی مبتنی بر PostgreSQL به‌جای Celery/Redis (research.md §۲)."""

    class JobType(models.TextChoices):
        SCAN_ATTACHMENT = "scan_attachment", "اسکن فایل"
        CLEANUP_UPLOAD = "cleanup_upload", "پاک‌سازی بارگذاری یتیم"

    class Status(models.TextChoices):
        PENDING = "pending", "در انتظار"
        IN_PROGRESS = "in_progress", "در حال انجام"
        SUCCEEDED = "succeeded", "موفق"
        FAILED = "failed", "ناموفق"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job_type = models.CharField(max_length=30, choices=JobType.choices)
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    lock_expires_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(auto_now_add=True)
    error_code = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["status", "next_attempt_at"])]
