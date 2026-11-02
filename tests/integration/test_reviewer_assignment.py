"""
T059: ترتیب و لغو ارجاع (علیه سرویس T020a، FR-041) — ارجاع مستقیم به مدیر استخدام رد می‌شود؛
ارجاع بعدی به مدیر استخدام ارجاع فعال کارشناس را باطل می‌کند؛ لغو ارجاع دسترسی بعدی را فوراً
قطع می‌کند بدون اثر روی فایل پیش‌تر دانلودشده؛ صلاحیت نقش دریافت‌کننده؛ رقابت هم‌زمان ارجاع.
"""
import secrets
import threading

import pytest
from django.core.exceptions import PermissionDenied
from django.db import close_old_connections
from django.utils import timezone
from rest_framework.test import APIClient

from apps.applications.models import Application, ApplicationReviewer, PrivacyNotice
from apps.applications.services import AssignmentConflict, assign_reviewer, revoke_reviewer
from apps.attachments.models import Attachment, AttachmentContent

pytestmark = pytest.mark.django_db(transaction=True)


def _create_application(candidate, job):
    unique = secrets.token_hex(6)
    return Application.objects.create(
        tracking_code=f"rv{unique}",
        candidate=candidate,
        job_position=job,
        first_name="سینا",
        last_name="تهرانی",
        mobile_snapshot=candidate.mobile,
        city="قم",
        employment=Application.Employment.FULL_TIME,
        experience=Application.Experience.YEARS_1_3,
        availability=Application.Availability.IMMEDIATE,
        last_title="x",
        last_company="y",
        status=Application.Status.NEW,
        idempotency_key=f"rev-k-{unique}",
    )


def test_direct_assignment_to_hiring_manager_without_prior_recruiter_is_rejected(
    candidate_factory, job_position_factory, hiring_manager, hr_manager
):
    candidate = candidate_factory()
    job = job_position_factory()
    application = _create_application(candidate, job)

    with pytest.raises(PermissionDenied):
        assign_reviewer(application=application, reviewer=hiring_manager, assigned_by=hr_manager)
    assert not ApplicationReviewer.objects.filter(application=application).exists()


def test_assigning_hiring_manager_after_recruiter_revokes_recruiters_active_referral(
    candidate_factory, job_position_factory, recruiter, hiring_manager, hr_manager
):
    candidate = candidate_factory()
    job = job_position_factory()
    application = _create_application(candidate, job)

    assign_reviewer(application=application, reviewer=recruiter, assigned_by=hr_manager)
    assign_reviewer(application=application, reviewer=hiring_manager, assigned_by=hr_manager)

    active = ApplicationReviewer.objects.filter(application=application, revoked_at__isnull=True)
    assert active.count() == 1
    assert active.first().reviewer_id == hiring_manager.id

    recruiter_assignment = ApplicationReviewer.objects.get(application=application, reviewer=recruiter)
    assert recruiter_assignment.revoked_at is not None


def test_only_recruiter_or_hiring_manager_roles_are_eligible_referral_recipients(
    candidate_factory, job_position_factory, hr_manager, system_operator
):
    """FR-041: فقط کارشناس جذب یا مدیر استخدام صلاحیت دریافت ارجاع دارند."""
    candidate = candidate_factory()
    job = job_position_factory()
    application = _create_application(candidate, job)

    with pytest.raises(PermissionDenied):
        assign_reviewer(application=application, reviewer=system_operator, assigned_by=hr_manager)
    with pytest.raises(PermissionDenied):
        assign_reviewer(application=application, reviewer=hr_manager, assigned_by=hr_manager)
    assert not ApplicationReviewer.objects.filter(application=application).exists()


def test_revoking_referral_blocks_list_detail_resume_notes_and_status_on_very_next_request(
    candidate_factory, job_position_factory, recruiter, hr_manager
):
    candidate = candidate_factory()
    job = job_position_factory()
    PrivacyNotice.objects.create(version="rev-cutoff-v1", body="x", published_at=timezone.now())

    attachment = Attachment.objects.create(
        candidate=candidate,
        upload_attempt_key="k",
        original_filename="resume.pdf",
        detected_mime_type="application/pdf",
        size_bytes=10,
        sha256="x",
        scan_status=Attachment.ScanStatus.CLEAN,
    )
    AttachmentContent.objects.create(attachment=attachment, data=b"%PDF-1.4\nreal content")
    application = _create_application(candidate, job)
    attachment.application = application
    attachment.save(update_fields=["application"])

    assign_reviewer(application=application, reviewer=recruiter, assigned_by=hr_manager)

    client = APIClient()
    client.force_authenticate(user=recruiter)

    assert client.get("/api/v1/staff/applications").json()["count"] == 1
    assert client.get(f"/api/v1/staff/applications/{application.id}").status_code == 200
    previously_downloaded = client.get(f"/api/v1/staff/applications/{application.id}/resume")
    assert previously_downloaded.status_code == 200
    assert client.post(
        f"/api/v1/staff/applications/{application.id}/notes", {"body": "یادداشت قبل از لغو"}, format="json"
    ).status_code == 201

    revoke_reviewer(application=application, revoked_by=hr_manager)

    assert client.get("/api/v1/staff/applications").json()["count"] == 0
    assert client.get(f"/api/v1/staff/applications/{application.id}").status_code == 404
    assert client.get(f"/api/v1/staff/applications/{application.id}/resume").status_code == 404
    assert client.post(
        f"/api/v1/staff/applications/{application.id}/notes", {"body": "یادداشت بعد از لغو"}, format="json"
    ).status_code == 404
    assert client.patch(
        f"/api/v1/staff/applications/{application.id}/status",
        {"to_status": Application.Status.PHONE, "expected_version": application.version},
        format="json",
    ).status_code == 404

    # نسخه‌ای که پیش از لغو واقعاً دانلود شده بود همچنان همان محتوای معتبر را داشت (قابل‌پس‌گرفتن نیست).
    assert previously_downloaded.content == b"%PDF-1.4\nreal content"


def test_concurrent_assignment_attempts_never_create_two_active_reviewers(
    candidate_factory, job_position_factory, staff_user_factory, hr_manager
):
    """
    الزام ۴ (US6): دو تلاش ارجاع هم‌زمان روی همان پرونده نباید رکورد ناسازگار (دو ارجاع فعال)
    بسازند؛ قفل ردیف `Application` باید آن‌ها را سریالی کند و قید یکتایی دیتابیسی خط دفاع دوم باشد.
    """
    from apps.accounts.models import StaffUser

    candidate = candidate_factory()
    job = job_position_factory()
    application = _create_application(candidate, job)
    recruiter_a = staff_user_factory(role=StaffUser.Role.RECRUITER)
    recruiter_b = staff_user_factory(role=StaffUser.Role.RECRUITER)

    errors = []

    def _worker(reviewer):
        close_old_connections()
        try:
            assign_reviewer(application=application, reviewer=reviewer, assigned_by=hr_manager)
        except AssignmentConflict as exc:
            errors.append(exc)
        finally:
            close_old_connections()

    t1 = threading.Thread(target=_worker, args=(recruiter_a,))
    t2 = threading.Thread(target=_worker, args=(recruiter_b,))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    active_reviewers = ApplicationReviewer.objects.filter(application=application, revoked_at__isnull=True)
    assert active_reviewers.count() == 1, "باید دقیقاً یک ارجاع فعال وجود داشته باشد، نه صفر یا بیشتر از یک"
