"""
T058/T058a: چرخه وضعیت موقعیت شغلی (FR-039a، تصمیم صریح کاربر — نه ابهام): `draft→open`،
`open→closed`، `closed→open`. انتقال‌های نامجاز رد شوند؛ فقط `hr_manager` مجاز باشد؛ بستن فقط
ثبت جدید را متوقف کند (FR-039)؛ حذف فیزیکی ممنوع (FR-038)؛ رقابت واقعی بستن/ثبت درخواست.
"""
import threading

import pytest
from django.core.exceptions import PermissionDenied
from django.db import close_old_connections
from django.utils import timezone
from rest_framework.test import APIClient

from apps.applications.models import Application, PrivacyNotice
from apps.applications.services import DuplicateActiveApplication, JobNotOpen, submit_application
from apps.attachments.models import Attachment, AttachmentContent
from apps.jobs.models import JobPosition
from apps.jobs.services import InvalidJobTransition, close_job, create_job, reopen_job, update_job

pytestmark = pytest.mark.django_db(transaction=True)

PDF_HEADER = b"%PDF-1.4\n%fake pdf content for tests\n"


def _make_clean_attachment(candidate, key: str) -> Attachment:
    attachment = Attachment.objects.create(
        candidate=candidate,
        upload_attempt_key=key,
        original_filename="resume.pdf",
        detected_mime_type="application/pdf",
        size_bytes=100,
        sha256=key,
        scan_status=Attachment.ScanStatus.CLEAN,
    )
    AttachmentContent.objects.create(attachment=attachment, data=PDF_HEADER)
    return attachment


def _payload(job, attachment, notice):
    return {
        "first_name": "علی",
        "last_name": "رضایی",
        "email": "",
        "city": "تهران",
        "job_position_obj": job,
        "employment": Application.Employment.FULL_TIME,
        "experience": Application.Experience.YEARS_1_3,
        "availability": Application.Availability.IMMEDIATE,
        "last_title": "برنامه‌نویس",
        "last_company": "شرکت الف",
        "resume_upload_id": attachment.id,
        "privacy_notice_version": notice.version,
    }


def test_new_job_is_created_as_draft_and_does_not_accept_applications(hr_manager):
    job = create_job(created_by=hr_manager, title="موقعیت تازه")
    assert job.status == JobPosition.Status.DRAFT
    assert not job.is_open_for_applications


def test_closing_job_blocks_new_submission_but_keeps_previous_applications_visible(
    candidate_factory, job_position_factory, hr_manager
):
    job = job_position_factory(status=JobPosition.Status.OPEN)
    candidate1 = candidate_factory()
    notice = PrivacyNotice.objects.create(version="job-lc-v1", body="x", published_at=timezone.now())
    attachment = _make_clean_attachment(candidate1, "k1")
    existing_application = submit_application(
        mobile=candidate1.mobile,
        upload_attempt_key=attachment.upload_attempt_key,
        idempotency_key="job-lc-key1",
        data=_payload(job, attachment, notice),
    )

    close_job(job_id=job.id, closed_by=hr_manager)
    job.refresh_from_db()
    assert job.status == JobPosition.Status.CLOSED

    candidate2 = candidate_factory()
    attachment2 = _make_clean_attachment(candidate2, "k2")
    with pytest.raises(JobNotOpen):
        submit_application(
            mobile=candidate2.mobile,
            upload_attempt_key=attachment2.upload_attempt_key,
            idempotency_key="job-lc-key2",
            data=_payload(job, attachment2, notice),
        )

    # سابقه قبلی حذف/تغییر نشده و همچنان موجود است.
    existing_application.refresh_from_db()
    assert existing_application.job_position_id == job.id
    assert Application.objects.filter(id=existing_application.id).exists()


def test_reopening_closed_job_requires_hr_manager_and_is_audited(hr_manager, recruiter, job_position_factory):
    from apps.audit.models import AuditEvent

    job = job_position_factory(status=JobPosition.Status.CLOSED)

    with pytest.raises(PermissionDenied):
        reopen_job(job_id=job.id, reopened_by=recruiter)
    job.refresh_from_db()
    assert job.status == JobPosition.Status.CLOSED

    reopened = reopen_job(job_id=job.id, reopened_by=hr_manager)
    assert reopened.status == JobPosition.Status.OPEN
    assert reopened.is_open_for_applications
    assert AuditEvent.objects.filter(action="job_reopened", object_id=str(job.id)).exists()


@pytest.mark.parametrize(
    "from_status,to_status",
    [
        (JobPosition.Status.DRAFT, JobPosition.Status.CLOSED),  # draft مستقیم به closed مجاز نیست
        (JobPosition.Status.OPEN, JobPosition.Status.DRAFT),  # open هرگز به draft برنمی‌گردد
        (JobPosition.Status.CLOSED, JobPosition.Status.DRAFT),  # closed هرگز به draft برنمی‌گردد
        (JobPosition.Status.OPEN, JobPosition.Status.OPEN),  # انتقال به همان وضعیت تعریف‌نشده است
    ],
)
def test_invalid_job_status_transitions_are_rejected(hr_manager, job_position_factory, from_status, to_status):
    from apps.jobs.services import change_job_status

    job = job_position_factory(status=from_status)
    with pytest.raises(InvalidJobTransition):
        change_job_status(job_id=job.id, changed_by=hr_manager, to_status=to_status)
    job.refresh_from_db()
    assert job.status == from_status


def test_only_hr_manager_can_create_update_or_change_status(recruiter, hr_manager, job_position_factory):
    with pytest.raises(PermissionDenied):
        create_job(created_by=recruiter, title="تلاش غیرمجاز")

    job = job_position_factory(status=JobPosition.Status.OPEN)
    with pytest.raises(PermissionDenied):
        update_job(job_id=job.id, updated_by=recruiter, title="تغییر غیرمجاز")
    with pytest.raises(PermissionDenied):
        close_job(job_id=job.id, closed_by=recruiter)


def test_no_physical_delete_route_exists_for_job_with_applications(hr_manager, candidate_factory, job_position_factory):
    """FR-038: حذف فیزیکی مجاز نیست — اصلاً مسیر/تابع DELETE در API برای موقعیت وجود ندارد."""
    job = job_position_factory()
    client = APIClient()
    client.force_authenticate(user=hr_manager)
    resp = client.delete(f"/api/v1/staff/jobs/{job.id}")
    assert resp.status_code in (404, 405)
    assert JobPosition.objects.filter(id=job.id).exists()


def test_staff_api_create_close_and_reopen_job_is_audited(hr_manager):
    from apps.audit.models import AuditEvent

    client = APIClient()
    client.force_authenticate(user=hr_manager)

    create_resp = client.post(
        "/api/v1/staff/jobs", {"title": "کارشناس حسابداری", "department": "مالی"}, format="json"
    )
    assert create_resp.status_code == 201
    job_id = create_resp.json()["id"]
    assert create_resp.json()["status"] == "draft"
    assert AuditEvent.objects.filter(action="job_created", object_id=job_id).exists()

    open_resp = client.patch(f"/api/v1/staff/jobs/{job_id}/status", {"status": "open"}, format="json")
    assert open_resp.status_code == 200
    assert open_resp.json()["status"] == "open"

    close_resp = client.patch(f"/api/v1/staff/jobs/{job_id}/status", {"status": "closed"}, format="json")
    assert close_resp.status_code == 200
    assert close_resp.json()["status"] == "closed"

    reopen_resp = client.patch(f"/api/v1/staff/jobs/{job_id}/status", {"status": "open"}, format="json")
    assert reopen_resp.status_code == 200
    assert reopen_resp.json()["status"] == "open"
    assert AuditEvent.objects.filter(action="job_reopened", object_id=job_id).count() == 2


def test_invalid_transition_via_api_returns_400(hr_manager, job_position_factory):
    job = job_position_factory(status=JobPosition.Status.DRAFT)
    client = APIClient()
    client.force_authenticate(user=hr_manager)
    resp = client.patch(f"/api/v1/staff/jobs/{job.id}/status", {"status": "closed"}, format="json")
    assert resp.status_code == 400
    job.refresh_from_db()
    assert job.status == JobPosition.Status.DRAFT


def test_non_hr_role_cannot_create_or_change_status_via_api(recruiter, job_position_factory):
    job = job_position_factory(status=JobPosition.Status.OPEN)
    client = APIClient()
    client.force_authenticate(user=recruiter)

    create_resp = client.post("/api/v1/staff/jobs", {"title": "تلاش غیرمجاز"}, format="json")
    assert create_resp.status_code == 403

    close_resp = client.patch(f"/api/v1/staff/jobs/{job.id}/status", {"status": "closed"}, format="json")
    assert close_resp.status_code == 403


def test_draft_and_closed_jobs_never_appear_in_public_job_list(job_position_factory):
    draft_job = job_position_factory(status=JobPosition.Status.DRAFT)
    closed_job = job_position_factory(status=JobPosition.Status.CLOSED)
    open_job = job_position_factory(status=JobPosition.Status.OPEN)

    client = APIClient()
    resp = client.get("/api/v1/jobs")
    assert resp.status_code == 200
    ids = {row["id"] for row in resp.json()}
    assert str(open_job.id) in ids
    assert str(draft_job.id) not in ids
    assert str(closed_job.id) not in ids


def test_concurrent_close_and_submission_never_produce_an_inconsistent_outcome(
    candidate_factory, job_position_factory, hr_manager
):
    """
    رقابت واقعی: بستن موقعیت و ثبت درخواست هم‌زمان روی همان ردیف PostgreSQL. نتیجه باید یکی از
    این دو حالت قطعی باشد، نه حالت بینابینی ناسازگار (مثلاً پرونده‌ای که برای موقعیت «بسته»
    ساخته شده باشد):
    ۱) بستن زودتر commit می‌شود → ثبت `JobNotOpen` می‌گیرد و هیچ Application ساخته نمی‌شود.
    ۲) ثبت زودتر commit می‌شود → بستن بعداً اعمال می‌شود و همان یک Application معتبر باقی می‌ماند.
    """
    job = job_position_factory(status=JobPosition.Status.OPEN)
    candidate = candidate_factory()
    notice = PrivacyNotice.objects.create(version="job-race-v1", body="x", published_at=timezone.now())
    attachment = _make_clean_attachment(candidate, "race-k1")

    results = {}

    def _submit():
        close_old_connections()
        try:
            app = submit_application(
                mobile=candidate.mobile,
                upload_attempt_key=attachment.upload_attempt_key,
                idempotency_key="job-race-key",
                data=_payload(job, attachment, notice),
            )
            results["submit"] = ("ok", app.id)
        except JobNotOpen:
            results["submit"] = ("blocked", None)
        except DuplicateActiveApplication:
            results["submit"] = ("duplicate", None)
        finally:
            close_old_connections()

    def _close():
        close_old_connections()
        try:
            close_job(job_id=job.id, closed_by=hr_manager)
            results["close"] = "ok"
        finally:
            close_old_connections()

    t1 = threading.Thread(target=_submit)
    t2 = threading.Thread(target=_close)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    job.refresh_from_db()
    assert job.status == JobPosition.Status.CLOSED
    assert results["close"] == "ok"

    application_count = Application.objects.filter(candidate=candidate, job_position=job).count()
    if results["submit"][0] == "ok":
        assert application_count == 1
    else:
        assert results["submit"][0] == "blocked"
        assert application_count == 0
