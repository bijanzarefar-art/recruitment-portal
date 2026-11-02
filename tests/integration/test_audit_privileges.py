"""
مجوز `AuditEvent`: این فایل دو چیز کاملاً جدا را می‌سنجد.

۱) **وضعیت محیط همین حالا** (این تست): نقش برنامه superuser است و DELETE/UPDATE دارد.
   این تست عمداً fail نمی‌شود، فقط اندازه می‌گیرد و چاپ می‌کند — **سبز شدنش ثابت نمی‌کند که
   کنترل امنیتی کار می‌کند**. اثبات کنترل واقعی در جای دیگری است:
   `docs/operations/db-roles.sql` (طراحی هدف) + آزمون دستی با نقش محدود
   `reqruitment_runtime` روی یک دیتابیس دوریختنی جداگانه که نتیجه‌اش:
     INSERT → موفق؛  UPDATE/DELETE/TRUNCATE روی audit_auditevent → permission denied.
   آن آزمون روی نقش **غیر superuser و غیر مالک جدول** اجرا شد و واقعاً رد کرد.

۲) رفتار کد: `enforce_retention` هرگز روی audit_auditevent عملیات نمی‌کند (تست پایین‌تر).

تست «فقط superuser بودن را کشف می‌کند» تست موفقیت کنترل است، نه.
"""
import pytest
from django.db import connection

pytestmark = pytest.mark.django_db


def _query(sql):
    with connection.cursor() as cur:
        cur.execute(sql)
        return cur.fetchall()


def test_runtime_role_and_its_privileges_on_audit_table_are_measured_not_assumed():
    rows = _query("SELECT current_user, rolsuper FROM pg_roles WHERE rolname = current_user")
    role, is_super = rows[0]

    can_delete = _query(f"SELECT has_table_privilege('{role}', 'audit_auditevent', 'DELETE')")[0][0]
    can_update = _query(f"SELECT has_table_privilege('{role}', 'audit_auditevent', 'UPDATE')")[0][0]

    # شاهد اندازه‌گیری‌شده — این‌ها وضعیت واقعی امروز هستند، نه ادعای ایمنی.
    print(f"\n[AUDIT-PRIV] role={role} superuser={is_super} can_delete={can_delete} can_update={can_update}")
    print(
        "[AUDIT-PRIV] توجه: superuser=True به‌معنای نبودِ کنترل است. طراحی هدف و شواهد آزمون نقش "
        "محدود در docs/operations/db-roles.sql ثبت شده است."
    )

    # اگر روزی نقش برنامه superuser نبود، محدودیت طراحی‌شده باید واقعاً برقرار باشد.
    if not is_super:
        assert can_delete is False, (
            f"نقش غیر-superuser «{role}» حق DELETE روی audit_auditevent دارد؛ کنترل طراحی‌شده "
            "در docs/operations/db-roles.sql نقض شده است."
        )
        assert can_update is False, (
            f"نقش غیر-superuser «{role}» حق UPDATE روی audit_auditevent دارد؛ کنترل طراحی‌شده "
            "در docs/operations/db-roles.sql نقض شده است."
        )


def test_retention_command_never_touches_audit_rows_regardless_of_privileges(
    candidate_factory, job_position_factory, hr_manager, settings
):
    """
    حتی وقتی نقش مجوز DELETE دارد (وضعیت فعلی توسعه)، فرمان retention رویدادهای حسابرسی را
    حذف نمی‌کند — مسیر پاک‌سازی audit در کد مسدود است، نه فقط در سطح مجوز دیتابیس.
    """
    from django.core.management import call_command
    from django.utils import timezone

    from apps.applications.models import Application, StatusHistory
    from apps.audit.models import AuditEvent

    settings.RETENTION_POLICY_APPROVED = True
    settings.RETENTION_OPERATIONAL_ENABLED = True
    settings.DATA_RETENTION_MONTHS = 12
    job = job_position_factory()
    candidate = candidate_factory()
    app = Application.objects.create(
        tracking_code="auditpriv001",
        candidate=candidate,
        job_position=job,
        first_name="a",
        last_name="b",
        mobile_snapshot=candidate.mobile,
        city="تهران",
        employment=Application.Employment.FULL_TIME,
        experience=Application.Experience.YEARS_1_3,
        availability=Application.Availability.IMMEDIATE,
        status=Application.Status.REJECTED,
        idempotency_key="auditpriv-k1",
    )
    hist = StatusHistory.objects.create(application=app, from_status="new", to_status="rejected")
    StatusHistory.objects.filter(id=hist.id).update(
        created_at=timezone.now() - timezone.timedelta(days=400)
    )
    event = AuditEvent.objects.create(
        action="status_changed", object_type="Application", object_id=str(app.id)
    )

    call_command("enforce_retention", actor_id=str(hr_manager.id))

    assert not Application.objects.filter(id=app.id).exists()
    assert AuditEvent.objects.filter(id=event.id).exists()
