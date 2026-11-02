"""
T076 (جایگزین T036): ثبت کامل از یک «دستگاه» (کانتکست مرورگر) بدون هیچ مرحلهٔ OTP (اصل V
نسخهٔ ۲.۰.۰) — فرم اکنون تک‌مرحله‌ای است: فیلدها (شامل موبایل) + رزومه + ارسال.
"""
import re
import threading
import time

import pytest
from django.core.management import call_command
from django.db import close_old_connections
from django.utils import timezone
from playwright.sync_api import expect

from apps.applications.models import Application, PrivacyNotice
from apps.attachments.scanning.base import ScanResult
from apps.jobs.models import JobPosition

pytestmark = pytest.mark.django_db(transaction=True)


def _run_background_worker_until(stop_event: threading.Event) -> None:
    """شبیه‌سازی `python manage.py run_worker` در پس‌زمینه تا تست مرورگری بدون نیاز به
    کانتینر worker جدا، اسکن فایل را واقعی (نه موک) اما فوری انجام دهد."""
    close_old_connections()
    while not stop_event.is_set():
        call_command("run_worker", "--once")
        time.sleep(0.3)
    close_old_connections()


def test_candidate_submission_end_to_end_and_visible_in_database(live_server, page, monkeypatch):
    job = JobPosition.objects.create(title="برنامه‌نویس بک‌اند", status=JobPosition.Status.OPEN)
    PrivacyNotice.objects.create(version="browser-v1", body="متن", published_at=timezone.now())

    # این تست مرورگری UI را آزمون می‌کند، نه موتور ClamAV (که در
    # tests/integration/test_malware_scan_real_clamav.py جداگانه و واقعی آزموده شده)؛
    # اینجا یک اسکنر ساختگی همیشه‌سالم جایگزین می‌شود تا worker واقعی بدون وابستگی به
    # دسترسی شبکه ClamAV در این محیط اجرا شود.
    monkeypatch.setattr(
        "apps.operations.management.commands.run_worker.get_scanner_client",
        lambda: type("FakeScanner", (), {"scan": lambda self, content: ScanResult(clean=True)})(),
    )

    stop_event = threading.Event()
    worker_thread = threading.Thread(target=_run_background_worker_until, args=(stop_event,), daemon=True)
    worker_thread.start()

    try:
        page.goto(f"{live_server.url}/apply")

        expect(page.locator("#application-section")).to_be_visible()

        page.fill("#first_name", "تست")
        page.fill("#last_name", "مرورگری")
        page.fill("#mobile", "09127654321")
        page.fill("#city", "تهران")
        page.select_option("#job_position", str(job.id))
        page.select_option("#employment", "full_time")
        page.select_option("#experience", "years_1_3")
        page.fill("#last_title", "برنامه‌نویس")
        page.fill("#last_company", "شرکت الف")
        page.select_option("#availability", "immediate")

        import os

        fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "sample_resume.pdf")
        page.set_input_files("#resume", fixture_path)
        page.check("input[name='consent']")
        page.click("#apply-form button[type=submit]")

        tracking_code_el = page.locator("#receipt-tracking-code")
        expect(tracking_code_el).not_to_have_text("", timeout=15000)
        tracking_code = tracking_code_el.text_content()
        assert re.match(r"^[0-9a-f]{16}$", tracking_code or "")

        application = Application.objects.get(tracking_code=tracking_code)
        assert application.job_position_id == job.id
        assert application.status == Application.Status.NEW
    finally:
        stop_event.set()
        worker_thread.join(timeout=5)
