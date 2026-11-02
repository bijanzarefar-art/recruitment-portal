"""صحت‌سنجی مسیر کامل US1 از طریق APIClient واقعی — بدون هیچ OTP (اصل V نسخهٔ ۲.۰.۰)."""
import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.applications.models import Application, PrivacyNotice

pytestmark = pytest.mark.django_db

PDF_HEADER = b"%PDF-1.4\n%fake pdf content for smoke test\n"


def test_full_apply_flow_via_http(job_position_factory):
    job = job_position_factory()
    PrivacyNotice.objects.create(version="smoke-v1", body="متن", published_at=timezone.now())

    client = APIClient()

    # ۱. مشاهده عمومی موقعیت‌ها
    resp = client.get("/api/v1/jobs")
    assert resp.status_code == 200
    assert any(item["id"] == str(job.id) for item in resp.json())

    # ۲. بارگذاری رزومه — بدون هیچ احراز هویتی؛ محدود فقط به‌وسیلهٔ upload_attempt_key (FR-051)
    from django.core.files.uploadedfile import SimpleUploadedFile

    upload_attempt_key = "smoke-attempt-1"
    resp = client.post(
        "/api/v1/candidate/uploads",
        {"file": SimpleUploadedFile("resume.pdf", PDF_HEADER, content_type="application/pdf")},
        format="multipart",
        HTTP_X_UPLOAD_ATTEMPT_KEY=upload_attempt_key,
    )
    assert resp.status_code == 201
    upload_id = resp.json()["id"]
    assert resp.json()["scan_status"] == "pending"

    # اسکن را به‌صورت دستی سالم علامت می‌زنیم (worker در این تست اجرا نمی‌شود)
    from apps.attachments.models import Attachment

    Attachment.objects.filter(id=upload_id).update(scan_status=Attachment.ScanStatus.CLEAN)

    # ۳. ثبت درخواست — mobile مستقیماً در بدنه، بدون هیچ نشست/تأیید
    resp = client.post(
        "/api/v1/candidate/applications",
        {
            "first_name": "سارا",
            "last_name": "احمدی",
            "mobile": "09121234567",
            "city": "تهران",
            "job_position": str(job.id),
            "employment": "full_time",
            "experience": "years_1_3",
            "availability": "immediate",
            "last_title": "طراح",
            "last_company": "شرکت ب",
            "resume_upload_id": upload_id,
            "privacy_notice_version": "smoke-v1",
            "consent": True,
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY="smoke-key-1",
        HTTP_X_UPLOAD_ATTEMPT_KEY=upload_attempt_key,
    )
    assert resp.status_code == 201, resp.content
    tracking_code = resp.json()["tracking_code"]
    assert Application.objects.filter(tracking_code=tracking_code, status="new").exists()

    # ۴. پیگیری فقط با کد پیگیری — بدون هیچ احراز هویتی (اصل V نسخهٔ ۲.۰.۰، FR-012)
    resp = client.get(f"/api/v1/track/{tracking_code}")
    assert resp.status_code == 200
    assert resp.json()["tracking_code"] == tracking_code

    # کد نامعتبر باید ۴۰۴ بگیرد، نه افشای وجود/عدم‌وجود (FR-016, FR-044)
    resp = client.get("/api/v1/track/this-code-does-not-exist")
    assert resp.status_code == 404


def test_upload_api_returns_413_for_oversized_file(settings):
    """T068: قرارداد ۴۱۳ را برای حجم بیش از حد مستند کرده بود، اما قبلاً کد همیشه ۴۱۵ می‌داد."""
    from django.core.files.uploadedfile import SimpleUploadedFile

    client = APIClient()
    settings.RESUME_MAX_SIZE_BYTES = 10

    resp = client.post(
        "/api/v1/candidate/uploads",
        {"file": SimpleUploadedFile("resume.pdf", PDF_HEADER, content_type="application/pdf")},
        format="multipart",
        HTTP_X_UPLOAD_ATTEMPT_KEY="oversized-attempt",
    )
    assert resp.status_code == 413


def test_upload_api_returns_415_for_wrong_type_within_size_limit():
    """T068: فایل کوچک اما با نوع نامعتبر باید ۴۱۵ بگیرد، نه ۴۱۳ (تفکیک از علت حجم)."""
    from django.core.files.uploadedfile import SimpleUploadedFile

    client = APIClient()

    resp = client.post(
        "/api/v1/candidate/uploads",
        {"file": SimpleUploadedFile("resume.exe", b"MZ\x90\x00not a pdf", content_type="application/octet-stream")},
        format="multipart",
        HTTP_X_UPLOAD_ATTEMPT_KEY="wrongtype-attempt",
    )
    assert resp.status_code == 415


def test_upload_api_requires_attempt_key_header():
    """FR-051: بدون X-Upload-Attempt-Key، بارگذاری رد می‌شود (اصل V نسخهٔ ۲.۰.۰، تنها مکانیزم کنترل دسترسی)."""
    from django.core.files.uploadedfile import SimpleUploadedFile

    client = APIClient()
    resp = client.post(
        "/api/v1/candidate/uploads",
        {"file": SimpleUploadedFile("resume.pdf", PDF_HEADER, content_type="application/pdf")},
        format="multipart",
    )
    assert resp.status_code == 400
