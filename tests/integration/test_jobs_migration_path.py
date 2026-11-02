"""
آزمون مسیر مهاجرت JobPosition (FR-039a) روی PostgreSQL واقعی با `MigrationExecutor`.

هر تست یک پایگاه‌داده کاملاً مستقل و دورریختنی برای خودش می‌سازد، **با یک alias اتصال Django
کاملاً جدا** (نه دستکاری `settings.DATABASES["default"]`، که چون `connections.settings` یک
cached_property است هیچ اثری روی اتصال از‌پیش‌مقداردهی‌شده ندارد و در تلاش اول باعث شد این
تست‌ها به‌اشتباه روی دیتابیس *مشترک* `test_recruitment` اجرا و اسکیمای آن را برای بقیهٔ مجموعه
تست در همان session خراب کنند — این اشتباه کشف و اینجا اصلاح شده است). alias تازه مستقیماً در
`connections.settings` (نه در `django.conf.settings.DATABASES`) ثبت می‌شود تا با همان نمونهٔ
`ConnectionHandler` که از قبل مقداردهی شده هماهنگ باشد.

فرض این تست: کاربر PostgreSQL اجازه CREATE DATABASE دارد (همان کاربر دیتابیس توسعه).
"""
import uuid

import pytest
from django.db import DEFAULT_DB_ALIAS, connections
from django.db.migrations.executor import MigrationExecutor
from psycopg import connect

JOBS_START = [("jobs", "0001_initial")]
JOBS_HEAD = [("jobs", "0003_job_status_graph")]


@pytest.fixture
def fresh_db(django_db_blocker):
    """
    پایگاه‌داده واقعی مجزا، با alias اتصال Django مستقل، فقط برای همین تست. از
    `django_db_blocker.unblock()` استفاده می‌شود (نه نشانگر `pytest.mark.django_db`)، چون
    pytest-django فقط alias هایی را که از پیش در لیست «مجاز» می‌شناسد اجازه می‌دهد؛ alias
    تازه و تصادفی این تست هرگز در آن فهرست نیست و با نشانگر معمولی رد می‌شود.
    """
    base = dict(connections.settings[DEFAULT_DB_ALIAS])
    db_name = f"migdrill_{uuid.uuid4().hex[:12]}"
    conn_params = {
        "host": base["HOST"],
        "port": base["PORT"],
        "user": base["USER"],
        "password": base["PASSWORD"],
        "dbname": "postgres",
    }
    with django_db_blocker.unblock():
        with connect(**conn_params, autocommit=True) as admin:
            admin.execute(f'CREATE DATABASE "{db_name}"')

        alias = f"drill_{uuid.uuid4().hex[:8]}"
        drill_settings = dict(base)
        drill_settings["NAME"] = db_name
        connections.settings[alias] = drill_settings

        try:
            yield alias
        finally:
            connections[alias].close()
            del connections[alias]
            del connections.settings[alias]
            with connect(**conn_params, autocommit=True) as admin:
                admin.execute(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)')


def _full_snapshot(alias):
    """
    عکس فوری کامل و قابل‌مقایسه از سه لایه: اسکیما (ستون‌ها + ایندکس‌ها)، همهٔ ردیف‌های
    جدول، و تاریخچهٔ مهاجرت‌ها. برای اثبات «هیچ چیز تغییر نکرد» پس از یک عملیات ناموفق.
    """
    with _cursor(alias) as cur:
        cur.execute(
            "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
            "WHERE table_name='jobs_jobposition' ORDER BY column_name"
        )
        columns = list(cur.fetchall())
        cur.execute("SELECT indexname FROM pg_indexes WHERE tablename='jobs_jobposition' ORDER BY indexname")
        indexes = [r[0] for r in cur.fetchall()]
        cur.execute("SELECT id::text, title, status FROM jobs_jobposition ORDER BY id")
        rows = list(cur.fetchall())
        cur.execute("SELECT name FROM django_migrations WHERE app='jobs' ORDER BY name")
        migrations = [r[0] for r in cur.fetchall()]
    return {
        "columns": columns,
        "indexes": indexes,
        "rows": rows,
        "migrations": migrations,
    }

def _migrate(alias, targets):
    executor = MigrationExecutor(connections[alias])
    executor.loader.build_graph()
    executor.migrate(targets)
    connections[alias].close()  # آزادسازی قفل‌/تراکنش قبل از کوئری‌های بعدی روی همان alias.


def _cursor(alias):
    return connections[alias].cursor()


def _insert_old_job(alias, job_id, title, is_published, status):
    with _cursor(alias) as cur:
        cur.execute(
            'INSERT INTO jobs_jobposition (id, title, department, location, status, is_published, '
            "created_at, updated_at) VALUES (%s, %s, '', '', %s, %s, now(), now())",
            [str(job_id), title, status, is_published],
        )


def _all_jobs(alias):
    with _cursor(alias) as cur:
        cur.execute("SELECT id::text, status, is_published FROM jobs_jobposition ORDER BY id")
        return {row[0]: (row[1], row[2]) for row in cur.fetchall()}


def test_forward_migration_maps_only_approved_combinations(fresh_db):
    alias = fresh_db
    _migrate(alias, JOBS_START)

    approved_open = uuid.uuid4()
    approved_closed = uuid.uuid4()
    _insert_old_job(alias, approved_open, "True-open", True, "open")
    _insert_old_job(alias, approved_closed, "True-closed", True, "closed")

    _migrate(alias, JOBS_HEAD)

    with _cursor(alias) as cur:
        cur.execute("SELECT id::text, status FROM jobs_jobposition ORDER BY id")
        rows = dict(cur.fetchall())
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='jobs_jobposition'")
        columns = {r[0] for r in cur.fetchall()}

    assert rows[str(approved_open)] == "open"
    assert rows[str(approved_closed)] == "closed"
    assert "is_published" not in columns


@pytest.mark.parametrize(
    "is_published,status",
    [
        (False, "open"),
        (False, "closed"),
        (True, "archived"),
        (False, "archived"),
        (True, "paused"),  # مقدار ناشناخته
    ],
)
def test_forward_migration_halts_on_any_unapproved_combination(fresh_db, is_published, status):
    alias = fresh_db
    _migrate(alias, JOBS_START)

    job_id = uuid.uuid4()
    _insert_old_job(alias, job_id, "blocking", is_published, status)

    with pytest.raises(RuntimeError, match="مهاجرت متوقف شد"):
        _migrate(alias, JOBS_HEAD)

    # هیچ رکوردی تغییر نکرده یا حذف نشده است.
    assert _all_jobs(alias) == {str(job_id): (status, is_published)}


def test_approved_and_blocking_rows_together_leave_everything_unchanged(fresh_db):
    alias = fresh_db
    _migrate(alias, JOBS_START)

    ok_id = uuid.uuid4()
    bad_id = uuid.uuid4()
    _insert_old_job(alias, ok_id, "approved", True, "open")
    _insert_old_job(alias, bad_id, "archived", True, "archived")
    before = _all_jobs(alias)

    with pytest.raises(RuntimeError, match="مهاجرت متوقف شد"):
        _migrate(alias, JOBS_HEAD)

    assert _all_jobs(alias) == before


def test_successful_migration_preserves_ids_applications_and_row_counts(fresh_db):
    alias = fresh_db
    _migrate(alias, [("jobs", "0001_initial"), ("applications", "0001_initial")])

    job_id = uuid.uuid4()
    candidate_id = uuid.uuid4()
    application_id = uuid.uuid4()
    _insert_old_job(alias, job_id, "linked", True, "open")
    with _cursor(alias) as cur:
        cur.execute(
            "INSERT INTO candidates_candidate (id, mobile, verified_at, created_at) VALUES (%s, %s, now(), now())",
            [str(candidate_id), "09120000999"],
        )
        cur.execute(
            "INSERT INTO applications_application (id, tracking_code, candidate_id, job_position_id, first_name, "
            "last_name, mobile_snapshot, email, city, employment, experience, availability, last_title, "
            "last_company, status, version, idempotency_key, created_at, updated_at) VALUES "
            "(%s, 'migptrk00000001', %s, %s, 'a', 'b', '09120000999', '', 'تهران', 'full_time', 'years_1_3', "
            "'immediate', '', '', 'new', 1, 'k1', now(), now())",
            [str(application_id), str(candidate_id), str(job_id)],
        )

    _migrate(alias, JOBS_HEAD)

    with _cursor(alias) as cur:
        cur.execute("SELECT id::text, status FROM jobs_jobposition")
        assert cur.fetchall() == [(str(job_id), "open")]
        cur.execute("SELECT id::text, job_position_id::text FROM applications_application")
        assert cur.fetchall() == [(str(application_id), str(job_id))]
        cur.execute("SELECT count(*) FROM jobs_jobposition")
        assert cur.fetchone()[0] == 1


def test_reverse_is_blocked_before_any_change(fresh_db):
    """
    سیاست واقعی (مستند در `0003_job_status_graph.py`): برگشت عمداً غیرقابل‌اجراست و **پیش از
    هر تغییر اسکیما/داده** با RuntimeError متوقف می‌شود — نه اینکه ستون `is_published` را با
    مقدار حدسی `False` بازسازی کند.
    """
    alias = fresh_db
    _migrate(alias, JOBS_START)

    job_id = uuid.uuid4()
    _insert_old_job(alias, job_id, "published", True, "closed")

    _migrate(alias, JOBS_HEAD)

    # عکس فوری کامل **پیش از** تلاش برگشت: اسکیما، все ردیف‌ها، و تاریخچهٔ مهاجرت.
    snapshot_before = _full_snapshot(alias)

    with pytest.raises(RuntimeError, match="برگشت به .* عمداً مسدود است"):
        _migrate(alias, JOBS_START)

    snapshot_after = _full_snapshot(alias)

    # مقایسهٔ کامل عکس فوری قبل/بعد — نه فقط assert raises و چند بررسی نقطه‌ای.
    assert snapshot_after == snapshot_before, (
        "پس از شکست برگشت، وضعیت دیتابیس تغییر کرده است.\n"
        f"قبل: {snapshot_before}\nبعد: {snapshot_after}"
    )
    # تکمیل شواهد: ستون is_published واقعاً حذف‌مانده و داده طبق نگاشت مصوب است.
    assert "is_published" not in [c[0] for c in snapshot_after["columns"]]
    assert snapshot_after["rows"] == [(str(job_id), "published", "closed")]
    assert snapshot_after["migrations"] == [
        "0001_initial",
        "0002_preflight_job_status_mapping",
        "0003_job_status_graph",
    ]
