# Implementation Plan: نسخه اولیه پورتال فارسی جذب و استخدام

**Branch**: `001-recruitment-portal` | **Date**: 2026-10-31 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-recruitment-portal/spec.md`

## Summary

متقاضیان از هر دستگاهی، **بدون هیچ مرحلهٔ احراز هویت یا تأیید موبایل** (اصل V نسخهٔ ۳.۰.۰)، برای
موقعیت‌های شغلی باز درخواست می‌دهند، رزومه بارگذاری می‌کنند و یک کد پیگیری غیرقابل‌حدس دریافت
می‌کنند که بعداً برای مشاهدهٔ وضعیت همان درخواست (و فقط همان درخواست) استفاده می‌شود. کارکنان
مجاز HR (فقط با نام‌کاربری + رمز عبور — بدون عامل دوم، اصل V نسخهٔ ۳.۰.۰) در یک داشبورد متمرکز
پرونده‌ها را جست‌وجو، بررسی، ارجاع، وضعیت‌دهی و
خروجی می‌گیرند؛ مدیر HR («ادمین») اکنون از همان پنل می‌تواند حساب کارمند جدید با نقش دلخواه
بسازد و نقش/فعال‌بودن حساب‌های موجود را مدیریت کند (US7)، بدون نیاز به خط فرمان. رویکرد فنی: یک
برنامه یکپارچه ماژولار Django + DRF روی PostgreSQL، با محتوای رزومه در ستون `bytea`/`BinaryField`
یک جدول جداگانه (بدون S3)، صف کار داخلی مبتنی بر PostgreSQL برای اسکن بدافزار/تطبیق فایل به‌جای
Celery/Redis، و قالب‌های Django هم‌مبدأ با API برای حفظ ظاهر راست‌به‌چپ نمونه.

## Technical Context

**Language/Version**: Python 3.12، Django 5.2 (LTS)

**Primary Dependencies**: Django REST Framework 3.15، psycopg 3 (درایور PostgreSQL)،
`openpyxl` (حالت `write_only`) برای XLSX، ماژول استاندارد `csv` برای CSV، `jdatetime`
برای نمایش تقویم شمسی در لایه ارائه، `clamd` (کلاینت ClamAV) پشت یک رابط `ScannerClient` داخلی
قابل‌تعویض. **`SmsGateway` و همهٔ پیاده‌سازی‌های پیامک حذف شدند** (دیگر هیچ OTP پیامکی در
سامانه وجود ندارد)؛ `apps/notifications` از اسکوپ این نسخه خارج شد. **`django-otp` نیز کامل
حذف شد** — از اصل V نسخهٔ ۳.۰.۰ به بعد دیگر هیچ MFA/TOTPی، نه برای متقاضی و نه برای کارکنان،
در سامانه وجود ندارد؛ ورود کارکنان فقط نام‌کاربری/رمز عبور است.

**Storage**: PostgreSQL 16. محتوای رزومه در ستون `bytea` (`BinaryField` در Django) در جدول
`AttachmentContent` جداگانه از فراداده؛ بدون S3 یا سرویس فایل خارجی (تصمیم قطعی کاربر).

**Testing**: `pytest` + `pytest-django` برای واحد/یکپارچه (یکپارچه همیشه روی PostgreSQL واقعی، نه
SQLite)؛ تست مرورگری (Playwright) برای ثبت (بدون OTP)/پیگیری با کد/داشبورد HR/مدیریت کاربران/
خروجی روی موبایل و RTL؛ `locust` یا معادل آن برای آزمون بار پیش‌تولید.

**Target Platform**: سرور لینوکس (کانتینری)؛ رابط کاربری (قالب Django) و API هم‌مبدأ (یک دامنه،
بدون CORS میان‌دامنه‌ای).

**Project Type**: برنامه وب یکپارچه ماژولار (Django monolith با چند app داخلی)، نه ترکیب
frontend/backend مجزا.

**Performance Goals**: صدک ۹۵ فهرست/جزئیات پرونده < ۱ ثانیه (بدون شبکه) با ۱۰۰٬۰۰۰ درخواست و ۲۰
کارمند هم‌زمان (SC-002)؛ رسید ثبت موفق ≤ ۳ ثانیه پس از آماده‌شدن فایل سالم (SC-007).

**Constraints**: خطای سرور (۵xx) < ۱٪ زیر بار (SC-003)؛ سقف فایل رزومه ۵ MiB؛ سقف خروجی ۱۰٬۰۰۰
ردیف (تولید هم‌زمان/synchronous، بدون صف پس‌زمینه در MVP، FR-037a)؛ محدودیت نرخ خروجی ۵ درخواست
در ۱۰ دقیقه برای هر حساب کارمند (پس از احراز هویت و بررسی مجوز خروجی، شمارنده اتمی دیتابیسی،
FR-037a)؛ **محدودیت نرخ جست‌وجوی کد پیگیری بر اساس IP** (FR-043، شمارنده اتمی دیتابیسی، آستانه
پیشنهادی `TRACKING_LOOKUP_IP_LIMIT=20` در ۱۰ دقیقه — نیازمند تصویب مالک پروژه مثل FR-047)؛
هیچ نشست یا کوکی‌ای برای متقاضی وجود ندارد (اصل V نسخهٔ ۲.۰.۰)؛ نشست کارمند ۳۰ دقیقه/۸ ساعت سقف؛
محدودیت نرخ ورود کارمند بر اساس حساب و IP (FR-047، شمارنده اتمی دیتابیسی، آستانه‌های مصوب طبق
`docs/decisions.md` D6: ۵ تلاش/۱۵ دقیقه برای هر حساب، ۱۵ تلاش/۲۰ دقیقه برای هر IP)؛ RPO موقت
۲۴ ساعت و RTO موقت ۴ ساعت (نیازمند تصویب نهایی زیرساخت).

**سیاست نگهداری (FR-061)**: پیش‌فرض **fail-closed** — `RETENTION_POLICY_APPROVED=False`.
`enforce_retention` تا تصویب صریح سیاست توسط مالک پروژه و فعال‌سازی آگاهانه، با `CommandError`
پیش از هر حذف متوقف می‌شود؛ `--dry-run` غیرمخرب باقی می‌ماند. پاک‌سازی `AuditEvent` مسدود است
تا نقش دیتابیس حداقل‌مجوز جداگانه تعریف شود (اصل VIII؛ نقش فعلی برنامه superuser است).
**برگشت مهاجرت JobPosition** عمداً غیرقابل‌اجراست و پیش از هر تغییر اسکیما/داده با `RuntimeError`
متوقف می‌شود؛ بازگشت واقعی فقط از پشتیبان پیش از مهاجرت.

**Scale/Scope**: حدود ۱۰۰٬۰۰۰ درخواست ثبت‌شده، حداکثر ۲۰ کارمند هم‌زمان، یک منطقه استقرار (نسخه
اولیه تک‌منطقه‌ای).

هیچ مورد `NEEDS CLARIFICATION` باقی نمانده است؛ تمام تصمیم‌های فنی باز در `research.md` مستند و
نهایی شده‌اند.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| اصل قانون اساسی | ارزیابی | وضعیت |
|---|---|---|
| I. معماری یکپارچه ماژولار | Django + DRF + PostgreSQL، رزومه در `bytea` بدون S3، قالب‌های Django با CSS/JS استخراج‌شده، بدون SPA/میکروسرویس | گذر |
| II. مرجعیت سرور | تمام اعتبارسنجی، مجوز، گردش وضعیت و idempotency سمت سرور (`IdempotencyRecord`، تراکنش‌های دیتابیس)؛ هیچ منبع حقیقتی در مرورگر | گذر |
| III. حداقل دسترسی/دسترسی رکوردی | مجوز per-role و per-record در لایه serializer/queryset DRF روی هر مسیر `staff/*`؛ ۴۰۱/۴۰۳/۴۰۴ بدون افشای وجود رکورد | گذر |
| IV. حداقل‌سازی داده | مدل `Application` فاقد کد ملی؛ هیچ فیلد اضافه بر فرم مصوب | گذر |
| V. احراز هویت و نشست امن | **بازتعریف‌شده دوبار (نسخهٔ ۲.۰.۰ و ۳.۰.۰)**: متقاضی هیچ احراز هویت/نشستی ندارد؛ پیگیری فقط با کد پیگیری پرآنتروپی + نرخ‌محدودسازی IP (FR-042 تا FR-044). کارکنان فقط با نام‌کاربری/رمز عبور — بدون عامل دوم — وارد می‌شوند؛ نشست کارمند مستقل، کوکی HttpOnly/Secure/SameSite=Lax، CSRF روی مسیرهای ایجاد نشست، و نرخ‌محدودسازی ورود (FR-047) بدون تغییر | گذر (پس از اصلاح رسمی اصل) |
| VI. امنیت فایل رزومه | بررسی magic bytes/پسوند/حجم سمت سرور، قرنطینه تا نتیجه اسکن، دانلود فقط از مسیر احرازهویت‌شده Django | گذر |
| VII. عدم اعتماد به ورودی کاربر | قالب‌های Django auto-escape، بدون `innerHTML`/`mark_safe` خام، خنثی‌سازی فرمول در CSV/XLSX در سرویس مشترک | گذر |
| VIII. حسابرسی بدون افشای داده حساس | مدل `AuditEvent` فقط افزودنی، بدون رمز/محتوای فایل؛ رویدادهای تازهٔ مدیریت کاربران (`staff_account_created`/`staff_role_changed`/`staff_deactivated`) هم همین قاعده را رعایت می‌کنند | گذر |
| IX. تست یکپارچه گردش‌های حیاتی | تست‌های یکپارچه روی PostgreSQL واقعی برای race condition ثبت درخواست، قفل‌ها، کنترل دسترسی رکوردی و نرخ‌محدودسازی پیگیری/ورود | گذر |
| X. آماده‌سازی تولید | HTTPS، پشتیبان رمزگذاری‌شده خارج از میزبان، بدون داده/دکمه دمو در تولید؛ مستند در فاز عملیات | گذر |
| XI. ثبت تصمیم‌ها و انحراف‌ها | حذف OTP متقاضی (نسخهٔ ۲.۰.۰) و حذف عامل دوم کارکنان (نسخهٔ ۳.۰.۰) هر دو تصمیم تجاری با پیامد امنیتی صریح‌اند؛ طبق رویهٔ اصلاح قانون اساسی (Governance)، با تصویب صریح مالک پروژه ثبت و اصل V بازتعریف شد (نه تصمیم یک‌طرفهٔ فنی) | گذر |
| XII. بومی‌سازی فارسی/زمان | ذخیره UTC، نمایش شمسی `Asia/Tehran` با `jdatetime` در لایه قالب؛ موبایل/شناسه‌ها `CharField`/`UUIDField` رشته‌ای | گذر |

هیچ تخطی غیرمجازی شناسایی نشد. تغییر اصل V یک بازتعریف رسمی (نه تخطی) است، چون پیش از این پلن در
خودِ `constitution.md` (نسخهٔ ۲.۰.۰، Sync Impact Report) ثبت شده است؛ بخش «ردیابی پیچیدگی» خالی
می‌ماند.

**بازبینی پس از فاز ۱**: پس از تکمیل `research.md`، `data-model.md`، `contracts/openapi.yaml` و
`quickstart.md`، جدول بالا دوباره مرور شد؛ طراحی داده (ارجاع فعال منحصربه‌فرد، جداسازی
`Attachment`/`AttachmentContent`، صف کار PostgreSQL، رابط `ScannerClient`، شمارندهٔ نرخ پیگیری
`TrackingLookupRateCounter`، مدیریت کاربران در `apps/accounts`) هیچ اصل جدیدی را نقض نمی‌کند.
وضعیت گذر برای هر ۱۲ اصل برقرار می‌ماند.

## Project Structure

### Documentation (this feature)

```text
specs/001-recruitment-portal/
├── plan.md              # این فایل (خروجی /speckit-plan)
├── research.md          # خروجی فاز ۰
├── data-model.md        # خروجی فاز ۱
├── quickstart.md        # خروجی فاز ۱
├── contracts/           # خروجی فاز ۱ (OpenAPI)
├── checklists/
│   └── requirements.md
└── tasks.md             # خروجی /speckit-tasks (در این فرمان ساخته نمی‌شود)
```

### Source Code (repository root)

```text
manage.py

config/                          # بسته تنظیمات پروژه Django
├── settings/
│   ├── base.py
│   ├── dev.py
│   └── prod.py
├── urls.py                      # شامل /api/v1/... و مسیرهای قالب
├── asgi.py
└── wsgi.py

apps/
├── common/                       # ماژول‌های مشترک بدون مدل اختصاصی (مثل فیلتر قالب to_jalali)
│   └── templatetags/
├── accounts/                    # کاربران کارمند، نقش‌ها، ورود/خروج کارمند (فقط رمز عبور)،
│                                 # مدیریت کاربران از پنل (US7: ایجاد/تغییر نقش/فعال‌وغیرفعال‌سازی)
│   ├── models.py  services.py  api/  admin.py
├── candidates/                  # Candidate (بدون احراز هویت)، جست‌وجوی کد پیگیری،
│                                 # TrackingLookupRateCounter — بدون OTPChallenge/OtpRateCounter
│                                 # (حذف‌شده طبق اصل V نسخهٔ ۲.۰.۰)
│   ├── models.py  services.py  api/
├── jobs/                        # JobPosition و مدیریت آن (US6)
│   ├── models.py  services.py  api/
├── applications/                # Application، ApplicationReviewer، ApplicationNote،
│                                 # StatusHistory، Consent/PrivacyNotice، IdempotencyRecord،
│                                 # سرویس ثبت/گردش‌وضعیت/ارجاع (US1–US4، US6)
│   ├── models.py  services.py  api/  statemachine.py
├── attachments/                 # Attachment، AttachmentContent، بارگذاری/دانلود/قرنطینه (US1، US3)
│   ├── models.py  services.py  api/  scanning/ (ScannerClient + پیاده‌سازی‌ها)
├── reporting/                   # خروجی CSV/XLSX، سیاست ستون‌ها، سرویس امن‌سازی مقادیر (US5)
│   ├── models.py (ExportRateCounter)  services.py  api/  export_policy.py
├── audit/                       # AuditEvent و سرویس ثبت حسابرسی مشترک همه اپ‌ها
│   ├── models.py  services.py
└── operations/                  # BackgroundJob، فرمان‌های مدیریتی worker/cleanup، health/readiness
    ├── models.py  management/commands/run_worker.py
    ├── management/commands/cleanup_uploads.py
    └── views_health.py

# apps/notifications حذف شد (SmsGateway دیگر لازم نیست — اصل V نسخهٔ ۲.۰.۰؛ هیچ OTP پیامکی
# در سامانه باقی نمانده است).

templates/                       # قالب‌های Django راست‌به‌چپ (برگرفته از نمونه، بدون منطق ناامن)
static/
├── css/   js/ (ماژول‌های fetch API به‌جای IndexedDB/دمو)

tests/
├── unit/           # نرمال‌سازی، انتقال وضعیت، ایمنی خروجی، سیاست دسترسی، نرخ‌محدودسازی پیگیری
├── integration/    # قید/رقابت روی PostgreSQL واقعی (idempotency، یکتایی شرطی، قفل فایل،
│                   # race condition نرخ‌محدودسازی کد پیگیری، مدیریت نقش/غیرفعال‌سازی کارمند)
├── contract/       # تست‌های OpenAPI/قرارداد هر مسیر برای هر ترکیب نقش/رکورد
└── browser/        # Playwright: ثبت (بدون OTP)/پیگیری با کد/داشبورد/مدیریت کاربران/خروجی، موبایل و RTL

docker/
└── docker-compose.yml           # برنامه + PostgreSQL + اسکنر (ClamAV) + پردازشگر پس‌زمینه

docs/
├── operations/                  # emergency-access.md، backup-restore.md، secrets.md، migrations.md، monitoring.md
└── decisions.md                 # تصمیم‌های تجاری/امنیتی مصوب ذی‌نفعان
```

**Structure Decision**: یک پروژه Django یکپارچه (monolith) با چند app داخلی مستقل اما هم‌پروسه،
مطابق اصل I قانون اساسی. قالب و API هم‌مبدأ هستند (بدون `frontend/`/`backend/` جدا)، چون رابط
کاربری نمونه با قالب‌های سروری Django بازسازی می‌شود، نه یک SPA مستقل. پردازش پس‌زمینه با فرمان
مدیریتی Django (`apps/operations`) به‌جای Celery/Redis انجام می‌شود، مطابق تصمیم کاربر.

## Complexity Tracking

> هیچ تخطی از قانون اساسی شناسایی نشد؛ این بخش خالی می‌ماند.
