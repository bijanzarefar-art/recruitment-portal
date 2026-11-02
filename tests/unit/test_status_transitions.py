"""
T047: انتقال وضعیت (FR-027 تا FR-031). انتقال‌های مجاز/نامجاز، اجباری‌بودن دلیل برای رد و
برای بازگشایی استثنایی، محدودیت نقش (hiring_manager/system_operator هرگز نمی‌توانند وضعیت را
تغییر دهند)، و رگرسیون SC-008 (یادداشت/تاریخچه هرگز از بین نرود یا بازنویسی نشود).
"""
import secrets

import pytest
from django.core.exceptions import PermissionDenied

from apps.applications.models import Application, StatusHistory
from apps.applications.services import (
    InvalidTransition,
    ReasonRequired,
    add_note,
    change_status,
)
from apps.applications.statemachine import is_final, is_transition_allowed

pytestmark = pytest.mark.django_db


def _create_application(candidate, job, status=Application.Status.NEW):
    unique = secrets.token_hex(6)
    return Application.objects.create(
        tracking_code=f"st{unique}",
        candidate=candidate,
        job_position=job,
        first_name="سارا",
        last_name="محمدی",
        mobile_snapshot=candidate.mobile,
        city="تهران",
        employment=Application.Employment.FULL_TIME,
        experience=Application.Experience.YEARS_1_3,
        availability=Application.Availability.IMMEDIATE,
        last_title="x",
        last_company="y",
        status=status,
        idempotency_key=f"st-k-{unique}",
    )


def test_statemachine_allows_defined_transitions_only():
    assert is_transition_allowed(Application.Status.NEW, Application.Status.PHONE)
    assert is_transition_allowed(Application.Status.NEW, Application.Status.REJECTED)
    assert not is_transition_allowed(Application.Status.NEW, Application.Status.HIRED)
    assert not is_transition_allowed(Application.Status.PHONE, Application.Status.NEW)
    assert is_final(Application.Status.HIRED)
    assert is_final(Application.Status.REJECTED)
    assert not is_final(Application.Status.INTERVIEW)


def test_recruiter_can_perform_valid_transition(candidate_factory, job_position_factory, recruiter):
    application = _create_application(candidate_factory(), job_position_factory())
    updated = change_status(
        application_id=application.id,
        changed_by=recruiter,
        expected_version=application.version,
        to_status=Application.Status.PHONE,
    )
    assert updated.status == Application.Status.PHONE
    assert updated.version == application.version + 1


def test_invalid_transition_is_rejected(candidate_factory, job_position_factory, recruiter):
    application = _create_application(candidate_factory(), job_position_factory())
    with pytest.raises(InvalidTransition):
        change_status(
            application_id=application.id,
            changed_by=recruiter,
            expected_version=application.version,
            to_status=Application.Status.HIRED,
        )
    application.refresh_from_db()
    assert application.status == Application.Status.NEW
    assert application.version == 1


def test_rejected_transition_requires_reason(candidate_factory, job_position_factory, recruiter):
    application = _create_application(candidate_factory(), job_position_factory())
    with pytest.raises(ReasonRequired):
        change_status(
            application_id=application.id,
            changed_by=recruiter,
            expected_version=application.version,
            to_status=Application.Status.REJECTED,
        )
    application.refresh_from_db()
    assert application.status == Application.Status.NEW


def test_rejected_transition_succeeds_with_reason(candidate_factory, job_position_factory, recruiter):
    application = _create_application(candidate_factory(), job_position_factory())
    updated = change_status(
        application_id=application.id,
        changed_by=recruiter,
        expected_version=application.version,
        to_status=Application.Status.REJECTED,
        reason="عدم تطابق مهارت",
    )
    assert updated.status == Application.Status.REJECTED


@pytest.mark.parametrize("role_fixture", ["hiring_manager", "system_operator"])
def test_roles_without_status_change_permission_are_blocked(
    request, candidate_factory, job_position_factory, role_fixture
):
    actor = request.getfixturevalue(role_fixture)
    application = _create_application(candidate_factory(), job_position_factory())
    with pytest.raises(PermissionDenied):
        change_status(
            application_id=application.id,
            changed_by=actor,
            expected_version=application.version,
            to_status=Application.Status.PHONE,
        )
    application.refresh_from_db()
    assert application.status == Application.Status.NEW


def test_only_hr_manager_can_reopen_final_status_and_reason_is_mandatory(
    candidate_factory, job_position_factory, recruiter, hr_manager
):
    application = _create_application(candidate_factory(), job_position_factory(), status=Application.Status.HIRED)

    with pytest.raises(PermissionDenied):
        change_status(
            application_id=application.id,
            changed_by=recruiter,
            expected_version=application.version,
            to_status=Application.Status.REJECTED,
            reason="دلیل",
        )

    with pytest.raises(ReasonRequired):
        change_status(
            application_id=application.id,
            changed_by=hr_manager,
            expected_version=application.version,
            to_status=Application.Status.REJECTED,
        )

    updated = change_status(
        application_id=application.id,
        changed_by=hr_manager,
        expected_version=application.version,
        to_status=Application.Status.REJECTED,
        reason="بازگشایی استثنایی به دلیل خطای قبلی",
    )
    assert updated.status == Application.Status.REJECTED
    history = StatusHistory.objects.filter(application=application).latest("created_at")
    assert history.is_exception is True


def test_status_change_and_history_are_recorded_in_one_transaction(
    candidate_factory, job_position_factory, recruiter
):
    application = _create_application(candidate_factory(), job_position_factory())
    before_count = StatusHistory.objects.filter(application=application).count()
    change_status(
        application_id=application.id,
        changed_by=recruiter,
        expected_version=application.version,
        to_status=Application.Status.PHONE,
    )
    after_count = StatusHistory.objects.filter(application=application).count()
    assert after_count == before_count + 1


def test_notes_and_status_history_are_never_lost_or_overwritten_by_later_changes(
    candidate_factory, job_position_factory, recruiter, hr_manager
):
    """رگرسیون SC-008: افزودن یادداشت/تغییر وضعیت بعدی نباید رکوردهای قبلی را حذف/بازنویسی کند."""
    application = _create_application(candidate_factory(), job_position_factory())

    note1 = add_note(application=application, author=recruiter, body="یادداشت اول")
    change_status(
        application_id=application.id,
        changed_by=recruiter,
        expected_version=application.version,
        to_status=Application.Status.PHONE,
    )
    application.refresh_from_db()
    note2 = add_note(application=application, author=hr_manager, body="یادداشت دوم")
    change_status(
        application_id=application.id,
        changed_by=hr_manager,
        expected_version=application.version,
        to_status=Application.Status.INTERVIEW,
    )

    assert application.notes.filter(id=note1.id).exists()
    assert application.notes.filter(id=note2.id).exists()
    assert application.notes.count() == 2
    # این تست مستقیماً با Application.objects.create ساخته شده (نه submit_application)، پس
    # بدون رکورد «ثبت اولیه»؛ فقط دو تغییر وضعیت ثبت می‌شود.
    assert StatusHistory.objects.filter(application=application).count() == 2
