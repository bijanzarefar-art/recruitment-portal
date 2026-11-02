"""
T041: ماتریس کامل نقش × عملیات برای فهرست/جزئیات/آمار/دانلود رزومه (FR-018)؛ درخواست خارج
از دامنه مجوز باید ۴۰۱/۴۰۳/۴۰۴ بدون افشای وجود رکورد بگیرد (FR-019، SC-004).
"""
import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import StaffUser
from apps.applications.models import Application, ApplicationReviewer, PrivacyNotice
from apps.attachments.models import Attachment, AttachmentContent

pytestmark = pytest.mark.django_db


@pytest.fixture
def application_referred_to_recruiter(candidate_factory, job_position_factory, staff_user_factory, recruiter, hr_manager):
    candidate = candidate_factory()
    job = job_position_factory()
    PrivacyNotice.objects.create(version="matrix-v1", body="x", published_at=timezone.now())

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
        tracking_code="matrixcode00001",
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
        idempotency_key="matrix-k1",
    )
    attachment.application = application
    attachment.save(update_fields=["application"])

    ApplicationReviewer.objects.create(
        application=application, reviewer=recruiter, reviewer_role_at_assignment="recruiter", assigned_by=hr_manager
    )
    return application


def _login_as(client: APIClient, staff_user: StaffUser) -> None:
    client.force_authenticate(user=staff_user)


@pytest.mark.parametrize(
    "role_fixture,expect_list_count,expect_detail_ok,expect_resume_ok",
    [
        ("recruiter", 1, True, True),
        ("hiring_manager", 0, False, False),
        ("hr_manager", 1, True, True),
    ],
)
def test_access_matrix_per_role(
    application_referred_to_recruiter, request, role_fixture, expect_list_count, expect_detail_ok, expect_resume_ok
):
    application = application_referred_to_recruiter
    staff_user = request.getfixturevalue(role_fixture)
    client = APIClient()
    _login_as(client, staff_user)

    list_resp = client.get("/api/v1/staff/applications")
    assert list_resp.status_code == 200
    assert list_resp.json()["count"] == expect_list_count

    detail_resp = client.get(f"/api/v1/staff/applications/{application.id}")
    if expect_detail_ok:
        assert detail_resp.status_code == 200
    else:
        assert detail_resp.status_code == 404  # بدون افشای وجود رکورد (FR-019)

    metrics_resp = client.get("/api/v1/staff/applications/metrics")
    assert metrics_resp.status_code == 200
    assert metrics_resp.json()["total"] == expect_list_count

    resume_resp = client.get(f"/api/v1/staff/applications/{application.id}/resume")
    if expect_resume_ok:
        assert resume_resp.status_code == 200
        assert resume_resp["Content-Disposition"].startswith("attachment;")
        assert resume_resp["Cache-Control"] == "no-store"
    else:
        assert resume_resp.status_code == 404


def test_system_operator_has_zero_business_access(application_referred_to_recruiter, system_operator):
    client = APIClient()
    _login_as(client, system_operator)

    assert client.get("/api/v1/staff/applications").json()["count"] == 0
    assert client.get(f"/api/v1/staff/applications/{application_referred_to_recruiter.id}").status_code == 404
    assert client.get(f"/api/v1/staff/applications/{application_referred_to_recruiter.id}/resume").status_code == 404


def test_unauthenticated_request_is_rejected_without_record_disclosure(application_referred_to_recruiter):
    client = APIClient()  # بدون force_authenticate: درخواست کاملاً ناشناس

    assert client.get("/api/v1/staff/applications").status_code in (401, 403)
    resp = client.get(f"/api/v1/staff/applications/{application_referred_to_recruiter.id}")
    assert resp.status_code in (401, 403, 404)
    resp = client.get(f"/api/v1/staff/applications/{application_referred_to_recruiter.id}/resume")
    assert resp.status_code in (401, 403, 404)


def test_full_login_grants_staff_endpoint_access_in_a_single_step(application_referred_to_recruiter, recruiter):
    """
    الزام ۱ (اصل V نسخهٔ ۳.۰.۰): ورود واقعی فقط با `POST /auth/staff/login` (نام‌کاربری/رمز
    عبور) تکمیل می‌شود؛ بدون هیچ گام تأیید دومی، بلافاصله پس از این فراخوانی، دسترسی به منابع
    کارمند مجاز است. پیش از ورود، همین مسیر باید رد شود.
    """
    recruiter.set_password("a-strong-password-123")
    recruiter.save(update_fields=["password"])

    client = APIClient()

    # پیش از ورود، هیچ دسترسی‌ای نیست.
    assert client.get("/api/v1/staff/applications").status_code in (401, 403)

    login_resp = client.post(
        "/api/v1/auth/staff/login",
        {"username": recruiter.username, "password": "a-strong-password-123"},
        format="json",
    )
    assert login_resp.status_code == 200

    # بلافاصله پس از ورود، بدون هیچ گام تأیید دومی، دسترسی مجاز است.
    list_resp = client.get("/api/v1/staff/applications")
    assert list_resp.status_code == 200
    assert list_resp.json()["count"] == 1


# test_candidate_session_cannot_reach_staff_endpoints حذف شد — اصل V نسخهٔ ۲.۰.۰: دیگر هیچ
# «نشست متقاضی»ای برای آزمودن وجود ندارد (متقاضی اصلاً کوکی/نشست ندارد). درخواست ناشناس به
# مسیرهای staff/* از پیش با test_unauthenticated_request_is_rejected_without_record_disclosure
# (بالاتر در همین فایل) پوشش داده شده است.
