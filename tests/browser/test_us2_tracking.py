"""
T082 (جایگزین T040): پیگیری فقط با کد پیگیری — بدون هیچ OTP/نشست (اصل V نسخهٔ ۲.۰.۰؛
FR-012, FR-016). با Playwright واقعی روی سرور زنده اجرا می‌شود (نه skip).
"""
import pytest
from django.utils import timezone
from playwright.sync_api import expect

from apps.applications.models import Application, PrivacyNotice

pytestmark = pytest.mark.django_db(transaction=True)


def _create_application(candidate, job, suffix: str) -> Application:
    return Application.objects.create(
        tracking_code=f"track{suffix}0000",
        candidate=candidate,
        job_position=job,
        first_name="کاربر",
        last_name="تست",
        mobile_snapshot=candidate.mobile,
        city="تهران",
        employment=Application.Employment.FULL_TIME,
        experience=Application.Experience.YEARS_1_3,
        availability=Application.Availability.IMMEDIATE,
        last_title="x",
        last_company="y",
        status=Application.Status.NEW,
        idempotency_key=f"seed-{suffix}",
    )


def test_tracking_code_shows_status_without_any_authentication(live_server, page, candidate_factory, job_position_factory):
    candidate = candidate_factory(mobile="09120009001")
    job = job_position_factory(title="موقعیت اول")
    PrivacyNotice.objects.create(version="track-v1", body="x", published_at=timezone.now())
    application = _create_application(candidate, job, "a")

    page.goto(f"{live_server.url}/track")
    page.fill("#tracking-code", application.tracking_code)
    page.click("#track-submit")

    expect(page.locator("#result-section")).to_be_visible()
    expect(page.locator("#result-job")).to_contain_text("موقعیت اول")


def test_same_tracking_code_is_visible_from_a_fully_independent_browser_context(
    live_server, page, browser, candidate_factory, job_position_factory
):
    """
    اصل V نسخهٔ ۲.۰.۰: دیگر هیچ مفهوم نشستی وجود ندارد — دانستن کد پیگیری، تنها و کافی‌ترین
    شرط مشاهدهٔ وضعیت است، حتی از یک کانتکست مرورگر کاملاً مستقل (بدون هیچ کوکی مشترک).
    """
    candidate = candidate_factory(mobile="09120009002")
    job = job_position_factory(title="موقعیت محرمانه نیست")
    PrivacyNotice.objects.create(version="track-v2", body="x", published_at=timezone.now())
    application = _create_application(candidate, job, "c")

    other_context = browser.new_context()
    other_page = other_context.new_page()
    try:
        other_page.goto(f"{live_server.url}/track")
        other_page.fill("#tracking-code", application.tracking_code)
        other_page.click("#track-submit")
        expect(other_page.locator("#result-section")).to_be_visible()
        expect(other_page.locator("#result-job")).to_contain_text("موقعیت محرمانه نیست")
    finally:
        other_context.close()


def test_wrong_tracking_code_shows_error_not_someone_elses_data(
    live_server, page, candidate_factory, job_position_factory
):
    candidate = candidate_factory(mobile="09120009003")
    job = job_position_factory(title="موقعیت واقعی")
    PrivacyNotice.objects.create(version="track-v3", body="x", published_at=timezone.now())
    _create_application(candidate, job, "d")

    page.goto(f"{live_server.url}/track")
    page.fill("#tracking-code", "this-code-does-not-exist")
    page.click("#track-submit")

    expect(page.locator("#result-section")).to_be_hidden()
    expect(page.locator('[data-error-for="tracking-code"]')).to_contain_text("نامعتبر")
