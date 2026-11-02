"""
مدیریت موقعیت شغلی توسط مدیر HR (T060/T060a، FR-038 تا FR-039a). بدون مسیر حذف فیزیکی —
فقط ایجاد/ویرایش/بستن/بازگشایی. هر تغییر حسابرسی می‌شود.
"""
from django.core.exceptions import PermissionDenied
from django.db import transaction

from apps.accounts.models import StaffUser
from apps.audit.services import record_event

from .models import JobPosition
from .statemachine import is_transition_allowed

EDITABLE_FIELDS = ("title", "department", "location", "requirements")


class InvalidJobTransition(Exception):
    pass


def _require_hr_manager(user: StaffUser) -> None:
    if user.role != StaffUser.Role.HR_MANAGER:
        raise PermissionDenied("فقط مدیر HR می‌تواند موقعیت شغلی را ایجاد/ویرایش/ببندد/بازگشایی کند.")


@transaction.atomic
def create_job(
    *, created_by: StaffUser, title: str, department: str = "", location: str = "", requirements: str = ""
) -> JobPosition:
    """موقعیت جدید همیشه `draft` می‌شود (FR-039a) — فعال‌سازی باید صریح باشد (`change_job_status`)."""
    _require_hr_manager(created_by)
    job = JobPosition.objects.create(
        title=title, department=department, location=location, requirements=requirements
    )
    record_event(
        action="job_created",
        staff_actor=created_by,
        object_type="JobPosition",
        object_id=str(job.id),
        metadata={"title": title, "status": job.status},
    )
    return job


@transaction.atomic
def update_job(*, job_id, updated_by: StaffUser, **fields) -> JobPosition:
    """ویرایش فیلدهای توصیفی فقط؛ تغییر وضعیت مسیر جداگانه (`change_job_status`) دارد."""
    _require_hr_manager(updated_by)

    invalid_fields = set(fields) - set(EDITABLE_FIELDS)
    if invalid_fields:
        raise ValueError(f"فیلدهای نامجاز برای ویرایش: {invalid_fields}")

    job = JobPosition.objects.select_for_update().get(id=job_id)
    for field, value in fields.items():
        setattr(job, field, value)
    job.save(update_fields=list(fields.keys()) + ["updated_at"])

    record_event(
        action="job_updated",
        staff_actor=updated_by,
        object_type="JobPosition",
        object_id=str(job.id),
        metadata={"fields": list(fields.keys())},
    )
    return job


@transaction.atomic
def change_job_status(*, job_id, changed_by: StaffUser, to_status: str) -> JobPosition:
    """
    تنها مسیر تغییر وضعیت (FR-039a): `draft→open`، `open→closed`، `closed→open`. ورود به
    `open` همیشه «بازگشایی/فعال‌سازی» است و فقط `hr_manager` مجاز است (همان `_require_hr_manager`);
    هر تغییر حسابرسی می‌شود. قفل ردیف تا با رقابت ثبت درخواست (`submit_application`) سریالی شود.
    """
    _require_hr_manager(changed_by)

    job = JobPosition.objects.select_for_update().get(id=job_id)
    from_status = job.status

    if not is_transition_allowed(from_status, to_status):
        raise InvalidJobTransition(f"انتقال {from_status}→{to_status} مجاز نیست.")

    job.status = to_status
    job.save(update_fields=["status", "updated_at"])

    action = "job_reopened" if to_status == JobPosition.Status.OPEN else "job_status_changed"
    record_event(
        action=action,
        staff_actor=changed_by,
        object_type="JobPosition",
        object_id=str(job.id),
        metadata={"from_status": from_status, "to_status": to_status},
    )
    return job


def close_job(*, job_id, closed_by: StaffUser) -> JobPosition:
    """بستن موقعیت (FR-039) — فقط از ثبت درخواست جدید جلوگیری می‌کند، سوابق قبلی اثر نمی‌پذیرند."""
    return change_job_status(job_id=job_id, changed_by=closed_by, to_status=JobPosition.Status.CLOSED)


def reopen_job(*, job_id, reopened_by: StaffUser) -> JobPosition:
    """بازگشایی (FR-039a) — فقط `hr_manager`، حسابرسی‌شده."""
    return change_job_status(job_id=job_id, changed_by=reopened_by, to_status=JobPosition.Status.OPEN)
