"""
T027/T075: نوع واقعی، مرز ۵ MiB، بدافزار/رمزگذاری، شکست پردازشگر، نام ناامن (FR-005, FR-010,
FR-049). مالکیت بارگذاری اکنون فقط با `upload_attempt_key` کنترل می‌شود (FR-051؛ اصل V نسخهٔ
۲.۰.۰ — دیگر هیچ هویت تأییدشده‌ای در لحظهٔ بارگذاری وجود ندارد).
"""
import pytest
from django.core.management import call_command

from apps.attachments.models import Attachment
from apps.attachments.scanning.base import ScanResult
from apps.attachments.scanning.clamd_client import ScannerUnavailable
from apps.attachments.services import create_upload
from apps.attachments.validators import InvalidResumeFile, ResumeTooLarge
from apps.operations.models import BackgroundJob

pytestmark = pytest.mark.django_db

PDF_HEADER = b"%PDF-1.4\n%fake pdf content for tests\n"


def test_upload_rejects_oversized_file(settings):
    settings.RESUME_MAX_SIZE_BYTES = 10
    with pytest.raises(InvalidResumeFile):
        create_upload(upload_attempt_key="a1", original_filename="resume.pdf", content=PDF_HEADER)


def test_oversized_file_raises_the_specific_subclass(settings):
    """T068: حجم بیش از سقف باید `ResumeTooLarge` (زیرکلاس) باشد، نه `InvalidResumeFile` عمومی."""
    settings.RESUME_MAX_SIZE_BYTES = 10
    with pytest.raises(ResumeTooLarge):
        create_upload(upload_attempt_key="a1b", original_filename="resume.pdf", content=PDF_HEADER)


def test_upload_rejects_unrecognized_type():
    with pytest.raises(InvalidResumeFile):
        create_upload(
            upload_attempt_key="a2",
            original_filename="resume.exe",
            content=b"MZ\x90\x00 not a real resume",
        )


def test_upload_ignores_claimed_filename_extension_and_uses_magic_bytes():
    """پسوند فایل گمراه‌کننده است (.docx) اما محتوا واقعاً PDF است؛ باید روی magic bytes تشخیص شود."""
    attachment = create_upload(upload_attempt_key="a3", original_filename="resume.docx", content=PDF_HEADER)
    assert attachment.detected_mime_type == "application/pdf"


def test_upload_has_no_candidate_until_attached_to_an_application():
    """FR-051: در لحظهٔ بارگذاری هیچ هویتی وجود ندارد؛ candidate فقط در submit_application پر می‌شود."""
    attachment = create_upload(upload_attempt_key="a4", original_filename="resume.pdf", content=PDF_HEADER)
    assert attachment.candidate_id is None


def test_upload_is_bound_to_its_own_attempt_key_not_another_attempts():
    attachment_x = create_upload(upload_attempt_key="attempt-x", original_filename="resume.pdf", content=PDF_HEADER)
    assert not Attachment.objects.filter(id=attachment_x.id, upload_attempt_key="attempt-y").exists()
    assert Attachment.objects.filter(id=attachment_x.id, upload_attempt_key="attempt-x").exists()


def test_worker_marks_malicious_file_quarantined_not_clean(monkeypatch):
    attachment = create_upload(upload_attempt_key="a5", original_filename="resume.pdf", content=PDF_HEADER)

    monkeypatch.setattr(
        "apps.operations.management.commands.run_worker.get_scanner_client",
        lambda: type("FakeScanner", (), {"scan": lambda self, content: ScanResult(clean=False, reason="EICAR")})(),
    )
    call_command("run_worker", "--once")

    attachment.refresh_from_db()
    assert attachment.scan_status == Attachment.ScanStatus.QUARANTINED
    assert attachment.scan_status != Attachment.ScanStatus.CLEAN


def test_worker_scanner_outage_marks_scan_failed_not_clean(monkeypatch):
    attachment = create_upload(upload_attempt_key="a6", original_filename="resume.pdf", content=PDF_HEADER)

    def _raise(*args, **kwargs):
        raise ScannerUnavailable("اتصال به ClamAV قطع است")

    monkeypatch.setattr(
        "apps.operations.management.commands.run_worker.get_scanner_client",
        lambda: type("FailingScanner", (), {"scan": _raise})(),
    )
    for _ in range(5):
        call_command("run_worker", "--once")

    attachment.refresh_from_db()
    job = BackgroundJob.objects.get(payload__attachment_id=str(attachment.id))
    assert job.status == BackgroundJob.Status.FAILED
    assert attachment.scan_status == Attachment.ScanStatus.SCAN_FAILED
    assert attachment.scan_status != Attachment.ScanStatus.CLEAN


def test_unsafe_filename_is_stripped_to_safe_basename():
    unsafe_name = "../../../etc/passwd\r\nX-Injected: evil" + "x" * 300
    attachment = create_upload(upload_attempt_key="a7", original_filename=unsafe_name, content=PDF_HEADER)
    assert len(attachment.original_filename) <= 255
    assert "/" not in attachment.original_filename
    assert "\r" not in attachment.original_filename
    assert "\n" not in attachment.original_filename
