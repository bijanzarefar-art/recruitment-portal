import uuid

from django.db import models


class JobPosition(models.Model):
    """
    موقعیت شغلی (FR-038, FR-039, FR-039a). چرخه وضعیت صریح و قطعی (تصمیم کاربر، نه ابهام):
    `draft → open`، `open → closed`، `closed → open` (بازگشایی). فقط `open` پذیرای درخواست
    جدید است؛ بدون `is_published` جدا — خودِ `draft` معادل «منتشرنشده» است. حذف فیزیکی ممنوع.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "پیش‌نویس"
        OPEN = "open", "باز"
        CLOSED = "closed", "بسته"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    department = models.CharField(max_length=200, blank=True)
    location = models.CharField(max_length=200, blank=True)
    # شایستگی‌ها/صلاحیت‌های احراز شغل — هر خط یک مورد؛ هم به متقاضی (قبل از ثبت درخواست) و هم
    # به کارمند HR (در فهرست مدیریت) نمایش داده می‌شود.
    requirements = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["status"])]

    def __str__(self) -> str:
        return self.title

    @property
    def is_open_for_applications(self) -> bool:
        return self.status == self.Status.OPEN
