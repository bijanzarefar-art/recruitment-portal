"""
T080 (جایگزین T037): `GET /api/v1/track/{tracking_code}` فاقد یادداشت HR، ارجاع، دلیل
داخلی، هویت کارکنان و گزارش حسابرسی باشد (FR-015)؛ کد نامعتبر/ناموجود پاسخ کاملاً یکسان
۴۰۴ می‌گیرد (FR-016, FR-044) — اصل V نسخهٔ ۲.۰.۰: بدون هیچ احراز هویتی.
"""
import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.applications.models import Application, PrivacyNotice
from apps.attachments.models import Attachment, AttachmentContent

pytestmark = pytest.mark.django_db

LEAKY_FIELDS = {
    "notes",
    "internal_reason",
    "reviewer",
    "reviewer_id",
    "assigned_by",
    "changed_by",
    "audit",
    "status_history",
    "mobile",
    "mobile_snapshot",
    "email",
    "first_name",
    "last_name",
}


@pytest.fixture
def application_with_internal_data(candidate_factory, job_position_factory, staff_user_factory):
    from apps.applications.models import ApplicationNote, ApplicationReviewer, StatusHistory
    from apps.accounts.models import StaffUser

    candidate = candidate_factory()
    job = job_position_factory()
    PrivacyNotice.objects.create(version="priv-v1", body="x", published_at=timezone.now())

    attachment = Attachment.objects.create(
        candidate=candidate,
        upload_attempt_key="k",
        original_filename="r.pdf",
        detected_mime_type="application/pdf",
        size_bytes=10,
        sha256="x",
        scan_status=Attachment.ScanStatus.CLEAN,
    )
    AttachmentContent.objects.create(attachment=attachment, data=b"%PDF-1.4\nx")

    application = Application.objects.create(
        tracking_code="trackcode1234567",
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
        status=Application.Status.REJECTED,
        idempotency_key="k1",
    )
    attachment.application = application
    attachment.save(update_fields=["application"])

    hr_manager = staff_user_factory(role=StaffUser.Role.HR_MANAGER)
    ApplicationNote.objects.create(application=application, author=hr_manager, body="یادداشت داخلی محرمانه")
    StatusHistory.objects.create(
        application=application,
        from_status=Application.Status.INTERVIEW,
        to_status=Application.Status.REJECTED,
        changed_by=hr_manager,
        internal_reason="دلیل داخلی محرمانه رد پرونده",
    )
    recruiter = staff_user_factory(role=StaffUser.Role.RECRUITER)
    ApplicationReviewer.objects.create(
        application=application, reviewer=recruiter, reviewer_role_at_assignment="recruiter", assigned_by=hr_manager
    )
    return application


def test_tracking_by_code_excludes_internal_fields(application_with_internal_data):
    application = application_with_internal_data
    client = APIClient()  # بدون هیچ احراز هویتی — اصل V نسخهٔ ۲.۰.۰

    resp = client.get(f"/api/v1/track/{application.tracking_code}")
    assert resp.status_code == 200

    body = resp.json()
    assert set(body.keys()) == {"tracking_code", "job_position", "status", "updated_at"}

    serialized_text = str(body)
    assert "یادداشت داخلی محرمانه" not in serialized_text
    assert "دلیل داخلی محرمانه" not in serialized_text
    for leaky_field in LEAKY_FIELDS:
        assert leaky_field not in body


def test_unknown_tracking_code_returns_404_without_disclosure(application_with_internal_data):
    client = APIClient()
    resp = client.get("/api/v1/track/this-code-does-not-exist-at-all")
    assert resp.status_code == 404
    assert resp.content in (b"", b"null")


def test_invalid_and_unknown_tracking_code_responses_are_identical_shape():
    """FR-016, FR-044: پاسخ برای کد نامعتبر و کد ناموجود باید از نظر ظاهر یکسان باشد."""
    client = APIClient()
    resp_malformed = client.get("/api/v1/track/!!!not-a-real-code")
    resp_well_formed_missing = client.get("/api/v1/track/a1b2c3d4e5f6a7b8")

    assert resp_malformed.status_code == resp_well_formed_missing.status_code == 404
    assert resp_malformed.content == resp_well_formed_missing.content
