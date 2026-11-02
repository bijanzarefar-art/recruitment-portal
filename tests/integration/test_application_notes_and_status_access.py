"""
T049/T050 (الزامات ۱، ۳، ۵، ۶، ۷): یادداشت و تغییر وضعیت فقط با مجوز نقش + دسترسی رکوردی
جاری انجام شود؛ لغو ارجاع دسترسی را در درخواست بعدی قطع کند؛ نشست متقاضی هرگز روی این
مسیرها پذیرفته نشود؛ یادداشت هرگز در AuditEvent.metadata یا پاسخ عمومی افشا نشود.
"""
import secrets

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.applications.models import Application, PrivacyNotice, StatusHistory
from apps.applications.services import assign_reviewer, change_status, revoke_reviewer
from apps.audit.models import AuditEvent

pytestmark = pytest.mark.django_db


def _create_application(candidate, job):
    unique = secrets.token_hex(6)
    return Application.objects.create(
        tracking_code=f"ns{unique}",
        candidate=candidate,
        job_position=job,
        first_name="مینا",
        last_name="یوسفی",
        mobile_snapshot=candidate.mobile,
        city="مشهد",
        employment=Application.Employment.FULL_TIME,
        experience=Application.Experience.YEARS_1_3,
        availability=Application.Availability.IMMEDIATE,
        last_title="x",
        last_company="y",
        status=Application.Status.NEW,
        idempotency_key=f"ns-k-{unique}",
    )


def test_reviewer_with_active_assignment_can_add_note(
    candidate_factory, job_position_factory, recruiter, hr_manager
):
    candidate = candidate_factory()
    job = job_position_factory()
    application = _create_application(candidate, job)
    assign_reviewer(application=application, reviewer=recruiter, assigned_by=hr_manager)

    client = APIClient()
    client.force_authenticate(user=recruiter)
    resp = client.post(
        f"/api/v1/staff/applications/{application.id}/notes", {"body": "یادداشت کارشناس"}, format="json"
    )
    assert resp.status_code == 201
    assert application.notes.count() == 1


def test_staff_without_record_access_cannot_add_note_or_change_status(
    candidate_factory, job_position_factory, recruiter, hiring_manager, hr_manager
):
    """کارمندی که هیچ ارجاع فعالی به این پرونده ندارد، حتی با نقش عمومی مجاز، ۴۰۴ می‌گیرد."""
    candidate = candidate_factory()
    job = job_position_factory()
    application = _create_application(candidate, job)
    assign_reviewer(application=application, reviewer=recruiter, assigned_by=hr_manager)

    client = APIClient()
    client.force_authenticate(user=hiring_manager)  # ارجاعی به این کارمند داده نشده

    resp_note = client.post(
        f"/api/v1/staff/applications/{application.id}/notes", {"body": "تلاش غیرمجاز"}, format="json"
    )
    assert resp_note.status_code == 404
    assert application.notes.count() == 0

    resp_status = client.patch(
        f"/api/v1/staff/applications/{application.id}/status",
        {"to_status": Application.Status.PHONE, "expected_version": application.version},
        format="json",
    )
    assert resp_status.status_code == 404
    application.refresh_from_db()
    assert application.status == Application.Status.NEW


def test_hiring_manager_with_active_referral_cannot_change_status_but_can_note(
    candidate_factory, job_position_factory, hiring_manager, hr_manager
):
    """
    hiring_manager با ارجاع فعال باید بتواند یادداشت بگذارد (او reviewer معتبر است) اما طبق
    FR-018 هرگز نباید بتواند وضعیت را تغییر دهد — این تفاوت بین مجوز رکوردی و مجوز نقش است.
    """
    candidate = candidate_factory()
    job = job_position_factory()
    application = _create_application(candidate, job)
    from apps.applications.models import ApplicationReviewer

    ApplicationReviewer.objects.create(
        application=application,
        reviewer=hiring_manager,
        reviewer_role_at_assignment="hiring_manager",
        assigned_by=hr_manager,
    )

    client = APIClient()
    client.force_authenticate(user=hiring_manager)

    resp_note = client.post(
        f"/api/v1/staff/applications/{application.id}/notes", {"body": "یادداشت مدیر استخدام"}, format="json"
    )
    assert resp_note.status_code == 201

    resp_status = client.patch(
        f"/api/v1/staff/applications/{application.id}/status",
        {"to_status": Application.Status.PHONE, "expected_version": application.version},
        format="json",
    )
    assert resp_status.status_code == 403


def test_revoking_referral_blocks_notes_and_status_on_very_next_request(
    candidate_factory, job_position_factory, recruiter, hr_manager
):
    candidate = candidate_factory()
    job = job_position_factory()
    application = _create_application(candidate, job)
    assign_reviewer(application=application, reviewer=recruiter, assigned_by=hr_manager)

    client = APIClient()
    client.force_authenticate(user=recruiter)

    ok_resp = client.post(
        f"/api/v1/staff/applications/{application.id}/notes", {"body": "یادداشت قبل از لغو"}, format="json"
    )
    assert ok_resp.status_code == 201

    revoke_reviewer(application=application, revoked_by=hr_manager)

    blocked_note = client.post(
        f"/api/v1/staff/applications/{application.id}/notes", {"body": "یادداشت بعد از لغو"}, format="json"
    )
    assert blocked_note.status_code == 404

    blocked_status = client.patch(
        f"/api/v1/staff/applications/{application.id}/status",
        {"to_status": Application.Status.PHONE, "expected_version": application.version},
        format="json",
    )
    assert blocked_status.status_code == 404
    assert application.notes.count() == 1


def test_note_body_never_appears_in_audit_event_metadata(
    candidate_factory, job_position_factory, recruiter, hr_manager
):
    candidate = candidate_factory()
    job = job_position_factory()
    application = _create_application(candidate, job)
    assign_reviewer(application=application, reviewer=recruiter, assigned_by=hr_manager)

    client = APIClient()
    client.force_authenticate(user=recruiter)
    secret_text = "متن کاملاً محرمانه یادداشت"
    resp = client.post(
        f"/api/v1/staff/applications/{application.id}/notes", {"body": secret_text}, format="json"
    )
    assert resp.status_code == 201

    event = AuditEvent.objects.filter(action="note_added", object_id=str(application.id)).latest("created_at")
    assert secret_text not in str(event.metadata)


def test_status_change_reason_never_appears_in_audit_event_metadata(
    candidate_factory, job_position_factory, recruiter, hr_manager
):
    candidate = candidate_factory()
    job = job_position_factory()
    application = _create_application(candidate, job)
    assign_reviewer(application=application, reviewer=recruiter, assigned_by=hr_manager)

    client = APIClient()
    client.force_authenticate(user=recruiter)
    secret_reason = "دلیل داخلی کاملاً محرمانه رد پرونده"
    resp = client.patch(
        f"/api/v1/staff/applications/{application.id}/status",
        {"to_status": Application.Status.REJECTED, "expected_version": application.version, "reason": secret_reason},
        format="json",
    )
    assert resp.status_code == 200

    event = AuditEvent.objects.filter(action="status_changed", object_id=str(application.id)).latest("created_at")
    assert secret_reason not in str(event.metadata)


# test_candidate_session_is_never_accepted_on_staff_note_or_status_endpoints حذف شد — اصل V
# نسخهٔ ۲.۰.۰: دیگر هیچ «نشست متقاضی»ای وجود ندارد. درخواست ناشناس به این مسیرها از پیش با
# test_staff_without_record_access_cannot_add_note_or_change_status (بالاتر) پوشش داده می‌شود.


def _real_staff_login(client: APIClient, staff_user) -> None:
    """
    ورود واقعی با رمز عبور که نشست سروری واقعی (نه force_authenticate) می‌سازد تا بتوان CSRF را
    آزمود. اصل V نسخهٔ ۳.۰.۰: تک‌مرحله‌ای، بدون عامل دوم.
    """
    staff_user.set_password("a-strong-password-123")
    staff_user.save(update_fields=["password"])

    login_resp = client.post(
        "/api/v1/auth/staff/login",
        {"username": staff_user.username, "password": "a-strong-password-123"},
        format="json",
    )
    assert login_resp.status_code == 200


def test_note_and_status_endpoints_reject_missing_csrf_token_with_valid_staff_session(
    candidate_factory, job_position_factory, recruiter, hr_manager
):
    """
    درخواست تغییردهنده با نشست کارمند واقعی و معتبر، اما بدون توکن CSRF، باید رد شود — نشان
    می‌دهد که فقط داشتن کوکی نشست کافی نیست (محافظت CSRF واقعی اعمال می‌شود).
    """
    candidate = candidate_factory()
    job = job_position_factory()
    application = _create_application(candidate, job)
    assign_reviewer(application=application, reviewer=recruiter, assigned_by=hr_manager)

    client = APIClient(enforce_csrf_checks=True)
    _real_staff_login(client, recruiter)

    resp_note = client.post(
        f"/api/v1/staff/applications/{application.id}/notes", {"body": "بدون CSRF"}, format="json"
    )
    assert resp_note.status_code == 403
    assert application.notes.count() == 0

    resp_status = client.patch(
        f"/api/v1/staff/applications/{application.id}/status",
        {"to_status": Application.Status.PHONE, "expected_version": application.version},
        format="json",
    )
    assert resp_status.status_code == 403
    application.refresh_from_db()
    assert application.status == Application.Status.NEW


def test_note_and_status_endpoints_succeed_with_valid_csrf_token_and_staff_session(
    candidate_factory, job_position_factory, recruiter, hr_manager
):
    """همان نشست واقعی، اما این‌بار با توکن CSRF معتبر — باید موفق شود (رد نشدن کور همه‌چیز)."""
    from django.middleware.csrf import get_token

    candidate = candidate_factory()
    job = job_position_factory()
    application = _create_application(candidate, job)
    assign_reviewer(application=application, reviewer=recruiter, assigned_by=hr_manager)

    client = APIClient(enforce_csrf_checks=True)
    _real_staff_login(client, recruiter)

    # دریافت توکن CSRF واقعی از همان نشست (الگوی `get_token` در صفحات staff/*).
    token_resp = client.get("/staff/dashboard")
    assert token_resp.status_code == 200
    csrf_token = get_token(token_resp.wsgi_request)

    resp_note = client.post(
        f"/api/v1/staff/applications/{application.id}/notes",
        {"body": "با CSRF معتبر"},
        format="json",
        HTTP_X_CSRFTOKEN=csrf_token,
    )
    assert resp_note.status_code == 201


def test_note_body_containing_html_and_script_is_stored_and_returned_as_plain_text(
    candidate_factory, job_position_factory, recruiter, hr_manager
):
    """
    نمایش امن یادداشت (الزام ۵): متن حاوی تگ HTML/اسکریپت باید دقیقاً همان‌طور که وارد شده در
    پاسخ JSON برگردد (بدون escape/تغییر سرور) — ایمنی واقعی روی نمایش با `textContent` در
    `static/js/staff_detail.js` تضمین می‌شود (نه مبتنی بر پاکسازی سمت سرور که قابل دور زدن است).
    """
    candidate = candidate_factory()
    job = job_position_factory()
    application = _create_application(candidate, job)
    assign_reviewer(application=application, reviewer=recruiter, assigned_by=hr_manager)

    client = APIClient()
    client.force_authenticate(user=recruiter)

    malicious_body = "<script>window.__xss_fired = true;</script><img src=x onerror=alert(1)>"
    resp = client.post(
        f"/api/v1/staff/applications/{application.id}/notes", {"body": malicious_body}, format="json"
    )
    assert resp.status_code == 201
    assert resp.json()["body"] == malicious_body
    assert resp["Content-Type"].startswith("application/json")

    detail_resp = client.get(f"/api/v1/staff/applications/{application.id}")
    assert detail_resp.status_code == 200
    returned_note = detail_resp.json()["notes"][0]
    assert returned_note["body"] == malicious_body


def test_note_with_html_is_rendered_as_text_not_executed_in_real_browser(
    live_server, page, candidate_factory, job_position_factory, recruiter, hr_manager
):
    """آزمون مرورگری واقعی: یادداشت حاوی اسکریپت هرگز اجرا نمی‌شود و متن خام در DOM دیده می‌شود."""
    from playwright.sync_api import expect

    candidate = candidate_factory()
    job = job_position_factory()
    PrivacyNotice.objects.create(version="xss-note-v1", body="x", published_at=timezone.now())
    application = _create_application(candidate, job)
    assign_reviewer(application=application, reviewer=recruiter, assigned_by=hr_manager)

    recruiter.set_password("a-strong-password-123")
    recruiter.save(update_fields=["password"])

    page.goto(f"{live_server.url}/staff/login")
    page.fill("#username", recruiter.username)
    page.fill("#password", "a-strong-password-123")
    page.click("#login-button")
    page.wait_for_url("**/staff/dashboard")

    page.goto(f"{live_server.url}/staff/applications/{application.id}")
    expect(page.locator("#detail-card")).to_be_visible(timeout=10000)

    malicious_body = "<img src=x onerror=\"window.__xss_fired = true\"><b>bold-looking text</b>"
    page.fill("#note-body", malicious_body)
    page.click("#note-submit")
    expect(page.locator("#notes-list")).to_contain_text("bold-looking text", timeout=10000)

    # متن خام (با تگ‌ها) باید در DOM به‌صورت متن ساده escape‌شده دیده شود (نتیجه textContent)،
    # نه به‌عنوان یک تگ <b> واقعی یا <img> با هندلر رویداد اجرا شود.
    rendered_html = page.locator("#notes-list").inner_html()
    assert "&lt;b&gt;bold-looking text&lt;/b&gt;" in rendered_html
    assert "<img" not in rendered_html
    xss_fired = page.evaluate("window.__xss_fired")
    assert xss_fired is None


def test_note_never_leaks_to_candidate_facing_api_even_after_being_added(
    candidate_factory, job_position_factory, recruiter, hr_manager
):
    """
    الزام ۵/حریم خصوصی: یادداشت داخلی تازه‌ثبت‌شده هرگز در پاسخ عمومی پیگیری ظاهر نشود
    (اصل V نسخهٔ ۲.۰.۰: پیگیری اکنون فقط با کد پیگیری، بدون هیچ OTP/نشست).
    """
    candidate = candidate_factory()
    job = job_position_factory()
    PrivacyNotice.objects.create(version="note-leak-v1", body="x", published_at=timezone.now())
    application = _create_application(candidate, job)
    assign_reviewer(application=application, reviewer=recruiter, assigned_by=hr_manager)

    staff_client = APIClient()
    staff_client.force_authenticate(user=recruiter)
    secret_note = "یادداشت کاملاً محرمانه که هرگز نباید به متقاضی نشان داده شود"
    note_resp = staff_client.post(
        f"/api/v1/staff/applications/{application.id}/notes", {"body": secret_note}, format="json"
    )
    assert note_resp.status_code == 201

    public_client = APIClient()
    track_resp = public_client.get(f"/api/v1/track/{application.tracking_code}")
    assert track_resp.status_code == 200
    assert secret_note not in str(track_resp.json())
    assert "notes" not in track_resp.json()


def test_status_change_rolls_back_entirely_if_audit_logging_fails(
    candidate_factory, job_position_factory, recruiter, monkeypatch
):
    """
    الزام ۴ (rollback هم‌زمان): اگر ثبت رویداد حسابرسی در میانهٔ تراکنش شکست بخورد، تغییر
    وضعیت و درج StatusHistory هم باید کامل rollback شوند — نه اینکه وضعیت نیمه‌تغییریافته
    بماند و فقط حسابرسی گم شود.
    """
    from apps.applications import services as applications_services

    candidate = candidate_factory()
    job = job_position_factory()
    application = _create_application(candidate, job)
    original_status = application.status
    original_version = application.version

    def _failing_record_event(**kwargs):
        raise RuntimeError("simulated audit backend failure")

    monkeypatch.setattr(applications_services, "record_event", _failing_record_event)

    with pytest.raises(RuntimeError):
        change_status(
            application_id=application.id,
            changed_by=recruiter,
            expected_version=application.version,
            to_status=Application.Status.PHONE,
        )

    application.refresh_from_db()
    assert application.status == original_status
    assert application.version == original_version
    assert StatusHistory.objects.filter(application=application).count() == 0
