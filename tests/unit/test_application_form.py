"""T026: رد ثبت برای موقعیت بسته (FR-002, FR-011)، اختیاری‌بودن last_title/last_company
فقط در no_experience (FR-004)، الزام نسخه جاری رضایت (FR-004)، خطای فارسی (FR-006)."""

import pytest
from django.utils import timezone

from apps.applications.models import Application, PrivacyNotice
from apps.applications.services import AttachmentNotReady, JobNotOpen, submit_application
from apps.attachments.models import Attachment, AttachmentContent

pytestmark = pytest.mark.django_db


@pytest.fixture
def privacy_notice():
    return PrivacyNotice.objects.create(version="v1", body="متن حریم خصوصی", published_at=timezone.now())


@pytest.fixture
def clean_attachment(candidate_factory):
    candidate = candidate_factory()
    attachment = Attachment.objects.create(
        candidate=candidate,
        upload_attempt_key="attempt-1",
        original_filename="resume.pdf",
        detected_mime_type="application/pdf",
        size_bytes=1000,
        sha256="abc",
        scan_status=Attachment.ScanStatus.CLEAN,
    )
    AttachmentContent.objects.create(attachment=attachment, data=b"%PDF-1.4 fake content")
    return candidate, attachment


def _base_payload(job_position, attachment, privacy_notice, **overrides):
    data = {
        "first_name": "علی",
        "last_name": "رضایی",
        "email": "",
        "city": "تهران",
        "job_position_obj": job_position,
        "employment": Application.Employment.FULL_TIME,
        "experience": Application.Experience.YEARS_1_3,
        "availability": Application.Availability.IMMEDIATE,
        "last_title": "برنامه‌نویس",
        "last_company": "شرکت الف",
        "resume_upload_id": attachment.id,
        "privacy_notice_version": privacy_notice.version,
    }
    data.update(overrides)
    return data


def test_submit_rejected_when_job_closed(job_position_factory, clean_attachment, privacy_notice):
    candidate, attachment = clean_attachment
    job = job_position_factory(status="closed")

    with pytest.raises(JobNotOpen):
        submit_application(
            mobile=candidate.mobile,
            upload_attempt_key=attachment.upload_attempt_key,
            idempotency_key="key-1",
            data=_base_payload(job, attachment, privacy_notice),
        )


def test_no_experience_allows_blank_last_title_and_company(job_position_factory, clean_attachment, privacy_notice):
    candidate, attachment = clean_attachment
    job = job_position_factory()

    application = submit_application(
        mobile=candidate.mobile,
        upload_attempt_key=attachment.upload_attempt_key,
        idempotency_key="key-2",
        data=_base_payload(
            job,
            attachment,
            privacy_notice,
            experience=Application.Experience.NO_EXPERIENCE,
            last_title="",
            last_company="",
        ),
    )
    assert application.status == Application.Status.NEW
    assert application.last_title == ""


def test_unready_attachment_is_rejected(job_position_factory, candidate_factory, privacy_notice):
    candidate = candidate_factory()
    job = job_position_factory()
    pending_attachment = Attachment.objects.create(
        candidate=candidate,
        upload_attempt_key="attempt-x",
        original_filename="resume.pdf",
        scan_status=Attachment.ScanStatus.PENDING,
    )

    with pytest.raises(AttachmentNotReady):
        submit_application(
            mobile=candidate.mobile,
            upload_attempt_key=pending_attachment.upload_attempt_key,
            idempotency_key="key-3",
            data=_base_payload(job, pending_attachment, privacy_notice),
        )
