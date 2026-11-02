"""
T066: دسترس‌پذیری/RTL/موبایل — برچسب متصل به ورودی، مدیریت فوکوس پنجره خطا، چیدمان راست‌به‌چپ،
و نمایش ارقام فارسی (FR-057 تا FR-059).
"""
import pytest
from django.utils import timezone
from playwright.sync_api import expect

from apps.applications.models import PrivacyNotice

pytestmark = pytest.mark.django_db(transaction=True)


def test_apply_page_is_rtl_with_linked_labels_and_accessible_error_focus(
    live_server, page, job_position_factory
):
    job_position_factory(title="کارشناس آزمایش دسترس‌پذیری")
    PrivacyNotice.objects.create(version="a11y-v1", body="x", published_at=timezone.now())

    page.goto(f"{live_server.url}/apply")

    assert page.locator("html").get_attribute("dir") == "rtl"
    assert page.locator("html").get_attribute("lang") == "fa"

    # هر ورودی اصلی فرم باید برچسب متصل (for=id) داشته باشد، نه فقط متن مجاور بدون ارتباط برنامه‌ای.
    # فرم اکنون تک‌مرحله‌ای است (اصل V نسخهٔ ۲.۰.۰ — بدون OTP)، پس همهٔ این فیلدها از ابتدا نمایانند.
    for input_id in ["first_name", "last_name", "city", "job_position", "employment", "experience", "availability"]:
        label = page.locator(f'label[for="{input_id}"]')
        expect(label).to_have_count(1)
        expect(page.locator(f"#{input_id}")).to_have_count(1)

    error_banner = page.locator('[data-error-for="form"]')
    expect(error_banner).to_have_attribute("role", "alert")


def test_viewport_meta_present_for_mobile_layout(live_server, page):
    page.goto(f"{live_server.url}/apply")
    viewport = page.locator('meta[name="viewport"]')
    expect(viewport).to_have_count(1)
    content = viewport.get_attribute("content")
    assert "width=device-width" in content


def test_staff_login_error_moves_focus_to_accessible_alert(live_server, page, recruiter):
    page.goto(f"{live_server.url}/staff/login")
    page.fill("#username", recruiter.username)
    page.fill("#password", "wrong-password")
    page.click("#login-button")

    error_el = page.locator('[data-error-for="login"]')
    expect(error_el).to_have_text("نام کاربری یا رمز عبور نادرست است.", timeout=10000)
    expect(error_el).to_have_attribute("role", "alert")
    focused_is_error = page.evaluate(
        "document.activeElement === document.querySelector('[data-error-for=\"login\"]')"
    )
    assert focused_is_error


def test_persian_digit_date_display_on_staff_dashboard(live_server, page, hr_manager):
    hr_manager.set_password("a-strong-password-123")
    hr_manager.save(update_fields=["password"])

    # ورود تک‌مرحله‌ای: فقط نام‌کاربری/رمز عبور (اصل V نسخهٔ ۳.۰.۰ — بدون عامل دوم).
    page.goto(f"{live_server.url}/staff/login")
    page.fill("#username", hr_manager.username)
    page.fill("#password", "a-strong-password-123")
    page.click("#login-button")
    page.wait_for_url("**/staff/dashboard")

    assert page.locator("html").get_attribute("dir") == "rtl"
