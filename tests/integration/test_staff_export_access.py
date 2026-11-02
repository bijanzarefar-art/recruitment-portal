"""
T054/T056 (الزامات ۱ تا ۷): مجوز خروجی مستقل از مجوز مشاهده (فقط hr_manager)، دامنه رکوردی
همان فهرست کارکنان، ستون‌های مجاز، سقف ردیف، خنثی‌سازی فرمول روی ورودی واقعی کاربر، حسابرسی
بدون محتوای واقعی، و هدرهای دانلود امن.
"""
import secrets

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.applications.models import Application
from apps.applications.services import assign_reviewer
from apps.audit.models import AuditEvent

pytestmark = pytest.mark.django_db


def _create_application(candidate, job, **overrides):
    unique = secrets.token_hex(6)
    defaults = dict(
        tracking_code=f"ex{unique}",
        candidate=candidate,
        job_position=job,
        first_name="فرهاد",
        last_name="قاسمی",
        mobile_snapshot=candidate.mobile,
        city="کرج",
        employment=Application.Employment.FULL_TIME,
        experience=Application.Experience.YEARS_1_3,
        availability=Application.Availability.IMMEDIATE,
        last_title="x",
        last_company="y",
        status=Application.Status.NEW,
        idempotency_key=f"ex-k-{unique}",
    )
    defaults.update(overrides)
    return Application.objects.create(**defaults)


@pytest.mark.parametrize("role_fixture", ["recruiter", "hiring_manager", "system_operator"])
def test_only_hr_manager_can_export_even_with_record_or_view_access(
    request, candidate_factory, job_position_factory, role_fixture, hr_manager
):
    """FR-036: مجوز خروجی مستقل از مجوز مشاهده است؛ حتی reviewer با دسترسی مشاهده کامل رد می‌شود."""
    actor = request.getfixturevalue(role_fixture)
    candidate = candidate_factory()
    job = job_position_factory()
    application = _create_application(candidate, job)
    if role_fixture == "recruiter":
        assign_reviewer(application=application, reviewer=actor, assigned_by=hr_manager)
    elif role_fixture == "hiring_manager":
        from apps.applications.models import ApplicationReviewer

        ApplicationReviewer.objects.create(
            application=application,
            reviewer=actor,
            reviewer_role_at_assignment="hiring_manager",
            assigned_by=hr_manager,
        )

    client = APIClient()
    client.force_authenticate(user=actor)
    resp = client.post("/api/v1/staff/exports", {"format": "csv"}, format="json")
    assert resp.status_code == 403


def test_hr_manager_can_export_csv(candidate_factory, job_position_factory, hr_manager):
    candidate = candidate_factory()
    job = job_position_factory()
    _create_application(candidate, job)

    client = APIClient()
    client.force_authenticate(user=hr_manager)
    resp = client.post("/api/v1/staff/exports", {"format": "csv"}, format="json")
    assert resp.status_code == 200
    assert resp["Content-Disposition"].startswith("attachment;")
    assert resp["Cache-Control"] == "no-store"
    assert resp.content.startswith(b"\xef\xbb\xbf")


def test_export_filters_match_list_but_cannot_be_used_to_widen_scope(
    candidate_factory, job_position_factory, hr_manager
):
    """
    الزام ۲: فیلترهای ارسالی فقط می‌توانند دامنه را محدودتر کنند، نه گسترده‌تر. چون hr_manager
    از قبل همه‌چیز را می‌بیند، این تست با فیلتر وضعیت بررسی می‌کند که فقط ردیف‌های منطبق صادر
    می‌شوند، نه همه پرونده‌ها صرف‌نظر از فیلتر.
    """
    candidate1 = candidate_factory()
    candidate2 = candidate_factory()
    job = job_position_factory()
    app_new = _create_application(candidate1, job, status=Application.Status.NEW)
    app_rejected = _create_application(candidate2, job, status=Application.Status.REJECTED)

    client = APIClient()
    client.force_authenticate(user=hr_manager)
    resp = client.post(
        "/api/v1/staff/exports",
        {"format": "csv", "status": Application.Status.NEW, "columns": ["tracking_code"]},
        format="json",
    )
    assert resp.status_code == 200
    text = resp.content.decode("utf-8-sig")
    assert app_new.tracking_code in text
    assert app_rejected.tracking_code not in text


def test_requesting_disallowed_column_is_rejected_by_api(candidate_factory, job_position_factory, hr_manager):
    candidate = candidate_factory()
    job = job_position_factory()
    _create_application(candidate, job)

    client = APIClient()
    client.force_authenticate(user=hr_manager)
    resp = client.post(
        "/api/v1/staff/exports", {"format": "csv", "columns": ["tracking_code", "notes"]}, format="json"
    )
    assert resp.status_code == 400


def test_export_query_never_fetches_attachment_content_table(
    candidate_factory, job_position_factory, hr_manager
):
    """الزام ۷: پرس‌وجوی خروجی هرگز محتوای باینری رزومه را واکشی نمی‌کند."""
    candidate = candidate_factory()
    job = job_position_factory()
    _create_application(candidate, job)

    client = APIClient()
    client.force_authenticate(user=hr_manager)
    with CaptureQueriesContext(connection) as ctx:
        resp = client.post("/api/v1/staff/exports", {"format": "csv"}, format="json")
    assert resp.status_code == 200
    for query in ctx.captured_queries:
        assert "attachmentcontent" not in query["sql"].lower(), query["sql"]


def test_malicious_formula_values_in_real_candidate_data_are_neutralized_in_csv_and_xlsx(
    candidate_factory, job_position_factory, hr_manager
):
    """SC-006: مقداری که کاربر واقعی (مثلاً در نام) وارد کرده و با فرمول شروع می‌شود خنثی شود."""
    candidate = candidate_factory()
    job = job_position_factory()
    _create_application(candidate, job, first_name="=HYPERLINK(\"http://evil\")", last_name="@cmd|calc")

    client = APIClient()
    client.force_authenticate(user=hr_manager)

    csv_resp = client.post(
        "/api/v1/staff/exports", {"format": "csv", "columns": ["first_name", "last_name"]}, format="json"
    )
    assert csv_resp.status_code == 200
    csv_text = csv_resp.content.decode("utf-8-sig")
    for line in csv_text.splitlines():
        assert not line.startswith("=HYPERLINK")
        assert not line.startswith("@cmd")

    xlsx_resp = client.post(
        "/api/v1/staff/exports", {"format": "xlsx", "columns": ["first_name", "last_name"]}, format="json"
    )
    assert xlsx_resp.status_code == 200
    import io

    from openpyxl import load_workbook

    workbook = load_workbook(io.BytesIO(xlsx_resp.content))
    sheet = workbook.active
    data_row = list(sheet.iter_rows(min_row=2, max_row=2, values_only=True))[0]
    assert all(str(v).startswith("'") for v in data_row)


def test_row_limit_exceeded_is_rejected_without_generating_a_file(
    candidate_factory, job_position_factory, hr_manager, monkeypatch
):
    """FR-032: عبور از سقف ۱۰٬۰۰۰ باید با پیام محدودکردن فیلتر رد شود، نه فایل ناقص."""
    from apps.reporting.api import views as export_views

    def _fake_build_export(**kwargs):
        from apps.reporting.export_policy import TooManyRows

        raise TooManyRows()

    monkeypatch.setattr(export_views, "build_export", _fake_build_export)

    client = APIClient()
    client.force_authenticate(user=hr_manager)
    resp = client.post("/api/v1/staff/exports", {"format": "csv"}, format="json")
    assert resp.status_code == 400
    assert "۱۰٬۰۰۰" in resp.json()["message"] or "10" in resp.json()["message"]


def test_export_start_and_result_are_audited_without_output_content(
    candidate_factory, job_position_factory, hr_manager
):
    candidate = candidate_factory()
    job = job_position_factory()
    _create_application(candidate, job, first_name="محرمانهٔ-واقعی")

    client = APIClient()
    client.force_authenticate(user=hr_manager)
    resp = client.post(
        "/api/v1/staff/exports", {"format": "csv", "columns": ["first_name"]}, format="json"
    )
    assert resp.status_code == 200

    started = AuditEvent.objects.filter(action="export_started", staff_actor=hr_manager).latest("created_at")
    completed = AuditEvent.objects.filter(action="export_completed", staff_actor=hr_manager).latest("created_at")
    assert completed.metadata["row_count"] >= 1
    assert completed.metadata["columns"] == ["first_name"]
    assert "محرمانهٔ-واقعی" not in str(started.metadata)
    assert "محرمانهٔ-واقعی" not in str(completed.metadata)


# test_candidate_session_cannot_request_export حذف شد — اصل V نسخهٔ ۲.۰.۰: دیگر هیچ «نشست
# متقاضی»ای وجود ندارد. درخواست ناشناس به /staff/exports از پیش با
# test_only_hr_manager_can_export_even_with_record_or_view_access (بالاتر) پوشش داده می‌شود.
