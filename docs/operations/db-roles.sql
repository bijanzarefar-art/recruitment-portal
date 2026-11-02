-- طراحی هدف نقش‌های PostgreSQL (اصل VIII، FR-055) — **مرجع طراحی، نه اسکریپت اجرا در تولید**.
--
-- دو نقش جدا:
--   reqruitment_migrate — مالک schema/جداول؛ فقط برای اجرای migration استفاده می‌شود.
--   reqruitment_runtime — نقش برنامه در زمان اجرا؛ کمترین مجوز لازم.
--
-- این فایل با شواهد واقعی آزموده شده است (جدول زیر). اعتبارنامه/نقش محیط واقعی فقط با
-- مجوز ذی‌نفع تنظیم شود.

-- ---------------------------------------------------------------- ۱. ساخت نقش‌ها
CREATE ROLE reqruitment_migrate LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE;
CREATE ROLE reqruitment_runtime LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;

-- ---------------------------------------------------------------- ۲. مالکیت
-- پس از اجرای `manage.py migrate` با reqruitment_migrate:
--   ALTER TABLE/SEQUENCE ... OWNER TO reqruitment_migrate;   (برای همهٔ جداول public)

-- ---------------------------------------------------------------- ۳. مجوز runtime
GRANT CONNECT ON DATABASE <db> TO reqruitment_runtime;
GRANT USAGE ON SCHEMA public TO reqruitment_runtime;

-- پایه: هیچ مجوزی به‌صورت PUBLIC/ALL داده نمی‌شود.
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC;
REVOKE ALL ON SCHEMA public FROM PUBLIC;

-- ---- (الف) جداول فقط‌افزودنی (سابقه): INSERT + SELECT، بدون UPDATE/DELETE/TRUNCATE ----
-- `audit_auditevent` (D5: هرگز حذف نمی‌شود)، `applications_statushistory` (FR-028: ردیف
-- غیرقابل‌تغییر)، `applications_consent` (ثبت رضایت، بدون ویرایش).
GRANT SELECT, INSERT ON
    audit_auditevent,
    applications_statushistory,
    applications_consent
  TO reqruitment_runtime;

-- ---- (ب) جداول داده زنده — خواندن/نوشتن/حذف ردیف، بدون TRUNCATE ----
-- اینها رکوردهایی هستند که چرخهٔ عمرشان با کد مدیریت می‌شود (ثبت/ویرایش/حذف تک‌ردیفی).
GRANT SELECT, INSERT, UPDATE, DELETE ON
    accounts_staffuser,
    accounts_staffuser_groups,
    accounts_staffuser_user_permissions,
    accounts_staffrecoverycode,
    accounts_staffloginratecounter,
    auth_group,
    auth_group_permissions,
    auth_permission,
    django_admin_log,
    django_content_type,
    django_migrations,
    django_session,
    candidates_candidate,
    candidates_otpchallenge,
    candidates_otpratecounter,
    jobs_jobposition,
    applications_application,
    applications_applicationnote,
    applications_applicationreviewer,
    applications_privacynotice,
    applications_idempotencyrecord,
    attachments_attachment,
    attachments_attachmentcontent,
    operations_backgroundjob,
    reporting_exportratecounter,
    otp_totp_totpdevice
  TO reqruitment_runtime;

-- ---- (ج) TRUNCATE هرگز، روی هیچ جدولی ----
REVOKE TRUNCATE ON ALL TABLES IN SCHEMA public FROM reqruitment_runtime;

-- ---- (د) Sequence ها ----
-- فقط sequence هایی که ORM برای INSERT به آن‌ها نیاز دارد (BIGSERIAL/AutoField).
-- UUID PKها sequence ندارند. اگر جدول تازه‌ای sequence جدید گرفت، اینجا باید صریح اضافه شود.
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO reqruitment_runtime;

-- ---------------------------------------------------------------- ۴. جدول مجوزهای طراحی‌شده
--
-- دسته                          | SELECT | INSERT | UPDATE | DELETE | TRUNCATE
-- ------------------------------|--------|--------|--------|--------|---------
-- سابقه (audit, statushistory, consent) | ✅ | ✅ | ❌ | ❌ | ❌
-- داده زنده (بقیه)              | ✅ | ✅ | ✅ | ✅ | ❌
-- PUBLIC (همه)                  | ❌ | ❌ | ❌ | ❌ | ❌
--
-- آزمون واقعی که انجام شد (نقش reqruitment_runtime، نه superuser و نه صاحب جدول):
--   INSERT روی audit_auditevent → موفق
--   UPDATE / DELETE / TRUNCATE روی audit_auditevent → "permission denied for table audit_auditevent"
--   نقش: rolsuper=f, rolcreaterole=f, rolinherit=f، بدون عضویت گروهی.
--
-- **محدودسازی دقیق‌تر (D7) هنوزروی دیتابیس اعمال و آزموده نشده است** — آزمون قبلی با
-- GRANT روی ALL TABLES انجام شد؛ فهرست صریح بالا (دسته‌بندی سابقه/زنده) نیازمند اجرای
-- دوباره‌ی آزمون روی دیتابیس دوریختنی است (باز باقی‌مانده — O7).
--
-- نکته: در محیط فعلی توسعه، نقش برنامه (reqruitment) superuser است؛ این طراحی هنوز در آن
-- محیط اعمال نشده و در docs/decisions.md به‌عنوان تصمیم باز (O2) ثبت است.
