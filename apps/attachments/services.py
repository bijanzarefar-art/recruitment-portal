"""
بارگذاری تراکنشی فراداده/محتوا/کار اسکن (T030، FR-049, FR-052). از اصل V نسخهٔ ۲.۰.۰ به بعد
هیچ هویت تأییدشده‌ای در لحظهٔ بارگذاری وجود ندارد؛ تنها مکانیزم محدودکردن استفادهٔ فایل به همان
تلاش ارسال، `upload_attempt_key` است (FR-051). `Attachment.candidate` در این مرحله خالی
می‌ماند و فقط در `submit_application` (apps/applications/services.py) پر می‌شود.
"""
import ntpath
import posixpath

from django.db import transaction

from apps.operations.models import BackgroundJob

from .models import Attachment, AttachmentContent
from .validators import validate_resume_file


def _safe_filename(raw_name: str) -> str:
    """فقط نام پایه فایل (بدون مسیر/CRLF) را نگه می‌دارد تا در Content-Disposition امن باشد."""
    name = posixpath.basename(ntpath.basename(raw_name or "resume"))
    name = name.replace("\r", "").replace("\n", "")
    return name[:255] or "resume"


@transaction.atomic
def create_upload(*, upload_attempt_key: str, original_filename: str, content: bytes) -> Attachment:
    mime, size, digest = validate_resume_file(content)  # InvalidResumeFile در صورت نامعتبر بودن منتقل می‌شود

    attachment = Attachment.objects.create(
        upload_attempt_key=upload_attempt_key,
        original_filename=_safe_filename(original_filename),
        detected_mime_type=mime,
        size_bytes=size,
        sha256=digest,
        scan_status=Attachment.ScanStatus.PENDING,
    )
    AttachmentContent.objects.create(attachment=attachment, data=content)
    BackgroundJob.objects.create(
        job_type=BackgroundJob.JobType.SCAN_ATTACHMENT,
        payload={"attachment_id": str(attachment.id)},
    )
    return attachment
