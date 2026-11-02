"""
سیاست مجوز نقش/رکورد (T020، FR-018 تا FR-021, FR-040)، سرویس ارجاع پرونده (T020a، رفع
یافته C2 در تحلیل)، و ثبت تراکنشی درخواست (T033، FR-007 تا FR-009).
"""
import hashlib
import json
import secrets

from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import QuerySet
from django.utils import timezone

from apps.accounts.models import StaffUser
from apps.attachments.models import Attachment
from apps.audit.services import record_event
from apps.candidates.services import resolve_candidate
from apps.jobs.models import JobPosition

from .models import (
    Application,
    ApplicationNote,
    ApplicationReviewer,
    Consent,
    IdempotencyRecord,
    PrivacyNotice,
    StatusHistory,
)
from .statemachine import is_final, is_transition_allowed


class DuplicateActiveApplication(Exception):
    pass


class VersionConflict(Exception):
    """درخواست روی نسخه قدیمی رکورد انجام شده (FR-029)."""


class InvalidTransition(Exception):
    pass


class ReasonRequired(Exception):
    pass


STATUS_CHANGE_ALLOWED_ROLES = (StaffUser.Role.RECRUITER, StaffUser.Role.HR_MANAGER)


class IdempotencyConflict(Exception):
    """همان کلید با بدنه متفاوت ارسال شده است."""


class JobNotOpen(Exception):
    pass


class AttachmentNotReady(Exception):
    pass


def get_applications_queryset(user: StaffUser) -> QuerySet[Application]:
    """پیش‌فرض منع (deny-by-default)؛ هیچ نقشی به‌صورت پیش‌فرض همه‌چیز نمی‌بیند."""
    base = Application.objects.all()

    if user.role == StaffUser.Role.HR_MANAGER:
        return base

    if user.role in (StaffUser.Role.RECRUITER, StaffUser.Role.HIRING_MANAGER):
        return base.filter(
            reviewer_assignments__reviewer=user,
            reviewer_assignments__revoked_at__isnull=True,
        ).distinct()

    # system_operator و هر نقش ناشناخته دیگر: هیچ پرونده تجاری (FR-021).
    return base.none()


def apply_staff_filters(queryset: QuerySet[Application], params) -> QuerySet[Application]:
    """
    فیلتر/جست‌وجوی مشترک فهرست و آمار (T043، FR-022 تا FR-024) تا دامنه هر دو دقیقاً یکسان
    بماند. `params` یک `QueryDict`/dict با کلیدهای اختیاری است؛ هیچ ورودی کاربر مستقیماً در
    SQL خام قرار نمی‌گیرد (همه از طریق ORM).
    """
    status_value = params.get("status")
    if status_value:
        queryset = queryset.filter(status=status_value)

    job_position = params.get("job_position")
    if job_position:
        queryset = queryset.filter(job_position_id=job_position)

    city = params.get("city")
    if city:
        queryset = queryset.filter(city__icontains=city)

    experience = params.get("experience")
    if experience:
        queryset = queryset.filter(experience=experience)

    date_from = params.get("date_from")
    if date_from:
        queryset = queryset.filter(created_at__date__gte=date_from)

    date_to = params.get("date_to")
    if date_to:
        queryset = queryset.filter(created_at__date__lte=date_to)

    reviewer = params.get("reviewer")
    if reviewer:
        queryset = queryset.filter(
            reviewer_assignments__reviewer_id=reviewer, reviewer_assignments__revoked_at__isnull=True
        )

    query_text = params.get("q")
    if query_text:
        from django.db.models import Q

        queryset = queryset.filter(
            Q(first_name__icontains=query_text)
            | Q(last_name__icontains=query_text)
            | Q(mobile_snapshot__icontains=query_text)
            | Q(tracking_code__icontains=query_text)
        )

    return queryset.distinct()


class AssignmentConflict(Exception):
    pass


ELIGIBLE_REVIEWER_ROLES = (StaffUser.Role.RECRUITER, StaffUser.Role.HIRING_MANAGER)


@transaction.atomic
def assign_reviewer(*, application: Application, reviewer: StaffUser, assigned_by: StaffUser) -> ApplicationReviewer:
    """
    اولین ارجاع باید به `recruiter` باشد؛ ارجاع بعدی به `hiring_manager` ارجاع فعال
    `recruiter` را بلافاصله باطل می‌کند (FR-041). فقط `recruiter`/`hiring_manager` صلاحیت
    دریافت ارجاع دارند (مطابق متن صریح FR-041 — نه ابهام، یک قید از‌قلم‌افتاده که اینجا رفع شد).

    قفل روی خودِ ردیف `Application` (نه فقط `ApplicationReviewer`) گرفته می‌شود تا دو درخواست
    ارجاع هم‌زمان روی همان پرونده کاملاً سریالی شوند؛ حتی اگر این قفل کافی نباشد، قید یکتایی
    دیتابیسی `uniq_active_reviewer_per_application` به‌عنوان خط دفاع دوم، درج دوم را به
    `AssignmentConflict` تبدیل می‌کند (نه خرابی رکورد).
    """
    if assigned_by.role != StaffUser.Role.HR_MANAGER:
        raise PermissionDenied("فقط مدیر HR می‌تواند ارجاع دهد.")

    if reviewer.role not in ELIGIBLE_REVIEWER_ROLES:
        raise PermissionDenied("فقط کارشناس جذب یا مدیر استخدام صلاحیت دریافت ارجاع دارند.")

    locked_application = Application.objects.select_for_update().get(id=application.id)

    current = (
        ApplicationReviewer.objects.select_for_update()
        .filter(application=locked_application, revoked_at__isnull=True)
        .first()
    )

    if reviewer.role == StaffUser.Role.HIRING_MANAGER and current is None:
        raise PermissionDenied("ارجاع مستقیم به مدیر استخدام بدون ارجاع قبلی به کارشناس جذب مجاز نیست.")

    if current is not None:
        current.revoked_at = timezone.now()
        current.save(update_fields=["revoked_at"])

    try:
        new_assignment = ApplicationReviewer.objects.create(
            application=locked_application,
            reviewer=reviewer,
            reviewer_role_at_assignment=reviewer.role,
            assigned_by=assigned_by,
        )
    except IntegrityError as exc:
        raise AssignmentConflict() from exc

    record_event(
        action="reviewer_assigned",
        staff_actor=assigned_by,
        object_type="Application",
        object_id=str(locked_application.id),
        metadata={"reviewer_id": str(reviewer.id), "reviewer_role": reviewer.role},
    )
    return new_assignment


@transaction.atomic
def revoke_reviewer(*, application: Application, revoked_by: StaffUser) -> None:
    if revoked_by.role != StaffUser.Role.HR_MANAGER:
        raise PermissionDenied("فقط مدیر HR می‌تواند ارجاع را لغو کند.")

    from django.utils import timezone

    updated = (
        ApplicationReviewer.objects.filter(application=application, revoked_at__isnull=True).update(
            revoked_at=timezone.now()
        )
    )
    if updated:
        record_event(
            action="reviewer_revoked",
            staff_actor=revoked_by,
            object_type="Application",
            object_id=str(application.id),
        )


def _generate_tracking_code() -> str:
    return secrets.token_hex(8)


def _hash_request(candidate_id, data: dict) -> str:
    canonical = json.dumps({"candidate": str(candidate_id), **data}, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


@transaction.atomic
def submit_application(*, mobile: str, upload_attempt_key: str, idempotency_key: str, data: dict) -> Application:
    """
    گام‌های «سازگاری ثبت درخواست» (plan.md): حل هویت متقاضی (بدون تأیید — اصل V نسخهٔ ۲.۰.۰)،
    قفل Attachment و IdempotencyRecord، بررسی بازبودن موقعیت/نسخه رضایت/قاعده تکرار، ایجاد
    Application+Consent+StatusHistory+AuditEvent+IdempotencyRecord در یک تراکنش؛ رسید فقط
    پس از commit صادر می‌شود.
    """
    candidate = resolve_candidate(mobile)
    request_hash = _hash_request(candidate.id, data)

    existing = (
        IdempotencyRecord.objects.select_for_update()
        .filter(candidate=candidate, idempotency_key=idempotency_key)
        .first()
    )
    if existing is not None:
        if existing.request_hash != request_hash:
            raise IdempotencyConflict()
        return existing.application

    attachment = (
        Attachment.objects.select_for_update()
        .filter(id=data["resume_upload_id"], upload_attempt_key=upload_attempt_key, application__isnull=True)
        .first()
    )
    if attachment is None or not attachment.is_downloadable:
        raise AttachmentNotReady()

    # قفل ردیف موقعیت شغلی تا رقابت «بستن موقعیت» و «ثبت درخواست» سریالی شود (FR-039، US6
    # الزام ۵) — بدون این قفل، بررسی `is_open_for_applications` روی نسخه از پیش‌خوانده‌شده در
    # حافظه ممکن است با یک بستن هم‌زمان ناسازگار شود؛ `close_job` هم همین ردیف را قفل می‌کند.
    job_position = JobPosition.objects.select_for_update().get(id=data["job_position_obj"].id)
    if not job_position.is_open_for_applications:
        raise JobNotOpen()

    if Application.objects.select_for_update().filter(
        candidate=candidate, job_position=job_position, status__in=Application.ACTIVE_STATUSES
    ).exists():
        raise DuplicateActiveApplication()

    privacy_notice = PrivacyNotice.objects.get(version=data["privacy_notice_version"])
    now = timezone.now()

    try:
        application = Application.objects.create(
            tracking_code=_generate_tracking_code(),
            candidate=candidate,
            job_position=job_position,
            first_name=data["first_name"],
            last_name=data["last_name"],
            mobile_snapshot=candidate.mobile,
            email=data.get("email", ""),
            city=data["city"],
            employment=data["employment"],
            experience=data["experience"],
            availability=data["availability"],
            last_title=data.get("last_title", ""),
            last_company=data.get("last_company", ""),
            status=Application.Status.NEW,
            idempotency_key=idempotency_key,
        )
    except IntegrityError as exc:
        raise DuplicateActiveApplication() from exc

    attachment.application = application
    attachment.candidate = candidate
    attachment.save(update_fields=["application", "candidate"])

    Consent.objects.create(application=application, privacy_notice=privacy_notice, accepted_at=now)
    StatusHistory.objects.create(
        application=application,
        from_status=Application.Status.NEW,
        to_status=Application.Status.NEW,
        changed_by=None,
        internal_reason="ثبت اولیه",
    )
    IdempotencyRecord.objects.create(
        candidate=candidate,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        application=application,
    )
    record_event(
        action="application_submitted",
        candidate_actor=candidate,
        object_type="Application",
        object_id=str(application.id),
    )
    return application


def lookup_by_tracking_code(tracking_code: str) -> Application | None:
    """
    جست‌وجوی عمومی با کد پیگیری (FR-012، FR-016؛ اصل V نسخهٔ ۲.۰.۰). بدون هیچ احراز هویتی؛
    فراخوان (view) باید پیش از این تابع نرخ‌محدودسازی را اعمال کرده باشد (FR-043) و برای
    `None`/موجود پاسخ کاملاً یکسان از نظر ظاهر/زمان‌بندی بدهد (FR-044).
    """
    return Application.objects.filter(tracking_code=tracking_code).select_related("job_position").first()


@transaction.atomic
def add_note(*, application: Application, author: StaffUser, body: str) -> ApplicationNote:
    """
    یادداشت جدید (T049، FR-026). دسترسی رکوردی توسط view (فیلتر با
    `get_applications_queryset`) پیش از فراخوانی این تابع تضمین شده؛ اینجا فقط ایجاد و
    حسابرسی انجام می‌شود. متن یادداشت هرگز در AuditEvent.metadata ذخیره نمی‌شود (الزام ۴).
    """
    note = ApplicationNote.objects.create(application=application, author=author, body=body)
    record_event(
        action="note_added",
        staff_actor=author,
        object_type="Application",
        object_id=str(application.id),
    )
    return note


@transaction.atomic
def change_status(
    *,
    application_id,
    changed_by: StaffUser,
    expected_version: int,
    to_status: str,
    reason: str = "",
) -> Application:
    """
    تغییر وضعیت (T050، FR-027 تا FR-031). قفل ردیف با `select_for_update` گرفته می‌شود تا
    رقابت هم‌زمان با ۴۰۹ (نه گم‌شدن تغییر) حل شود. تغییر وضعیت و درج `StatusHistory` در یک
    تراکنش واحد انجام می‌شود (FR-028)؛ `reason` هرگز در AuditEvent.metadata ذخیره نمی‌شود.

    قواعد نقش (مطابق متن مصوب نقش‌ها در spec.md، نه تعریف خودسرانه):
    - `hiring_manager` و `system_operator` هرگز نمی‌توانند وضعیت را تغییر دهند
      (FR-018 — «مدیر استخدام ... بدون تغییر وضعیت»).
    - `recruiter` و `hr_manager` می‌توانند انتقال‌های عادی (غیر-نهایی) را ثبت کنند.
    - فقط `hr_manager` می‌تواند یک وضعیت نهایی (`hired`/`rejected`) را بازگشایی/اصلاح کند
      (تغییر استثنایی، `is_exception=True`)، و فقط با ثبت دلیل (FR-031).
    """
    if changed_by.role not in STATUS_CHANGE_ALLOWED_ROLES:
        raise PermissionDenied("این نقش اجازه تغییر وضعیت را ندارد.")

    application = Application.objects.select_for_update().get(id=application_id)

    if application.version != expected_version:
        raise VersionConflict()

    from_status = application.status
    is_exception = is_final(from_status)

    if is_exception:
        if changed_by.role != StaffUser.Role.HR_MANAGER:
            raise PermissionDenied("فقط مدیر HR می‌تواند وضعیت نهایی را بازگشایی/اصلاح کند.")
        if not reason:
            raise ReasonRequired()
    else:
        if not is_transition_allowed(from_status, to_status):
            raise InvalidTransition()
        if to_status == Application.Status.REJECTED and not reason:
            raise ReasonRequired()

    application.status = to_status
    application.version = application.version + 1
    application.save(update_fields=["status", "version", "updated_at"])

    StatusHistory.objects.create(
        application=application,
        from_status=from_status,
        to_status=to_status,
        changed_by=changed_by,
        internal_reason=reason,
        is_exception=is_exception,
    )

    record_event(
        action="status_changed",
        staff_actor=changed_by,
        object_type="Application",
        object_id=str(application.id),
        metadata={"from_status": from_status, "to_status": to_status, "is_exception": is_exception},
    )
    return application
