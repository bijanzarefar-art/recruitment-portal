"""T028: درخواست فعال تکراری، تکرارپذیری هم‌زمان، و ثبت مجدد پس از رد (FR-008, FR-009, FR-056, FR-060)."""
import threading

import pytest
from django.db import close_old_connections
from django.utils import timezone

from apps.applications.models import Application, PrivacyNotice
from apps.applications.services import DuplicateActiveApplication, submit_application
from apps.attachments.models import Attachment, AttachmentContent

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


def test_duplicate_active_application_rejected_on_second_submit(candidate_factory, job_position_factory):
    candidate = candidate_factory()
    job = job_position_factory()
    notice = PrivacyNotice.objects.create(version="v-dup", body="x", published_at=timezone.now())

    attachment1 = _make_clean_attachment(candidate, "k1")
    submit_application(
        mobile=candidate.mobile,
        upload_attempt_key=attachment1.upload_attempt_key,
        idempotency_key="key-a",
        data=_payload(job, attachment1, notice),
    )

    attachment2 = _make_clean_attachment(candidate, "k2")
    with pytest.raises(DuplicateActiveApplication):
        submit_application(
            mobile=candidate.mobile,
            upload_attempt_key=attachment2.upload_attempt_key,
            idempotency_key="key-b",
            data=_payload(job, attachment2, notice),
        )

    assert Application.objects.filter(candidate=candidate, job_position=job).count() == 1


def test_concurrent_submissions_same_key_produce_exactly_one_application(candidate_factory, job_position_factory):
    candidate = candidate_factory()
    job = job_position_factory()
    notice = PrivacyNotice.objects.create(version="v-conc", body="x", published_at=timezone.now())
    attachment = _make_clean_attachment(candidate, "k-conc")

    results = []
    errors = []

    def _worker():
        close_old_connections()
        try:
            app = submit_application(
                mobile=candidate.mobile,
                upload_attempt_key=attachment.upload_attempt_key,
                idempotency_key="shared-key",
                data=_payload(job, attachment, notice),
            )
            results.append(app.id)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)
        finally:
            close_old_connections()

    threads = [threading.Thread(target=_worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert Application.objects.filter(candidate=candidate, job_position=job).count() == 1
    # همه نخ‌هایی که موفق بودند باید همان یک Application را گرفته باشند (رسید قبلی برمی‌گردد).
    assert len(set(results)) <= 1


def test_reapplication_after_rejection_on_reopened_job_creates_independent_record(candidate_factory, job_position_factory):
    """FR-060: پس از rejected و بازگشایی موقعیت، ثبت مجدد باید موفق و مستقل باشد؛
    FR-056: رکورد قبلی تغییر نمی‌کند."""
    candidate = candidate_factory()
    job = job_position_factory()
    notice = PrivacyNotice.objects.create(version="v-re", body="x", published_at=timezone.now())

    attachment1 = _make_clean_attachment(candidate, "k-re1")
    first = submit_application(
        mobile=candidate.mobile,
        upload_attempt_key=attachment1.upload_attempt_key,
        idempotency_key="key-re-1",
        data=_payload(job, attachment1, notice),
    )
    first.status = Application.Status.REJECTED
    first.save(update_fields=["status"])
    first_city_before = first.city

    attachment2 = _make_clean_attachment(candidate, "k-re2")
    second = submit_application(
        mobile=candidate.mobile,
        upload_attempt_key=attachment2.upload_attempt_key,
        idempotency_key="key-re-2",
        data=_payload(job, attachment2, notice),
    )

    first.refresh_from_db()
    assert first.city == first_city_before
    assert first.status == Application.Status.REJECTED
    assert second.id != first.id
    assert second.status == Application.Status.NEW
    assert Application.objects.filter(candidate=candidate, job_position=job).count() == 2
