"""
فرمان مدیریتی محدود ساخت حساب کارمند (T025، FR-020)؛ ثبت‌نام عمومی کارکنان ممنوع است.
اصل V نسخهٔ ۳.۰.۰: ورود فقط نام‌کاربری/رمز عبور است؛ حساب بلافاصله قابل ورود است.
"""
import getpass

from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import StaffUser
from apps.audit.services import record_event


class Command(BaseCommand):
    help = "ساخت حساب کارمند جدید با نقش مشخص (فقط از طریق فرمان مدیریتی، نه ثبت‌نام عمومی)."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)
        parser.add_argument("--role", required=True, choices=StaffUser.Role.values)
        parser.add_argument("--created-by", dest="created_by", help="نام کاربری عامل ایجادکننده (برای حسابرسی)")

    def handle(self, *args, **options):
        if StaffUser.objects.filter(username=options["username"]).exists():
            raise CommandError("این نام کاربری از قبل وجود دارد.")

        password = getpass.getpass("رمز عبور کارمند: ")
        created_by = None
        if options.get("created_by"):
            created_by = StaffUser.objects.filter(username=options["created_by"]).first()

        user = StaffUser.objects.create_user(
            username=options["username"], password=password, role=options["role"], created_by=created_by
        )

        record_event(
            action="staff_account_created",
            staff_actor=created_by,
            object_type="StaffUser",
            object_id=str(user.id),
            metadata={"role": user.role},
        )

        self.stdout.write(self.style.SUCCESS(f"حساب {user.username} ساخته شد و بلافاصله قابل ورود است."))
