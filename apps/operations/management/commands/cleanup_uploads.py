"""
حذف تراکنشی بارگذاری‌های یتیم (بدون Application) پس از ۲۴ ساعت (T034، FR-053).
ترتیب قفل‌گیری با مسیر ثبت (apps/applications/services.submit_application) یکسان است:
قفل ردیف Attachment پیش از حذف گرفته می‌شود تا فایلی که درحال‌اتصال است حذف نشود.
"""
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.attachments.models import Attachment


class Command(BaseCommand):
    help = "پاک‌سازی بارگذاری‌های موقت بدون Application که از مهلت مقرر گذشته‌اند."

    def handle(self, *args, **options):
        cutoff = timezone.now() - timezone.timedelta(hours=settings.UPLOAD_ORPHAN_CLEANUP_AFTER_HOURS)
        deleted_count = 0

        orphan_ids = list(
            Attachment.objects.filter(application__isnull=True, created_at__lt=cutoff).values_list("id", flat=True)
        )
        for attachment_id in orphan_ids:
            with transaction.atomic():
                attachment = (
                    Attachment.objects.select_for_update()
                    .filter(id=attachment_id, application__isnull=True, created_at__lt=cutoff)
                    .first()
                )
                if attachment is None:
                    continue  # هم‌زمان به یک درخواست متصل شد؛ از حذف صرف‌نظر می‌شود.
                attachment.delete()  # AttachmentContent با on_delete=CASCADE حذف می‌شود.
                deleted_count += 1

        self.stdout.write(self.style.SUCCESS(f"{deleted_count} بارگذاری یتیم پاک‌سازی شد."))
