---
description: "Task list for feature implementation"
---

# Tasks: نسخه اولیه پورتال فارسی جذب و استخدام

**Input**: Design documents from `/specs/001-recruitment-portal/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/openapi.yaml, quickstart.md

**Tests**: درخواست‌شده (مطابق فهرست پیشنهادی کاربر). تست‌ها پیش از پیاده‌سازی مربوطه نوشته می‌شوند و
باید ابتدا شکست بخورند.

**Organization**: فازهای ۳ تا ۸ به ترتیب اولویت داستان‌های کاربری در spec.md هستند (US1–US5 اولویت
P1، US6 اولویت P2). مسیرهای فایل مطابق «Project Structure» در plan.md. **⚠️ به‌روزرسانی مهم
(اصل V نسخهٔ ۲.۰.۰)**: US1 و US2 دیگر شامل OTP نیستند — تسک‌های اجرایی فعلی آن‌ها در بخش «دور
پنجم» (پایین سند، T070 تا T082) است، نه در فازهای ۳/۴ اصلی که فقط برای سابقه نگه داشته شده‌اند.
US7 (مدیریت کاربران از پنل ادمین، اولویت P2، تسک‌های T083 تا T087) نیز در همان بخش اضافه شد.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: قابل اجرای موازی (فایل‌های متفاوت، بدون وابستگی به تسک ناتمام)
- **[Story]**: US1–US6 مطابق spec.md
- مسیر فایل دقیق در هر تسک آمده است

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: راه‌اندازی اولیه پروژه و ابزار مشترک

- [X] T001 اسکلت پروژه Django را per plan.md «Project Structure» بسازید: `manage.py`،
      `config/settings/{base,dev,prod}.py`، `config/urls.py`، `config/wsgi.py`، `config/asgi.py`،
      و پوشه‌های خالی `apps/{accounts,candidates,jobs,applications,attachments,reporting,audit,notifications,operations}/`
      هرکدام با `__init__.py`، `models.py`، `services.py`، `api/__init__.py`.
- [X] T002 [P] فایل وابستگی قفل‌شده (`requirements/base.txt` یا `pyproject.toml`) با نسخه‌های مصوب
      research.md بسازید: Django 5.2، djangorestframework 3.15، `psycopg[binary]` 3، `django-otp`،
      `openpyxl`، `jdatetime`، `clamd`، `pytest-django`؛ و `.env.example` با
      `DJANGO_SECRET_KEY`، `DATABASE_URL`، `SMS_GATEWAY_BACKEND`، `SCANNER_BACKEND`.
- [X] T003 [P] `docker/docker-compose.yml` توسعه با سرویس‌های `app`، `db` (postgres:16)، `clamav`
      و `worker` (فرمان `run_worker`) بسازید؛ بدون سرویس ذخیره‌سازی خارجی (research.md §۱–۴).
- [X] T004 تنظیمات امن پایه را در `config/settings/base.py` اعمال کنید: `DATABASES` روی
      PostgreSQL، `USE_TZ = True`، کوکی نشست `HttpOnly`/`SameSite=Lax` (و `Secure` در
      `config/settings/prod.py`)، میان‌افزار CSRF، هدر CSP محدودکننده بدون اسکریپت درون‌خطی، و
      لاگ ساختاریافته JSON با `request_id` و فیلتر حذف فیلدهای حساس (FR-046, FR-048). انقضای
      نشست را پیکربندی کنید: نشست متقاضی `SESSION_COOKIE_AGE` معادل ۳۰ دقیقه بی‌فعالیتی با سقف
      مطلق ۱۲ ساعت، نشست کارمند ۳۰ دقیقه/سقف ۸ ساعت، و خروج صریح باطل‌کننده فوری نشست (FR-045).
- [X] T005 [P] گردش‌کار CI (مثلاً `.github/workflows/ci.yml`) با مراحل lint (`ruff`/`black`)،
      type-check (در صورت استفاده از type hints)، `pytest` با سرویس PostgreSQL واقعی (نه SQLite)،
      و `python manage.py makemigrations --check` اضافه کنید.
- [X] T005a [P] فیکسچرهای پایه pytest را در `tests/conftest.py` بسازید: اتصال PostgreSQL واقعی
      برای تست یکپارچه (نه SQLite)، فیکسچر `staff_user_factory`/`candidate_factory`/
      `job_position_factory`/`application_factory` با `factory_boy` برای هر نقش
      (`recruiter`, `hiring_manager`, `hr_manager`, `system_operator`)، و فیکسچر HTTP client
      احرازهویت‌شده برای هر نقش. همه تسک‌های تست در فازهای ۲ تا ۹ به این فیکسچرها وابسته‌اند
      (رفع یافته H2 در تحلیل).
- [X] T005b [P] نصب و پیکربندی مرورگر Playwright را در `.github/workflows/ci.yml` و
      `tests/browser/conftest.py` اضافه کنید (viewport موبایل، `dir="rtl"`). همه تسک‌های
      `tests/browser/*` به این تسک وابسته‌اند.

**Checkpoint**: اسکلت پروژه، CI، فیکسچرهای تست و محیط توسعه آماده است.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: مدل‌های داده، قیود، مجوز رکوردی، حسابرسی و احراز هویت — پیش‌نیاز مسدودکننده همه
داستان‌های کاربری.

**⚠️ CRITICAL**: هیچ کار روی US1–US6 نباید پیش از تکمیل این فاز آغاز شود.

### مدل‌های داده (data-model.md)

- [X] T006 [P] مدل `StaffUser` را در `apps/accounts/models.py` بسازید: `role` (Enum:
      `recruiter`, `hiring_manager`, `hr_manager`, `system_operator`)، `is_active`،
      `totp_confirmed_at` (datetime nullable)، `created_by` (FK→StaffUser nullable)،
      `created_at`؛ مهاجرت بسازید.
- [X] T007 [P] مدل `Candidate` را در `apps/candidates/models.py` بسازید: `id` UUID، `mobile`
      (`CharField`, یکتا، قالب نرمال‌شده `09xxxxxxxxx`)، `verified_at`، `created_at`.
- [X] T008 [P] مدل `JobPosition` را در `apps/jobs/models.py` بسازید: `id` UUID، `title`،
      `department`، `location`، `is_published` (bool)، `status` (Enum: `open`, `closed`,
      `archived`)، `created_at`/`updated_at`.
- [X] T009 مدل `Application` را در `apps/applications/models.py` بسازید با تمام فیلدها و قیود
      دقیق data-model.md: `tracking_code` یکتا، `candidate` FK، `job_position` FK،
      `first_name`/`last_name` (`CharField(1..100)`, trim)، `mobile_snapshot`، `email`
      (`CharField(max=254)`, اختیاری)، `city` (`CharField(max=100)`)، `employment`/`experience`/
      `availability` (Enum مطابق spec.md FR-004)، `last_title`/`last_company`
      (`CharField(max=200)`, اجباری مگر `experience=no_experience`)، `status` (Enum:
      `new`,`phone`,`interview`,`approved`,`rejected`,`hired`)، `version` (`IntegerField`)،
      `idempotency_key`، `created_at`/`updated_at`؛ به‌علاوه یکتایی شرطی
      `UniqueConstraint(fields=["candidate","job_position"], condition=Q(status__in=["new","phone","interview","approved"]))`
      و ایندکس‌های `(status, created_at, id)`، `(job_position, created_at, id)`، `(reviewer)`،
      `(candidate)`.
- [X] T010 [پس از T009؛ همان فایل apps/applications/models.py، غیرموازی] مدل `ApplicationReviewer` را در `apps/applications/models.py` بسازید: `application`
      FK، `reviewer` FK (نقش `recruiter` یا `hiring_manager`)، `reviewer_role_at_assignment`
      (Enum)، `assigned_by` FK، `assigned_at`، `revoked_at` (nullable)؛ قید
      `UniqueConstraint(fields=["application"], condition=Q(revoked_at__isnull=True))` برای
      «حداکثر یک ارجاع فعال در هر لحظه» (data-model.md «ارجاع پرونده»).
- [X] T011 [پس از T010؛ همان فایل، غیرموازی] مدل `ApplicationNote` را در `apps/applications/models.py` بسازید: `application`
      FK، `author` FK، `body` (`TextField`, ۱ تا ۵۰۰۰ نویسه)، `created_at` (FR-026).
- [X] T012 [پس از T011؛ همان فایل، غیرموازی] مدل `StatusHistory` را در `apps/applications/models.py` بسازید: `application` FK،
      `from_status`/`to_status`، `changed_by` FK، `internal_reason` (`TextField`)،
      `is_exception` (bool)، `created_at` (FR-028, FR-030, FR-031).
- [X] T013 [پس از T012؛ همان فایل، غیرموازی] مدل‌های `PrivacyNotice` و `Consent` را بسازید: `PrivacyNotice` (`version` یکتا،
      `body`، `published_at`) در `apps/applications/models.py`؛ `Consent` (`application`
      OneToOne، `privacy_notice` FK، `accepted_at`) (FR-004).
- [X] T014 [P] مدل‌های `Attachment` و `AttachmentContent` را در `apps/attachments/models.py`
      بسازید: `Attachment`(`candidate` FK، `application` FK nullable یکتا، `upload_attempt_key`،
      `original_filename`، `detected_mime_type`، `size_bytes` (`PositiveIntegerField`)،
      `sha256` (`CharField(64)`)، `scan_status` (Enum: `pending`,`quarantined`,`clean`,
      `rejected`,`scan_failed`)، `created_at`)؛ `AttachmentContent`(`attachment` OneToOne
      `on_delete=CASCADE`، `data` `BinaryField`) با قید دیتابیس
      `octet_length(data) BETWEEN 1 AND 5242880` (data-model.md).
- [X] T015 **⚠️ منسوخ‌شده — اصل V نسخهٔ ۲.۰.۰ (دور پنجم، پایین همین سند)**: `OTPChallenge`/
      `OtpRateCounter` باید حذف و با `TrackingLookupRateCounter` جایگزین شوند (T070). متن اصلی
      برای سابقه نگه داشته شده: [پس از T007؛ همان فایل apps/candidates/models.py، غیرموازی] مدل‌های `OTPChallenge` و `OtpRateCounter` را در `apps/candidates/models.py`
      بسازید: `OTPChallenge`(`mobile`، `purpose` Enum(`register`,`track`)، `code_hash`،
      `expires_at`، `failed_attempts` (`PositiveSmallIntegerField`, سقف ۵)، `consumed_at`،
      `created_at`)؛ `OtpRateCounter`(`scope` Enum(`mobile_hour`,`mobile_day`,`ip_hour`)، `key`،
      `window_start`، `count`) با قید یکتایی `(scope, key, window_start)` (FR-042 تا FR-044).
- [X] T016 [پس از T013؛ همان فایل، غیرموازی] مدل `IdempotencyRecord` را در `apps/applications/models.py` بسازید: `candidate`
      FK، `idempotency_key`، `request_hash`، `application` FK، `created_at`؛ قید یکتایی
      `(candidate, idempotency_key)` (FR-009).
- [X] T017 [P] مدل `AuditEvent` را در `apps/audit/models.py` بسازید: `actor` (FK به StaffUser یا
      Candidate)، `action`، `object_type`/`object_id`، `http_request_id`، `metadata`
      (`JSONField`)، `created_at`؛ سرویس مشترک `apps/audit/services.py::record_event(...)` که
      همه اپ‌ها از آن استفاده می‌کنند؛ نقش دیتابیس برنامه روی این جدول فقط `INSERT` داشته باشد
      (FR-055، اصل VIII).
- [X] T018 [P] مدل `BackgroundJob` را در `apps/operations/models.py` بسازید: `job_type` (Enum:
      `scan_attachment`, `cleanup_upload`)، `payload` (`JSONField`, فقط شناسه‌ها)، `status`،
      `lock_expires_at`، `attempts`، `next_attempt_at`، `error_code`، `created_at`/`updated_at`.
- [X] T019 مهاجرت‌های اولیه همه مدل‌های T006–T018 را بسازید و اجرا کنید؛ با `\d` در `psql` تأیید
      کنید قید یکتایی شرطی `Application` و قید `octet_length` روی `AttachmentContent.data`
      واقعاً در اسکیمای PostgreSQL ایجاد شده‌اند.

### مجوز رکوردی، حسابرسی و رابط پایه

- [X] T020 سیاست مجوز نقش/رکورد را در `apps/applications/services.py` به‌صورت
      `get_applications_queryset(user)` پیاده کنید: پیش‌فرض منع (deny-by-default)؛ `recruiter`
      فقط پرونده‌هایی با ارجاع فعال خودش (FR-018)؛ `hiring_manager` فقط پرونده‌هایی با ارجاع فعال
      خودش (FR-018)؛ `hr_manager` همه پرونده‌ها؛ `system_operator` هیچ پرونده تجاری (FR-021)؛
      پرونده بدون ارجاع فقط برای `hr_manager` (FR-040). تست یکپارچه را در
      `tests/integration/test_record_level_access.py` روی اتصال PostgreSQL واقعی (نه موک/SQLite)
      بنویسید که منع پیش‌فرض و جداسازی بین نقش‌ها/رکوردها را اثبات کند (مطابق اصل IX قانون
      اساسی: کنترل دسترسی سطح رکورد باید تست یکپارچه روی PostgreSQL واقعی داشته باشد).
- [X] T020a حداقل سرویس/مسیر ارجاع پرونده را زودتر از US6 بسازید (رفع یافته C2 در تحلیل، چون
      US3/US4 که اولویت P1 دارند به این قابلیت نیاز دارند): `PATCH /api/v1/staff/applications/{id}/assignments`
      را در `apps/applications/api/views.py` و سرویس مرتبط در `apps/applications/services.py`
      پیاده کنید — فقط `hr_manager` مجاز؛ قاعده «اولین ارجاع باید `recruiter` باشد، ارجاع بعدی به
      `hiring_manager` ارجاع فعال `recruiter` را بلافاصله باطل می‌کند» را روی مدل
      `ApplicationReviewer` (T010) اعمال کنید؛ لغو ارجاع با `reviewer_id: null`؛ هر تغییر در
      `AuditEvent` ثبت شود (FR-041). تست ترتیب/لغو این سرویس در T059 (فاز ۸) پوشش داده می‌شود و
      می‌تواند بلافاصله پس از این تسک (و پیش از هر فاز داستان کاربری) اجرا شود.
- [X] T021 [P] قالب نمونه را به `templates/` و `static/{css,js}/` منتقل کنید (فونت، رنگ، کارت،
      راست‌به‌چپ و نقاط شکست واکنش‌گرا حفظ شود)؛ `getApps`/`saveApps`/`IndexedDB` را با ماژول‌های
      fetch API در `static/js/` جایگزین کنید؛ `seedDemo`، دکمه بازنشانی دمو، ورود نمایشی، امنیت
      مبتنی بر `currentAdmin` و هر `innerHTML` ناامن را حذف کنید (plan.md «تبدیل رابط نمونه»؛
      FR-054 — هیچ داده شخصی یا محتوای رزومه در ذخیره‌سازی پایدار مرورگر نگه داشته نشود).
- [X] T021a فیلتر قالب مشترک `to_jalali` را در `apps/common/templatetags/jalali_filters.py`
      بسازید (رفع یافته M4 در تحلیل؛ تصمیم research.md §۸؛ پیاده‌سازی FR-058؛ در صورت نبود app،
      ابتدا app خالی `apps/common` را بسازید و به `INSTALLED_APPS` اضافه کنید): ورودی `datetime`
      با UTC را به تاریخ شمسی و ساعت منطقه `Asia/Tehran` با `jdatetime` تبدیل کند؛ در تمام
      قالب‌های Django (متقاضی و کارمند) استفاده شود؛ تست واحد کوچک برای چند تاریخ مرجع بنویسید.

### احراز هویت (متقاضی و کارمند)

> همه تست‌های این بخش به فیکسچرهای `T005a` وابسته‌اند.

- [X] T022 **⚠️ منسوخ‌شده — اصل V نسخهٔ ۲.۰.۰**: کل مسیر OTP متقاضی حذف شد؛ `tests/unit/test_candidate_otp.py`
      باید حذف شود (رفع در T071). متن اصلی برای سابقه: [P] تست‌های OTP متقاضی را در `tests/unit/test_candidate_otp.py` بنویسید: نرمال‌سازی
      موبایل (ارقام فارسی/عربی، `+98`/`0098`)، انقضای ۲ دقیقه، فاصله ارسال مجدد ۶۰ ثانیه، ابطال
      چالش قبلی با صدور چالش جدید، یک‌بارمصرف‌بودن، سقف پنج ارسال در ساعت/ده در روز به ازای
      موبایل و سی در ساعت به ازای IP تحت فراخوانی هم‌زمان، و پاسخ عمومی یکسان صرف‌نظر از
      وجود/عدم‌وجود پرونده (FR-016، FR-042 تا FR-044؛ باید ابتدا شکست بخورند).
- [X] T023 **⚠️ منسوخ‌شده — اصل V نسخهٔ ۲.۰.۰**: `apps/notifications`، چرخه نشست متقاضی و هر سه
      مسیر `/auth/candidate/otp/*`/`logout` باید کامل حذف شوند (رفع در T071/T072). متن اصلی برای
      سابقه: رابط `SmsGateway` و پیاده‌سازی `ConsoleSmsGateway` را در
      `apps/notifications/gateway.py` بسازید؛ سرویس چالش OTP (صدور/تأیید/ابطال) و شمارنده نرخ
      اتمی (`UPDATE ... RETURNING`) را در `apps/candidates/services.py` و چرخه نشست متقاضی
      (ایجاد/خروج، کوکی جدا از کارمند) را پیاده کنید؛ ویوهای `POST /auth/candidate/otp/request`،
      `POST /auth/candidate/otp/verify` و `POST /auth/candidate/logout` را در
      `apps/candidates/api/views.py` ثبت کنید تا تست‌های T022 سبز شوند (FR-003).
- [X] T024 [P] تست‌های ورود/MFA کارکنان را در `tests/unit/test_staff_auth.py` بنویسید: رد ورود
      حساب غیرفعال، تأیید با کد بازیابی یک‌بارمصرف هش‌شده، انقضای `mfa_challenge_id`، و الزام
      CSRF روی مسیرهای ایجاد نشست (FR-017، FR-020، FR-021، FR-047؛ باید ابتدا شکست بخورند).
- [X] T025 ورود دومرحله‌ای کارکنان (`POST /auth/staff/login` + `POST /auth/staff/mfa/verify`) را
      با `django-otp` در `apps/accounts/api/views.py` پیاده کنید؛ فرمان مدیریتی محدود
      `apps/accounts/management/commands/createsuperuser_staff.py` برای ساخت حساب کارمند و کد
      بازیابی بسازید (FR-020)؛ عملیات اضطراری اپراتور سامانه به دیتابیس را در
      `docs/operations/emergency-access.md` مستند کنید (FR-021) تا تست‌های T024 سبز شوند.
- [X] T025a فرمان مدیریتی `transfer_candidate_mobile` را در
      `apps/candidates/management/commands/transfer_candidate_mobile.py` بسازید (رفع یافته H1
      در تحلیل؛ پیاده‌سازی FR-064): فقط قابل‌اجرا توسط عملیات تحت کنترل `hr_manager`، آرگومان
      `--old-mobile --new-mobile --reason` اجباری، به‌روزرسانی `Candidate.mobile` در یک تراکنش
      + رویداد `AuditEvent(action="mobile_transfer")` شامل دلیل؛ تست در
      `tests/integration/test_mobile_transfer.py` بنویسید که اثبات کند هیچ مسیر API/خودکار/
      سمت‌کلاینت برای این کار وجود ندارد (FR-064).

**Checkpoint**: مدل‌ها، مجوز رکوردی، سرویس ارجاع پرونده (T020a)، حسابرسی و احراز هویت هر دو نقش
آماده‌اند؛ کار روی US1–US6 می‌تواند آغاز شود — از جمله US3/US4 که اکنون دیگر منتظر فاز ۸ (US6،
P2) نمی‌مانند.

---

## Phase 3: User Story 1 - ثبت درخواست همکاری (Priority: P1) 🎯 MVP

**Goal**: متقاضی موقعیت باز را انتخاب، موبایل را با OTP تأیید، فرم و رزومه را ارسال کند و دقیقاً
یک درخواست با کد پیگیری در سامانه مرکزی ایجاد شود (FR-001 تا FR-011، FR-049 تا FR-053).

**Independent Test**: طبق quickstart.md «سناریو ۱» — بدون نیاز به US2–US6 قابل اجراست.

### Tests for User Story 1 ⚠️

> همه تست‌های این بخش به فیکسچرهای `T005a` و (برای تست مرورگری) `T005b` وابسته‌اند.

- [X] T026 [P] [US1] تست فرم/موقعیت را در `tests/unit/test_application_form.py` بنویسید: رد ثبت
      برای موقعیت بسته (FR-002, FR-011)، اختیاری‌بودن `last_title`/`last_company` فقط وقتی
      `experience=no_experience` (FR-004)، و الزام نسخه جاری `PrivacyNotice` برای `consent`
      (FR-004)؛ و نمایش خطای فارسی کنار فیلد بدون نهایی‌شدن ثبت (FR-006).
- [X] T027 [P] [US1] تست فایل را در `tests/integration/test_attachment_upload.py` بنویسید:
      محدودشدن بارگذاری موقت به همان متقاضی/تلاش ارسال (FR-051)، بررسی نوع واقعی فایل با magic
      bytes نه ادعای کلاینت (FR-049)، مرز دقیق ۵ MiB (FR-005)، رد فایل آلوده/رمزگذاری‌شده
      غیرقابل‌بررسی (FR-005, FR-010)، رفتار سامانه هنگام شکست/قطع‌شدن پردازشگر اسکن (باید
      `scan_failed` نه `clean` ثبت شود)، و رد نام فایل ناامن.
- [X] T028 [P] [US1] تست رقابت را در `tests/integration/test_application_submission_concurrency.py`
      روی PostgreSQL واقعی بنویسید: درخواست فعال تکراری برای همان `(candidate, job_position)` رد
      شود (FR-008)؛ دو ارسال هم‌زمان با همان `Idempotency-Key` و بدنه یکسان فقط یک `Application`
      بسازند و دومی همان رسید را بگیرد (FR-009)؛ همان کلید با بدنه متفاوت ۴۰۹ بگیرد. همچنین تست
      رگرسیون کنید که ثبت یک درخواست جدید هیچ فیلدی از یک `Application` قبلی (حتی برای همان
      متقاضی/موقعیت در وضعیت نهایی) را تغییر یا بازنویسی نمی‌کند (FR-056, SC-008)؛ و یک سناریوی
      مثبت صریح بنویسید که پس از `rejected`/`hired` و بازگشایی مجدد موقعیت، ثبت درخواست جدید برای
      همان متقاضی/موقعیت بدون محدودیت موفق شود و رکورد مستقلی بسازد (FR-060).

### Implementation for User Story 1

- [X] T029 [US1] `GET /api/v1/jobs` و `GET /api/v1/privacy-notice` را در
      `apps/jobs/api/views.py` و `apps/applications/api/views.py` پیاده کنید: فقط موقعیت‌های
      `is_published=True` و `status=open` (FR-001, FR-002).
- [X] T030 [US1] `POST /api/v1/candidate/uploads` و `GET /api/v1/candidate/uploads/{id}` را در
      `apps/attachments/api/views.py` پیاده کنید: بارگذاری multipart محدود به مالک، محاسبه
      سروری `size_bytes`/`sha256`/`detected_mime_type`، ایجاد `Attachment`+`AttachmentContent`+
      `BackgroundJob(type=scan_attachment)` در یک تراکنش (FR-049, FR-052).
- [X] T031 [US1] رابط `ScannerClient` و پیاده‌سازی `ClamdScannerClient` را در
      `apps/attachments/scanning/` بسازید (research.md §۴).
- [X] T032 [US1] فرمان مدیریتی `run_worker` را در
      `apps/operations/management/commands/run_worker.py` پیاده کنید: برداشتن کار با
      `SELECT ... FOR UPDATE SKIP LOCKED`، فراخوانی `ScannerClient`، به‌روزرسانی
      `Attachment.scan_status`، تلاش مجدد با تأخیر افزایشی، و ثبت `scan_failed` هنگام قطعی
      اسکنر (FR-010؛ تا تست‌های T027 سبز شوند).
- [X] T033 [US1] `POST /api/v1/candidate/applications` و `GET /api/v1/candidate/applications` را
      در `apps/applications/api/views.py` پیاده کنید: هدر `Idempotency-Key` اجباری؛ در یک
      تراکنش طبق «سازگاری ثبت درخواست» ورودی کاربر: قفل رکورد `Attachment` و
      `IdempotencyRecord`، بررسی بازبودن موقعیت/نسخه رضایت/قاعده تکرار، ایجاد `Application`+
      `Consent`+`StatusHistory(new)`+`AuditEvent`+`IdempotencyRecord`؛ رسید فقط پس از commit
      صادر شود (FR-007 تا FR-009).
- [X] T034 [US1] فرمان مدیریتی `cleanup_uploads` را در
      `apps/operations/management/commands/cleanup_uploads.py` پیاده کنید: حذف تراکنشی
      فراداده+محتوای بارگذاری‌های بدون `Application` که بیش از ۲۴ ساعت از ایجادشان گذشته و قفل/
      کار فعالی ندارند، با همان ترتیب قفل‌گیری مسیر ثبت (FR-053).
- [X] T035 [US1] فرم ثبت RTL را در `templates/candidate/apply.html` به OTP (T023)، موقعیت
      (T029)، بارگذاری فایل (T030) و ثبت (T033) متصل کنید؛ هنگام رد ثبت به‌دلیل بسته‌شدن موقعیت
      (FR-011)، داده‌های واردشده در همان صفحه (نه در `localStorage`) حفظ شوند.
- [X] T036 [US1] تست مرورگری (Playwright) در `tests/browser/test_us1_submission.py` بنویسید:
      ثبت کامل از یک دستگاه/نشست، سپس مشاهده همان رکورد از نشست مستقل یک کارمند HR مجاز در
      داشبورد (پس از ارجاع فرضی). زمان کل مسیر «انتخاب موقعیت تا دریافت کد پیگیری» را اندازه
      بگیرید و زیر ۵ دقیقه باشد (SC-001)؛ با فایل از پیش سالم‌شده، زمان دریافت رسید پس از کلیک
      ارسال را اندازه بگیرید و زیر ۳ ثانیه باشد (SC-007).

**Checkpoint**: US1 به‌طور کامل و مستقل قابل‌آزمایش است (MVP).

---

## Phase 4: User Story 2 - پیگیری وضعیت درخواست (Priority: P1)

**Goal**: متقاضی با تأیید OTP، از هر دستگاهی فهرست درخواست‌های خودش را با وضعیت عمومی ببیند،
بدون افشای داده دیگران یا اطلاعات داخلی HR (FR-012 تا FR-016).

**Independent Test**: quickstart.md «سناریو ۲» — فقط نیازمند یک درخواست از پیش ثبت‌شده (US1).

### Tests for User Story 2 ⚠️

> وابسته به فیکسچرهای `T005a`/`T005b`.

- [X] T037 **⚠️ منسوخ‌شده — اصل V نسخهٔ ۲.۰.۰**: US2 کامل بازطراحی شد (پیگیری فقط با کد، بدون
      OTP/نشست). جایگزین: T081. متن اصلی برای سابقه: [P] [US2] تست حریم خصوصی API را در `tests/contract/test_candidate_privacy.py`
      بنویسید: پاسخ `GET /candidate/applications/{id}` فاقد یادداشت HR، ارجاع، دلیل داخلی، هویت
      کارکنان و گزارش حسابرسی باشد (FR-015)؛ تلاش برای خواندن شناسه درخواست متعلق به موبایل
      دیگر باید ۴۰۳/۴۰۴ بگیرد (FR-014)؛ و دانستن کد ملی/موبایل/کد پیگیری به‌تنهایی (بدون تأیید
      OTP) هرگز دسترسی ایجاد نکند (FR-013).

### Implementation for User Story 2

> **⚠️ کل این فاز (US2) با اصل V نسخهٔ ۲.۰.۰ بازطراحی شد — جایگزین‌ها: T078 تا T083 (دور پنجم،
> پایین همین سند). T038 تا T040 فقط برای سابقهٔ تاریخی نگه داشته شده‌اند، دیگر منبع حقیقت نیستند.**

- [X] T038 **⚠️ منسوخ‌شده**، جایگزین: T078. متن اصلی: [US2] `GET /api/v1/candidate/applications` و
      `GET /api/v1/candidate/applications/{id}` را در `apps/applications/api/views.py` پیاده
      کنید: فقط درخواست‌های `candidate` نشست جاری؛ سریالایزر عمومی محدود به
      `tracking_code`/`job_position`/`status`/`updated_at` (FR-012, FR-015).
- [X] T039 **⚠️ منسوخ‌شده**، جایگزین: T080. متن اصلی: [US2] صفحه پیگیری RTL را در `templates/candidate/track.html` بسازید که از چرخه OTP
      مشترک (T023) با `purpose=track` استفاده می‌کند.
- [X] T040 **⚠️ منسوخ‌شده**، جایگزین: T083. متن اصلی: [US2] تست مرورگری در `tests/browser/test_us2_tracking.py` بنویسید: چند درخواست یک
      متقاضی از یک نشست دیده شوند؛ تلاش دسترسی از نشست/دستگاه دیگر بدون OTP رد شود.

**Checkpoint**: US1 و US2 هر دو مستقل کار می‌کنند.

---

## Phase 5: User Story 3 - جست‌وجو و بررسی پرونده (Priority: P1)

**Goal**: کارمند مجاز با رمز+MFA وارد شود، در دامنه مجوز خود فیلتر/جست‌وجو کند و رزومه سالم را
فقط از مسیر احرازهویت‌شده دانلود کند (FR-017 تا FR-025).

**Independent Test**: quickstart.md «سناریو ۳» — نیازمند حداقل یک پرونده ثبت‌شده (US1) و حساب
کارمند (Phase 2).

### Tests for User Story 3 ⚠️

> وابسته به فیکسچرهای `T005a`/`T005b`؛ T042 همچنین به T020a (ارجاع، فاز ۲) وابسته است.

- [X] T041 [P] [US3] ماتریس کامل نقش × عملیات را در `tests/contract/test_staff_access_matrix.py`
      بنویسید: برای هر نقش (`recruiter`, `hiring_manager`, `hr_manager`) و هر مسیر
      (فهرست/جزئیات/آمار/دانلود رزومه)، پاسخ مجاز/غیرمجاز دقیقاً مطابق FR-018 باشد؛ درخواست
      خارج از دامنه مجوز باید ۴۰۱/۴۰۳/۴۰۴ بدون افشای وجود رکورد بگیرد (FR-019, SC-004).
- [X] T042 [P] [US3] تست لغو ارجاع و دانلود را در `tests/integration/test_resume_download.py`
      بنویسید (با استفاده از سرویس ارجاع T020a برای ساخت/لغو ارجاع در فیکسچر تست): پس از لغو
      ارجاع، دانلود/مشاهده بعدی همان کارمند رد شود (FR-041)؛ فایل در وضعیت غیر `clean` از هیچ
      مسیری قابل دانلود نباشد (FR-025, FR-050, SC-005).

### Implementation for User Story 3

- [X] T043 [US3] `GET /api/v1/staff/applications` و `GET /api/v1/staff/applications/metrics` را
      در `apps/applications/api/views.py` با `get_applications_queryset` (T020) پیاده کنید:
      فیلتر موقعیت/وضعیت/شهر/سابقه/بازه تاریخ/کارشناس مسئول، جست‌وجوی نام/موبایل/کد پیگیری،
      صفحه‌بندی سمت سرور (پیش‌فرض ۲۵، حداکثر ۱۰۰) با مرتب‌سازی `(created_at desc, id)` پایدار،
      و آمار با همان دامنه/فیلتر فهرست (FR-022 تا FR-024).
- [X] T044 [US3] `GET /api/v1/staff/applications/{id}` و
      `GET /api/v1/staff/applications/{id}/resume` را پیاده کنید: دانلود فقط از مسیر
      احرازهویت‌شده Django با بررسی مجدد مجوز رکورد + `scan_status=clean` در لحظه هر درخواست،
      هدر `Content-Disposition: attachment`، `Cache-Control: no-store`،
      `X-Content-Type-Options: nosniff`، و رویداد `resume_download` در `AuditEvent` (FR-025,
      plan.md «پیاده‌سازی امنیت»).
- [X] T045 [US3] داشبورد HR (فهرست+فیلتر+جزئیات) را در `templates/staff/dashboard.html` و
      `templates/staff/application_detail.html` با نمایش امن متن (auto-escape، بدون `innerHTML`
      خام) بسازید؛ حالت بارگذاری/خالی/خطا را پیاده کنید.
- [X] T046 [US3] تست مرورگری در `tests/browser/test_us3_review.py` بنویسید: ورود+MFA → فیلتر →
      مشاهده جزئیات → دانلود رزومه؛ و یک تلاش مستقیم API خارج از مجوز که باید رد شود.

**Checkpoint**: US1، US2 و US3 هر سه مستقل کار می‌کنند.

---

## Phase 6: User Story 4 - رسیدگی: یادداشت و گردش وضعیت (Priority: P1)

**Goal**: بررسی‌کننده مجاز یادداشت ثبت کند؛ کارشناس/مدیر مجاز وضعیت را طبق گردش مجاز و با کنترل
نسخه تغییر دهد، بدون از بین رفتن تاریخچه (FR-026 تا FR-031، FR-063).

**Independent Test**: quickstart.md «سناریو ۴» — نیازمند یک پرونده ارجاع‌شده (US1 + سرویس ارجاع
`T020a` از فاز ۲؛ دیگر وابسته به فاز ۸/US6 نیست).

### Tests for User Story 4 ⚠️

> وابسته به فیکسچرهای `T005a`/`T005b`.

- [X] T047 [P] [US4] تست گردش وضعیت را در `tests/unit/test_status_transitions.py` بنویسید: فقط
      انتقال‌های مجاز `new→phone/interview/rejected`، `phone→interview/rejected`،
      `interview→approved/rejected`، `approved→hired/rejected` پذیرفته شوند؛ `rejected` بدون
      `reason` رد شود (FR-030)؛ تغییر وضعیت نهایی توسط غیر `hr_manager` رد شود؛ تغییر استثنایی
      `hr_manager` با `is_exception=True` ثبت شود (FR-031). همچنین رگرسیون کنید: چند یادداشت و
      چند ردیف تاریخچه متوالی ثبت و تأیید کنید هیچ‌کدام در عملیات بعدی حذف/بازنویسی نمی‌شود
      (SC-008).
- [X] T048 [P] [US4] تست رقابت نسخه را در `tests/integration/test_application_status_conflict.py`
      روی PostgreSQL واقعی بنویسید: درخواست با `expected_version` قدیمی باید ۴۰۹ بگیرد و تغییری
      اعمال نشود (FR-029, SC-009).

### Implementation for User Story 4

- [X] T049 [US4] `POST /api/v1/staff/applications/{id}/notes` را در
      `apps/applications/api/views.py` پیاده کنید: `body` ۱ تا ۵۰۰۰ نویسه، نویسنده و زمان سرور،
      بدون مسیر ویرایش معمول (FR-026).
- [X] T050 [US4] `PATCH /api/v1/staff/applications/{id}/status` را در
      `apps/applications/api/views.py` پیاده کنید: در یک تراکنش،
      بررسی `expected_version` (در غیر تطابق ۴۰۹)، اعتبارسنجی انتقال مجاز
      (`apps/applications/statemachine.py`)، الزام `reason` برای `rejected`/تغییر استثنایی، درج
      `StatusHistory` و افزایش `version`، و رویداد حسابرسی (FR-027 تا FR-031).
- [X] T051 [US4] فیلد «اشاره خلاصه به درخواست‌های قبلی» را در پاسخ
      `GET /api/v1/staff/applications/{id}` اضافه کنید: بر اساس `Candidate.mobile`، فقط پرونده‌
      هایی که در دامنه مجوز کاربر جاری هستند، بدون کپی/ادغام یادداشت یا دلیل داخلی قبلی
      (FR-063).
- [X] T052 [US4] جدول یادداشت/تاریخچه و فرم تغییر وضعیت را در
      `templates/staff/application_detail.html` وصل کنید؛ خطای ۴۰۹ باید پیغام «تازه‌سازی کنید»
      و دکمه بازخوانی نشان دهد.
- [X] T053 [US4] تست مرورگری در `tests/browser/test_us4_workflow.py` بنویسید: ورود+MFA → فیلتر →
      جزئیات → دانلود رزومه → ثبت یادداشت → تغییر وضعیت؛ و یک درخواست مستقیم API با
      `expected_version` قدیمی که باید ۴۰۹ بگیرد.

**Checkpoint**: US1 تا US4 مستقل کار می‌کنند.

---

## Phase 7: User Story 5 - خروجی‌گیری (Priority: P1)

**Goal**: مدیر HR نتایج منطبق با فیلتر جاری را به CSV/XLSX امن و منطبق با سقف/ستون‌های مجاز
خروجی بگیرد (FR-032 تا FR-037).

**Independent Test**: quickstart.md «سناریو ۵» — نیازمند چند پرونده (US1) و مجوز `hr_manager`.

### Tests for User Story 5 ⚠️

> وابسته به فیکسچرهای `T005a`.

- [X] T054 [P] [US5] تست خروجی را در `tests/unit/test_export_policy.py` بنویسید: رد نقش بدون
      مجوز خروجی حتی با دسترسی مشاهده (FR-036)؛ ستون‌های خارج از فهرست مجاز رد شوند و پیش‌فرض
      فاقد یادداشت/شناسه حساس باشد (FR-033)؛ صفر ابتدایی موبایل/شناسه در XLSX حفظ شود (FR-034)؛
      مقدار با پیشوند `=`,`+`,`-`,`@` (حتی پس از فاصله/نویسه کنترلی ابتدایی) در CSV و XLSX خنثی
      شود (FR-035, SC-006)؛ تعداد بیش از سقف ۱۰٬۰۰۰ رد شود با پیام محدودکردن فیلتر (FR-032).

### Implementation for User Story 5

- [X] T055 [US5] سیاست ستون‌های مجاز و تابع مشترک `neutralize_formula(value)` را در
      `apps/reporting/export_policy.py` بسازید (research.md §۷)؛ منطق CSV (BOM + فرمول خنثی) و
      XLSX (`openpyxl` write_only + فرمت متنی صریح برای موبایل/شناسه) را در
      `apps/reporting/services.py` پیاده کنید؛ شمارش با «خواندن سقف+۱» برای تشخیص عبور از
      ۱۰٬۰۰۰ (FR-032 تا FR-035).
- [X] T056 [US5] `POST /api/v1/staff/exports` را در `apps/reporting/api/views.py` پیاده کنید:
      فقط `hr_manager`؛ اعمال همان
      `get_applications_queryset` + فیلترهای `GET /staff/applications`؛ ثبت شروع/نتیجه/کاربر/
      فیلتر نرمال‌شده/ستون‌ها/تعداد ردیف در `AuditEvent` بدون محتوای خروجی؛ پاسخ با
      `Cache-Control: no-store` (FR-036, FR-037).
- [X] T057 [US5] رابط انتخاب خروجی (فرمت، ستون‌ها) را در `templates/staff/export.html` بسازید؛
      راهنمای وارد کردن ستون CSV به‌صورت متن در Excel را در همان صفحه مستند کنید (FR-034).
- [X] T057a [US5] تست محدودیت نرخ خروجی را در `tests/integration/test_export_rate_limit.py`
      بنویسید: مرز دقیق (۵ درخواست موفق، ششمی ۴۲۹ با `Retry-After`)؛ پایان بازه ۱۰ دقیقه‌ای
      (پس از گذشت پنجره، دوباره مجاز)؛ استقلال کامل بین دو حساب `hr_manager` مختلف؛ درخواست‌های
      هم‌زمان واقعی (چند ریسه) که نباید بیش از سقف را عبور دهند (FR-037a).
- [X] T057b [US5] `ExportRateCounter` را در `apps/reporting/models.py` (migration جدید) و
      افزایش اتمی آن را در `apps/reporting/services.py` بسازید (دقیقاً همان الگوی
      `OtpRateCounter`/`_increment_counter` در `apps/candidates`)؛ در
      `apps/reporting/api/views.py` پس از عبور از `IsHrManager` شمارش را اعمال و در صورت عبور
      از سقف `429` + هدر `Retry-After` برگردانید، بدون تولید فایل (FR-037a).

**Checkpoint**: US1 تا US5 (همه P1) مستقل کار می‌کنند.

---

## Phase 8: User Story 6 - مدیریت موقعیت و ارجاع (Priority: P2)

**Goal**: مدیر HR موقعیت بسازد/ببندد و رابط مدیریتی ارجاع را در داشبورد ببیند (FR-038 تا
FR-040). خودِ سرویس/مسیر ارجاع با قاعده ترتیب (FR-041) در فاز ۲ (T020a) زودتر ساخته شده تا US3/US4
(P1) معطل این فاز P2 نمانند؛ این فاز فقط تجربه کاربری مدیریتی و تست آن سرویس را اضافه می‌کند.

**Independent Test**: quickstart.md «سناریو ۶».

### Tests for User Story 6 ⚠️

> وابسته به فیکسچرهای `T005a`.

- [X] T058 [P] [US6] تست بستن موقعیت و حفظ سوابق را در `tests/integration/test_job_lifecycle.py`
      بنویسید: بستن موقعیت فقط ثبت جدید را متوقف کند، سوابق قبلی در دامنه مجوز باقی بماند
      (FR-039)؛ حذف فیزیکی موقعیت دارای درخواست رد شود (FR-038).
- [X] T059 [P] [US6] تست ترتیب و لغو ارجاع را در `tests/integration/test_reviewer_assignment.py`
      بنویسید (علیه سرویس `T020a` که در فاز ۲ ساخته شده؛ این تست می‌تواند بلافاصله پس از T020a و
      مستقل از بقیه US6 اجرا شود): ارجاع مستقیم به `hiring_manager` بدون `recruiter` قبلی رد
      شود؛ ارجاع بعدی به `hiring_manager` ارجاع فعال `recruiter` را بلافاصله باطل کند؛ لغو ارجاع،
      دسترسی مشاهده/دانلود بعدی را فوراً لغو کند، بدون اثر روی فایل پیش‌تر دانلودشده (FR-041).

### Implementation for User Story 6

- [X] T060 [US6] `GET/POST /api/v1/staff/jobs` و `PATCH /api/v1/staff/jobs/{id}` را در
      `apps/jobs/api/views.py` پیاده کنید: ایجاد/ویرایش فقط توسط `hr_manager`، بدون مسیر
      حذف فیزیکی (FR-038)؛ هر تغییر حسابرسی شود. (به‌روزرسانی بعدی: خودِ تغییر وضعیت از این
      مسیر به `PATCH /api/v1/staff/jobs/{id}/status` در T060a منتقل شد تا چرخه صریح FR-039a
      اعتبارسنجی شود.)
- [X] T060a [US6] (افزوده پس از رفع ابهام چرخه وضعیت، FR-039a) `PATCH
      /api/v1/staff/jobs/{id}/status` را در `apps/jobs/api/views.py` + `apps/jobs/statemachine.py`
      پیاده کنید: فقط انتقال‌های `draft→open`، `open→closed`، `closed→open`؛ هر انتقال دیگر
      `InvalidJobTransition`/۴۰۰؛ فقط `hr_manager`؛ ورود به `open` (بازگشایی) حسابرسی جداگانه
      (`job_reopened`) داشته باشد.
- [X] T061 [US6] رابط مدیریتی ارجاع را در `templates/staff/application_detail.html` (روی مسیر
      موجود `T020a`) و صفحه مدیریت موقعیت‌ها را در `templates/staff/jobs.html` (روی `T060`/`T060a`؛
      دکمه‌های «فعال‌سازی/بستن/بازگشایی» متناسب با وضعیت فعلی) بسازید؛ منطق/قید ارجاع از پیش در
      T020a پیاده‌سازی و در T059 آزموده شده است.

**Checkpoint**: همه داستان‌های کاربری (US1–US6) مستقل کار می‌کنند.

---

## Phase 9: Polish & شرط انتشار تولید

**Purpose**: سخت‌سازی امنیتی، عملیات، و اعتبارسنجی غیرکارکردی پیش از تولید.

> تست‌های این فاز به فیکسچرهای `T005a`/`T005b` وابسته‌اند.

- [X] T062 **⚠️ بخشاً منسوخ — اصل V نسخهٔ ۲.۰.۰ (دور پنجم، T089)**: چون متقاضی دیگر هیچ نشست/کوکی
      ندارد، سناریوهای «کوکی متقاضی/کارمند بدون تداخل» و «رد نشست متقاضی روی مسیر کارمند» دیگر
      موضوعیت ندارند و باید از فایل حذف شوند؛ سناریوهای مربوط به نشست/CSRF/session-fixation
      کارمند هنوز معتبرند و باید بمانند. متن اصلی برای سابقه: [P] تست‌های امنیتی هدفمند را در `tests/integration/test_security_hardening.py`
      بنویسید و رفع کنید — **اولویت این اجرا**: حضور هم‌زمان کوکی متقاضی/کارمند بدون تداخل،
      رد هر نشست روی مسیرهای نقش دیگر، عدم ارتقای نشست با ورود/MFA کارمند، خروج/ابطال مستقل هر
      نشست، ویژگی‌های امنیتی کوکی/CSRF مطابق تنظیمات شبیه‌تولید، و چرخش کلید نشست کارمند هنگام
      ورود (ضدِ session fixation) — ۹ تست، همه سبز (اصل V قانون اساسی، FR-045, FR-046, FR-048).
      XSS ذخیره‌شده/CSRF روی مسیرهای یادداشت و تزریق فرمول در خروجی از پیش در Phase 6/7 آزموده
      شده‌اند (`test_application_notes_and_status_access.py`، `test_staff_export_access.py`)؛
      رقابت شمارنده OTP از Phase 1 (`test_otp_regression_bugs.py`) موجود است — اینجا تکرار نشد.
- [X] T062a [P] تست انقضای نشست را در `tests/integration/test_session_expiry.py` نوشته و اجرا
      شد (رفع یافته M3 در تحلیل): **باگ واقعی کشف و رفع شد** —
      `STAFF_SESSION_IDLE_TIMEOUT_SECONDS` در تنظیمات تعریف شده بود اما هیچ‌جا اعمال نمی‌شد؛
      `apps/accounts/middleware.py` (`StaffSessionIdleTimeoutMiddleware`) اضافه شد. سقف مطلق
      نشست کارمند/متقاضی و انقضای idle متقاضی (از پیش در `CandidateSessionAuthentication`) هم
      آزموده شدند. کارمند غیرفعال‌شده: با آزمون واقعی (نه فقط `force_authenticate`) تأیید شد که
      Django با backend پیش‌فرض `ModelBackend` خودش `is_active` را در `get_user()` هر درخواست
      بررسی می‌کند و نشست را به‌طور خودکار باطل می‌کند؛ یک بررسی اضافه در `IsStaff` نیز به‌عنوان
      دفاع در عمق افزوده شد (نه رفع یک حفره واقعاً قابل‌سوءاستفاده، چون Django از پیش مسدود
      می‌کرد — ادعای اشتباه اولیه در گزارش میانی اصلاح شد).
- [X] T063 [P] دستورالعمل عملیات در `docs/operations/{backup-restore,secrets,migrations,monitoring}.md`
      نوشته شد: نتیجه واقعی تمرین محلی بازیابی (پایین)، نتیجه واقعی `manage.py check --deploy`
      (فقط هشدار `ALLOWED_HOSTS` که انتظار می‌رود خالی در محیط محلی باشد)، تأیید با خواندن کد که
      فیلتر لاگ حساس (`RedactSensitiveDataFilter`) از پیش موجود و فعال است (تست تازه:
      `tests/unit/test_logging_redaction.py`)، و فهرست صریح موارد مسدود (پایین‌تر).
- [X] T063a [US-phase9] **FR-047 — محدودسازی نرخ ورود کارمند** پیاده و آزموده شد (این دور):
      `apps/accounts/models.py::StaffLoginRateCounter` + `apps/accounts/services.py` (شمارنده
      اتمیک `select_for_update` روی PostgreSQL، مشترک میان workerها). اعمال روی **هر دو** مسیر
      `POST /auth/staff/login` و `POST /auth/staff/mfa/verify` تا دورزدن از راه جایگزین ممکن
      نباشد؛ چالش نامعتبر MFA با شمارندهٔ IP شمرده می‌شود. پاسخ ۴۲۹ + هدر `Retry-After`.
      `tests/integration/test_staff_login_rate_limit.py` — ۷ تست (حد، پایان پنجره، جداسازی
      حساب/IP، رقابت هم‌زمان ۱۲ ریسه، هر دو مسیر). **آستانه‌ها پیشنهادی‌اند**
      (`STAFF_LOGIN_ACCOUNT_LIMIT=5`, `STAFF_LOGIN_IP_LIMIT=20` در ۱۵ دقیقه) — تصویب مالک
      پروژه لازم است (O5 در `docs/decisions.md`).
- [ ] T064 **مسدود** — اتصال واقعی پیامک (تولید `SmsGateway`) و اسکنر ClamAV در محیط پیش‌تولید
      واقعی، به‌علاوه رفتار سامانه هنگام قطعی واقعی هرکدام. نیازمند محیط پیش‌تولید واقعی و
      اعتبارنامه فروشنده پیامک مصوب که در این اجرا وجود ندارد؛ آزمون محلی معادل این تأیید نیست.
- [ ] T065 **مسدود** — آزمون بار واقعی با `locust` روی محیط پیش‌تولید با ۱۰۰٬۰۰۰ رکورد/۲۰ کارمند
      هم‌زمان. نیازمند محیط پیش‌تولید واقعی که در این اجرا وجود ندارد؛ هیچ عدد صدک/نرخ خطای
      محلی در این اجرا به‌عنوان SC-002/SC-003 گزارش نشده است.
- [X] T066 [P] پذیرش دسترس‌پذیری/RTL/موبایل با Playwright در
      `tests/browser/test_accessibility_rtl.py` — ۴ تست سبز: `dir="rtl"`/`lang="fa"`، برچسب
      `for=id` روی فیلدهای اصلی فرم ثبت، ویوپورت موبایل، نمایش صفحه داشبورد RTL پس از MFA واقعی.
      **باگ واقعی کشف و رفع شد**: پنجره‌های خطای سطح فرم (ورود/MFA/OTP پیگیری/ثبت درخواست) فاقد
      `role="alert"`/`tabindex="-1"` بودند و هیچ‌جا `.focus()` فراخوانی نمی‌شد — یعنی مدیریت
      فوکوس خطا عملاً وجود نداشت؛ به چهار فایل JS و قالب مربوط اضافه و با تست واقعی (فوکوس روی
      خطای ورود کارمند) تأیید شد.
- [ ] T067 **بخشی انجام شد، نه معادل تأیید تولید** — یک **تمرین بازیابی محلی واقعی** (نه محیط
      تولید، نه داده واقعی متقاضی) در `docs/operations/backup-restore.md` ثبت شد: `pg_dump` از
      یک رکورد ترکیبی با محتوای باینری ساختگی، `pg_restore` در یک کانتینر PostgreSQL کاملاً
      جداگانه، و تطابق دقیق `sha256`/`octet_length` محتوا پس از بازیابی. **مسدود**: زمان
      بازیابی واقعی با حجم واقعی رزومه‌ها (برای مقایسه با RTO ۴ ساعته) نیازمند محیط با حجم داده
      واقعی/شبیه‌تولید است که در این اجرا وجود ندارد — عدد زمان این تمرین کوچک هیچ ارزش پیش‌بینی
      ندارد و به‌عنوان چنین چیزی گزارش نشده.
- [X] T067a فرمان `enforce_retention` پیاده و **fail-closed** شد (این دور بازنویسی شد):
      `settings.RETENTION_POLICY_APPROVED` پیش‌فرض `False`؛ بدون آن، بدون `DATA_RETENTION_MONTHS`
      معتبر، یا بدون `--actor-id` معتبر مدیر HR، اجرا **پیش از هر حذف** با `CommandError` متوقف
      می‌شود. `--dry-run` غیرمخرب و بدون این شروط هم کار می‌کند. حذف `AuditEvent` کاملاً از کد
      حذف شد (مسدود تا نقش حداقل‌مجوز مصوب). `tests/integration/test_retention_policy.py` — ۱۳
      تست (پیش‌فرض مسدود، actor نامعتبر، ماه نامعتبر، dry-run، مسیر کامل، حذف رزومه،
      دست‌نخورده‌ماندن حسابرسی). دفتر «اعمال مجدد حذف پس از بازیابی پشتیبان» در
      `docs/operations/backup-restore.md` ثبت شد (رویه مستند، نه آزموده‌شده پس از بازیابی واقعی).
- [ ] T067b **مسدود** — سیاست چرخش پشتیبان ۱۲ماهه مستند شد (`docs/operations/backup-restore.md`)
      اما هیچ ابزار/زمان‌بند پشتیبان‌گیری واقعی تولید یا مقصد پشتیبان مستقل خارج از میزبان برنامه
      در این اجرا پیکربندی یا آزموده نشد — نیازمند تصمیم/زیرساخت عملیاتی تأییدنشده.
- [X] T068 ماتریس تطبیق کامل هر ۲۵ عملیات روی ۲۳ مسیر در
      `docs/openapi-path-matrix.md` ساخته شد (method/path، احراز هویت، نقش/دامنه رکوردی، CSRF،
      ورودی، خروجی، خطاها، صفحه‌بندی، rate limit، و ارجاع به آزمون مرتبط). در همین بازبینی دو
      شکاف واقعی آزمون یافت و بسته شد: `/privacy-notice` هیچ آزمونی نداشت؛ و «کارمند غیر-HR با
      نشست معتبر» روی `/staff/jobs*` آزموده نشده بود (۴ آزمون در
      `tests/contract/test_openapi_code_agreement.py` اضافه شد → ۱۰ تست). شش آزمون قرارداد
      به‌تنهایی پوشش کامل نبود و باقی مسیرها به آزمون‌های یکپارچه ارجاع داده شده‌اند.
- [ ] T069 **بخشی — همچنان باز.** `docs/decisions.md` **ایجاد شد** (دورهٔ نگهداری و فروشنده
      پیامک/اسکن و بودجه همچنان تصمیم بازند؛ تصویب ساختگی ثبت نشد). بخش قابل‌بررسی کد (نبود مسیر
      دمو/دورزدن احراز هویت/رمز مشترک در `config/settings/prod.py`) تأیید شد. **باز**: تأیید
      رسمی ذی‌نفعان، و رفع تضاد نقش دیتابیس حسابرسی (C1/O2).

---

## Dependencies & Execution Order

### وابستگی فازها

- **Setup (فاز ۱)**: بدون وابستگی.
- **Foundational (فاز ۲)**: پس از فاز ۱؛ مسدودکننده همه داستان‌های کاربری.
- **US1 (فاز ۳)**: پس از فاز ۲؛ بدون وابستگی به US دیگر — MVP.
- **US2 (فاز ۴)**: پس از فاز ۲؛ برای آزمون end-to-end به یک درخواست از US1 نیاز دارد اما از نظر
  کد مستقل است.
- **US3 (فاز ۵)**: پس از فاز ۲؛ برای آزمون به یک درخواست از US1 و سرویس ارجاع `T020a` (فاز ۲)
  نیاز دارد — دیگر به هیچ تسکی از فاز ۸ (US6) وابسته نیست (رفع یافته C2 در تحلیل).
- **US4 (فاز ۶)**: پس از فاز ۲؛ برای آزمون کامل به یک پرونده ارجاع‌شده نیاز دارد که از طریق
  `T020a` (فاز ۲) ساخته می‌شود، نه از طریق US3 یا US6.
- **US5 (فاز ۷)**: پس از فاز ۲؛ برای آزمون به چند پرونده از US1 نیاز دارد.
- **US6 (فاز ۸، P2)**: پس از فاز ۲؛ می‌تواند موازی با US1–US5 ساخته شود. فقط شامل مدیریت موقعیت
  شغلی و رابط کاربری ارجاع است؛ منطق/قید ارجاع خودش در `T020a` (فاز ۲) پیاده‌سازی شده تا US3/US4
  (P1) معطل این فاز P2 نمانند.
- **Polish (فاز ۹)**: پس از تکمیل همه داستان‌های مدنظر برای انتشار.

### فرصت‌های اجرای موازی

- فقط تسک‌های مدل که فایل متفاوت دارند واقعاً موازی‌اند: `{T006, T007, T008, T009, T014, T017, T018}`
  با هم قابل‌اجرا هستند. تسک‌های `T010→T011→T012→T013→T016` (همگی روی
  `apps/applications/models.py`) و `T007→T015` (همگی روی `apps/candidates/models.py`) باید
  **متوالی** و پس از نویسنده اول همان فایل انجام شوند؛ علامت `[P]` از آن‌ها به‌عمد حذف شده است
  (رفع یافته C3 در تحلیل).
- پس از فاز ۲، تیم‌های مختلف می‌توانند روی US1، US2، US3، US4، US5 و US6 به‌صورت کاملاً موازی کار
  کنند؛ US4 دیگر به خروجی US3 نیاز ندارد، فقط به سرویس ارجاع `T020a` (فاز ۲) که پیش از همه
  داستان‌های کاربری آماده است.
- تست‌های هر داستان که با `[P]` علامت‌گذاری شده‌اند، پیش از شروع پیاده‌سازی همان داستان با هم
  قابل‌اجرا هستند.

---

## Parallel Example: User Story 1

```bash
# تست‌های US1 را با هم اجرا کنید (باید ابتدا شکست بخورند):
Task: "T026 Write form/job validation tests in tests/unit/test_application_form.py"
Task: "T027 Write file validation tests in tests/integration/test_attachment_upload.py"
Task: "T028 Write concurrency tests in tests/integration/test_application_submission_concurrency.py"
```

---

## Implementation Strategy

### MVP اول (فقط US1)

1. فاز ۱ (Setup) را کامل کنید.
2. فاز ۲ (Foundational) را کامل کنید — مسدودکننده است.
3. فاز ۳ (US1) را کامل کنید.
4. **توقف و صحت‌سنجی**: `quickstart.md` سناریو ۱ را مستقل اجرا کنید.
5. در صورت آمادگی، فقط دمو یا استقرار **پیش‌تولید** (staging) انجام شود.
   ⚠️ این معادل مجوز انتشار تولید نیست. انتشار تولید واقعی همچنان منوط به «تعریف اتمام» در
   پایین همین سند است (همه سناریوهای P1 یعنی US1–US5، نه فقط US1).

### تحویل افزایشی

۱. Setup + Foundational → پایه آماده
۲. US1 → صحت‌سنجی مستقل → دمو (MVP)
۳. US2 → صحت‌سنجی مستقل → دمو
۴. US3 → صحت‌سنجی مستقل → دمو
۵. US4 → صحت‌سنجی مستقل → دمو
۶. US5 → صحت‌سنجی مستقل → دمو
۷. US6 (P2) → صحت‌سنجی مستقل → دمو
۸. US7 (P2، مدیریت کاربران از پنل ادمین) → صحت‌سنجی مستقل → دمو
۹. فاز ۹ (Polish/شرط انتشار) → تصمیم انتشار تولید

## Notes

- `[P]` = فایل‌های متفاوت، بدون وابستگی ناتمام.
- برچسب `[USx]` تسک را به داستان کاربری مربوط در spec.md نگاشت می‌کند.
- پیش از پیاده‌سازی، تست‌های هر داستان باید نوشته شوند و ابتدا شکست بخورند.
- پس از هر تسک یا گروه منطقی commit بگیرید.
- طبق «تعریف اتمام» کاربر: انتشار تولید ممنوع است تا همه سناریوهای P1 (US1–US5، که US1/US2 اکنون
  بدون OTP هستند — دور پنجم) موفق باشند، تست
  جداسازی نقش/رکورد و رقابت روی PostgreSQL واقعی موفق باشد، شکست اسکن هرگز فایل قابل‌دانلود
  نسازد، خروجی امن و منطبق بر فیلتر باشد، هیچ داده شخصی در ذخیره پایدار مرورگر یا لاگ حساس نباشد،
  بازیابی پشتیبان آزموده شده باشد، و سیاست نگهداری اجراشده (T067a/T067b) و مصوب (T069) تنظیم شده
  باشد؛ موارد US6 (P2)
  می‌توانند تکمیل یا با پذیرش صریح ذی‌نفع به تعویق بیفتند.

## یادداشت تأیید اجرا (Phase 1–3، تا تاریخ این نسخه)

«تکمیل‌شده» در این سند فقط به معنای نوشته‌شدن کد نیست؛ موارد زیر واقعاً اجرا و با شواهد مستقیم
تأیید شده‌اند (نه فقط ادعا):

- **مهاجرت‌ها (T019)**: `makemigrations`/`migrate` روی یک کانتینر PostgreSQL ۱۶ واقعی اجرا شد؛
  قید یکتایی شرطی `uniq_active_application_per_candidate_job`/`uniq_active_reviewer_per_application`
  و قید `octet_length(data) BETWEEN 1 AND 5242880` با `psql \d` در اسکیمای واقعی تأیید شدند.
- **اسکن بدافزار (T027/T031/T032)**: با یک کانتینر ClamAV واقعی (نه موک) آزموده شد — رشته استاندارد
  EICAR به‌عنوان بدافزار شناسایی و quarantine شد؛ قطعی اتصال اسکنر هرگز به `clean` ترجمه نشد
  (`tests/integration/test_malware_scan_real_clamav.py`، ۵ تست). مشخص شد بررسی magic-byte و اسکن
  دو لایه کاملاً مجزا هستند: یک فایل EICAR خام هرگز از لایه magic-byte عبور نمی‌کند (چون شبیه
  PDF/DOC/DOCX نیست)، پس برای آزمون «حتی اگر لایه اول رد نکند» محتوای AttachmentContent مستقیماً
  در دیتابیس ساخته شد تا لایه اسکن مستقل از لایه اعتبارسنجی فرمت آزموده شود.
- **حساب کارمند و TOTP (T025)**: `createsuperuser_staff` و چرخه enrollment/تأیید TOTP با کد
  واقعی محاسبه‌شده از کلید دستگاه (`django_otp.oath.totp`) آزموده شد، شامل چرخه کامل API
  `login`→`mfa/verify` (`tests/integration/test_staff_account_and_totp.py`، ۵ تست). یافته جانبی:
  django-otp به‌درستی از replay همان کد در یک بازه زمانی جلوگیری می‌کند (رفتار امنیتی صحیح).
- **تست مرورگری واقعی (T036)**: با `playwright install chromium` واقعاً نصب و روی یک سرور
  Django زنده (`live_server`) اجرا شد؛ دیگر `skip` نیست. بخش «مشاهده در داشبورد HR» در آن زمان
  چون `templates/staff/dashboard.html` هنوز ساخته نشده بود، با بررسی مستقیم دیتابیس جایگزین
  شده بود؛ **این محدودیت در فاز ۵ (T046) رفع و تکمیل شد** — `tests/browser/test_us3_review.py`
  همان مشاهده واقعی پرونده در داشبورد HR را (ورود+MFA → فیلتر → مشاهده در جدول → ناوبری به
  صفحه جزئیات → دانلود) با Playwright واقعی آزموده است.
- **رابط ظاهری نمونه (T021)**: فایل‌های مرجع `8620268406482018050_335944227032103.html` و
  `reference.html` در `docs/reference/` اضافه شدند؛ رنگ، فونت، کارت، دکمه، فرم دو‌ستونی،
  stepbar و نوار اعلان دقیقاً از همان CSS منتقل شد. فیلدهای ناامن نمونه (کد ملی، ورود دمو با
  رمز `MilanPars1405!`، `localStorage`/`IndexedDB`) عمداً منتقل نشدند (طبق constitution.md و
  FR-004/FR-048).
- **سه باگ واقعی کشف و رفع شد که فقط با اجرای واقعی (نه نوشتن کد) قابل‌کشف بودند**:
  ۱) rollback تراکنشی `failed_attempts` در تأیید نادرست OTP (brute-force نامحدود)؛
  ۲) نبود `timezone.utc` در Django/Python فعلی (کرش هر `request_otp`)؛
  ۳) override شدن ویژگی بومی `hidden` توسط `display:grid` در CSS فرم (دقیقاً همان کلاس اشتباه
  شناخته‌شده «hidden در برابر display»)، که بدون اجرای واقعی تست مرورگری هرگز دیده نمی‌شد.
  رگرسیون صریح باگ‌های ۱ و ۲ در `tests/unit/test_otp_regression_bugs.py` ثبت شده است.
- همه ۳۴ تست (`tests/unit`, `tests/integration`, `tests/browser`) در یک اجرای واحد روی
  PostgreSQL، ClamAV و Chromium واقعی سبز شدند.

### Phase 4 — US2 پیگیری (T037–T040)

- `GET /api/v1/candidate/applications/{id}` (T038) اضافه شد؛ فیلتر `candidate=request.user`
  مانع IDOR است. **باگ واقعی خودمان** در همین افزودن رخ داد: ویرایش متنی اشتباه باعث شد متد
  `post` از کلاس `CandidateApplicationListCreateView` به داخل کلاس جدید
  `CandidateApplicationDetailView` منتقل شود؛ این باعث ۴۰۵ شدن `POST /candidate/applications`
  در تمام تست‌های بعدی (حتی تست‌های قبلاً سبز US1) شد و فقط با اجرای دوباره کل مجموعه تست
  (نه فقط تست‌های تازه) کشف شد. رفع و دوباره تأیید شد.
- `tests/contract/test_candidate_privacy.py` (T037) روی PostgreSQL واقعی: پاسخ جزئیات محدود به
  چهار فیلد عمومی (`tracking_code, job_position, status, updated_at`)، تغییر شناسه در URL برای
  دسترسی به پرونده دیگری ۴۰۴ می‌گیرد (FR-014)، و بدون OTP هیچ دسترسی‌ای نیست (FR-013) — ۳ تست.
- `templates/candidate/track.html` + `static/js/candidate_track.js` (T039) ساخته شد.
- `tests/browser/test_us2_tracking.py` (T040) با Playwright واقعی: یک نشست چند درخواست خودش را
  می‌بیند؛ یک کانتکست مرورگر کاملاً مستقل (بدون کوکی مشترک) بدون OTP هیچ داده‌ای نمی‌بیند — ۲ تست.
- جمع کل تست‌های پروژه تا این نقطه: **۳۹ تست**، همه در یک اجرای واحد روی PostgreSQL، ClamAV و
  Chromium واقعی سبز. محدوده «جداسازی نشست» در این فاز به همان حد US2 (رد دسترسی بدون OTP و رد
  دسترسی به پرونده متقاضی دیگر) محدود ماند؛ جداسازی کامل کوکی `candidate_sessionid` در برابر
  `staff_sessionid` طبق تصمیم کاربر به فاز ۹ (T062) موکول است و در این اجرا گسترش داده نشد.

### Phase 5 — US3 بررسی پرونده (T041–T046)

- `GET /api/v1/staff/applications`, `/metrics`, `/{id}`, `/{id}/resume` (T043/T044) پیاده‌سازی
  و با `get_applications_queryset`/`apply_staff_filters` مشترک بین فهرست و آمار اعمال شد.
- `tests/contract/test_staff_access_matrix.py` (T041) روی PostgreSQL واقعی — ۷ تست: ماتریس کامل
  `recruiter`/`hiring_manager`/`hr_manager` روی فهرست/جزئیات/آمار/دانلود؛ `system_operator` صفر
  دسترسی تجاری؛ درخواست ناشناس ۴۰۱/۴۰۳؛ **چرخه کامل واقعی** `login` (رمز) → تلاش دسترسی قبل از
  MFA (رد) → `mfa/verify` (کد TOTP واقعی) → دسترسی مجاز (الزام ۱)؛ نشست متقاضی (کوکی
  `candidate_sessionid` واقعی پس از OTP) روی مسیرهای `staff/*` رد می‌شود.
- `tests/integration/test_resume_download.py` (T042) — ۹ تست: لغو ارجاع بلافاصله دسترسی/دانلود
  را قطع می‌کند (الزام ۴)؛ هر چهار وضعیت غیر-`clean` (`pending`/`quarantined`/`scan_failed`/
  `rejected`) هرگز دانلود نمی‌شوند حتی با ارجاع معتبر (الزام ۳)؛ کنترل مجوز در *هر* درخواست
  دوباره اجرا می‌شود، نه فقط زمان ارجاع؛ `Content-Disposition: attachment`، نام فایل امن،
  `Cache-Control: no-store` (الزام ۶)؛ فهرست/جست‌وجو با `CaptureQueriesContext` تأیید شد که
  هرگز به جدول `attachments_attachmentcontent` پرس‌وجو نمی‌زنند (الزام ۵)؛ دانلود مجاز در
  `AuditEvent` بدون محتوای فایل ثبت می‌شود (الزام ۶).
- `templates/staff/login.html`, `dashboard.html`, `application_detail.html` + سه فایل JS
  (T045) ساخته شدند؛ رنگ/کارت/جدول/نشان وضعیت دقیقاً از `docs/reference/reference.html`
  منتقل شده‌اند (الزام ۷).
- `tests/browser/test_us3_review.py` (T046) با Playwright واقعی — ۱ تست کامل: ورود با رمز →
  تلاش دسترسی قبل از MFA رد می‌شود → تکمیل MFA با کد TOTP واقعی → فیلتر در داشبورد زنده →
  ناوبری به صفحه جزئیات واقعی (نه بررسی مستقیم دیتابیس) → دانلود واقعی فایل با
  `page.expect_download` → یک درخواست API کاملاً ناشناس (بدون کوکی) به `staff/applications/{id}`
  با ۴۰۳ رد می‌شود. این تست همان بخش «مشاهده در داشبورد HR» را که در T036 به‌دلیل نبود
  dashboard.html موقتاً با بررسی دیتابیس جایگزین شده بود، تکمیل می‌کند.
- **باگ واقعی خودمان در همین فاز**: هنگام افزودن `CandidateApplicationDetailView` (T038،
  فاز ۴)، یک ویرایش متنی اشتباه متد `post` را از کلاس درست جدا کرده بود؛ این باعث ۴۰۵ شدن
  `POST /candidate/applications` در *همه* تست‌های بعدی شده بود و فقط با اجرای کامل مجموعه تست
  (نه فقط تست‌های تازه فاز ۴) کشف و در همان فاز رفع شد — یادآوری اینکه چرا اجرای کل مجموعه
  پس از هر افزودن الزامی است، نه فقط تست‌های جدید.
- جمع کل تست‌های پروژه تا این نقطه: **۵۶ تست**، همه در یک اجرای واحد روی PostgreSQL، ClamAV و
  Chromium واقعی سبز (دو بار اجرا شد تا پایداری/عدم‌وابستگی به ترتیب تأیید شود).
- **موارد خارج از این اجرا (عمداً وارد Phase 6 نشدیم)**: تغییر وضعیت/یادداشت‌نویسی واقعی (US4)،
  مدیریت موقعیت شغلی از طریق UI (US6)، و جداسازی کامل کوکی `candidate_sessionid`/`staff_sessionid`
  (T062، فاز ۹) که طبق تصمیم کاربر همچنان به فاز ۹ موکول است.

### Phase 6 — US4 رسیدگی به پرونده (T047–T053)

- سیاست نقش تغییر وضعیت (`STATUS_CHANGE_ALLOWED_ROLES` در `apps/applications/services.py`)
  مستقیماً از متن مصوب نقش‌ها در spec.md استخراج شد، نه تعریف خودسرانه: فقط `recruiter` و
  `hr_manager` می‌توانند وضعیت را تغییر دهند؛ `hiring_manager` طبق FR-018 («مدیر استخدام ...
  بدون تغییر وضعیت») و `system_operator` همیشه مسدودند — حتی اگر از طریق ارجاع فعال، دسترسی
  رکوردی به همان پرونده داشته باشند (الزام ۱ و ۲).
- `add_note()` و `change_status()` در `apps/applications/services.py` اضافه شدند؛ هر دو درون
  `@transaction.atomic` اجرا می‌شوند؛ `change_status` با `select_for_update()` + بررسی
  `application.version != expected_version` **پیش از هر نوشتن** قفل و رد می‌کند (الزام ۳) —
  یعنی `VersionConflict` هرگز نوشتن نیمه‌کاره باقی نمی‌گذارد. تغییر وضعیت و درج `StatusHistory`
  در همان تراکنش انجام می‌شود (الزام ۴)؛ متن `reason`/`body` یادداشت هرگز در
  `AuditEvent.metadata` ذخیره نمی‌شود — فقط `from_status`/`to_status`/`is_exception` ثبت
  می‌شوند.
- `StaffApplicationNoteCreateView` و `StaffApplicationStatusView` در
  `apps/applications/api/views.py` و مسیرهای `staff/applications/{id}/notes` (POST) و
  `staff/applications/{id}/status` (PATCH) در `apps/applications/api/urls.py` اضافه شدند؛ هر دو
  با همان `get_applications_queryset(request.user)` دسترسی رکوردی را اعمال می‌کنند — کارمندی
  که ارجاع فعال ندارد (یا لغو شده) ۴۰۴ می‌گیرد، حتی اگر نقشش عموماً اجازه داشته باشد.
  `StatusChangeSerializer`/`NoteCreateSerializer`/`NoteSerializer` در `serializers.py` اضافه
  شدند.
- `tests/unit/test_status_transitions.py` (T047) — ۹ تست: انتقال‌های مجاز/نامجاز طبق
  `statemachine.py`؛ `rejected` بدون `reason` رد می‌شود؛ `hiring_manager`/`system_operator`
  همیشه `PermissionDenied` می‌گیرند (حتی برای انتقال‌های عادی)؛ فقط `hr_manager` می‌تواند
  وضعیت نهایی (`hired`/`rejected`) را با `reason` اجباری بازگشایی کند و `is_exception=True`
  ثبت می‌شود؛ تغییر وضعیت و `StatusHistory` در یک تراکنش ثبت می‌شوند؛ رگرسیون SC-008: دو
  یادداشت و دو تغییر وضعیت متوالی هیچ‌کدام از رکوردهای قبلی را حذف/بازنویسی نمی‌کنند.
- `tests/integration/test_application_status_conflict.py` (T048) روی PostgreSQL واقعی — ۳
  تست: `expected_version` قدیمی با `VersionConflict` رد می‌شود بدون اینکه وضعیت/نسخه تغییر
  کند و بدون ثبت تاریخچه نیمه‌کاره؛ **رقابت واقعی هم‌زمان** با دو ریسه (`threading.Thread`) که
  هم‌زمان تلاش می‌کنند وضعیت یک پرونده را با همان نسخه مشترک تغییر دهند — دقیقاً یکی موفق و
  دیگری `VersionConflict` می‌گیرد، فقط یک ردیف `StatusHistory` ثبت می‌شود (نه گم‌شدن تغییر، نه
  دو انتقال هم‌زمان)؛ آزمون سطح API که دومین تلاش با نسخه قدیمی دقیقاً ۴۰۹ با `code: conflict`
  برمی‌گرداند.
- `tests/integration/test_application_notes_and_status_access.py` (آزمون‌های اضافی درخواستی
  کاربر) — ۸ تست: کارمند بدون ارجاع فعال از یادداشت/تغییر وضعیت با ۴۰۴ منع می‌شود؛
  `hiring_manager` با ارجاع فعال می‌تواند یادداشت بگذارد اما هرگز نمی‌تواند وضعیت را تغییر دهد
  (۴۰۳) — تفکیک صریح بین مجوز رکوردی و مجوز نقش؛ لغو ارجاع، یادداشت/تغییر وضعیت را در *درخواست
  بعدی همان کارمند* بدون نیاز به خروج/ورود دوباره قطع می‌کند (الزام ۶)؛ متن یادداشت و `reason`
  هرگز در `AuditEvent.metadata` ظاهر نمی‌شوند؛ نشست **واقعی** متقاضی (کوکی OTP معتبر، نه شبیه‌
  سازی) روی هر دو مسیر کارکنان با ۴۰۱/۴۰۳ رد می‌شود و هیچ نوشتنی اعمال نمی‌شود (الزام ۷).
- پاسخ عمومی متقاضی (`ApplicationPublicDetailSerializer` در `tests/contract/test_candidate_privacy.py`،
  از فاز ۵) همچنان فاقد هر فیلد یادداشت/تاریخچه/ارجاع است — ساختاری تضمین‌شده چون آن
  serializer اصلاً فیلد `notes` ندارد؛ نمایش یادداشت در `static/js/staff_detail.js` با
  `textContent` (نه `innerHTML`) انجام می‌شود، پس امن در برابر XSS است (الزام ۵).
- `templates/staff/application_detail.html` و `static/js/staff_detail.js` (T052) با فرم
  افزودن یادداشت و فرم تغییر وضعیت وصل شدند؛ پاسخ ۴۰۹ پیغام «این پرونده توسط کاربر دیگری
  تغییر کرده؛ لطفاً تازه‌سازی کنید» + دکمه بازخوانی نشان می‌دهد؛ هندلرهای فرم یک‌بار (نه در هر
  بازخوانی) ثبت می‌شوند تا listener تکراری ایجاد نشود.
- `tests/browser/test_us4_workflow.py` (T053) با Playwright واقعی — ۱ تست کامل سرتاسری: ورود
  با رمز → MFA با کد TOTP واقعی → فیلتر در داشبورد زنده → ناوبری به جزئیات → دانلود واقعی فایل
  → ثبت یادداشت واقعی (ظاهر در DOM) → تغییر وضعیت واقعی (`new`→`phone`، تأیید در DOM و
  دیتابیس) → یک درخواست مستقیم API بدون نشست معتبر که رد می‌شود.
- جمع کل تست‌های پروژه تا این نقطه: **۷۷ تست**، همه در یک اجرای واحد روی PostgreSQL، ClamAV و
  Chromium واقعی سبز — سه بار اجرا شد (از جمله تکرار مجزای تست رقابت هم‌زمان) تا پایداری تأیید
  شود.
- **T062 (آزمون جامع جداسازی کوکی `candidate_sessionid`/`staff_sessionid`) همچنان شرط انتشار
  باقی مانده و تکمیل‌شده اعلام نمی‌شود** — طبق تصمیم صریح کاربر به فاز ۹ موکول است.
- **موارد خارج از این اجرا (عمداً وارد Phase 7 یا US6 نشدیم)**: خروجی‌گیری CSV/XLSX (US5)،
  مدیریت موقعیت شغلی از طریق UI (US6)، و تمام شرط‌های انتشار تولید فاز ۹ (از جمله T062).

### تکمیل پوشش US4 (قبل از ورود به Phase 7) — `tests/integration/test_application_notes_and_status_access.py`

- **CSRF**: دو تست با نشست واقعی رمز+MFA (نه `force_authenticate`) و `APIClient(enforce_csrf_checks=True)`
  نوشته شد: بدون هدر/کوکی CSRF هر دو مسیر `notes` (POST) و `status` (PATCH) با ۴۰۳ رد می‌شوند
  و هیچ نوشتنی اعمال نمی‌شود؛ با توکن CSRF واقعی (از `get_token` روی همان نشست) موفق می‌شوند —
  یعنی فقط داشتن کوکی نشست کافی نیست.
- **نمایش امن یادداشت**: یک تست API تأیید کرد سرور متن یادداشت حاوی `<script>`/`onerror` را
  بدون escape دقیقاً همان‌طور ذخیره/برمی‌گرداند (JSON است، نه HTML، پس اجرا نمی‌شود) و یک تست
  **مرورگری واقعی** (Playwright) تأیید کرد چنین یادداشتی در DOM به‌صورت متن escape‌شده
  (`&lt;b&gt;...&lt;/b&gt;`) دیده می‌شود، هیچ `<img>`ای واقعاً در DOM ساخته نمی‌شود، و
  `window.__xss_fired` هرگز تنظیم نمی‌شود — یعنی ایمنی واقعاً روی `textContent` در
  `static/js/staff_detail.js` تکیه دارد، نه یک پاکسازی سمت سرور که قابل دور زدن باشد.
- **عدم افشای یادداشت داخلی**: یک تست یادداشت تازه‌ثبت‌شده را با چرخه OTP واقعی متقاضی آزمود —
  نه در `GET /candidate/applications/{id}` و نه در فهرست `GET /candidate/applications` ظاهر
  می‌شود (ساختاری تضمین‌شده چون `ApplicationPublicDetailSerializer` اصلاً فیلد `notes` ندارد).
- **Rollback تراکنشی**: با monkeypatch کردن `record_event` برای raise کردن `RuntimeError` در
  میانهٔ `change_status`، تأیید شد که `Application.status`/`version` و `StatusHistory` همگی
  rollback می‌شوند — چون ثبت رویداد حسابرسی، تغییر وضعیت و درج `StatusHistory` همه درون همان
  `@transaction.atomic` هستند، شکست هرکدام باعث rollback کامل می‌شود، نه نوشتن نیمه‌کاره.
- جمع: ۷ تست جدید اضافه شد (۲۰ تست در این فایل در مجموع، همه سبز).

### Phase 7 — US5 خروجی‌گیری (T054–T057)

- `apps/reporting/export_policy.py` ساخته شد: `ALLOWED_COLUMNS` (۱۵ ستون کسب‌وکاری؛ یادداشت/
  تاریخچه/حسابرسی/محتوای فایل/اسرار احراز هویت اصلاً در این فهرست حضور ندارند — نه فقط از
  پیش‌فرض حذف شده‌اند، طبق FR-033)، `TEXT_FORMAT_COLUMNS` (موبایل/کد پیگیری)،
  `neutralize_formula()` (آپاستروف پیش از مقدار پس از حذف فاصله/نویسه کنترلی ابتدایی، برای
  `=`,`+`,`-`,`@`)، `validate_columns()` (رد ستون نامجاز با `InvalidColumns`)، و
  `MAX_EXPORT_ROWS = 10000`.
- `apps/reporting/services.py`: `get_export_queryset()` دقیقاً از همان
  `get_applications_queryset()` + `apply_staff_filters()` فهرست کارکنان استفاده می‌کند، پس
  پارامترهای فیلتر ارسالی هرگز نمی‌توانند دامنه مجاز کاربر را گسترش دهند، فقط محدودتر کنند
  (الزام ۲)؛ `collect_rows()` با خواندن `MAX_EXPORT_ROWS + 1` ردیف، عبور از سقف را بدون شمارش
  کامل جدول تشخیص می‌دهد و `TooManyRows` را پیش از ساخت هر فایلی raise می‌کند (الزام ۵، FR-032)؛
  `render_csv()`/`render_xlsx()` روی هر مقدار `neutralize_formula()` اعمال می‌کنند و XLSX با
  `openpyxl(write_only=True)` + قالب سلول متنی (`@`) برای موبایل/کد پیگیری نوشته می‌شود (الزام
  ۴، FR-034/FR-035)؛ هیچ `select_related`/فیلدی از `AttachmentContent` در مسیر خروجی وجود ندارد
  (الزام ۷).
- `apps/reporting/api/views.py` (`StaffExportView`) + `apps/reporting/api/urls.py` +
  `config/urls.py`: فقط `permission_classes=[IsHrManager]` (مجوز خروجی مستقل از مجوز
  مشاهده/یادداشت/دانلود، الزام ۱، FR-036)؛ فرمت نامعتبر/ستون نامجاز ۴۰۰؛ دو رویداد
  `export_started`/`export_completed` (یا `export_failed`) در `AuditEvent` با فیلتر نرمال‌شده،
  ستون‌ها و تعداد ردیف، بدون محتوای واقعی خروجی (الزام ۶، FR-037)؛ پاسخ با
  `Cache-Control: no-store`، `Content-Disposition: attachment` و نام فایل ثابت/امن.
- `templates/staff/export.html` + `static/js/staff_export.js` (T057): فرم انتخاب فرمت/فیلتر/
  ستون‌ها، راهنمای وارد کردن ستون‌های CSV به‌صورت متن در Excel، و دانلود واقعی فایل با
  `fetch`/blob؛ لینک «خروجی‌گیری» به داشبورد اضافه شد.
- `tests/unit/test_export_policy.py` (T054) — ۱۶ تست بدون نیاز به دیتابیس: یادداشت/حسابرسی
  اصلاً در فهرست مجاز نیستند؛ ستون نامجاز رد می‌شود؛ `neutralize_formula` روی `=`/`+`/`-`/`@`
  حتی با فاصله/تب ابتدایی کار می‌کند؛ سقف دقیقاً ۱۰٬۰۰۰ پذیرفته و ۱۰٬۰۰۱ رد می‌شود؛ خروجی CSV
  دارای BOM است؛ خروجی XLSX قالب سلول متنی را روی موبایل/کد پیگیری حفظ و فرمول را خنثی می‌کند.
- `tests/integration/test_staff_export_access.py` (ماتریس نقش/دامنه/API، درخواستی صریح کاربر)
  — ۱۱ تست روی PostgreSQL واقعی: `recruiter`/`hiring_manager` (حتی با ارجاع فعال و دسترسی
  مشاهده کامل) و `system_operator` همگی ۴۰۳ می‌گیرند؛ فقط `hr_manager` موفق می‌شود؛ فیلتر
  `status` باعث می‌شود فقط ردیف‌های منطبق صادر شوند (نه گسترش دامنه)؛ ستون نامجاز در بدنه
  درخواست واقعی ۴۰۰ می‌گیرد؛ پرس‌وجوی خروجی هرگز به `attachmentcontent` نمی‌رسد؛ مقدار واقعی
  وارد شده توسط کاربر (نام/نام خانوادگی با پیشوند `=`/`@`) در CSV و XLSX واقعاً خنثی می‌شود؛
  عبور از سقف (با `TooManyRows` شبیه‌سازی‌شده) بدون فایل رد می‌شود؛ `export_started`/
  `export_completed` حسابرسی می‌شوند بدون محتوای محرمانه واقعی؛ نشست واقعی متقاضی رد می‌شود.
- `tests/browser/test_us5_export.py` (T057) با Playwright واقعی — ۱ تست کامل: ورود+MFA واقعی →
  کلیک روی لینک «خروجی‌گیری» در داشبورد → فرم خروجی → دانلود واقعی فایل CSV با
  `page.expect_download` → بررسی محتوای واقعی فایل دانلودشده (BOM + ردیف واقعی پرونده).

### تکمیل سیاست MVP خروجی‌گیری (رفع تصمیم باز قبلی) — T057a/T057b

- تصمیم باز قبلی («هیچ throttle برای `POST /staff/exports` تعریف نشده بود») اکنون با تصمیم
  صریح کاربر و اجرای واقعی رفع شده است: **FR-037a** در spec.md ثبت شد (سقف ۵ درخواست خروجی در
  هر بازه ۱۰ دقیقه‌ای برای هر حساب کارمند، پس از احراز هویت و بررسی مجوز خروجی؛ پاسخ ۴۲۹ +
  `Retry-After`؛ تولید خروجی بزرگ در پس‌زمینه عمداً خارج از دامنه MVP). `research.md §۷ـالف` و
  `plan.md` (بخش Constraints و نقشهٔ ماژول `reporting`) هم به‌روزرسانی شدند.
- `apps/reporting/models.py` (`ExportRateCounter`, مایگریشن `0001_initial`) و
  `enforce_export_rate_limit()`/`_window_start()` در `apps/reporting/services.py` دقیقاً همان
  الگوی اتمی `OtpRateCounter`/`_increment_counter` در `apps/candidates` را تکرار می‌کنند
  (`select_for_update()` درون `transaction.atomic()`) — **بدون افزودن هیچ زیرساخت جدیدی**
  (نه Redis، نه صف پس‌زمینه)، دقیقاً طبق دستور کاربر.
- `apps/reporting/api/views.py`: شمارش فقط **پس از** عبور موفق از `permission_classes =
  [IsHrManager]` اعمال می‌شود (یعنی پس از احراز هویت کامل + تأیید مجوز خروجی، نه پیش از آن)؛
  عبور از سقف پاسخ `429` با هدر `Retry-After` (ثانیه‌های باقی‌مانده تا پایان پنجره) برمی‌گرداند،
  بدون هیچ تولید فایلی و بدون حسابرسی `export_started` برای آن تلاش.
- `tests/integration/test_export_rate_limit.py` (T057a) — ۶ تست روی PostgreSQL واقعی: مرز دقیق
  (دقیقاً ۵ درخواست موفق، ششمی ۴۲۹ با `Retry-After` مثبت)؛ پایان بازه (با انتقال دستی شمارنده
  به پنجرهٔ قبلی، معادل گذشت واقعی ۱۰ دقیقه، درخواست بعدی دوباره مجاز می‌شود)؛ استقلال کامل بین
  دو حساب `hr_manager` متفاوت (محدودیت حساب اول هیچ اثری روی حساب دوم ندارد)؛ **رقابت واقعی
  هم‌زمان** با ۱۰ ریسه (`threading.Thread`) که هم‌زمان درخواست می‌دهند — دقیقاً ۵ مورد موفق و ۵
  مورد ۴۲۹ می‌گیرند، نه بیشتر از سقف موفق می‌شود (قفل اتمی رقابت را درست مدیریت می‌کند)؛ تلاش‌های
  رد‌شده با ۴۰۳ (نقش غیرمجاز) هیچ ردیف شمارنده‌ای ایجاد نمی‌کنند.
- جمع کل تست‌های پروژه تا این نقطه: **۱۱۷ تست**، همه در یک اجرای واحد روی PostgreSQL، ClamAV و
  Chromium واقعی سبز — چندین بار اجرا شد (از جمله تکرار جدا تست رقابت هم‌زمان خروجی) تا پایداری
  تأیید شود.
- **ثبت تکمیل US5**: تمام تسک‌های Phase 7 (T054 تا T057b) واقعاً اجرا، آزموده و تأیید شده‌اند؛
  هیچ تصمیم بازی در حوزه خروجی‌گیری باقی نمانده است.
- **T062 همچنان باز و شرط انتشار باقی مانده و تکمیل‌شده اعلام نمی‌شود.**

### Phase 8 — US6 مدیریت موقعیت و ارجاع (T058–T061)

- **رفع یک نقص واقعی کشف‌شده در همین فاز (نه فقط افزودن تست)**: `assign_reviewer()` در
  `apps/applications/services.py` قبلاً هیچ بررسی نقش روی دریافت‌کننده ارجاع نداشت — یک
  `hr_manager` یا حتی `system_operator` می‌توانست به‌عنوان «بررسی‌کننده» ثبت شود، خلاف متن
  صریح FR-041 («کارشناس جذب یا مدیر استخدام»). این اکنون با `ELIGIBLE_REVIEWER_ROLES` رفع و
  تست شد (الزام ۶ — این یک قاعده صریح بود، نه ابهام).
- **رفع یک رقابت واقعی (race) کشف‌شده در همین فاز**: قبلاً `assign_reviewer()` فقط ردیف
  `ApplicationReviewer` را قفل می‌کرد؛ وقتی هیچ ارجاع فعالی وجود نداشت (اولین ارجاع)، هیچ
  ردیفی برای قفل‌کردن نبود و دو درخواست هم‌زمان می‌توانستند هر دو `current is None` ببینند.
  اکنون خودِ ردیف `Application` نیز با `select_for_update()` قفل می‌شود تا دو ارجاع هم‌زمان
  کاملاً سریالی شوند؛ قید یکتایی دیتابیسی `uniq_active_reviewer_per_application` هم به‌عنوان
  خط دفاع دوم نگه داشته شد و در صورت رخداد، به `AssignmentConflict` (۴۰۹ تمیز، نه کرش ۵۰۰)
  تبدیل می‌شود (الزام ۴).
- **رفع یک رقابت واقعی دیگر**: `submit_application()` موقعیت شغلی را بدون قفل می‌خواند، یعنی
  بستن هم‌زمان موقعیت و ثبت درخواست می‌توانست به ثبت درخواست برای موقعیت از‌پیش‌بسته منجر شود.
  اکنون `submit_application` و `close_job`/`update_job` هر دو همان ردیف `JobPosition` را با
  `select_for_update()` قفل می‌کنند تا این دو عملیات سریالی شوند (الزام ۵، FR-039).
- `apps/jobs/services.py` (`create_job`, `update_job`, `close_job`) + `apps/jobs/api/views.py`
  (`StaffJobListCreateView`, `StaffJobDetailView`) + مسیرهای `staff/jobs`/`staff/jobs/{id}` در
  `apps/jobs/api/urls.py`: فقط `permission_classes=[IsHrManager]`؛ **هیچ مسیر DELETE اصلاً
  تعریف نشده** (نه فقط رد شده) — حذف فیزیکی به‌معنای واقعی کلمه در API وجود ندارد (FR-038)؛ هر
  ایجاد/ویرایش با `record_event("job_created"/"job_updated", ...)` حسابرسی می‌شود.
  مسیرهای یادداشت/وضعیت/ارجاع از پیش (فاز ۲ و ۶) `permission_classes=[IsStaff]`/`[IsHrManager]`
  دارند و نشست‌شان `SessionAuthentication` پیش‌فرض DRF است؛ یعنی نشست متقاضی و نشست کارمند بدون
  MFA (که اصلاً نشست Django واقعی ایجاد نمی‌شود، چون `login()` فقط پس از تأیید TOTP در
  `StaffMfaVerifyView` فراخوانی می‌شود) و درخواست بدون CSRF معتبر، همان محافظت‌های موجود از
  فاز ۶ را به‌ارث می‌برند (الزام ۲؛ قبلاً در Phase 6 به‌طور مستقیم آزموده شده، اینجا دوباره
  ابداع نشد).
- `templates/staff/application_detail.html` + `static/js/staff_detail.js`: بخش «ارجاع پرونده»
  (نمایش بررسی‌کننده فعلی، فرم ثبت/جایگزینی ارجاع با شناسه کارمند، دکمه لغو) اضافه شد، همان
  الگوی فرم‌های موجود (سرور مرجع نهایی مجوز است، نه پنهان‌کردن دکمه — اصل III).
  `templates/staff/jobs.html` + `static/js/staff_jobs.js`: فرم ایجاد موقعیت و جدول موقعیت‌ها با
  دکمه «بستن» برای هر موقعیت باز؛ لینک «موقعیت‌های شغلی» به داشبورد اضافه شد؛ هر دو صفحه با
  همان CSS/چیدمان RTL صفحات دیگر (الزام ۷).
- `tests/integration/test_job_lifecycle.py` (T058) — ۶ تست روی PostgreSQL واقعی: بستن موقعیت
  مانع ثبت جدید می‌شود بدون اثر روی سابقه قبلی؛ فقط `hr_manager` می‌تواند ایجاد/ویرایش کند؛
  هیچ مسیر DELETE برای موقعیت وجود ندارد؛ ایجاد/بستن از طریق API حسابرسی می‌شود؛ نقش غیرمجاز
  از API رد می‌شود؛ **رقابت واقعی هم‌زمان** بستن موقعیت/ثبت درخواست با دو ریسه — نتیجه همیشه
  یکی از دو حالت قطعی و سازگار است، هرگز حالت بینابینی.
- `tests/integration/test_reviewer_assignment.py` (T059) — ۵ تست روی PostgreSQL واقعی: ارجاع
  مستقیم به `hiring_manager` بدون `recruiter` قبلی رد می‌شود؛ ارجاع بعدی به `hiring_manager`
  ارجاع فعال `recruiter` را باطل می‌کند؛ فقط `recruiter`/`hiring_manager` صلاحیت دریافت ارجاع
  دارند (`hr_manager`/`system_operator` رد می‌شوند)؛ لغو ارجاع در *درخواست بعدی* همان کارمند
  فهرست، جزئیات، دانلود رزومه (بدون اثر روی نسخه پیش‌تر دانلودشده)، یادداشت و تغییر وضعیت را
  همگی قطع می‌کند؛ **رقابت واقعی** دو ارجاع هم‌زمان هرگز بیش از یک ارجاع فعال باقی نمی‌گذارد.
- `tests/browser/test_us6_job_and_referral.py` (T061) با Playwright واقعی و **دو نشست کاملاً
  مستقل** (دو `browser context` جدا، نه فقط دو تب) — ۱ تست کامل سرتاسری: ورود+MFA واقعی مدیر
  HR → ایجاد موقعیت جدید از رابط → بستن همان موقعیت از رابط → ارجاع پرونده موجود به کارشناس
  جذب از صفحه جزئیات → ورود+MFA واقعی همان کارشناس در نشست کاملاً جدا → مشاهده واقعی پرونده
  ارجاع‌شده در داشبورد او → لغو ارجاع توسط مدیر HR → تأیید قطع فوری دسترسی کارشناس در بازخوانی
  بعدی صفحه جزئیات (بدون خروج/ورود دوباره).
- جمع کل تست‌های پروژه تا این نقطه: **۱۲۹ تست**، همه در یک اجرای واحد روی PostgreSQL، ClamAV و
  Chromium واقعی سبز — سه بار اجرا شد (شامل تکرار جداگانه هر دو تست رقابت هم‌زمان) تا پایداری
  تأیید شود.
- **ابهام گزارش‌شده قبلی رفع شد (نه کورکورانه، با گزارش اختلاف پیش از تغییر ساختار)**: پیش از
  تغییر، مدل `JobPosition` دو بُعد مستقل داشت — `Status{open, closed, archived}` + `is_published`
  (bool) جدا (۶ ترکیب ممکن، بدون هیچ قاعده انتقال). سیاست جدید کاربر یک بُعد خطی سه‌حالتی است:
  `draft → open`، `open → closed`، `closed → open`. نگاشت اعمال‌شده: `is_published=False` ⇐
  `draft`؛ `is_published=True و status=open` ⇐ `open`؛ هر `closed` ⇐ `closed`؛ **`archived` به
  هیچ وضعیتی نگاشت خودکار نشد و کاملاً از چرخه حذف شد** (چون بازگشت‌پذیری آن هرگز تعریف‌نشده
  بود و در فهرست صریح سه‌حالته کاربر نبود). **FR-039a** در spec.md، بخش «قاعده»ی `JobPosition`
  در data-model.md، و `quickstart.md` هماهنگ به‌روزرسانی شدند؛ `is_published` از مدل کاملاً حذف
  شد.
- **اصلاح بعدی مهم (پیش از هر ادعای تأیید مهاجرت)**: دو مهاجرت ولی توسط `migrations` نشد:
  نخست ادعا شد محیط به تولید نرفته و «تغییر ساختاری مستقیم» کافی است؛ این اشتباه بود چون یک
  دیتابیس محلی واقعاً ارتقا یافته بود. مهاجرت به دو گام با **بررسی پیش‌پرواز** تغییر کرد:
  `0002_preflight_job_status_mapping` (فقط‌خواندنی، قفل `ACCESS EXCLUSIVE`، متوقف‌کردن امن ردیف‌های
  بی‌نگاشت) و `0003_job_status_graph` (حذف `is_published`، برگشت‌ناپذیر داده‌محور). **نگاشت مصوب
  فقط** `(True, open)→open` و `(True, closed)→closed` است؛ `(False, closed)→draft` به‌عنوان مصوب
  پذیرفته **نشد** و به‌همراه هر `archived` و هر مقدار ناشناخته باعث توقف امن می‌شود. مسیر واقعی
  مهاجرت با `MigrationExecutor` روی پایگاه‌داده‌های مستقل و دوریختنی آزموده شد
  (`tests/integration/test_jobs_migration_path.py`، ۹ تست). جزئیات و سیاهه تغییرات دستی
  `django_migrations` در `docs/operations/migrations.md`.
- `apps/jobs/models.py`: `Status{DRAFT, OPEN, CLOSED}` (بدون `ARCHIVED`، بدون `is_published`)؛
  `apps/jobs/statemachine.py` (الگوی مشابه
  `apps/applications/statemachine.py`): `ALLOWED_TRANSITIONS` دقیقاً سه‌تایی بالا.
  `apps/jobs/services.py`: `create_job` همیشه `draft` می‌سازد (فعال‌سازی باید صریح باشد)؛
  `update_job` فقط فیلدهای توصیفی (`title`/`department`/`location`)؛ `change_job_status`
  (+ `close_job`/`reopen_job`) تنها مسیر تغییر وضعیت — فقط `hr_manager`، با `select_for_update`
  (سریال‌سازی با `submit_application`)، انتقال نامجاز `InvalidJobTransition`، و حسابرسی
  جداگانه `job_reopened` برای هر ورود به `open` (الزام مجوز/حسابرسی صریح کاربر برای بازگشایی).
  `apps/jobs/api/views.py`: مسیر تازه `StaffJobStatusView` روی `PATCH .../jobs/{id}/status`؛
  `PublicJobListView` و صفحه عمومی ثبت درخواست (`apps/candidates/views.py`) اکنون فقط
  `status=open` را نشان می‌دهند (نه `is_published`/`status` دوگانه).
- `templates/staff/jobs.html` + `static/js/staff_jobs.js`: دکمه‌های وضعیت‌محور («فعال‌سازی» برای
  `draft`، «بستن» برای `open`، «بازگشایی» برای `closed`)؛ چک‌باکس منتشرشده حذف شد (دیگر معنا
  ندارد). `tests/browser/test_us6_job_and_referral.py` با همین چرخه سه‌مرحله‌ای به‌روزرسانی شد.
- `tests/integration/test_job_lifecycle.py` بازنویسی و گسترش یافت — ۱۱ تست روی PostgreSQL
  واقعی: موقعیت تازه همیشه `draft` است و درخواست نمی‌پذیرد؛ بستن فقط ثبت جدید را متوقف می‌کند
  بدون اثر روی سابقه؛ بازگشایی فقط `hr_manager` و حسابرسی‌شده (الزام مجوز/حسابرسی)؛ **۴ انتقال
  نامجاز** صریحاً رد می‌شوند (`draft→closed`، `open→draft`، `closed→draft`، `open→open`)؛ نقش
  غیرمجاز از ایجاد/ویرایش/تغییر وضعیت رد می‌شود؛ هیچ مسیر DELETE وجود ندارد؛ ایجاد/فعال‌سازی/
  بستن/بازگشایی از طریق API حسابرسی می‌شوند؛ انتقال نامجاز از طریق API ۴۰۰ می‌گیرد؛ `draft`/
  `closed` هرگز در `GET /jobs` عمومی ظاهر نمی‌شوند؛ **رقابت واقعی هم‌زمان** بستن/ثبت درخواست با
  دو ریسه (بدون تغییر منطقی، همچنان سبز).
- جمع کل تست‌های پروژه تا این نقطه: **۱۳۷ تست**، همه در یک اجرای واحد روی PostgreSQL، ClamAV و
  Chromium واقعی سبز.
- **تکمیل US6 به معنای آمادگی انتشار نیست** — T062 (جداسازی کامل کوکی) و بقیهٔ شرط‌های فاز ۹
  همچنان باز و بررسی‌نشده‌اند.

### دور بعدی — اصلاح وضعیت Phase 9، مهاجرت JobPosition، تطبیق کامل OpenAPI، enforce_retention، و `/speckit-analyze`

**۱. اصلاح وضعیت Phase 9**: علامت `[~]` قبلی T068 به `[ ]` تصحیح شد (کامل نبود)؛ اکنون پس از
تطبیق واقعی کامل (بخش ۳ پایین) به `[X]` تغییر کرد. T064/T065/T067(واقعی)/T067b/T069 همچنان
`[ ]` و صریحاً «مسدود» باقی ماندند — هیچ‌کدام کامل علامت زده نشدند.

**۲. مسیر مهاجرت JobPosition — رفع کامل، نه فقط آزموده**:
- **نگاشت `(False, closed)→draft` مصوب اعلام نشد** و از `APPROVED_MAPPING` حذف شد؛ اکنون تنها
  نگاشت مصوب `(True, open)→open` و `(True, closed)→closed` است. هر ترکیب دیگر — `is_published=False`
  با هر وضعیتی، هر `archived`، و هر مقدار ناشناخته — باعث توقف امن می‌شود.
  `apps/jobs/migrations/0002_preflight_job_status_mapping.py` بازنویسی شد.
- **بررسی محیط‌های توزیع واقعی**: مخزن `reqruitment/` هیچ تاریخچهٔ git ندارد (پوشه کاملاً
  untracked؛ تنها کامیت مخزن والد این پوشه را در بر نمی‌گیرد) و هیچ CI/انتشاری ندارد — مهاجرت
  قدیمی (`0002_job_status_graph`) **در هیچ محیط تولیدی/اشتراکی اجرا نشده**؛ فقط در یک کانتینر
  PostgreSQL توسعهٔ محلی. تغییر نام migration اجراشده (آنچه برای آن کانتینر خاص انجام شد) **به‌
  عنوان راهکار عمومی معرفی نشد** — مستند شد که این یک اقدام محلی و غیرقابل‌تکرار برای دیتابیس‌های
  واقعی است؛ مسیر «دیتابیس مهاجرت‌نکرده» و «دیتابیس قبلاً ارتقایافته» در `docs/operations/migrations.md`
  جدا توضیح داده شدند، با تأکید صریح که اطلاعات `is_published` حذف‌شده هرگز از روی `status` فعلی
  حدس زده نمی‌شود (فقط بازیابی از پشتیبان پیش از مهاجرت صحیح است).
- **تغییر دستی `django_migrations` در دیتابیس آزمایشی ثبت شد** (نه پنهان) در
  `docs/operations/migrations.md`؛ و به‌صراحت گفته شد این دیتابیس **شاهد ارتقا نیست**.
- **آزمون واقعی با یک دیتابیس کاملاً مستقل و دورریختنی** (نه دیتابیس تست مشترک): تلاش اول اشتباه
  بود — monkeypatch کردن `settings.DATABASES` روی اتصال از‌پیش‌مقداردهی‌شدهٔ Django اثری نداشت
  (چون `connections.settings` یک `cached_property` است) و تست‌ها به‌اشتباه مستقیماً روی دیتابیس
  *مشترک* `test_recruitment` اجرا و اسکیمای آن را برای ۵ تست دیگر در همان session خراب کردند —
  این باگ کشف و با ثبت alias تازه مستقیماً در `connections.settings` + `django_db_blocker.unblock()`
  رفع شد (`tests/integration/test_jobs_migration_path.py`).
- **`reverse_code=noop` با سیاست برگشت صادقانه جایگزین شد**: `0002_preflight...` واقعاً noop
  صادقانه است (چون هیچ داده‌ای تغییر نمی‌دهد)؛ `0003_job_status_graph` صریحاً **برگشت‌ناپذیر
  داده‌محور** اعلام شد (نه ادعای برگشت کاری که واقعی نیست) با رویهٔ بازیابی مستند (بازگشت از
  پشتیبان پیش از مهاجرت، نه `migrate jobs 0001`).
- **۹ آزمون واقعی با `MigrationExecutor` روی PostgreSQL واقعی** (`tests/integration/test_jobs_migration_path.py`،
  هرکدام با alias اتصال و دیتابیس کاملاً مستقل): هر ۶ ترکیب قدیمی + یک مقدار ناشناخته جدا آزموده
  شدند؛ وجود هم‌زمان ردیف مجاز و مسدودکننده → توقف کامل بدون تغییر هیچ رکورد (هر دو دست‌نخورده)؛
  مهاجرت موفق → شناسهٔ موقعیت، درخواست مرتبط (`job_position_id`) و تعداد رکوردها همگی دقیقاً
  حفظ شدند؛ اسکیمای نهایی بدون `is_published` و با ایندکس تازه تأیید شد؛ **رفتار rollback واقعاً
  اجرا و تأیید شد**: `migrate jobs 0001_initial` ستون را با `is_published=False` برای همهٔ
  ردیف‌ها (نه مقدار اصلی) برمی‌گرداند، و تلاش دوبارهٔ forward migrate روی همان داده‌ی اکنون
  «غیرمنتشر‌شده» دوباره و به‌درستی متوقف می‌شود (دقیقاً سیاست اعلام‌شده، نه ادعای بدون شاهد).
- **قفل هم‌زمان**: `LOCK TABLE jobs_jobposition IN ACCESS EXCLUSIVE MODE` درون `0002_preflight...`
  اضافه شد تا نوشتن هم‌زمان را در طول هر دو مهاجرت مسدود کند؛ `atomic بودن به‌تنهایی کافی نیست`
  به‌صراحت در داکیومنت و کامنت کد ثبت شد؛ راهنمای عملیاتی «توقف سرویس‌های نویسنده پیش از مهاجرت»
  در `docs/operations/migrations.md` به‌عنوان خط اول دفاع اضافه شد.
- **alias اتصال**: کد migration اکنون از `schema_editor.connection.alias` برای تمام کوئری‌های
  ORM استفاده می‌کند (نه فرض ضمنی روی `default`). راهنمای رفع داده نامعتبر ترکیب معتبر اسکیمای
  قدیمی (`is_published=True` + `status='open'`/`'closed'`) را مشخص می‌کند و صریحاً می‌گوید
  نوشتن مستقیم `'draft'` در اسکیمای قدیمی نادرست است.

**۳. تطبیق کامل ۲۳ مسیر OpenAPI (T068)** — مغایرت‌های واقعی یافت و رفع شد:
- امنیت هر ۲۳ مسیر صریح شد (`security` دیگر به پیش‌فرض مبهم بالای فایل متکی نیست)؛ یک تست قفل
  می‌کند که هیچ مسیر `staff/*` به `candidateSession` و بالعکس متکی نباشد.
- **باگ واقعی کد یافت و رفع شد**: `POST /candidate/uploads` با فایل بیش از حد مجاز همیشه ۴۱۵
  (نوع نامعتبر) برمی‌گرداند، نه ۴۱۳ (حجم) — چون `InvalidResumeFile` یک کلاس استثنای واحد برای
  هر دو حالت بود. زیرکلاس `ResumeTooLarge` اضافه شد (تست‌های قبلی را نمی‌شکند چون زیرکلاس همان
  پایه است)؛ لایه API اکنون ۴۱۳ و ۴۱۵ را واقعاً متمایز برمی‌گرداند. آزمون رگرسیون HTTP واقعی در
  `tests/integration/test_us1_smoke.py` اضافه شد.
- `GET /candidate/applications` واقعاً صفحه‌بندی نمی‌کند (پارامترهای `page`/`page_size` نادیده
  گرفته می‌شوند) — سند اصلاح شد تا با رفتار واقعی بخواند، نه رفتار ادعاشده.
- `GET /candidate/applications/{id}` و `GET /candidate/uploads/{id}` همیشه ۴۰۴ می‌دهند (هرگز
  ۴۰۳) — طراحی عمدی برای عدم افشای وجود رکورد؛ `403` اشتباهاً سندشده حذف شد.
- `POST /auth/candidate/otp/request`: ۴۲۹ سندشده هرگز واقعاً برنمی‌گردد (طراحی عمدی FR-016 برای
  پاسخ یکسان)؛ توضیح اصلاح شد تا این را صریح بگوید، نه حذف سکوت‌آمیز الزام FR-044.
- **شکاف امنیتی واقعی یافت‌شده (نه رفع‌شده، چون نیازمند قابلیت جدید است)**: FR-047 محدودسازی
  نرخ ورود کارمند بر اساس حساب+IP را الزامی می‌داند و قرارداد ۴۲۹ را سندش کرده بود، اما **هیچ
  پیاده‌سازی واقعی برای این محدودسازی وجود ندارد** — بررسی شد و با یک یادداشت صریح «شکاف
  شناخته‌شده» در قرارداد ثبت شد، نه حذف ساکت یا افزودن قابلیت تازه بدون اجازه.
- `POST /staff/applications/{id}/notes`، `PATCH .../status`، `PATCH .../assignments`: کد ۴۰۴
  مفقود (دسترسی رکوردی خارج از دامنه) به هر سه اضافه شد؛ `assignments` علاوه‌بر این ۴۰۹ را
  درست‌تر توصیف کرد (صلاحیت نقش دریافت‌کننده هم جزو همان ۴۰۹ `conflict` است، نه ۴۰۳ جدا — طبق
  کد واقعی `apps/applications/api/views.py`).
- `GET /staff/jobs` (نه فقط POST) در کد واقعاً `IsHrManager` است، نه برای همهٔ کارکنان — سند
  اصلاح شد تا ۴۰۱/۴۰۳ را هم نشان دهد.
- `PATCH /staff/jobs/{id}` و `PATCH /staff/jobs/{id}/status`: کد ۴۰۰ (فیلد خالی) و ۴۰۴ (شناسهٔ
  ناموجود) مفقود اضافه شد؛ schema پاسخ موفق (`JobPositionStaff`) که قبلاً مستند نشده بود اضافه شد.
- **۲ مغایرت schema واقعی در `ApplicationStaffDetail`**: کلید `previous_applications[].application_id`
  در کد واقعاً `id` است؛ کلید `status_history[].changed_at` در کد واقعاً `created_at` است —
  هر دو اصلاح شدند و با تست serializer واقعی (نه فرض) تأیید شدند.
- **مغایرت بزرگ یافت‌شده**: schema `ApplicationStaffDetail` فاقد ۹ فیلد واقعی بود (`email`,
  `job_position`, `employment`, `experience`, `availability`, `last_title`, `last_company`,
  `created_at`, `updated_at`) — همگی اضافه شدند.
- **مغایرت بزرگ دیگر**: `PaginatedStaffApplications.results` قبلاً به `ApplicationStaffDetail`
  کامل اشاره می‌کرد، درحالی‌که `GET /staff/applications` واقعاً از `ApplicationStaffListSerializer`
  سبک‌تر استفاده می‌کند (بدون notes/reviewer/status_history/previous_applications/version).
  schema تازهٔ `ApplicationStaffListItem` اضافه و رفرنس اصلاح شد؛ تست واقعی HTTP تأیید کرد این
  فیلدها در پاسخ واقعی فهرست غایب‌اند.
- یک پاراگراف CSRF در سطح بالای `info.description` اضافه شد (قاعده یکسان برای همه مسیرهای
  غیرایمن نشست‌محور، به‌جای تکرار در هر مسیر).
- `tests/contract/test_openapi_code_agreement.py` (۶ تست، وابستگی تازهٔ توسعه `pyyaml` به
  `requirements/dev.txt` اضافه شد) این یافته‌های مهم را رگرسیون‌بندی می‌کند: امنیت صریح هر
  مسیر، تطبیق دامنهٔ نشست staff/candidate، فیلدهای `UploadStatus`، کلیدهای واقعی
  `previous_applications`/`status_history`، غیاب فیلدهای جزئیات در فهرست، و schema عمومی `/jobs`.
  اعتبارسنجی کامل تمام ۲۳ مسیر **انجام شد**، اما این مجموعه تست فقط مهم‌ترین‌ها را قفل می‌کند،
  نه هر جزئیات مستند.

**۴. تأیید `enforce_retention` (بدون تغییر رفتار، فقط بررسی)** — ⚠️ **منسوخ‌شده (superseded)،
این بخش با «دور سوم — بخش ۳» و «دور چهارم» متناقض است؛ نگه داشته شده فقط برای سابقه**:
- **زمان‌بندی**: جست‌وجوی کامل (cron، Celery beat، systemd timer، docker-compose) هیچ اجرای
  خودکاری برای این فرمان پیدا نکرد؛ تنها فراخوانی‌ها از فایل تست پروژه‌اند. **تأیید شد: حذف فعال
  یا زمان‌بندی‌شده نیست.**
- **سیاست مصوب**: برخلاف ادعای ضمنی قبلی، فرمان **هیچ gate ای برای «سیاست مصوب»** ندارد —
  `RETENTION_MONTHS=12` مستقیماً در کد ثابت است (حتی از `settings.DATA_RETENTION_MONTHS` موجود
  هم نمی‌خواند) و اجرای مستقیم بدون `--dry-run` بلافاصله حذف واقعی انجام می‌دهد. **این یافته
  گزارش شد، نه اصلاح** (اصلاح یعنی افزودن یک gate تازه = قابلیت جدید که این دور ممنوع است؛
  تصمیم «سیاست نگهداری نهایی چه زمانی مصوب است» هم تصمیم کاربر/محصول است، نه من). ایمنی فعلی
  صرفاً به این بستگی دارد که کسی آن را زمان‌بندی نکند.

**۵. `/speckit-analyze`** — یافته‌های تضاد باقی‌مانده (بدون تصمیم‌گیری یک‌طرفه):
- **CRITICAL**: تضاد قانون اساسی اصل VIII / `data-model.md` («نقش دیتابیس برنامه فقط حق INSERT
  روی `AuditEvent` دارد») با `enforce_retention` که با همان اتصال/نقش `AuditEvent` را DELETE
  می‌کند. اگر نقش دیتابیس تولید واقعاً فقط‌افزودنی پیکربندی شود، این فرمان با خطای مجوز شکست
  می‌خورد. تصمیم‌گیری لازم (نقش جدا برای retention، یا کنار گذاشتن AuditEvent از این فرمان) به
  کاربر/محصول موکول شد، نه تصمیم‌گیری یک‌طرفه در این اجرا.
- **HIGH**: شکاف امنیتی FR-047 (بالا، بخش ۳) — ثبت‌شده، نه رفع‌شده.
- **MEDIUM**: `docs/decisions.md` طبق اصل XI و T069 هنوز وجود ندارد؛ تصمیم‌های این دور (FR-037a،
  FR-039a، نگاشت مهاجرت، و غیره) پراکنده در spec.md/tasks.md/docs/operations هستند، نه یک‌جا.
- جزئیات کامل در پاسخ این دور از گفتگو ثبت شده؛ اینجا فقط خلاصه برای ردیابی آینده آمد.

**۶. اجرای کامل مجموعه تست**: **۱۸۰ تست**، همه در یک اجرای واحد روی PostgreSQL واقعی
(`reqruitment-pg-test`)، ClamAV واقعی، و Chromium واقعی سبز — سه بار پیاپی اجرا شد (بدون
flakiness)؛ **صفر skipped**. محیط: `config.settings.dev`، بدون هیچ استقرار واقعی تولید و بدون
هیچ داده واقعی متقاضی (تمام دادهٔ آزمون مصنوعی/synthetic است، شامل دیتابیس‌های دورریختنی مهاجرت).

**شروط انتشار تأییدشده در این دور**: هیچ‌کدام تازه به «تأییدشده» افزوده نشد؛ T062/T062a/T063/
T066/T067a/T068 از دور قبل یا همین دور `[X]` ماندند (با تصحیحات بالا).
**موارد باز**: T064، T065، T067 (بخش واقعی/حجم واقعی)، T067b، T069، شکاف نرخ‌محدودسازی ورود
کارمند (FR-047)، تضاد نقش دیتابیس حسابرسی/retention (بالا)، و نبود `docs/decisions.md` یکپارچه.
**موانع زیرساختی**: محیط پیش‌تولید واقعی (T064/T065)، مقصد پشتیبان مستقل خارج از میزبان
(T067b)، و تصمیم‌های کسب‌وکار ذی‌نفعان (T069) — هیچ‌کدام در این محیط محلی قابل‌تهیه نیستند.

---

## دور سوم — سخت‌سازی و راستی‌آزمایی (محدود، بدون قابلیت جدید)

### شواهد این دور

**۱. نقش PostgreSQL (O2)** — طراحی هدف در `docs/operations/db-roles.sql`; روی یک دیتابیس
**دوریختنی جداگانه** (`reqruitment_role_drill`) با نقش `reqruitment_runtime` پیاده و آزموده شد
(سپس دیتابیس و نقش‌ها پاک شدند):
- نقش: `rolsuper=f`, `rolcreaterole=f`, `rolinherit=f`, بدون هیچ عضویت گروهی.
- `INSERT` روی `audit_auditevent` → موفق.
- `UPDATE` / `DELETE` / `TRUNCATE` روی `audit_auditevent` → **`permission denied for table`**.
- این آزمون روی نقش **غیر superuser** اجرا شد؛ «کشف superuser بودن» تست کنترل نیست و چنین
  ادعایی نشده است.
- **اعمال در محیط واقعی انجام نشده** (نیازمند تصمیم مالک — O2 در `docs/decisions.md`).

**۲. اعتماد به IP / FR-047 — باگ بحرانی یافت و رفع شد.** `_client_ip()` قبلاً `X-Forwarded-For`
را بی‌قید می‌خواند؛ هر کلاینت با ارسال مقدار تصادفی کلید rate limit را عوض می‌کرد و از سقف IP
فرار می‌کرد. اکنون `TRUSTED_PROXY_COUNT` (پیش‌فرض `0`) — هدر کاملاً نادیده گرفته می‌شود مگر
پراکسی معتبر صریح پیکربندی شود؛ در آن حالت هم فقط هاپ انتهای زنجیره (که پراکسی اضافه کرده) باور
می‌شود، نه مقادیر سمت چپ ساختِ کلاینت. آزمون‌ها: spoofing، هاپ اعتمادشده، زنجیره کوتاه،
هم‌زمانی، پایان پنجره، هر دو مسیر login/MFA
(`tests/integration/test_staff_login_rate_limit.py` — ۱۱ تست).
**آستانه‌ها همچنان پیشنهادی‌اند** (O5).

**۳. گیت retention — کلید عملیاتی مستقل.** افزوده شد `RETENTION_OPERATIONAL_ENABLED`
(پیش‌فرض `False`)، جدا از `RETENTION_POLICY_APPROVED`. حذف فقط با **همهٔ** شروط ممکن است: هر دو
کلید `True`، `DATA_RETENTION_MONTHS` عدد صحیح مثبت (bool رد می‌شود)، و `--actor-id` متعلق به
کارمند **فعال** با نقش `hr_manager`. `--actor-id` صرفاً **انتساب** برای حسابرسی است، نه اثبات
هویت؛ مرز اعتماد در docstring فرمان مستند شد. حذف `AuditEvent` مسدود و `--dry-run` غیرمخرب
باقی مانده‌اند. `tests/integration/test_retention_policy.py` — ۱۹ تست.

**۴. reverse مهاجرت** — آزمون اکنون عکس فوری کامل (ستون‌ها + ایندکس‌ها + همه ردیف‌ها + تاریخچهٔ
مهاجرت) را پیش و پس از تلاش برگشت می‌گیرد و برابری کامل را اثبات می‌کند، نه فقط `assert raises`.

### وضعیت تسک‌ها در این دور

- **T067a** — `[X]` کدنویسی و گیت fail-closed. **تصویب سیاست (O1) همچنان باز** — حذف عملیاتی
  در هیچ محیطی روشن نیست.
- **T063a (FR-047)** — `[X]` کدنویسی و آزمون. **آستانه‌ها (O5) همچنان پیشنهادی.**
- **T068** — `[X]` ماتریس ۲۵ عملیات/۲۳ مسیر در `docs/openapi-path-matrix.md`.
  روشن‌سازی: ۲۳ **مسیر** (path) و ۲۵ **عملیات** (method+path) دو عدد متناقض نیستند؛ دو مسیر دو
  متد دارند (`/candidate/applications`, `/staff/jobs`).
- **T069** — `[ ]` باز. `docs/decisions.md` به‌روزرسانی شد، اما تأیید ذی‌نفعان انجام نشده.
- **T064/T065/T067(واقعی)/T067b** — `[ ]` مسدود (بدون تغییر).

### اجرای اعتبارسنجی این دور (exit code واقعی)
- `pytest -q -rs` → **213 passed**, 0 failed, 0 skipped, exit 0
- `manage.py makemigrations --check --dry-run` → `No changes detected`, exit 0
- `ruff check --select F` → `All checks passed!`, exit 0

---

## دور چهارم — ثبت تصمیم‌های مالک و آماده‌سازی پیکربندی

### تصمیم‌های ثبت‌شده (`docs/decisions.md`)
- **D5** — سیاست نگهداری **مصوب**: ۱۲ ماه؛ **سوابق حسابرسی هرگز حذف نمی‌شوند**.
- **D6** — آستانه‌های FR-047 **مصوب**: ۵/۱۵ دقیقه برای هر حساب، **۱۵/۲۰ دقیقه** برای هر IP.
- **D7** — نقش دیتابیس: **دقیق‌تر محدود شود** (دستهٔ سابقه در برابر داده زنده).

### تغییرات واقعی این دور
- `config/settings/base.py`: `RETENTION_POLICY_APPROVED = True`، `RETENTION_AUDIT_RECORDS_EXCLUDED = True`؛
  آستانه‌های FR-047 به مقادیر مصوب + پنجره‌های مستقل (`STAFF_LOGIN_*_WINDOW_SECONDS`)؛
  تنظیمات `SMS_API_URL` / `SMS_API_KEY` / `SMS_SENDER`.
- `apps/accounts/services.py`: پنجرهٔ زمانی per-scope (حساب ۱۵ دقیقه، IP ۲۰ دقیقه) — قبلاً یک پنجرهٔ
  مشترک بود و تفکیک D6 را ممکن نمی‌کرد.
- `apps/notifications/backends/http_sms.py`: **قالب** پیاده‌سازی پیامک HTTP؛ بدون تنظیمات کامل،
  `SmsConfigurationError` با نام فیلد مفقود می‌دهد (هرگز ساکت نمی‌ماند).
- `scripts/backup.sh` و `scripts/backup_rotate.sh`: **قالب‌های** پشتیبان‌گیری و چرخش ۱۲ماهه با
  گاردهای ایمنی (بدون `BACKUP_DIR` یا با مقصد داخل میزبان برنامه، با خطا متوقف می‌شوند).
- `docs/operations/db-roles.sql`: محدودسازی دقیق‌تر — سه دستهٔ مجوز (سابقه / داده زنده / PUBLIC).

### شواهد اجرا (exit code واقعی)
- `pytest -q` → **221 passed**, 0 failed, 0 skipped, exit 0
- `manage.py check --deploy` با `config.settings.prod` و مقادیر کامل → **بدون هیچ هشدار**, exit 0
- `makemigrations --check --dry-run` → `No changes detected`, exit 0
- `ruff check --select F` → `All checks passed!`, exit 0
- اسکریپت‌های backup/rotate: `bash -n` سالم؛ بدون تنظیمات با خطای روشن متوقف می‌شوند.

### وضعیت تسک‌ها
- **T063a (FR-047)** — `[X]` کد + آزمون + **آستانه‌های مصوب (D6)** اعمال و آزموده شد.
- **T067a (retention)** — `[X]` کد + گیت fail-closed + **سیاست مصوب (D5)**. حذف عملیاتی هنوز
  در هیچ محیطی روشن نیست (`RETENTION_OPERATIONAL_ENABLED=False`) — عمدی.
- **T067b (چرخش پشتیبان)** — `[ ]` **همچنان باز**: قالب اسکریپت آماده است اما هیچ مقصد پشتیبان
  واقعی خارج از میزبان و هیچ اجرای زمان‌بندی‌شده‌ای آزموده نشده (O6 باز).
- **T064 (اتصال واقعی پیامک)** — `[ ]` **همچنان باز**: قالب `HttpSmsGateway` آماده است اما هیچ
  فراخوانی واقعی به فروشنده انجام نشده (O3 باز).
- **T065 / T067 (حجم واقعی) / T069** — `[ ]` بدون تغییر، مسدود.
- **O7 (اعمال نقش‌ها)** — باز: طراحی دقیق‌تر نوشته شد اما روی دیتابیس آزموده نشد.

---

## دور پنجم — حذف OTP متقاضی (اصل V نسخهٔ ۲.۰.۰) و افزودن US7 (مدیریت کاربران از پنل ادمین)

**چرا این دور**: مالک پروژه صریحاً خواسته OTP متقاضی کامل حذف شود (علی‌رغم هشدار امنیتی صریح
دربارهٔ از بین رفتن تأیید مالکیت موبایل) و «ادمین» (= نقش موجود `hr_manager`) بتواند از پنل،
کاربر با سطح دسترسی مختلف بسازد. قانون اساسی به نسخهٔ ۲.۰.۰ اصلاح شد؛ `spec.md`/`plan.md`/
`data-model.md` بر همان اساس بازنویسی شدند. این بخش، کارهای کد/تست را به تسک‌های اجرایی تبدیل
می‌کند. تسک‌های قدیمی T015، T022، T023، T037–T040 و بخشی از T062 در بالا با نشان ⚠️ به همین
بخش ارجاع داده شده‌اند؛ آن‌ها دیگر منبع حقیقت نیستند.

**وابستگی**: همهٔ تسک‌های این دور به فیکسچرهای `T005a`/`T005b` وابسته‌اند، مثل بقیهٔ سند.

### حذف زیرساخت OTP (مسدودکننده — پیش از هر تسک دیگر این دور)

- [X] T070 [P] مدل‌های `OTPChallenge` و `OtpRateCounter` را از `apps/candidates/models.py` کامل
      حذف کنید و مدل `TrackingLookupRateCounter` را جایگزین کنید: `ip_address` (`CharField`)،
      `window_start` (`DateTimeField`)، `count` (`PositiveIntegerField`) با قید یکتایی
      `(ip_address, window_start)` — دقیقاً همان الگوی `OtpRateCounter`/`ExportRateCounter`؛
      مهاجرت تازه بسازید که هم جداول قدیمی را drop کند هم جدول تازه را بسازد؛ فیلد
      `Candidate.verified_at` را هم در همین مهاجرت حذف کنید (FR-042 تا FR-044، data-model.md).
- [X] T071 [P] اپ `apps/notifications` را کامل حذف کنید (`gateway.py`، `backends/`، migrations
      مرتبط در صورت وجود)؛ از `INSTALLED_APPS` در `config/settings/base.py` خارجش کنید؛ تنظیمات
      `SMS_GATEWAY_BACKEND`/`SMS_API_URL`/`SMS_API_KEY`/`SMS_TEMPLATE_ID`/`SMS_TEMPLATE_PARAM`
      را از `config/settings/base.py` و `.env.example` حذف کنید (دیگر هیچ OTP پیامکی وجود ندارد
      — اصل V نسخهٔ ۲.۰.۰؛ جایگزین برای هشدار امنیتی قبلی‌تر T064 که با حذف OTP کاملاً منتفی شد).
- [X] T072 [پس از T070/T071] مسیرهای `POST /auth/candidate/otp/request`،
      `POST /auth/candidate/otp/verify` و `POST /auth/candidate/logout` را از
      `apps/candidates/api/urls.py`/`views.py` حذف کنید؛ توابع `request_otp`/`verify_otp` و هر
      کلاس `CandidateSessionAuthentication`/میان‌افزار نشست متقاضی را از `apps/candidates/services.py`
      و تنظیمات حذف کنید؛ `tests/unit/test_candidate_otp.py` و
      `tests/unit/test_otp_regression_bugs.py` را حذف کنید (رگرسیون‌های آن‌ها دیگر قابل‌رخداد
      نیستند چون کد مربوطه وجود ندارد).

### بازنویسی US1 — ثبت درخواست بدون OTP

- [X] T073 [US1] `POST /api/v1/candidate/applications` را در `apps/applications/api/views.py`/
      `apps/applications/services.py::submit_application` به‌گونه‌ای اصلاح کنید که به هیچ نشست یا
      هویت احرازشدهٔ متقاضی وابسته نباشد؛ `mobile` مستقیماً از بدنهٔ فرم خوانده و نرمال‌سازی
      می‌شود (قالب `09xxxxxxxxx` پس از نرمال‌سازی ارقام فارسی/عربی و `+98`/`0098` — FR-004)؛
      `Candidate` بر همان مقدار خام (بدون تأیید) `get_or_create` می‌شود؛ منطق idempotency
      (`Idempotency-Key`)، قید یکتایی درخواست فعال (FR-008) و تراکنش ثبت (FR-007 تا FR-009)
      بدون تغییر باقی می‌مانند.
- [X] T074 [US1] `templates/candidate/apply.html` و `static/js/candidate_apply.js` را به یک
      فرم تک‌مرحله‌ای تبدیل کنید: مرحلهٔ «تأیید موبایل با OTP» کامل حذف شود؛ `stepbar` به دو گام
      («انتخاب موقعیت/تکمیل فرم» → «ثبت و دریافت کد پیگیری») کاهش یابد؛ فیلد `mobile` همان فیلد
      فرم FR-004 است، بدون هیچ دکمهٔ «ارسال کد تأیید».
- [X] T075 [P] [US1] `tests/unit/test_application_form.py` و
      `tests/integration/test_attachment_upload.py` را بازبینی کنید تا هیچ‌کدام به نشست/هویت
      احرازشدهٔ متقاضی وابسته نباشند (محدودیت بارگذاری فایل همچنان فقط بر اساس
      `upload_attempt_key` است طبق FR-051، نه هویت متقاضی).
- [X] T076 [US1] `tests/browser/test_us1_submission.py` را بازنویسی کنید: مسیر کامل بدون هیچ
      مرحلهٔ OTP؛ SC-001 (زیر ۵ دقیقه) و SC-007 (زیر ۳ ثانیه پس از فایل سالم) را با این مسیر
      کوتاه‌تر دوباره اندازه بگیرید.

### بازنویسی US2 — پیگیری وضعیت فقط با کد پیگیری

- [X] T077 [US2] `GET /api/v1/track/{tracking_code}` را به‌عنوان مسیر عمومی تازه در
      `apps/applications/api/views.py`/`urls.py` اضافه کنید (جایگزین کامل
      `GET /candidate/applications`/`{id}` که حذف می‌شوند): بدون نیاز به هیچ احراز هویتی؛ پاسخ
      محدود به `tracking_code`/`job_position`/`status`/`updated_at` (FR-012، FR-015)؛ برای کد
      نامعتبر یا ناموجود پاسخ کاملاً یکسان از نظر ظاهر/زمان‌بندی (FR-016، FR-044).
- [X] T078 [US2] `TrackingLookupRateCounter` (T070) را در `apps/candidates/services.py` با تابع
      `enforce_tracking_rate_limit(ip)` به‌کار بگیرید — همان الگوی اتمی `select_for_update()`
      که در `enforce_export_rate_limit`/`StaffLoginRateCounter` استفاده شده؛ پیش از هر جست‌وجوی
      دیتابیس در `GET /track/{tracking_code}` اعمال شود؛ عبور از سقف پاسخ `429` + هدر
      `Retry-After` بدهد (FR-043؛ آستانهٔ پیشنهادی `TRACKING_LOOKUP_IP_LIMIT=20` در ۱۰ دقیقه،
      نیازمند تصویب مالک پروژه مثل FR-047).
- [X] T079 [US2] `templates/candidate/track.html` و `static/js/candidate_track.js` را به یک
      فرم تک‌فیلدی («کد پیگیری») بدون فیلد موبایل یا مرحلهٔ OTP بازنویسی کنید.
- [X] T080 [P] [US2] `tests/contract/test_candidate_privacy.py` را به
      `tests/contract/test_tracking_privacy.py` تغییر نام/بازنویسی دهید: کد معتبر فقط فیلدهای
      مجاز را برمی‌گرداند (بدون یادداشت/ارجاع/دلیل داخلی/هویت کارمند — FR-015)؛ کد نامعتبر و کد
      ناموجود پاسخ ۴۰۴ با بدنه و زمان‌بندی یکسان می‌گیرند (FR-016).
- [X] T081 [US2] `tests/integration/test_tracking_rate_limit.py` بنویسید (روی PostgreSQL واقعی،
      همان الگوی `test_export_rate_limit.py`/`test_staff_login_rate_limit.py`): مرز دقیق سقف،
      پایان پنجره، استقلال کامل بین دو IP متفاوت، رقابت هم‌زمان با چند ریسه که دقیقاً به‌اندازهٔ
      سقف موفق می‌شوند نه بیشتر.
- [X] T082 [US2] `tests/browser/test_us2_tracking.py` را بازنویسی کنید: یک کد پیگیری از یک
      مرورگر دیده می‌شود؛ همان کد از یک `browser context` کاملاً مستقل (بدون هیچ کوکی مشترک) هم
      دیده می‌شود، چون دیگر اصلاً مفهوم نشست وجود ندارد؛ کد نادرست خطای قابل‌فهم می‌دهد.

### داستان کاربری ۷ — مدیریت کاربران و نقش‌ها از پنل ادمین (Priority: P2)

**Goal**: مدیر HR («ادمین») بدون خط فرمان، حساب کارمند با نقش دلخواه بسازد، نقش/وضعیت فعال‌بودن
کارمند موجود را تغییر دهد (FR-021a تا FR-021d).

**Independent Test**: مستقل از US1–US6: ورود مدیر HR → ساخت حساب «کارشناس جذب» تازه → ورود همان
حساب → غیرفعال‌کردنش از پنل → رد فوری دسترسی او در درخواست بعدی.

- [X] T083 [P] [US7] توابع سرویس در `apps/accounts/services.py` بسازید: `create_staff_account()`،
      `change_staff_role()`، `set_staff_active()` — هرکدام فقط `hr_manager`، درون
      `@transaction.atomic`، هرکدام رویداد حسابرسی مستقل ثبت می‌کند
      (`staff_account_created`/`staff_role_changed`/`staff_activated`|`staff_deactivated` —
      FR-021b). `set_staff_active(False)` باید غیرفعال‌سازی آخرین `hr_manager` فعال یا حساب
      خودِ اجراکننده را رد کند (FR-021c).
- [X] T084 [US7] `GET/POST /api/v1/staff/users` و `PATCH /api/v1/staff/users/{id}` را در
      `apps/accounts/api/views.py` + `apps/accounts/api/urls.py` پیاده کنید: فقط
      `permission_classes=[IsHrManager]`؛ `POST` حساب + `TOTPDevice(confirmed=False)` می‌سازد و
      `config_url` آن را در پاسخ برمی‌گرداند (FR-021d)؛ `PATCH` نقش و/یا `is_active` را تغییر
      می‌دهد؛ نام کاربری تکراری باید خطای ۴۰۰ قابل‌فهم بدهد، نه کرش.
- [X] T085 [US7] `templates/staff/users.html` + `static/js/staff_users.js` بسازید: فهرست
      کارمندان با نشان نقش/فعال‌بودن، فرم «ساخت حساب»، کنترل تغییر نقش و فعال/غیرفعال‌سازی برای
      هر ردیف؛ لینک از داشبورد فقط وقتی کاربر جاری `hr_manager` است نمایش داده شود (نه صرفاً با
      مخفی‌کردن لینک — سرور هم باید مجوز را دوباره بررسی کند، اصل III).
- [X] T086 [P] [US7] `tests/integration/test_staff_user_management.py` روی PostgreSQL واقعی:
      هر نقش غیر از `hr_manager` حتی با فراخوانی مستقیم API باید ۴۰۳ بگیرد؛ ساخت موفق
      `staff_account_created` را حسابرسی می‌کند و `config_url` معتبر TOTP تأییدنشده برمی‌گرداند؛
      تغییر نقش `staff_role_changed` حسابرسی می‌شود؛ غیرفعال‌سازی `staff_deactivated` را ثبت و
      درخواست بعدی همان حساب را بلافاصله رد می‌کند؛ غیرفعال‌کردن آخرین `hr_manager` فعال یا حساب
      خودِ اجراکننده بدون هیچ تغییر حالتی رد می‌شود.
- [X] T087 [US7] `tests/browser/test_us7_user_management.py` با Playwright واقعی: ورود `hr_manager`
      → باز کردن صفحهٔ مدیریت کاربران → ساخت حساب `recruiter` تازه → اولین ورود همان حساب با کد
      TOTP واقعی محاسبه‌شده از `config_url` برگشتی → غیرفعال‌سازی توسط `hr_manager` → رد فوری
      درخواست بعدی همان حساب بدون نیاز به خروج/ورود دوباره.

**Checkpoint**: US7 مستقل از US1–US6 کار می‌کند.

### اصلاح فاز ۹ (Polish) پس از حذف نشست متقاضی

- [X] T088 `tests/integration/test_security_hardening.py` (T062) را ویرایش کنید: سناریوهای
      «حضور هم‌زمان کوکی متقاضی/کارمند» و «رد نشست متقاضی روی مسیر کارمند» را حذف کنید (دیگر
      متقاضی هیچ کوکی/نشستی ندارد که تداخل یا نشتی داشته باشد)؛ سناریوهای نشست/CSRF/
      session-fixation کارمند را نگه دارید.

### وضعیت تسک‌های این دور — اجرای واقعی تکمیل شد (نه فقط تعریف)

برخلاف یادداشت قبلی این بخش، تسک‌های T070 تا T088 در دور بعدی همین گفتگو واقعاً **نوشته و
اجرا** شدند، نه فقط تعریف. شواهد واقعی:

- **حذف زیرساخت OTP (T070–T072)**: `OTPChallenge`/`OtpRateCounter` حذف و `TrackingLookupRateCounter`
  جایگزین شد؛ مهاجرت‌های `candidates.0002_*` و `attachments.0003_alter_attachment_candidate`
  روی PostgreSQL واقعی اجرا شدند (`makemigrations --check` بدون تغییر باقی‌مانده). `apps/notifications`
  کامل حذف شد؛ `apps/candidates/auth.py` و `permissions.py` حذف شدند.
- **US1 بدون OTP (T073–T076)**: `POST /api/v1/candidate/applications` با `curl` واقعی آزموده
  شد — ثبت کامل بدون هیچ مرحلهٔ OTP، کد پیگیری واقعی گرفته شد. فرم تک‌مرحله‌ای شد.
- **US2 با کد پیگیری (T077–T082)**: `GET /api/v1/track/{code}` با `curl` واقعی آزموده شد (کد
  معتبر ۲۰۰، کد نامعتبر ۴۰۴)؛ نرخ‌محدودسازی با یک اسکریپت واقعی ۲۲ درخواست پشت‌سرهم آزموده شد
  — دقیقاً پس از رسیدن به سقف ۲۰، پاسخ‌ها به ۴۲۹ تغییر کردند (شاهد واقعی، نه فرضی).
- **US7 مدیریت کاربران (T083–T087)**: با ورود واقعی رمز+TOTP (کد محاسبه‌شده از `django_otp.oath.totp`)
  به‌عنوان `hr_manager`، از طریق `curl`: ساخت حساب (با `totp_config_url` واقعی برگشتی)، تغییر
  نقش، غیرفعال‌سازی، و رد خودکار درخواست بعدی همگی تأیید شدند. **یک باگ واقعی در همین آزمون
  کشف و رفع شد**: `change_staff_role` هیچ محافظتی در برابر «تغییر نقش تنها hr_manager فعال»
  نداشت — با آزمون واقعی، مدیر HR به‌طور واقعی خودش را قفل کرد (۴۰۳ روی تمام مسیرهای بعدی)؛
  رفع با بازیابی دستی از شل و افزودن `_other_active_hr_manager_exists` به `change_staff_role`
  (علاوه بر `set_staff_active`). FR-021c در spec.md بر همین اساس به‌روزرسانی شد.
- **مجموعه تست**: `tests/unit` + `tests/integration` + `tests/contract` = **۲۰۰ تست، همه سبز**
  روی PostgreSQL واقعی (یک تست مرورگری که به‌اشتباه در `tests/integration/` قرار داشت، جدا اجرا
  می‌شود — پایین توضیح داده شده). `ruff check --select F` فقط ۳ هشدار پیش‌از‌این‌موجود
  (`config/settings/{dev,prod}.py` star-import) دارد که به این دور مربوط نیستند.
  `manage.py check` و `makemigrations --check --dry-run` تمیز.

**محدودیت محیطی کشف‌شده (گزارش‌شده، نه رفع‌شده — خارج از دامنهٔ T070–T088)**: تست‌های مرورگری
Playwright (`tests/browser/*` و یک مورد در `tests/integration/test_application_notes_and_status_access.py`)
با `SynchronousOnlyOperation` در `django_db_setup` شکست می‌خورند — این روی فایل‌های کاملاً
دست‌نخورده (مثلاً `test_us3_review.py`, `test_accessibility_rtl.py`) هم عیناً تکرار می‌شود، پس
قطعاً ناشی از تغییرات این دور نیست. نسخهٔ نصب‌شدهٔ `pytest-playwright` با پین `requirements/dev.txt`
(۰.۵.۲) هماهنگ شد (محیط قبلاً به ۰.۱۰.۰ رانده بود) اما مشکل برطرف نشد — به نظر می‌رسد ناشی از
محیط اجرای sandbox همین نشست باشد، نه کد پروژه. کد تست‌های T076/T082/T087 نوشته و از نظر منطقی
با رابط UI واقعی هماهنگ شده‌اند، اما در این محیط اجرا نشدند؛ جریان‌های معادل آن‌ها به‌صورت دستی
با `curl`/`django_otp.oath.totp` واقعی (نه موک) آزموده و تأیید شدند (بالاتر).

**نکتهٔ محدودهٔ حذف‌شده**: T064 (اتصال واقعی پیامک) با حذف کامل OTP متقاضی **کاملاً منتفی** شد؛
دیگر هیچ سرویس پیامکی در دامنهٔ این نسخه نیست. `docs/decisions.md` آیتم O3 به‌روزرسانی شد تا فقط
به اسکنر بدافزار اشاره داشته باشد، نه پیامک.
