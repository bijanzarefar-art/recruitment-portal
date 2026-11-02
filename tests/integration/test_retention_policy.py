"""
T067a (بازنویسی fail-closed): فرمان `enforce_retention` تا زمانی که سیاست نگهداری مصوب و در
پیکربندی فعال نشده باشد، **هیچ رکوردی را تغییر یا حذف نمی‌کند** — حتی با اجرای دستی بدون
`--dry-run` (FR-061، اصل XI، اصل X).
"""
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from apps.applications.models import Application, StatusHistory
from apps.attachments.models import Attachment, AttachmentContent
from apps.audit.models import AuditEvent

pytestmark = pytest.mark.django_db


def _create_application(candidate, job, tracking_code: str) -> Application:
    return Application.objects.create(
        tracking_code=tracking_code,
        candidate=candidate,
        job_position=job,
        first_name="رضا",
        last_name="یزدانی",
        mobile_snapshot=candidate.mobile,
        city="رشت",
        employment=Application.Employment.FULL_TIME,
        experience=Application.Experience.YEARS_1_3,
        availability=Application.Availability.IMMEDIATE,
        last_title="x",
        last_company="y",
        status=Application.Status.REJECTED,
        idempotency_key=f"ret-k-{tracking_code}",
    )


def _make_expired(application, days_old: int = 400):
    StatusHistory.objects.filter(application=application).delete()
    history = StatusHistory.objects.create(
        application=application, from_status="new", to_status="rejected"
    )
    StatusHistory.objects.filter(id=history.id).update(
        created_at=timezone.now() - timezone.timedelta(days=days_old)
    )


# --- ۱-۳: پیش‌فرض غیرفعال → هیچ حذفی، حتی با اجرای دستی ---


def test_deletion_is_blocked_by_default_with_no_policy_approval(candidate_factory, job_position_factory, hr_manager):
    """بدون فعال‌سازی صریح، اجرای بدون --dry-run باید پیش از هر حذف با CommandError متوقف شود."""
    job = job_position_factory()
    expired = _create_application(candidate_factory(), job, "retblocked01")
    _make_expired(expired)

    with pytest.raises(CommandError, match="مسدود"):
        call_command("enforce_retention", actor_id=str(hr_manager.id))

    assert Application.objects.filter(id=expired.id).exists()


def test_missing_actor_id_blocks_deletion_even_when_policy_approved(
    candidate_factory, job_position_factory, settings
):
    settings.RETENTION_POLICY_APPROVED = True
    settings.RETENTION_OPERATIONAL_ENABLED = True
    job = job_position_factory()
    expired = _create_application(candidate_factory(), job, "retnoactor01")
    _make_expired(expired)

    with pytest.raises(CommandError, match="actor-id"):
        call_command("enforce_retention")

    assert Application.objects.filter(id=expired.id).exists()


def test_invalid_actor_id_blocks_deletion_even_when_policy_approved(
    candidate_factory, job_position_factory, recruiter, settings
):
    """نقش غیر hr_manager (اینجا recruiter) نباید بتواند حذف را تأیید کند."""
    settings.RETENTION_POLICY_APPROVED = True
    settings.RETENTION_OPERATIONAL_ENABLED = True
    job = job_position_factory()
    expired = _create_application(candidate_factory(), job, "retbadactor1")
    _make_expired(expired)

    with pytest.raises(CommandError, match="مدیر HR"):
        call_command("enforce_retention", actor_id=str(recruiter.id))

    assert Application.objects.filter(id=expired.id).exists()


@pytest.mark.parametrize("bad_months", [None, 0, -1, "12", 12.5])
def test_invalid_retention_months_blocks_deletion(
    candidate_factory, job_position_factory, hr_manager, settings, bad_months
):
    settings.RETENTION_POLICY_APPROVED = True
    settings.RETENTION_OPERATIONAL_ENABLED = True
    settings.DATA_RETENTION_MONTHS = bad_months
    job = job_position_factory()
    expired = _create_application(candidate_factory(), job, "retbadmonths")
    _make_expired(expired)

    with pytest.raises(CommandError, match="DATA_RETENTION_MONTHS"):
        call_command("enforce_retention", actor_id=str(hr_manager.id))

    assert Application.objects.filter(id=expired.id).exists()


def test_dry_run_never_deletes_and_works_without_approval(candidate_factory, job_position_factory):
    job = job_position_factory()
    expired = _create_application(candidate_factory(), job, "retdryrun01")
    _make_expired(expired)

    call_command("enforce_retention", "--dry-run")

    assert Application.objects.filter(id=expired.id).exists()


def test_dry_run_reports_the_candidate_and_never_deletes(candidate_factory, job_position_factory, capsys):
    job = job_position_factory()
    expired = _create_application(candidate_factory(), job, "retdryrun02")
    _make_expired(expired)

    call_command("enforce_retention", "--dry-run")

    assert Application.objects.filter(id=expired.id).exists()
    assert str(expired.id) in capsys.readouterr().out


# --- ۴: با همه شروط کامل، رفتار درست ---


def test_with_all_preconditions_met_expired_is_deleted_and_fresh_kept(
    candidate_factory, job_position_factory, hr_manager, settings
):
    settings.RETENTION_POLICY_APPROVED = True
    settings.RETENTION_OPERATIONAL_ENABLED = True
    settings.DATA_RETENTION_MONTHS = 12
    job = job_position_factory()

    expired = _create_application(candidate_factory(), job, "retfull00001")
    _make_expired(expired, days_old=400)
    fresh = _create_application(candidate_factory(), job, "retfull00002")
    _make_expired(fresh, days_old=5)

    call_command("enforce_retention", actor_id=str(hr_manager.id))

    assert not Application.objects.filter(id=expired.id).exists()
    assert Application.objects.filter(id=fresh.id).exists()


def test_resume_binary_is_removed_with_its_expired_application(
    candidate_factory, job_position_factory, hr_manager, settings
):
    settings.RETENTION_POLICY_APPROVED = True
    settings.RETENTION_OPERATIONAL_ENABLED = True
    settings.DATA_RETENTION_MONTHS = 12
    candidate = candidate_factory()
    job = job_position_factory()
    expired = _create_application(candidate, job, "retfile000001")
    attachment = Attachment.objects.create(
        candidate=candidate,
        application=expired,
        upload_attempt_key="ret-k",
        original_filename="resume.pdf",
        detected_mime_type="application/pdf",
        size_bytes=10,
        sha256="x",
        scan_status=Attachment.ScanStatus.CLEAN,
    )
    AttachmentContent.objects.create(attachment=attachment, data=b"%PDF-1.4\nreal content")
    _make_expired(expired)

    call_command("enforce_retention", actor_id=str(hr_manager.id))

    assert not Attachment.objects.filter(id=attachment.id).exists()
    assert not AttachmentContent.objects.filter(attachment_id=attachment.id).exists()


# --- ۵: حسابرسی هرگز حذف نمی‌شود (مسدود تا نقش جداگانه مصوب) ---


def test_audit_events_are_never_deleted_by_retention(
    candidate_factory, job_position_factory, hr_manager, settings
):
    """
    مسیر پاک‌سازی AuditEvent عمداً مسدود است تا نقش حداقل‌مجوز جداگانه مصوب شود. حتی با همه
    شروط حذف پرونده فعال، رویداد حسابرسی مرتبط نباید حذف شود.
    """
    settings.RETENTION_POLICY_APPROVED = True
    settings.RETENTION_OPERATIONAL_ENABLED = True
    settings.DATA_RETENTION_MONTHS = 12
    job = job_position_factory()
    expired = _create_application(candidate_factory(), job, "retaudit0001")
    _make_expired(expired)
    event = AuditEvent.objects.create(
        action="status_changed", object_type="Application", object_id=str(expired.id)
    )

    call_command("enforce_retention", actor_id=str(hr_manager.id))

    assert not Application.objects.filter(id=expired.id).exists()
    assert AuditEvent.objects.filter(id=event.id).exists(), "رویداد حسابرسی نباید حذف شود"


def test_operational_enable_key_is_independent_of_policy_approval(
    candidate_factory, job_position_factory, hr_manager, settings
):
    """تصویب سیاست نباید به‌تنهایی حذف را روشن کند؛ کلید عملیاتی مستقل هم لازم است."""
    settings.RETENTION_POLICY_APPROVED = True
    settings.RETENTION_OPERATIONAL_ENABLED = False
    job = job_position_factory()
    expired = _create_application(candidate_factory(), job, "retopkey00001")
    _make_expired(expired)

    with pytest.raises(CommandError, match="RETENTION_OPERATIONAL_ENABLED"):
        call_command("enforce_retention", actor_id=str(hr_manager.id))
    assert Application.objects.filter(id=expired.id).exists()


def test_operational_enable_alone_does_not_bypass_policy_approval(
    candidate_factory, job_position_factory, hr_manager, settings
):
    settings.RETENTION_POLICY_APPROVED = False
    settings.RETENTION_OPERATIONAL_ENABLED = True
    job = job_position_factory()
    expired = _create_application(candidate_factory(), job, "retopkey00002")
    _make_expired(expired)

    with pytest.raises(CommandError, match="RETENTION_POLICY_APPROVED"):
        call_command("enforce_retention", actor_id=str(hr_manager.id))
    assert Application.objects.filter(id=expired.id).exists()


def test_inactive_hr_manager_cannot_authorise_deletion(
    candidate_factory, job_position_factory, hr_manager, settings
):
    settings.RETENTION_POLICY_APPROVED = True
    settings.RETENTION_OPERATIONAL_ENABLED = True
    hr_manager.is_active = False
    hr_manager.save(update_fields=["is_active"])
    job = job_position_factory()
    expired = _create_application(candidate_factory(), job, "retinactive01")
    _make_expired(expired)

    with pytest.raises(CommandError, match="کارمند فعال"):
        call_command("enforce_retention", actor_id=str(hr_manager.id))
    assert Application.objects.filter(id=expired.id).exists()


@pytest.mark.parametrize("bad_value", [True, False])
def test_boolean_retention_months_is_rejected(
    candidate_factory, job_position_factory, hr_manager, settings, bad_value
):
    """bool زیرکلاس int است؛ نباید به‌عنوان 'ماه' پذیرفته شود."""
    settings.RETENTION_POLICY_APPROVED = True
    settings.RETENTION_OPERATIONAL_ENABLED = True
    settings.DATA_RETENTION_MONTHS = bad_value
    job = job_position_factory()
    expired = _create_application(candidate_factory(), job, "retboolmon01")
    _make_expired(expired)

    with pytest.raises(CommandError, match="DATA_RETENTION_MONTHS"):
        call_command("enforce_retention", actor_id=str(hr_manager.id))
    assert Application.objects.filter(id=expired.id).exists()


def test_dry_run_still_works_when_operational_key_is_off(candidate_factory, job_position_factory):
    job = job_position_factory()
    expired = _create_application(candidate_factory(), job, "retdryoff0001")
    _make_expired(expired)

    call_command("enforce_retention", "--dry-run")

    assert Application.objects.filter(id=expired.id).exists()
