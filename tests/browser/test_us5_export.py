"""
T057: تست مرورگری خروجی‌گیری واقعی (FR-032 تا FR-037) — ورود تک‌مرحله‌ای (اصل V نسخهٔ ۳.۰.۰)
→ ناوبری به صفحه خروجی → انتخاب فرمت/ستون‌ها → دانلود واقعی فایل.
"""
import pytest
from django.utils import timezone
from playwright.sync_api import expect

from apps.applications.models import Application, PrivacyNotice

pytestmark = pytest.mark.django_db(transaction=True)


def _create_application(candidate, job):
    return Application.objects.create(
        tracking_code="exportbrowser001",
        candidate=candidate,
        job_position=job,
        first_name="زهرا",
        last_name="کریمی",
        mobile_snapshot=candidate.mobile,
        city="یزد",
        employment=Application.Employment.FULL_TIME,
        experience=Application.Experience.YEARS_1_3,
        availability=Application.Availability.IMMEDIATE,
        last_title="x",
        last_company="y",
        status=Application.Status.NEW,
        idempotency_key="export-browser-k1",
    )


def test_hr_manager_can_download_real_export_from_browser(
    live_server, page, candidate_factory, job_position_factory, hr_manager
):
    candidate = candidate_factory()
    job = job_position_factory(title="کارشناس مالی")
    PrivacyNotice.objects.create(version="export-browser-v1", body="x", published_at=timezone.now())
    _create_application(candidate, job)

    hr_manager.set_password("a-strong-password-123")
    hr_manager.save(update_fields=["password"])

    page.goto(f"{live_server.url}/staff/login")
    page.fill("#username", hr_manager.username)
    page.fill("#password", "a-strong-password-123")
    page.click("#login-button")
    page.wait_for_url("**/staff/dashboard")

    page.click("text=خروجی‌گیری")
    page.wait_for_url("**/staff/exports")
    expect(page.locator("#export-form")).to_be_visible(timeout=10000)

    with page.expect_download() as download_info:
        page.click("#export-submit")
    download = download_info.value
    assert download.suggested_filename == "applications_export.csv"

    path = download.path()
    with open(path, "rb") as f:
        content = f.read()
    assert content.startswith(b"\xef\xbb\xbf")
    assert "exportbrowser001" in content.decode("utf-8-sig")
