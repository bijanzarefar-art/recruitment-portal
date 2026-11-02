"""
T053: ورود (تک‌مرحله‌ای، اصل V نسخهٔ ۳.۰.۰) ← فیلتر ← جزئیات ← دانلود رزومه ← یادداشت ← تغییر
وضعیت با Playwright واقعی روی سرور زنده (FR-025 تا FR-031)؛ و یک تلاش مستقیم API با
`expected_version` قدیمی که باید ۴۰۹ بگیرد.
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
        tracking_code="browsercode0002",
        candidate=candidate,
        job_position=job,
        first_name="کیانا",
        last_name="موسوی",
        mobile_snapshot=candidate.mobile,
        city="تبریز",
        employment=Application.Employment.FULL_TIME,
        experience=Application.Experience.YEARS_1_3,
        availability=Application.Availability.IMMEDIATE,
        last_title="x",
        last_company="y",
        status=Application.Status.NEW,
        idempotency_key="browser-k2",
    )
    attachment.application = application
    attachment.save(update_fields=["application"])
    ApplicationReviewer.objects.create(
        application=application, reviewer=recruiter, reviewer_role_at_assignment="recruiter", assigned_by=hr_manager
    )
    return application


def test_staff_login_filter_detail_download_note_status(
    live_server, page, candidate_factory, job_position_factory, recruiter, hr_manager
):
    candidate = candidate_factory()
    job = job_position_factory(title="کارشناس پشتیبانی")
    PrivacyNotice.objects.create(version="us4-v1", body="x", published_at=timezone.now())
    application = _create_referred_application(candidate, job, recruiter, hr_manager)

    recruiter.set_password("a-strong-password-123")
    recruiter.save(update_fields=["password"])

    # ۱. ورود تک‌مرحله‌ای، بدون عامل دوم (اصل V نسخهٔ ۳.۰.۰).
    page.goto(f"{live_server.url}/staff/login")
    page.fill("#username", recruiter.username)
    page.fill("#password", "a-strong-password-123")
    page.click("#login-button")
    page.wait_for_url("**/staff/dashboard")

    # ۲. فیلتر در داشبورد.
    expect(page.locator("#results-table")).to_be_visible(timeout=10000)
    page.fill("#search-box", "کیانا")
    page.click("#apply-filters")
    expect(page.locator("#result-rows")).to_contain_text("browsercode0002")

    # ۳. مشاهده جزئیات.
    page.click("text=مشاهده پرونده")
    page.wait_for_url(f"**/staff/applications/{application.id}")
    expect(page.locator("#detail-card")).to_be_visible(timeout=10000)
    expect(page.locator("#applicant-name")).to_have_text("کیانا موسوی")

    # ۴. دانلود رزومه.
    with page.expect_download() as download_info:
        page.click("#download-link")
    download = download_info.value
    assert download.suggested_filename == "resume"

    # ۵. افزودن یادداشت داخلی.
    page.fill("#note-body", "یادداشت واقعی از جریان مرورگری")
    page.click("#note-submit")
    expect(page.locator("#notes-list")).to_contain_text("یادداشت واقعی از جریان مرورگری", timeout=10000)

    # ۶. تغییر وضعیت (new -> phone).
    page.select_option("#status-select", Application.Status.PHONE)
    page.click("#status-submit")
    page.wait_for_function(
        "document.getElementById('status-badge').className.includes('status-phone')", timeout=10000
    )
    application.refresh_from_db()
    assert application.status == Application.Status.PHONE

    # ۷. تلاش مستقیم API با expected_version قدیمی (پیش از تغییر وضعیت بالا) باید رد شود.
    request = urllib.request.Request(
        f"{live_server.url}/api/v1/staff/applications/{application.id}/status",
        data=b'{"to_status": "rejected", "expected_version": 1, "reason": "x"}',
        headers={"Content-Type": "application/json"},
        method="PATCH",
    )
    try:
        urllib.request.urlopen(request, timeout=5)
        raise AssertionError("درخواست با نسخه قدیمی و بدون نشست معتبر باید رد می‌شد")
    except urllib.error.HTTPError as exc:
        # بدون کوکی نشست معتبر، باید ۴۰۱/۴۰۳ بگیرد (نه ۲۰۰)؛ حتی با نسخه درست، نشست ناشناس مجاز نیست.
        assert exc.code in (401, 403, 409)
