"""
T042: پس از لغو ارجاع، دانلود/مشاهده بعدی همان کارمند رد شود (FR-041)؛ فایل در وضعیت غیر
`clean` از هیچ مسیری قابل دانلود نباشد (FR-025, FR-050, SC-005).
"""
import pytest
from django.test.utils import CaptureQueriesContext
from django.db import connection
from django.utils import timezone
from rest_framework.test import APIClient

from apps.applications.models import Application, PrivacyNotice
from apps.applications.services import assign_reviewer, revoke_reviewer
from apps.attachments.models import Attachment, AttachmentContent
from apps.audit.models import AuditEvent

pytestmark = pytest.mark.django_db


def _create_application_with_attachment(candidate, job, scan_status: str) -> Application:
    attachment = Attachment.objects.create(
        candidate=candidate,
        upload_attempt_key="k",
        original_filename="resume.pdf",
        detected_mime_type="application/pdf",
        size_bytes=10,
        sha256="x",
        scan_status=scan_status,
    )
    AttachmentContent.objects.create(attachment=attachment, data=b"%PDF-1.4\nreal content")

    application = Application.objects.create(
        tracking_code="dlcode0000000001",
        candidate=candidate,
        job_position=job,
        first_name="علی",
        last_name="رضایی",
        mobile_snapshot=candidate.mobile,
        city="تهران",
        employment=Application.Employment.FULL_TIME,
        experience=Application.Experience.YEARS_1_3,
        availability=Application.Availability.IMMEDIATE,
        last_title="x",
        last_company="y",
        status=Application.Status.NEW,
        idempotency_key="dl-k1",
    )
    attachment.application = application
    attachment.save(update_fields=["application"])
    return application


def test_revoking_referral_immediately_blocks_further_access_and_download(
    candidate_factory, job_position_factory, recruiter, hr_manager
):
    candidate = candidate_factory()
    job = job_position_factory()
    PrivacyNotice.objects.create(version="dl-v1", body="x", published_at=timezone.now())
    application = _create_application_with_attachment(candidate, job, Attachment.ScanStatus.CLEAN)

    assign_reviewer(application=application, reviewer=recruiter, assigned_by=hr_manager)

    client = APIClient()
    client.force_authenticate(user=recruiter)

    # پیش از لغو: دسترسی و دانلود مجاز است.
    assert client.get(f"/api/v1/staff/applications/{application.id}").status_code == 200
    ok_resp = client.get(f"/api/v1/staff/applications/{application.id}/resume")
    assert ok_resp.status_code == 200

    revoke_reviewer(application=application, revoked_by=hr_manager)

    # پس از لغو: همان کارمند بلافاصله رد می‌شود (بدون نیاز به خروج/ورود دوباره).
    assert client.get(f"/api/v1/staff/applications/{application.id}").status_code == 404
    revoked_resp = client.get(f"/api/v1/staff/applications/{application.id}/resume")
    assert revoked_resp.status_code == 404


@pytest.mark.parametrize(
    "scan_status",
    [
        Attachment.ScanStatus.PENDING,
        Attachment.ScanStatus.QUARANTINED,
        Attachment.ScanStatus.SCAN_FAILED,
        Attachment.ScanStatus.REJECTED,
    ],
)
def test_non_clean_resume_is_never_downloadable_even_with_valid_referral(
    candidate_factory, job_position_factory, recruiter, hr_manager, scan_status
):
    candidate = candidate_factory()
    job = job_position_factory()
    PrivacyNotice.objects.create(version=f"dl-v-{scan_status}", body="x", published_at=timezone.now())
    application = _create_application_with_attachment(candidate, job, scan_status)
    assign_reviewer(application=application, reviewer=recruiter, assigned_by=hr_manager)

    client = APIClient()
    client.force_authenticate(user=recruiter)

    resp = client.get(f"/api/v1/staff/applications/{application.id}/resume")
    assert resp.status_code == 404, f"scan_status={scan_status} باید دانلود را مسدود کند"


def test_download_response_has_safe_disposition_and_no_cache_headers(
    candidate_factory, job_position_factory, recruiter, hr_manager
):
    candidate = candidate_factory()
    job = job_position_factory()
    PrivacyNotice.objects.create(version="dl-v-headers", body="x", published_at=timezone.now())
    application = _create_application_with_attachment(candidate, job, Attachment.ScanStatus.CLEAN)
    assign_reviewer(application=application, reviewer=recruiter, assigned_by=hr_manager)

    client = APIClient()
    client.force_authenticate(user=recruiter)

    resp = client.get(f"/api/v1/staff/applications/{application.id}/resume")
    assert resp.status_code == 200
    assert resp["Content-Disposition"] == 'attachment; filename="resume.pdf"'
    assert resp["Cache-Control"] == "no-store"
    assert resp["X-Content-Type-Options"] == "nosniff"
    assert resp.content == b"%PDF-1.4\nreal content"


def test_download_requires_live_record_permission_check_not_just_past_referral(
    candidate_factory, job_position_factory, recruiter, hiring_manager, hr_manager
):
    """
    کنترل مجوز رکورد باید در *هر* درخواست دوباره بررسی شود، نه فقط زمان ارجاع اولیه؛ کارمندی
    که هرگز ارجاع نگرفته (hiring_manager در این سناریو) حتی اگر از قبل می‌دانست فایل کجاست
    نباید بتواند دانلود کند.
    """
    candidate = candidate_factory()
    job = job_position_factory()
    PrivacyNotice.objects.create(version="dl-v-norole", body="x", published_at=timezone.now())
    application = _create_application_with_attachment(candidate, job, Attachment.ScanStatus.CLEAN)
    assign_reviewer(application=application, reviewer=recruiter, assigned_by=hr_manager)

    client = APIClient()
    client.force_authenticate(user=hiring_manager)  # هیچ ارجاعی به این کارمند داده نشده

    resp = client.get(f"/api/v1/staff/applications/{application.id}/resume")
    assert resp.status_code == 404


def test_list_and_search_never_query_attachment_content_table(
    candidate_factory, job_position_factory, recruiter, hr_manager
):
    """
    الزام ۵: فهرست و جست‌وجو محتوای باینری رزومه را واکشی نکنند — هیچ پرس‌وجویی روی جدول
    `attachments_attachmentcontent` در مسیر فهرست/جست‌وجو اجرا نشود (اصل I، FR-050).
    """
    candidate = candidate_factory()
    job = job_position_factory()
    PrivacyNotice.objects.create(version="dl-v-noblob", body="x", published_at=timezone.now())
    application = _create_application_with_attachment(candidate, job, Attachment.ScanStatus.CLEAN)
    assign_reviewer(application=application, reviewer=recruiter, assigned_by=hr_manager)

    client = APIClient()
    client.force_authenticate(user=recruiter)

    with CaptureQueriesContext(connection) as ctx:
        resp = client.get("/api/v1/staff/applications?q=رضایی")
    assert resp.status_code == 200
    assert resp.json()["count"] == 1
    for query in ctx.captured_queries:
        assert "attachmentcontent" not in query["sql"].lower(), query["sql"]


def test_resume_download_is_audited_without_logging_file_content(
    candidate_factory, job_position_factory, recruiter, hr_manager
):
    """الزام ۶: دانلود مجاز باید در AuditEvent ثبت شود، بدون محتوای فایل در metadata."""
    candidate = candidate_factory()
    job = job_position_factory()
    PrivacyNotice.objects.create(version="dl-v-audit", body="x", published_at=timezone.now())
    application = _create_application_with_attachment(candidate, job, Attachment.ScanStatus.CLEAN)
    assign_reviewer(application=application, reviewer=recruiter, assigned_by=hr_manager)

    client = APIClient()
    client.force_authenticate(user=recruiter)

    before = AuditEvent.objects.filter(action="resume_download").count()
    resp = client.get(f"/api/v1/staff/applications/{application.id}/resume")
    assert resp.status_code == 200

    events = AuditEvent.objects.filter(action="resume_download")
    assert events.count() == before + 1
    event = events.latest("created_at")
    assert event.staff_actor_id == recruiter.id
    assert event.object_id == str(application.id)
    assert "real content" not in str(event.metadata)
