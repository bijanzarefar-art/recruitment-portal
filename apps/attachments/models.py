import uuid

from django.db import models


class Attachment(models.Model):
    """فراداده فایل رزومه؛ سبک، در پرس‌وجوهای فهرست/آمار/خروجی قابل‌واکشی (FR-049 تا FR-053)."""

    class ScanStatus(models.TextChoices):
        PENDING = "pending", "در انتظار بررسی"
        QUARANTINED = "quarantined", "قرنطینه"
        CLEAN = "clean", "سالم"
        REJECTED = "rejected", "رد‌شده"
        SCAN_FAILED = "scan_failed", "بررسی ناموفق"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    candidate = models.ForeignKey(
        "candidates.Candidate", null=True, blank=True, on_delete=models.CASCADE, related_name="attachments"
    )
    application = models.OneToOneField(
        "applications.Application", null=True, blank=True, on_delete=models.CASCADE, related_name="resume"
    )
    upload_attempt_key = models.CharField(max_length=128)
    original_filename = models.CharField(max_length=255)
    detected_mime_type = models.CharField(max_length=128, blank=True)
    size_bytes = models.PositiveIntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True)
    scan_status = models.CharField(max_length=20, choices=ScanStatus.choices, default=ScanStatus.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["candidate", "application"]),
            models.Index(fields=["scan_status", "created_at"]),
        ]

    @property
    def is_downloadable(self) -> bool:
        return self.scan_status == self.ScanStatus.CLEAN


class AttachmentContent(models.Model):
    """محتوای باینری فایل، یک‌به‌یک، هرگز در serializer عمومی/پنل مدیریت (اصل I، FR-052)."""

    attachment = models.OneToOneField(Attachment, on_delete=models.CASCADE, primary_key=True, related_name="content")
    data = models.BinaryField()

    # قید دیتابیس `octet_length(data) BETWEEN 1 AND 5242880` با RunSQL در مهاجرت
    # 0002_attachmentcontent_size_check اعمال می‌شود (CheckConstraint استاندارد Django
    # تابع octet_length پورتال‌ناپذیر PostgreSQL را پشتیبانی نمی‌کند).
