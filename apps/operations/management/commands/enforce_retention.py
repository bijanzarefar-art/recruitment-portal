"""
حذف تراکنشی رکوردهای منقضی طبق سیاست نگهداری (T067a، FR-061) — **fail-closed**.

مبنای «منقضی»: آخرین `StatusHistory.created_at` برای پرونده، یا `updated_at` پرونده اگر هیچ
تغییر وضعیتی نداشته باشد. حذف `Application` آبشاری `Attachment`/`AttachmentContent`/
`StatusHistory`/`ApplicationNote`/`Consent` را نیز حذف می‌کند (CASCADE در مدل‌ها).

## شرایط اجرای حذف (همه الزامی و هم‌زمان)
۱. `settings.RETENTION_POLICY_APPROVED is True` — تأیید **سیاست کسب‌وکار** توسط ذی‌نفع (T069).
۲. `settings.RETENTION_OPERATIONAL_ENABLED is True` — فعال‌سازی **عملیاتی** در این محیط؛
   مستقل از تأیید سیاست، تا تصویب سیاست به‌طور خودکار حذف را روشن نکند.
۳. `settings.DATA_RETENTION_MONTHS` عدد صحیح مثبت باشد (نه bool، نه رشته).
۴. `--actor-id` به یک کارمند **فعال** با نقش `hr_manager` اشاره کند.

## مرز اعتماد اجراکننده
`--actor-id` فقط **انتساب عملیات** برای حسابرسی است؛ اثبات هویت اجراکننده نیست. هر کسی که به
shell سرور/دسترسی اجرای دستور مدیریتی دارد می‌تواند این مقدار را تنظیم کند. کنترل واقعی دسترسی
به اجرا در سطح عملیاتی است (دسترسی محدود به shell/CI، حسابرسی رویدادهای اجرا) و خارج از دامنه
این فرمان.

نبود هر یک از این‌ها اجرا را **پیش از هر حذف** با `CommandError` متوقف می‌کند.
`--dry-run` غیرمخرب است و حتی بدون داشتن شرایط هم فقط گزارش می‌دهد (برای بازبینی پیش از تصویب).

## حسابرسی — مسدود
رویدادهای `AuditEvent` **حذف نمی‌شوند**. قاعده `apps/audit/models.py` («فقط‌افزودنی») با نقش
دیتابیس واقعی برنامه در تضاد است (نقش فعلی superuser است و DELETE دارد؛ اصل VIII مستند است،
اجرا نشده). تا زمانی که یک مسیر نگهداری مصوب با نقش جداگانه و حداقل‌مجوز برای حسابرسی تعریف
نشود، پاک‌سازی `AuditEvent` عمداً انجام نمی‌شود. اگر سیاست مصوب به حذف حسابرسی نیاز داشت، این
فرمان باید با یک اتصال/نقش مجزا بازنویسی شود — نه با دادن DELETE به نقش عادی برنامه.
"""
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.applications.models import Application
from apps.audit.services import record_event


def _check_preconditions(actor_id: str):
    """پیش‌شرط‌ها را بررسی می‌کند؛ در صورت نقص `CommandError` می‌دهد (پیش از هر حذف)."""
    from apps.accounts.models import StaffUser

    problems = []

    if getattr(settings, "RETENTION_POLICY_APPROVED", False) is not True:
        problems.append(
            "RETENTION_POLICY_APPROVED فعال نیست. سیاست نگهداری هنوز توسط ذی‌نفع تصویب نشده است (T069)."
        )

    if getattr(settings, "RETENTION_OPERATIONAL_ENABLED", False) is not True:
        problems.append(
            "RETENTION_OPERATIONAL_ENABLED فعال نیست. حذف عملیاتی در این محیط روشن نشده است."
        )

    months = getattr(settings, "DATA_RETENTION_MONTHS", None)
    if not isinstance(months, int) or isinstance(months, bool) or months <= 0:
        problems.append(f"DATA_RETENTION_MONTHS معتبر نیست ({months!r})؛ باید عدد صحیح مثبت باشد.")

    if not actor_id:
        problems.append("--actor-id اجباری است (ثبت انتساب اجرا برای حسابرسی).")
        actor = None
    else:
        actor = StaffUser.objects.filter(id=actor_id, is_active=True).first()
        if actor is None:
            problems.append("شناسهٔ --actor-id به هیچ کارمند فعالی اشاره نمی‌کند.")
        elif actor.role != StaffUser.Role.HR_MANAGER:
            problems.append("--actor-id باید متعلق به یک مدیر HR باشد.")

    if problems:
        raise CommandError("اجرای حذف مسدود شد:\n" + "\n".join(f"  - {p}" for p in problems))
    return actor, months


class Command(BaseCommand):
    help = "حذف رکوردهای پرونده منقضی طبق سیاست نگهداری مصوب (FR-061). fail-closed."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="فقط تعداد قابل‌حذف را گزارش کن، بدون تغییر")
        parser.add_argument("--actor-id", default="", help="شناسهٔ مدیر HR تأییدکنندهٔ اجرا (اجباری برای حذف واقعی)")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        actor_id = options["actor_id"]

        actor = None
        months = getattr(settings, "DATA_RETENTION_MONTHS", None)
        if not dry_run:
            actor, months = _check_preconditions(actor_id)
        else:
            # در dry-run فقط برای گزارش؛ هیچ پیش‌شرطی اجرا را متوقف نمی‌کند.
            self._warn_if_not_approved()

        if not isinstance(months, int) or months <= 0:
            months = 12  # فقط برای محاسبهٔ گزارش dry-run؛ مقدار واقعی هرگز استفاده نمی‌شود.

        cutoff = timezone.now() - timedelta(days=30 * months)

        expired_ids = []
        for application in Application.objects.prefetch_related("status_history"):
            history = list(application.status_history.all())
            last_changed = max((h.created_at for h in history), default=application.updated_at)
            if last_changed < cutoff:
                expired_ids.append(application.id)

        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"[dry-run] {len(expired_ids)} پرونده منقضی برای حذف شناسایی شد.")
            )
            for application_id in expired_ids:
                self.stdout.write(f"  - {application_id}")
            return

        deleted = 0
        for application_id in expired_ids:
            with transaction.atomic():
                application = Application.objects.select_for_update().filter(id=application_id).first()
                if application is None:
                    continue
                application.delete()
                deleted += 1

        record_event(
            action="retention_enforced",
            staff_actor=actor,
            object_type="Application",
            metadata={"deleted_count": deleted, "retention_months": months, "cutoff": cutoff.isoformat()},
        )
        self.stdout.write(self.style.SUCCESS(f"{deleted} پرونده منقضی حذف شد."))

    def _warn_if_not_approved(self):
        """فقط هشدار در حالت dry-run؛ هیچ پیش‌شرطی اجرا را متوقف نمی‌کند (غیرمخرب)."""
        if getattr(settings, "RETENTION_POLICY_APPROVED", False) is not True:
            self.stdout.write(
                self.style.WARNING(
                    "توجه: RETENTION_POLICY_APPROVED فعال نیست — اجرای واقعی (بدون --dry-run) مسدود است."
                )
            )
        if getattr(settings, "RETENTION_OPERATIONAL_ENABLED", False) is not True:
            self.stdout.write(
                self.style.WARNING(
                    "توجه: RETENTION_OPERATIONAL_ENABLED فعال نیست — اجرای واقعی مسدود است."
                )
            )
