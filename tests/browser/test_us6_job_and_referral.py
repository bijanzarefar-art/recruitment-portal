"""
T061: جریان واقعی مرورگری US6 — مدیر HR وارد می‌شود، موقعیت جدید می‌سازد، آن را می‌بندد، پرونده‌
ای را به کارشناس جذب ارجاع می‌دهد، سپس همان کارشناس وارد می‌شود و پرونده ارجاع‌شده را می‌بیند؛
لغو ارجاع در درخواست بعدی دسترسی را قطع می‌کند (FR-038 تا FR-041).
"""
import pytest
from django.utils import timezone
from playwright.sync_api import expect

from apps.applications.models import Application, PrivacyNotice

pytestmark = pytest.mark.django_db(transaction=True)


def _login(page, live_server, staff_user, password: str):
    # ورود تک‌مرحله‌ای: فقط نام‌کاربری/رمز عبور (اصل V نسخهٔ ۳.۰.۰ — بدون عامل دوم).
    page.goto(f"{live_server.url}/staff/login")
    page.fill("#username", staff_user.username)
    page.fill("#password", password)
    page.click("#login-button")
    page.wait_for_url("**/staff/dashboard")


def test_hr_manager_creates_closes_job_and_assigns_referral_then_recruiter_sees_it(
    live_server, page, browser, candidate_factory, job_position_factory, hr_manager, recruiter
):
    PrivacyNotice.objects.create(version="us6-v1", body="x", published_at=timezone.now())
    candidate = candidate_factory()
    job = job_position_factory(title="کارشناس پیش از US6")

    application = Application.objects.create(
        tracking_code="us6browsercode01",
        candidate=candidate,
        job_position=job,
        first_name="آرش",
        last_name="نوری",
        mobile_snapshot=candidate.mobile,
        city="اهواز",
        employment=Application.Employment.FULL_TIME,
        experience=Application.Experience.YEARS_1_3,
        availability=Application.Availability.IMMEDIATE,
        last_title="x",
        last_company="y",
        status=Application.Status.NEW,
        idempotency_key="us6-browser-k1",
    )

    hr_manager.set_password("a-strong-password-123")
    hr_manager.save(update_fields=["password"])

    _login(page, live_server, hr_manager, "a-strong-password-123")

    # ۱. ایجاد موقعیت جدید واقعی از طریق رابط — همیشه `draft` (FR-039a).
    page.click("text=موقعیت‌های شغلی")
    page.wait_for_url("**/staff/jobs")
    expect(page.locator("#create-job-form")).to_be_visible(timeout=10000)
    page.fill("#job-title", "کارشناس تولید محتوا (US6)")
    page.click("#create-job-submit")
    row = page.locator("#jobs-rows tr", has_text="کارشناس تولید محتوا (US6)")
    expect(row).to_contain_text("پیش‌نویس", timeout=10000)

    # ۲. فعال‌سازی (draft→open)، سپس بستن (open→closed)، سپس بازگشایی (closed→open).
    row.get_by_role("button", name="فعال‌سازی").click()
    expect(row).to_contain_text("باز", timeout=10000)
    row.get_by_role("button", name="بستن").click()
    expect(row).to_contain_text("بسته", timeout=10000)
    row.get_by_role("button", name="بازگشایی").click()
    expect(row).to_contain_text("باز", timeout=10000)

    # ۳. ارجاع پرونده موجود به کارشناس جذب از صفحه جزئیات.
    page.goto(f"{live_server.url}/staff/applications/{application.id}")
    expect(page.locator("#detail-card")).to_be_visible(timeout=10000)
    # انتخاب از فهرست کارمندان واجد شرایط (D12) — نه وارد کردن شناسه به‌صورت دستی.
    select = page.locator("#assign-reviewer-id")
    expect(select.locator(f'option[value="{recruiter.id}"]')).to_have_count(1, timeout=10000)
    page.select_option("#assign-reviewer-id", str(recruiter.id))
    page.click("#assign-submit")
    expect(page.locator("#reviewer-current")).to_contain_text("کارشناس جذب", timeout=10000)

    # ۴. همان کارشناس وارد می‌شود و پرونده ارجاع‌شده را در داشبورد واقعی می‌بیند.
    recruiter.set_password("a-strong-password-456")
    recruiter.save(update_fields=["password"])
    # نشست کاملاً مستقل (context جدا، نه فقط تب جدید) تا کوکی hr_manager و recruiter قاطی نشود.
    recruiter_context = browser.new_context()
    page2 = recruiter_context.new_page()
    _login(page2, live_server, recruiter, "a-strong-password-456")
    page2.fill("#search-box", "آرش")
    page2.click("#apply-filters")
    expect(page2.locator("#result-rows")).to_contain_text("us6browsercode01", timeout=10000)

    # ۵. لغو ارجاع از صفحه مدیر و بررسی قطع دسترسی در درخواست بعدی همان کارشناس.
    page.click("#revoke-submit")
    expect(page.locator("#reviewer-current")).to_contain_text("هنوز هیچ ارجاعی", timeout=10000)

    page2.goto(f"{live_server.url}/staff/applications/{application.id}")
    expect(page2.locator("#error-state")).to_be_visible(timeout=10000)
