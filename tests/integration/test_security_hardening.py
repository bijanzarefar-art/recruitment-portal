"""
T062/T088: سخت‌سازی نشست کارمند (اصل V نسخهٔ ۳.۰.۰، FR-045, FR-046, FR-048).

اصل V نسخهٔ ۲.۰.۰ مفهوم «نشست متقاضی» را حذف کرد و نسخهٔ ۳.۰.۰ عامل دوم را نیز حذف کرد؛
سناریوهای مربوط به آن‌ها دیگر موضوعیت ندارند. این فایل فقط سناریوهای معتبر
نشست/CSRF/session-fixation کارمند را نگه می‌دارد — ورود اکنون تک‌مرحله‌ای است.
"""
import pytest
from django.test import Client, override_settings

pytestmark = pytest.mark.django_db


def _login_staff(client: Client, staff_user, password: str) -> None:
    staff_user.set_password(password)
    staff_user.save(update_fields=["password"])
    login_resp = client.post(
        "/api/v1/auth/staff/login",
        {"username": staff_user.username, "password": password},
        content_type="application/json",
    )
    assert login_resp.status_code == 200


def test_staff_login_session_key_is_rotated_not_fixed(recruiter):
    """
    بررسی ضدِ session fixation: Django هنگام `login()` کلید نشست را چرخش می‌دهد (در صورت نبود
    نشست قبلی) یا در صورت تغییر کاربر آن را کاملاً flush می‌کند؛ کلید نشست پیش و پس از MFA باید
    متفاوت باشد، نه همان مقداری که کلاینت از ابتدا داشت.
    """
    client = Client()
    client.get("/staff/login")  # یک نشست ناشناس اولیه (برای get_token) ایجاد می‌شود.
    pre_login_key = client.session.session_key

    _login_staff(client, recruiter, "a-strong-password-123")
    post_login_key = client.session.session_key

    assert post_login_key is not None
    assert post_login_key != pre_login_key


def test_logout_invalidates_the_staff_session(recruiter):
    """خروج کارمند باید فوراً نشست او را باطل کند؛ درخواست بعدی به مسیر کارمند رد می‌شود."""
    client = Client()
    _login_staff(client, recruiter, "a-strong-password-123")
    assert client.get("/api/v1/staff/applications").status_code == 200

    logout_resp = client.post("/api/v1/auth/staff/logout")
    assert logout_resp.status_code in (200, 204)

    assert client.get("/api/v1/staff/applications").status_code in (401, 403)


@override_settings(
    SESSION_COOKIE_SECURE=True,
    CSRF_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    CSRF_COOKIE_SAMESITE="Lax",
    DEBUG=False,
)
def test_cookie_security_attributes_match_production_like_settings(recruiter):
    """
    زیر تنظیمات شبیه‌تولید (`Secure=True`، `DEBUG=False`)، کوکی نشست کارمند باید
    `Secure`/`HttpOnly`/`SameSite=Lax` مناسب داشته باشد؛ کوکی CSRF باید `Secure` باشد اما
    قابل‌خوانش توسط جاوااسکریپت (برای fetch) بماند — یعنی `HttpOnly=False`.
    """
    client = Client(enforce_csrf_checks=False)
    client.get("/staff/login")  # صادرکردن کوکی csrftoken.

    csrf_cookie = client.cookies.get("csrftoken")
    assert csrf_cookie is not None
    assert csrf_cookie["secure"] is True
    assert not csrf_cookie["httponly"]  # باید توسط جاوااسکریپت fetch خوانده شود.
    assert csrf_cookie["samesite"] == "Lax"

    _login_staff(client, recruiter, "a-strong-password-123")
    staff_cookie = client.cookies.get("staff_sessionid")
    assert staff_cookie is not None
    assert staff_cookie["secure"] is True
    assert staff_cookie["httponly"]
    assert staff_cookie["samesite"] == "Lax"


def test_unauthenticated_request_to_staff_path_is_rejected():
    """بدون هیچ نشستی (نه کوکی کارمند، نه چیز دیگر)، مسیرهای staff/* باید رد شوند."""
    client = Client()
    for path in ("/api/v1/staff/applications", "/api/v1/staff/applications/metrics", "/api/v1/staff/jobs"):
        resp = client.get(path)
        assert resp.status_code in (401, 403), f"{path} باید بدون نشست رد شود"
