"""
T086: مدیریت کاربران از پنل ادمین (US7، FR-021a تا FR-021d) روی PostgreSQL واقعی.
«ادمین» = نقش موجود `hr_manager` (D10 در docs/decisions.md)، نه نقش جدید.
"""
import pytest
from rest_framework.test import APIClient

from apps.accounts.models import StaffUser
from apps.audit.models import AuditEvent

pytestmark = pytest.mark.django_db


def test_non_hr_manager_roles_get_403_on_every_user_management_route(recruiter, hiring_manager, hr_manager):
    target = recruiter

    for actor in (recruiter, hiring_manager):
        client = APIClient()
        client.force_authenticate(user=actor)

        assert client.get("/api/v1/staff/users").status_code == 403
        assert (
            client.post(
                "/api/v1/staff/users",
                {"username": "whatever", "password": "Str0ngPass!", "role": "recruiter"},
                format="json",
            ).status_code
            == 403
        )
        assert (
            client.patch(f"/api/v1/staff/users/{target.id}", {"is_active": False}, format="json").status_code == 403
        )


def test_hr_manager_can_create_account_usable_immediately_with_username_and_password(hr_manager):
    client = APIClient()
    client.force_authenticate(user=hr_manager)

    resp = client.post(
        "/api/v1/staff/users",
        {"username": "new_recruiter_1", "password": "Str0ngPass!", "role": "recruiter"},
        format="json",
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["username"] == "new_recruiter_1"
    assert body["role"] == "recruiter"
    assert body["is_active"] is True

    user = StaffUser.objects.get(username="new_recruiter_1")
    # ورود بلافاصله با همین نام‌کاربری/رمز عبور، بدون هیچ عامل دوم (اصل V نسخهٔ ۳.۰.۰).
    anon_client = APIClient()
    login_resp = anon_client.post(
        "/api/v1/auth/staff/login", {"username": "new_recruiter_1", "password": "Str0ngPass!"}, format="json"
    )
    assert login_resp.status_code == 200

    event = AuditEvent.objects.get(action="staff_account_created", object_id=str(user.id))
    assert event.staff_actor_id == hr_manager.id
    assert event.metadata["role"] == "recruiter"


def test_duplicate_username_is_rejected_without_creating_a_second_account(hr_manager, staff_user_factory):
    staff_user_factory(username="already_taken")
    client = APIClient()
    client.force_authenticate(user=hr_manager)

    resp = client.post(
        "/api/v1/staff/users",
        {"username": "already_taken", "password": "Str0ngPass!", "role": "recruiter"},
        format="json",
    )
    assert resp.status_code == 400
    assert StaffUser.objects.filter(username="already_taken").count() == 1


def test_role_change_is_applied_and_audited(hr_manager, staff_user_factory):
    target = staff_user_factory(role=StaffUser.Role.RECRUITER)
    client = APIClient()
    client.force_authenticate(user=hr_manager)

    resp = client.patch(f"/api/v1/staff/users/{target.id}", {"role": "hiring_manager"}, format="json")
    assert resp.status_code == 200
    assert resp.json()["role"] == "hiring_manager"

    event = AuditEvent.objects.get(action="staff_role_changed", object_id=str(target.id))
    assert event.metadata == {"old_role": "recruiter", "new_role": "hiring_manager"}


def test_deactivation_is_audited_and_blocks_the_very_next_request(hr_manager, staff_user_factory):
    target = staff_user_factory(role=StaffUser.Role.RECRUITER)
    admin_client = APIClient()
    admin_client.force_authenticate(user=hr_manager)

    target_client = APIClient()
    target_client.force_authenticate(user=target)
    assert target_client.get("/api/v1/staff/applications").status_code == 200

    resp = admin_client.patch(f"/api/v1/staff/users/{target.id}", {"is_active": False}, format="json")
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False
    assert AuditEvent.objects.filter(action="staff_deactivated", object_id=str(target.id)).exists()

    target.refresh_from_db()
    assert target.is_active is False
    # درخواست بعدی همان حساب (حتی با force_authenticate که مستقیماً شیء کاربر را می‌دهد)
    # باید با بررسی is_active در IsStaff رد شود، نه فقط در لحظهٔ لاگین.
    assert target_client.get("/api/v1/staff/applications").status_code == 403


def test_cannot_deactivate_own_account(hr_manager):
    client = APIClient()
    client.force_authenticate(user=hr_manager)

    resp = client.patch(f"/api/v1/staff/users/{hr_manager.id}", {"is_active": False}, format="json")
    assert resp.status_code == 403
    hr_manager.refresh_from_db()
    assert hr_manager.is_active is True


def test_cannot_deactivate_the_last_active_hr_manager(hr_manager, staff_user_factory):
    other_hr = staff_user_factory(role=StaffUser.Role.HR_MANAGER)
    client = APIClient()
    client.force_authenticate(user=hr_manager)

    # غیرفعال‌کردن other_hr توسط hr_manager مجاز است چون hr_manager خودش فعال باقی می‌ماند.
    resp = client.patch(f"/api/v1/staff/users/{other_hr.id}", {"is_active": False}, format="json")
    assert resp.status_code == 200

    # اکنون فقط hr_manager فعال است. تلاش other_hr (با force_authenticate مستقیم، بدون نیاز
    # به دور زدن IsStaff) برای غیرفعال‌کردن hr_manager باید رد شود چون او آخرین فعال است —
    # حتی اگر other_hr هنوز نقش hr_manager را داشته باشد (فقط is_active=False شده).
    other_hr_client = APIClient()
    other_hr_client.force_authenticate(user=other_hr)
    resp = other_hr_client.patch(f"/api/v1/staff/users/{hr_manager.id}", {"is_active": False}, format="json")
    assert resp.status_code == 403

    hr_manager.refresh_from_db()
    assert hr_manager.is_active is True


def test_role_change_away_from_hr_manager_is_blocked_for_the_last_active_one(hr_manager):
    """
    یافتهٔ واقعی کشف‌شده در آزمون دستی: بدون این بررسی، تنها `hr_manager` می‌توانست با تغییر
    نقش خودش (نه فقط غیرفعال‌سازی) کل سامانه را بدون هیچ مدیر HR فعال قفل کند.
    """
    client = APIClient()
    client.force_authenticate(user=hr_manager)

    resp = client.patch(f"/api/v1/staff/users/{hr_manager.id}", {"role": "recruiter"}, format="json")
    assert resp.status_code == 403
    hr_manager.refresh_from_db()
    assert hr_manager.role == StaffUser.Role.HR_MANAGER
