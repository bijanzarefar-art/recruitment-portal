"""
T048: کنترل هم‌زمانی مبتنی بر نسخه برای تغییر وضعیت روی PostgreSQL واقعی (FR-029). درخواست
روی نسخه قدیمی باید با VersionConflict/۴۰۹ رد شود، بدون گم‌شدن تغییر طرف دیگر و بدون نوشتن
نیمه‌کاره؛ در رقابت واقعی هم‌زمان، دقیقاً یکی از نخ‌ها موفق می‌شود.
"""
import secrets
import threading

import pytest
from django.db import close_old_connections
from django.utils import timezone
from rest_framework.test import APIClient

from apps.applications.models import Application, PrivacyNotice, StatusHistory
from apps.applications.services import VersionConflict, change_status

pytestmark = pytest.mark.django_db(transaction=True)


def _create_application(candidate, job):
    unique = secrets.token_hex(6)
    return Application.objects.create(
        tracking_code=f"co{unique}",
        candidate=candidate,
        job_position=job,
        first_name="رضا",
        last_name="کریمی",
        mobile_snapshot=candidate.mobile,
        city="شیراز",
        employment=Application.Employment.FULL_TIME,
        experience=Application.Experience.YEARS_1_3,
        availability=Application.Availability.IMMEDIATE,
        last_title="x",
        last_company="y",
        status=Application.Status.NEW,
        idempotency_key=f"con-k-{unique}",
    )


def test_stale_expected_version_is_rejected_without_mutation(candidate_factory, job_position_factory, recruiter):
    candidate = candidate_factory()
    job = job_position_factory()
    application = _create_application(candidate, job)
    stale_version = application.version

    change_status(
        application_id=application.id,
        changed_by=recruiter,
        expected_version=stale_version,
        to_status=Application.Status.PHONE,
    )

    # تلاش دوم با همان نسخه قدیمی (پیش از رفرش) باید رد شود؛ وضعیت نباید تغییر کند.
    with pytest.raises(VersionConflict):
        change_status(
            application_id=application.id,
            changed_by=recruiter,
            expected_version=stale_version,
            to_status=Application.Status.REJECTED,
            reason="دلیل",
        )

    application.refresh_from_db()
    assert application.status == Application.Status.PHONE
    assert application.version == stale_version + 1
    # هیچ تاریخچه نیمه‌کاره‌ای از تلاش ناموفق ثبت نشده باشد.
    assert StatusHistory.objects.filter(application=application, to_status=Application.Status.REJECTED).count() == 0


def test_concurrent_status_changes_real_postgres_exactly_one_wins(
    candidate_factory, job_position_factory, recruiter, hr_manager
):
    candidate = candidate_factory()
    job = job_position_factory()
    application = _create_application(candidate, job)
    shared_version = application.version

    results = []
    errors = []

    def _worker(actor, to_status):
        close_old_connections()
        try:
            updated = change_status(
                application_id=application.id,
                changed_by=actor,
                expected_version=shared_version,
                to_status=to_status,
                reason="دلیل" if to_status == Application.Status.REJECTED else "",
            )
            results.append(updated.status)
        except VersionConflict as exc:
            errors.append(exc)
        finally:
            close_old_connections()

    threads = [
        threading.Thread(target=_worker, args=(recruiter, Application.Status.PHONE)),
        threading.Thread(target=_worker, args=(hr_manager, Application.Status.REJECTED)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(results) == 1, "دقیقاً یک تغییر وضعیت باید موفق شود، نه هر دو"
    assert len(errors) == 1
    application.refresh_from_db()
    assert application.version == shared_version + 1
    assert application.status == results[0]
    assert StatusHistory.objects.filter(application=application).count() == 1


def test_api_status_endpoint_returns_409_on_version_conflict(
    candidate_factory, job_position_factory, recruiter, hr_manager
):
    from apps.applications.services import assign_reviewer

    candidate = candidate_factory()
    job = job_position_factory()
    PrivacyNotice.objects.create(version="conc-api-v1", body="x", published_at=timezone.now())
    application = _create_application(candidate, job)
    assign_reviewer(application=application, reviewer=recruiter, assigned_by=hr_manager)

    client = APIClient()
    client.force_authenticate(user=recruiter)

    stale_version = application.version
    resp1 = client.patch(
        f"/api/v1/staff/applications/{application.id}/status",
        {"to_status": Application.Status.PHONE, "expected_version": stale_version},
        format="json",
    )
    assert resp1.status_code == 200

    resp2 = client.patch(
        f"/api/v1/staff/applications/{application.id}/status",
        {"to_status": Application.Status.REJECTED, "expected_version": stale_version, "reason": "دلیل"},
        format="json",
    )
    assert resp2.status_code == 409
    assert resp2.json()["code"] == "conflict"
