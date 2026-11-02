"""
T062a (رفع یافته M3 در تحلیل، FR-045): پس از ۳۰ دقیقه بی‌فعالیتی یا سقف مطلق، نشست کارمند
باید باطل باشد؛ کارمند غیرفعال‌شده نباید بتواند نشست قبلی خود را ادامه دهد. اصل V نسخهٔ ۳.۰.۰:
ورود تک‌مرحله‌ای (بدون عامل دوم).
"""
import time

import pytest
from django.conf import settings
from django.test import Client

pytestmark = pytest.mark.django_db


def _login_staff(client: Client, staff_user, password: str) -> None:
    staff_user.set_password(password)
    staff_user.save(update_fields=["password"])
    login_resp = client.post(
        "/api/v1/auth/staff/login", {"username": staff_user.username, "password": password}, content_type="application/json"
    )
    assert login_resp.status_code == 200


def test_staff_session_is_invalidated_after_idle_timeout(recruiter, job_position_factory):
    client = Client()
    _login_staff(client, recruiter, "a-strong-password-123")

    ok_resp = client.get("/api/v1/staff/applications")
    assert ok_resp.status_code == 200

    # شبیه‌سازی گذشت بیش از ۳۰ دقیقه بی‌فعالیتی با دست‌کاری مستقیم `last_activity` ذخیره‌شده در
    # خودِ نشست سروری (نه کوکی کلاینت) — معادل واقعیِ گذشت زمان، بدون نیاز به صبر واقعی در تست.
    session = client.session
    session["last_activity"] = time.time() - settings.STAFF_SESSION_IDLE_TIMEOUT_SECONDS - 1
    session.save()

    idle_resp = client.get("/api/v1/staff/applications")
    assert idle_resp.status_code in (401, 403)


def test_staff_session_within_idle_window_remains_valid(recruiter):
    client = Client()
    _login_staff(client, recruiter, "a-strong-password-123")

    session = client.session
    session["last_activity"] = time.time() - (settings.STAFF_SESSION_IDLE_TIMEOUT_SECONDS - 60)
    session.save()

    resp = client.get("/api/v1/staff/applications")
    assert resp.status_code == 200


def test_deactivated_staff_account_cannot_continue_its_existing_session(recruiter):
    """
    حتی بدون انقضای نشست، غیرفعال‌کردن حساب باید بلافاصله دسترسی درخواست بعدی را قطع کند —
    نه فقط ورودهای تازه را مسدود کند.
    """
    client = Client()
    _login_staff(client, recruiter, "a-strong-password-123")

    ok_resp = client.get("/api/v1/staff/applications")
    assert ok_resp.status_code == 200

    recruiter.is_active = False
    recruiter.save(update_fields=["is_active"])

    blocked_resp = client.get("/api/v1/staff/applications")
    assert blocked_resp.status_code in (401, 403)


# test_candidate_session_idle_timeout_invalidates_cookie و
# test_candidate_session_absolute_timeout_invalidates_cookie_even_if_recently_active حذف شدند —
# اصل V نسخهٔ ۲.۰.۰: متقاضی دیگر هیچ کوکی/نشستی ندارد که منقضی یا باطل شود؛ ثبت و پیگیری هر دو
# بدون هیچ احراز هویتی انجام می‌شوند.
