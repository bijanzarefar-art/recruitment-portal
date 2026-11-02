"""
فرمان مدیریتی انتقال دستی موبایل متقاضی (T025a، FR-064). هیچ مسیر خودکار/سمت‌کلاینت
برای این کار وجود ندارد؛ فقط از طریق این فرمان، پس از تماس مستقیم متقاضی با HR.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import StaffUser
from apps.audit.services import record_event
from apps.common.text import normalize_mobile

from ...models import Candidate


class Command(BaseCommand):
    help = "انتقال درخواست‌های یک متقاضی از موبایل قبلی به موبایل جدید (فقط دستی، توسط مدیر HR)."

    def add_arguments(self, parser):
        parser.add_argument("--old-mobile", required=True, dest="old_mobile")
        parser.add_argument("--new-mobile", required=True, dest="new_mobile")
        parser.add_argument("--reason", required=True)
        parser.add_argument("--performed-by", required=True, dest="performed_by")

    @transaction.atomic
    def handle(self, *args, **options):
        performer = StaffUser.objects.filter(username=options["performed_by"]).first()
        if performer is None or performer.role != StaffUser.Role.HR_MANAGER:
            raise CommandError("فقط مدیر HR می‌تواند این انتقال را انجام دهد.")

        old_mobile = normalize_mobile(options["old_mobile"])
        new_mobile = normalize_mobile(options["new_mobile"])

        try:
            candidate = Candidate.objects.select_for_update().get(mobile=old_mobile)
        except Candidate.DoesNotExist as exc:
            raise CommandError("متقاضی با این موبایل یافت نشد.") from exc

        if Candidate.objects.filter(mobile=new_mobile).exists():
            raise CommandError("موبایل جدید از قبل متعلق به متقاضی دیگری است.")

        candidate.mobile = new_mobile
        candidate.save(update_fields=["mobile"])

        record_event(
            action="mobile_transfer",
            staff_actor=performer,
            object_type="Candidate",
            object_id=str(candidate.id),
            metadata={"old_mobile": old_mobile, "new_mobile": new_mobile, "reason": options["reason"]},
        )

        self.stdout.write(self.style.SUCCESS(f"موبایل متقاضی از {old_mobile} به {new_mobile} منتقل شد."))
