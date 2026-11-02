"""
فرمان مدیریتی بلندمدت worker به‌جای Celery/Redis (research.md §۲، T032).
کار اسکن فایل رزومه را با SELECT ... FOR UPDATE SKIP LOCKED برمی‌دارد، اسکنر را
فراخوانی و وضعیت Attachment را به‌روزرسانی می‌کند (FR-010).
"""
import logging
import time

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.attachments.models import Attachment, AttachmentContent
from apps.attachments.scanning.base import get_scanner_client
from apps.attachments.scanning.clamd_client import ScannerUnavailable
from apps.operations.models import BackgroundJob

logger = logging.getLogger("apps.operations.run_worker")

MAX_ATTEMPTS = 5
POLL_INTERVAL_SECONDS = 2


class Command(BaseCommand):
    help = "پردازشگر پس‌زمینه کارهای اسکن فایل و پاک‌سازی (research.md §۲)."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="فقط یک دور اجرا کن (برای تست)")

    def handle(self, *args, **options):
        while True:
            processed = self._process_one_batch()
            if options["once"]:
                return
            if not processed:
                time.sleep(POLL_INTERVAL_SECONDS)

    def _process_one_batch(self) -> bool:
        with transaction.atomic():
            job = (
                BackgroundJob.objects.select_for_update(skip_locked=True)
                .filter(status=BackgroundJob.Status.PENDING, job_type=BackgroundJob.JobType.SCAN_ATTACHMENT)
                .order_by("next_attempt_at")
                .first()
            )
            if job is None:
                return False
            job.status = BackgroundJob.Status.IN_PROGRESS
            job.save(update_fields=["status"])

        self._run_scan_job(job)
        return True

    def _run_scan_job(self, job: BackgroundJob) -> None:
        attachment_id = job.payload.get("attachment_id")
        try:
            attachment = Attachment.objects.get(id=attachment_id)
            content = AttachmentContent.objects.get(attachment=attachment).data
            result = get_scanner_client().scan(bytes(content))
        except ScannerUnavailable as exc:
            self._fail_or_retry(job, Attachment.ScanStatus.SCAN_FAILED, str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            logger.exception("scan job failed")
            self._fail_or_retry(job, Attachment.ScanStatus.SCAN_FAILED, str(exc))
            return

        attachment.scan_status = Attachment.ScanStatus.CLEAN if result.clean else Attachment.ScanStatus.QUARANTINED
        attachment.save(update_fields=["scan_status"])
        job.status = BackgroundJob.Status.SUCCEEDED
        job.save(update_fields=["status"])

    def _fail_or_retry(self, job: BackgroundJob, attachment_status: str, error_code: str) -> None:
        job.attempts += 1
        if job.attempts >= MAX_ATTEMPTS:
            job.status = BackgroundJob.Status.FAILED
            Attachment.objects.filter(id=job.payload.get("attachment_id")).update(scan_status=attachment_status)
        else:
            job.status = BackgroundJob.Status.PENDING
            job.next_attempt_at = timezone.now() + timezone.timedelta(seconds=2 ** job.attempts)
        job.error_code = error_code[:100]
        job.save(update_fields=["status", "attempts", "next_attempt_at", "error_code"])
