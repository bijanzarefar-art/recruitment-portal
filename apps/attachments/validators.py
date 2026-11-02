"""بررسی امضای واقعی فایل، پسوند و حجم سمت سرور (FR-049, FR-005)."""
import hashlib

from django.conf import settings

_MAGIC_BYTES = {
    b"%PDF": "application/pdf",
    b"\xd0\xcf\x11\xe0": "application/msword",  # فرمت OLE قدیمی DOC
    b"PK\x03\x04": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # DOCX (zip)
}


class InvalidResumeFile(Exception):
    pass


class ResumeTooLarge(InvalidResumeFile):
    """
    زیرکلاس عمدی `InvalidResumeFile` (T068 — رفع مغایرت واقعی قرارداد/کد): قبلاً حجم نامعتبر و
    نوع نامعتبر هر دو همان `InvalidResumeFile` را raise می‌کردند و لایه API همه را به ۴۱۵
    (نوع نامعتبر) ترجمه می‌کرد، در حالی‌که قرارداد ۴۱۳ را برای حجم مستند کرده بود. با این
    زیرکلاس، `except InvalidResumeFile` قدیمی (و تست‌های موجود) همچنان بدون تغییر کار می‌کنند،
    اما لایه API اکنون می‌تواند این حالت را جدا بگیرد و ۴۱۳ واقعی برگرداند.
    """


def detect_mime_type(content: bytes) -> str:
    for magic, mime in _MAGIC_BYTES.items():
        if content.startswith(magic):
            return mime
    raise InvalidResumeFile("نوع فایل پشتیبانی نمی‌شود")


def validate_resume_file(content: bytes) -> tuple[str, int, str]:
    """برمی‌گرداند: (detected_mime_type, size_bytes, sha256)."""
    size = len(content)
    if size == 0 or size > settings.RESUME_MAX_SIZE_BYTES:
        raise ResumeTooLarge("حجم فایل نامعتبر است (حداکثر ۵ MiB)")

    mime = detect_mime_type(content)
    if mime not in settings.RESUME_ALLOWED_MIME_TYPES:
        raise InvalidResumeFile("نوع فایل پشتیبانی نمی‌شود")

    digest = hashlib.sha256(content).hexdigest()
    return mime, size, digest
