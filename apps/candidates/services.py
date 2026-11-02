"""
حل‌وفصل متقاضی بدون احراز هویت و نرخ‌محدودسازی جست‌وجوی کد پیگیری (FR-004، FR-043).
اصل V نسخهٔ ۲.۰.۰: دیگر هیچ OTP/نشست متقاضی وجود ندارد.
"""
from datetime import timezone as dt_timezone

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.common.text import normalize_mobile

from .models import Candidate, TrackingLookupRateCounter


class TrackingRateLimitExceeded(Exception):
    pass


def resolve_candidate(mobile: str) -> Candidate:
    """
    مقدار خام فرم را نرمال‌سازی و یک `Candidate` بدون هیچ تأیید هویتی برمی‌گرداند
    (اصل V نسخهٔ ۲.۰.۰). رقابت هم‌زمان روی مقدار موبایل تازه با قید یکتایی دیتابیسی کنترل
    می‌شود، نه با قفل برنامه‌ای.
    """
    normalized = normalize_mobile(mobile)
    try:
        with transaction.atomic():
            return Candidate.objects.create(mobile=normalized)
    except IntegrityError:
        return Candidate.objects.get(mobile=normalized)


def _window_start(now, bucket_seconds: int):
    epoch = int(now.timestamp())
    return timezone.datetime.fromtimestamp(epoch - (epoch % bucket_seconds), tz=dt_timezone.utc)


def enforce_tracking_rate_limit(ip_address: str) -> None:
    """
    نرخ‌محدودسازی جست‌وجوی کد پیگیری بر اساس IP (FR-043؛ آستانهٔ مصوب D9:
    `TRACKING_LOOKUP_IP_LIMIT` در `TRACKING_LOOKUP_IP_WINDOW_SECONDS`). شمارش اتمی با
    `select_for_update()` — دقیقاً همان الگوی `OtpRateCounter`/`ExportRateCounter` قدیمی.
    """
    now = timezone.now()
    window_start = _window_start(now, settings.TRACKING_LOOKUP_IP_WINDOW_SECONDS)

    with transaction.atomic():
        counter, _ = TrackingLookupRateCounter.objects.select_for_update().get_or_create(
            ip_address=ip_address, window_start=window_start, defaults={"count": 0}
        )
        if counter.count >= settings.TRACKING_LOOKUP_IP_LIMIT:
            raise TrackingRateLimitExceeded()
        counter.count = counter.count + 1
        counter.save(update_fields=["count"])
