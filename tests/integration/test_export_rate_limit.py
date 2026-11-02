"""
T057a: محدودیت نرخ خروجی (FR-037a) — ۵ درخواست در ۱۰ دقیقه برای هر حساب کارمند، پس از
احراز هویت/مجوز؛ مرز دقیق، پایان بازه، استقلال حساب‌ها، و رقابت واقعی هم‌زمان روی PostgreSQL.
"""
import threading

import pytest
from django.db import close_old_connections
from django.utils import timezone
from rest_framework.test import APIClient

from apps.reporting.models import ExportRateCounter
from apps.reporting.services import EXPORT_RATE_LIMIT, EXPORT_RATE_WINDOW_SECONDS, _window_start

pytestmark = pytest.mark.django_db(transaction=True)


def test_sixth_request_within_window_is_rejected_with_429_and_retry_after(
    candidate_factory, job_position_factory, hr_manager
):
    client = APIClient()
    client.force_authenticate(user=hr_manager)

    for _ in range(EXPORT_RATE_LIMIT):
        resp = client.post("/api/v1/staff/exports", {"format": "csv"}, format="json")
        assert resp.status_code == 200

    sixth = client.post("/api/v1/staff/exports", {"format": "csv"}, format="json")
    assert sixth.status_code == 429
    assert "Retry-After" in sixth
    assert int(sixth["Retry-After"]) > 0
    assert sixth.json()["code"] == "rate_limited"


def test_fifth_request_is_still_accepted_exactly_at_the_boundary(hr_manager):
    client = APIClient()
    client.force_authenticate(user=hr_manager)

    responses = [client.post("/api/v1/staff/exports", {"format": "csv"}, format="json") for _ in range(5)]
    assert all(r.status_code == 200 for r in responses)


def test_after_window_elapses_the_same_account_is_allowed_again(hr_manager):
    client = APIClient()
    client.force_authenticate(user=hr_manager)

    for _ in range(EXPORT_RATE_LIMIT):
        assert client.post("/api/v1/staff/exports", {"format": "csv"}, format="json").status_code == 200
    assert client.post("/api/v1/staff/exports", {"format": "csv"}, format="json").status_code == 429

    # شبیه‌سازی پایان بازه: شمارنده همان پنجره فعلی را به پنجره‌ای در گذشته منتقل می‌کنیم تا
    # معادل «بازه ۱۰ دقیقه‌ای گذشته» باشد، بدون نیاز به صبر واقعی ۱۰ دقیقه‌ای در تست.
    now = timezone.now()
    current_window = _window_start(now, EXPORT_RATE_WINDOW_SECONDS)
    ExportRateCounter.objects.filter(staff_user_id=str(hr_manager.id), window_start=current_window).update(
        window_start=current_window - timezone.timedelta(seconds=EXPORT_RATE_WINDOW_SECONDS)
    )

    resp = client.post("/api/v1/staff/exports", {"format": "csv"}, format="json")
    assert resp.status_code == 200


def test_rate_limit_is_independent_per_staff_account(staff_user_factory):
    from apps.accounts.models import StaffUser

    hr1 = staff_user_factory(role=StaffUser.Role.HR_MANAGER)
    hr2 = staff_user_factory(role=StaffUser.Role.HR_MANAGER)

    client1 = APIClient()
    client1.force_authenticate(user=hr1)
    for _ in range(EXPORT_RATE_LIMIT):
        assert client1.post("/api/v1/staff/exports", {"format": "csv"}, format="json").status_code == 200
    assert client1.post("/api/v1/staff/exports", {"format": "csv"}, format="json").status_code == 429

    client2 = APIClient()
    client2.force_authenticate(user=hr2)
    resp = client2.post("/api/v1/staff/exports", {"format": "csv"}, format="json")
    assert resp.status_code == 200, "حساب دوم نباید از محدودیت حساب اول اثر بگیرد"


def test_concurrent_export_requests_never_exceed_the_limit_on_real_postgres(hr_manager):
    """
    رقابت واقعی: ۱۰ درخواست هم‌زمان (بیش از سقف ۵) ارسال می‌شود؛ قفل اتمی `select_for_update`
    باید تضمین کند که دقیقاً ۵ مورد موفق و بقیه ۴۲۹ بگیرند — نه بیشتر از سقف موفق شود.
    """
    results = []
    lock = threading.Lock()

    def _worker():
        close_old_connections()
        try:
            client = APIClient()
            client.force_authenticate(user=hr_manager)
            resp = client.post("/api/v1/staff/exports", {"format": "csv"}, format="json")
            with lock:
                results.append(resp.status_code)
        finally:
            close_old_connections()

    threads = [threading.Thread(target=_worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    success_count = results.count(200)
    rejected_count = results.count(429)
    assert success_count == EXPORT_RATE_LIMIT
    assert rejected_count == 10 - EXPORT_RATE_LIMIT


def test_rate_limit_counted_only_after_permission_check_passes(
    candidate_factory, job_position_factory, recruiter
):
    """
    پیش از احراز مجوز (نقش غیر hr_manager) نباید شمارنده افزایش یابد — تلاش‌های رد‌شده با ۴۰۳
    نباید سهمیه حساب‌های دیگر/آینده را مصرف کنند.
    """
    client = APIClient()
    client.force_authenticate(user=recruiter)
    for _ in range(EXPORT_RATE_LIMIT + 2):
        resp = client.post("/api/v1/staff/exports", {"format": "csv"}, format="json")
        assert resp.status_code == 403

    assert ExportRateCounter.objects.filter(staff_user_id=str(recruiter.id)).count() == 0
