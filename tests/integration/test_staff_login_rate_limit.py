"""
FR-047: محدودسازی نرخ تلاش ورود کارمند بر اساس ترکیب حساب و IP، با شمارنده اتمیک دیتابیسی.
آزمون‌ها: رسیدن به حد، پایان پنجره، جداسازی کلیدها، رفتار هم‌زمان، و پاسخ قراردادی (۴۲۹ +
Retry-After). آستانه از settings خوانده می‌شود (پیشنهاد، نه سیاست مصوب).
"""
import threading

import pytest
from django.db import close_old_connections
from rest_framework.test import APIClient

from apps.accounts.models import StaffLoginRateCounter
from apps.accounts.services import _window_start
from django.utils import timezone

pytestmark = pytest.mark.django_db(transaction=True)


def _login(client, username="someone", password="wrong-password", ip="1.1.1.1"):
    return client.post(
        "/api/v1/auth/staff/login",
        {"username": username, "password": password},
        format="json",
        REMOTE_ADDR=ip,
    )


def test_account_reaches_limit_then_returns_429_with_retry_after(settings):
    settings.STAFF_LOGIN_ACCOUNT_LIMIT = 3
    settings.STAFF_LOGIN_IP_LIMIT = 100
    client = APIClient()

    for _ in range(3):
        assert _login(client).status_code == 401  # اعتبارنامه غلط، اما هنوز زیر سقف.

    blocked = _login(client)
    assert blocked.status_code == 429
    assert "Retry-After" in blocked
    assert int(blocked["Retry-After"]) > 0


def test_window_expiry_allows_attempts_again(settings):
    settings.STAFF_LOGIN_ACCOUNT_LIMIT = 2
    settings.STAFF_LOGIN_IP_LIMIT = 100
    client = APIClient()

    assert _login(client).status_code == 401
    assert _login(client).status_code == 401
    assert _login(client).status_code == 429

    # انتقال شمارندهٔ همان پنجره به گذشته = معادل گذشت واقعی بازه (پنجرهٔ حساب: ۱۵ دقیقه).
    now = timezone.now()
    window = settings.STAFF_LOGIN_ACCOUNT_WINDOW_SECONDS
    current = _window_start(now, window)
    StaffLoginRateCounter.objects.filter(
        scope=StaffLoginRateCounter.Scope.ACCOUNT, window_start=current
    ).update(window_start=current - timezone.timedelta(seconds=window))

    assert _login(client).status_code == 401  # دوباره مجاز.


def test_different_accounts_are_counted_independently(settings):
    settings.STAFF_LOGIN_ACCOUNT_LIMIT = 2
    settings.STAFF_LOGIN_IP_LIMIT = 100
    client = APIClient()

    assert _login(client, username="alice", ip="2.2.2.2").status_code == 401
    assert _login(client, username="alice", ip="2.2.2.2").status_code == 401
    assert _login(client, username="alice", ip="2.2.2.2").status_code == 429

    # حساب دیگر از محدودیت حساب اول اثر نمی‌گیرد.
    assert _login(client, username="bob", ip="2.2.2.2").status_code == 401


def test_ip_limit_blocks_across_many_accounts_from_same_ip(settings):
    """فرض FR-047 «ترکیب حساب و IP» است: مهاجم از یک IP با حساب‌های گوناگون هم محدود می‌شود."""
    settings.STAFF_LOGIN_ACCOUNT_LIMIT = 100
    settings.STAFF_LOGIN_IP_LIMIT = 3
    client = APIClient()

    for i in range(3):
        assert _login(client, username=f"user{i}", ip="9.9.9.9").status_code == 401
    assert _login(client, username="user99", ip="9.9.9.9").status_code == 429


def test_concurrent_attempts_never_exceed_the_limit_on_real_postgres(settings):
    settings.STAFF_LOGIN_ACCOUNT_LIMIT = 5
    settings.STAFF_LOGIN_IP_LIMIT = 1000

    results = []
    lock = threading.Lock()

    def _worker():
        close_old_connections()
        try:
            client = APIClient()
            resp = _login(client, username="race-user", ip="3.3.3.3")
            with lock:
                results.append(resp.status_code)
        finally:
            close_old_connections()

    threads = [threading.Thread(target=_worker) for _ in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert results.count(401) == 5, f"دقیقاً ۵ تلاش باید عبور کنند؛ دریافت‌شده: {results}"
    assert results.count(429) == 7


# test_invalid_mfa_challenges_are_counted_against_the_ip_so_the_path_cannot_be_spammed و
# test_valid_account_mfa_attempts_count_against_that_account حذف شدند — اصل V نسخهٔ ۳.۰.۰:
# مسیر /auth/staff/mfa/verify دیگر وجود ندارد؛ ورود تک‌مرحله‌ای فقط از /auth/staff/login
# نرخ‌محدود می‌شود (همان پوشش که در بقیهٔ این فایل آزموده شده است).


def test_spoofed_x_forwarded_for_cannot_change_the_ip_key_by_default(settings):
    """
    باگ بحرانی که در همین دور یافت و رفع شد: قبلاً `X-Forwarded-For` بی‌قید خوانده می‌شد و هر
    کلاینت با فرستادن مقدار تصادفی برای هر درخواست، کلید IP را عوض می‌کرد و از سقف فرار می‌کرد.
    پیش‌فرض `TRUSTED_PROXY_COUNT=0` باید هدر را کاملاً نادیده بگیرد.
    """
    settings.STAFF_LOGIN_ACCOUNT_LIMIT = 1000
    settings.STAFF_LOGIN_IP_LIMIT = 3
    settings.TRUSTED_PROXY_COUNT = 0
    client = APIClient()

    # ۱۰ درخواست، هر بار با X-Forwarded-For جعلی متفاوت، اما REMOTE_ADDR ثابت.
    for i in range(10):
        client.post(
            "/api/v1/auth/staff/login",
            {"username": f"spoof{i}", "password": "x"},
            format="json",
            REMOTE_ADDR="7.7.7.7",
            HTTP_X_FORWARDED_FOR=f"10.0.0.{i}",
        )

    # پس از ۳ تلاش، IP واقعی باید قفل شده باشد — نه اینکه با هر XFF جدید از نو شروع شود.
    blocked = client.post(
        "/api/v1/auth/staff/login",
        {"username": "spoof-final", "password": "x"},
        format="json",
        REMOTE_ADDR="7.7.7.7",
        HTTP_X_FORWARDED_FOR="192.168.1.1",
    )
    assert blocked.status_code == 429


def test_with_trusted_proxy_the_rightmost_hop_is_used_not_client_supplied_leftmost(settings):
    """
    با یک پراکسی معتبر (`TRUSTED_PROXY_COUNT=1`)، آدرس واقعی کلاینت عنصر انتهای زنجیره است؛
    عناصر سمت چپ که کلاینت ساخته را نباید باور کرد.
    """
    from apps.accounts.services import _client_ip

    settings.TRUSTED_PROXY_COUNT = 1

    class _Req:
        META = {"REMOTE_ADDR": "203.0.113.9", "HTTP_X_FORWARDED_FOR": "1.2.3.4, 198.51.100.7"}

    # زنجیره: کلاینت واقعی=198.51.100.7 (سمت راست), مقادیر جعلی=1.2.3.4 (سمت چپ).
    assert _client_ip(_Req()) == "198.51.100.7"


def test_forwarded_header_ignored_when_chain_shorter_than_trusted_hops(settings):
    from apps.accounts.services import _client_ip

    settings.TRUSTED_PROXY_COUNT = 2

    class _Req:
        META = {"REMOTE_ADDR": "203.0.113.9", "HTTP_X_FORWARDED_FOR": "1.2.3.4"}

    # زنجیره کوتاه‌تر از تعداد پراکسی مورد اعتماد → شکست امن به REMOTE_ADDR.
    assert _client_ip(_Req()) == "203.0.113.9"


def test_login_still_works_normally_when_no_forwarded_header_present(settings):
    settings.STAFF_LOGIN_ACCOUNT_LIMIT = 5
    settings.STAFF_LOGIN_IP_LIMIT = 5
    client = APIClient()
    resp = _login(client, username="normal-user", ip="8.8.8.8")
    assert resp.status_code == 401  # تلاش عادی، زیر سقف.


def test_approved_thresholds_are_account_5_per_15min_and_ip_15_per_20min():
    """D6 (مصوب): مقادیر پیش‌فرض باید دقیقاً همان‌هایی باشند که مالک پروژه تأیید کرد."""
    from django.conf import settings as dj_settings

    assert dj_settings.STAFF_LOGIN_ACCOUNT_LIMIT == 5
    assert dj_settings.STAFF_LOGIN_ACCOUNT_WINDOW_SECONDS == 15 * 60
    assert dj_settings.STAFF_LOGIN_IP_LIMIT == 15
    assert dj_settings.STAFF_LOGIN_IP_WINDOW_SECONDS == 20 * 60


def test_account_and_ip_windows_are_independent():
    """
    پنجرهٔ IP (۲۰ دقیقه) از پنجرهٔ حساب (۱۵ دقیقه) جداست؛ شمارنده‌هایشان نباید با هم جمع شوند
    یا هم‌زمان منقضی شوند.
    """
    from django.conf import settings as dj_settings
    from apps.accounts.services import _window_start
    from datetime import timezone as dt_timezone

    now = timezone.datetime(2026, 1, 1, 12, 0, 0, tzinfo=dt_timezone.utc)
    acct = _window_start(now, dj_settings.STAFF_LOGIN_ACCOUNT_WINDOW_SECONDS)
    ip = _window_start(now, dj_settings.STAFF_LOGIN_IP_WINDOW_SECONDS)

    # 12:00 → پنجرهٔ حساب از 12:00 شروع می‌شود (۱۵ دقیقه)، پنجرهٔ IP از 12:00 هم (۲۰ دقیقه)
    # اما نزدیک مرز، شروع‌هایشان لزوماً یکی نیست.
    at_1214 = timezone.datetime(2026, 1, 1, 12, 14, 59, tzinfo=dt_timezone.utc)
    at_1215 = timezone.datetime(2026, 1, 1, 12, 15, 0, tzinfo=dt_timezone.utc)
    at_1220 = timezone.datetime(2026, 1, 1, 12, 20, 0, tzinfo=dt_timezone.utc)

    assert acct.minute == 0
    assert ip.minute == 0
    # در 12:14:59 پنجرهٔ حساب هنوز همان است؛ در 12:15 عوض می‌شود.
    assert _window_start(at_1214, 15 * 60) == acct
    assert _window_start(at_1215, 15 * 60) != acct
    # اما پنجرهٔ IP در 12:15 هنوز عوض نشده؛ فقط در 12:20.
    assert _window_start(at_1215, 20 * 60) == ip
    assert _window_start(at_1220, 20 * 60) != ip
