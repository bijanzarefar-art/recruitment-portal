"""
T081: محدودیت نرخ جست‌وجوی کد پیگیری بر اساس IP (FR-043) — ۲۰ تلاش در هر IP در هر ۱۰ دقیقه
(D9 در docs/decisions.md)؛ مرز دقیق، پایان بازه، استقلال IPها، و رقابت واقعی هم‌زمان روی
PostgreSQL. اصل V نسخهٔ ۲.۰.۰: این تنها خط دفاع در برابر حدس‌زدن کد پیگیری است.
"""
import threading

import pytest
from django.conf import settings
from django.db import close_old_connections
from django.utils import timezone
from rest_framework.test import APIClient

from apps.candidates.models import TrackingLookupRateCounter
from apps.candidates.services import _window_start

pytestmark = pytest.mark.django_db(transaction=True)

LIMIT = settings.TRACKING_LOOKUP_IP_LIMIT
WINDOW_SECONDS = settings.TRACKING_LOOKUP_IP_WINDOW_SECONDS


def _lookup(client, ip="203.0.113.5"):
    return client.get("/api/v1/track/does-not-matter-code", REMOTE_ADDR=ip)


def test_request_beyond_limit_is_rejected_with_429_and_retry_after():
    client = APIClient()
    ip = "203.0.113.10"

    for _ in range(LIMIT):
        resp = _lookup(client, ip)
        assert resp.status_code == 404  # کد وجود ندارد، اما هنوز زیر سقف مجاز است

    over_limit = _lookup(client, ip)
    assert over_limit.status_code == 429
    assert "Retry-After" in over_limit
    assert int(over_limit["Retry-After"]) > 0


def test_limit_th_request_is_still_accepted_exactly_at_the_boundary():
    client = APIClient()
    ip = "203.0.113.11"
    responses = [_lookup(client, ip) for _ in range(LIMIT)]
    assert all(r.status_code == 404 for r in responses)


def test_after_window_elapses_the_same_ip_is_allowed_again():
    client = APIClient()
    ip = "203.0.113.12"

    for _ in range(LIMIT):
        assert _lookup(client, ip).status_code == 404
    assert _lookup(client, ip).status_code == 429

    now = timezone.now()
    current_window = _window_start(now, WINDOW_SECONDS)
    TrackingLookupRateCounter.objects.filter(ip_address=ip, window_start=current_window).update(
        window_start=current_window - timezone.timedelta(seconds=WINDOW_SECONDS)
    )

    assert _lookup(client, ip).status_code == 404


def test_rate_limit_is_independent_per_ip():
    client = APIClient()
    ip1, ip2 = "203.0.113.20", "203.0.113.21"

    for _ in range(LIMIT):
        assert _lookup(client, ip1).status_code == 404
    assert _lookup(client, ip1).status_code == 429

    assert _lookup(client, ip2).status_code == 404, "IP دوم نباید از محدودیت IP اول اثر بگیرد"


def test_concurrent_lookups_never_exceed_the_limit_on_real_postgres():
    """
    رقابت واقعی: درخواست‌های هم‌زمان بیش از سقف ارسال می‌شود؛ قفل اتمی `select_for_update`
    باید تضمین کند دقیقاً به‌اندازهٔ سقف موفق (غیر ۴۲۹) و بقیه ۴۲۹ بگیرند.
    """
    ip = "203.0.113.30"
    results = []
    lock = threading.Lock()

    def _worker():
        close_old_connections()
        try:
            client = APIClient()
            resp = _lookup(client, ip)
            with lock:
                results.append(resp.status_code)
        finally:
            close_old_connections()

    total_requests = LIMIT + 10
    threads = [threading.Thread(target=_worker) for _ in range(total_requests)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    allowed_count = results.count(404)
    rejected_count = results.count(429)
    assert allowed_count == LIMIT
    assert rejected_count == total_requests - LIMIT


def test_valid_and_invalid_code_both_count_against_the_same_limit():
    """FR-044: شمارش نرخ باید پیش از جست‌وجوی دیتابیس اعمال شود، صرف‌نظر از معتبربودن کد."""
    client = APIClient()
    ip = "203.0.113.40"

    for _ in range(LIMIT):
        assert _lookup(client, ip).status_code == 404

    over_limit = client.get("/api/v1/track/any-code-at-all", REMOTE_ADDR=ip)
    assert over_limit.status_code == 429
