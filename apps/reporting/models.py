from django.db import models


class ExportRateCounter(models.Model):
    """
    شمارنده نرخ اتمی برای `POST /staff/exports` (FR-037a) — دقیقاً همان الگوی
    `OtpRateCounter` در `apps/candidates/models.py`: پنجره ثابت در دیتابیس به‌جای حافظه
    فرایند، تا میان نشست‌ها و کارگرهای مختلف یکسان و بدون رقابت ناسازگار به‌کار رود.
    """

    staff_user_id = models.CharField(max_length=64)
    window_start = models.DateTimeField()
    count = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["staff_user_id", "window_start"], name="uniq_export_rate_window")
        ]
