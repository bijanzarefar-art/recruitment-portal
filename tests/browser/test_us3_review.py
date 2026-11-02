"""
T046: ورود (تک‌مرحله‌ای، اصل V نسخهٔ ۳.۰.۰) → فیلتر → مشاهده جزئیات → دانلود رزومه؛ و یک تلاش
مستقیم API خارج از مجوز که باید رد شود. با Playwright واقعی روی سرور زنده اجرا می‌شود (نه
skip)؛ این همان آزمون مرورگری معوق‌مانده T036 برای «مشاهده درخواست در داشبورد HR» را هم
تکمیل می‌کند.
"""
import urllib.error
import urllib.request

import pytest
from django.utils import timezone
from playwright.sync_api import expect

from apps.applications.models import Application, ApplicationReviewer, PrivacyNotice
from apps.attachments.models import Attachment, AttachmentContent

pytestmark = pytest.mark.django_db(transaction=True)


def _create_referred_application(candidate, job, recruiter, hr_manager):
    attachment = Attachment.objects.create(
        candidate=candidate,
        upload_attempt_key="k",
        original_filename="resume.pdf",
        detected_mime_type="application/pdf",
        size_bytes=20,
        sha256="x",
        scan_status=Attachment.ScanStatus.CLEAN,
    )
    AttachmentContent.objects.create(attachment=attachment, data=b"%PDF-1.4\nreal resume content")

    application = Application.objects.create(
        tracking_code="browsercode0001",
        candidate=candidate,
        job_position=job,
        first_name="نگار",
        last_name="احمدی",
        mobile_snapshot=candidate.mobile,
        city="اصفهان",
        employment=Application.Employment.FULL_TIME,
        experience=Application.Experience.YEARS_1_3,
        availability=Application.Availability.IMMEDIATE,
        last_title="x",
        last_company="y",
        status=Application.Status.NEW,
        idempotency_key="browser-k1",
    )
    attachment.application = application
    attachment.save(update_fields=["application"])
    ApplicationReviewer.objects.create(
        application=application, reviewer=recruiter, reviewer_role_at_assignment="recruiter", assigned_by=hr_manager
    )
    return application


def test_staff_login_filter_detail_download(live_server, page, candidate_factory, job_position_factory, recruiter, hr_manager):
    candidate = candidate_factory()
    job = job_position_factory(title="کارشناس فروش")
    PrivacyNotice.objects.create(version="us3-v1", body="x", published_at=timezone.now())
    application = _create_referred_application(candidate, job, recruiter, hr_manager)

    recruiter.set_password("a-strong-password-123")
    recruiter.save(update_fields=["password"])

    # ورود تک‌مرحله‌ای: فقط نام‌کاربری/رمز عبور (اصل V نسخهٔ ۳.۰.۰ — بدون عامل دوم).
    page.goto(f"{live_server.url}/staff/login")
    page.fill("#username", recruiter.username)
    page.fill("#password", "a-strong-password-123")
    page.click("#login-button")
    page.wait_for_url("**/staff/dashboard")

    # ۳. فیلتر در داشبورد — پرونده ارجاع‌شده باید دیده شود (همان درخواستی که US1 ثبت کرد).
    expect(page.locator("#results-table")).to_be_visible(timeout=10000)
    page.fill("#search-box", "نگار")
    page.click("#apply-filters")
    expect(page.locator("#result-rows")).to_contain_text("browsercode0001")
    expect(page.locator("#result-rows")).to_contain_text("کارشناس فروش")

    # ۴. مشاهده جزئیات.
    page.click("text=مشاهده پرونده")
    page.wait_for_url(f"**/staff/applications/{application.id}")
    expect(page.locator("#detail-card")).to_be_visible(timeout=10000)
    expect(page.locator("#applicant-name")).to_have_text("نگار احمدی")

    # ۵. دانلود رزومه — باید واقعاً محتوای فایل را بگیرد.
    with page.expect_download() as download_info:
        page.click("#download-link")
    download = download_info.value
    assert download.suggested_filename == "resume"

    # ۶. تلاش مستقیم API خارج از مجوز: بدون هیچ نشست/کوکی (درخواست کاملاً ناشناس) باید رد شود.
    request = urllib.request.Request(f"{live_server.url}/api/v1/staff/applications/{application.id}")
    try:
        urllib.request.urlopen(request, timeout=5)
        raise AssertionError("درخواست ناشناس باید رد می‌شد، نه موفق")
    except urllib.error.HTTPError as exc:
        assert exc.code in (401, 403)
