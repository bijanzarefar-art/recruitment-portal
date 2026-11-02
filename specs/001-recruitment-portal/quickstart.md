# راهنمای صحت‌سنجی (Quickstart): نسخه اولیه پورتال جذب و استخدام

این سند سناریوهای قابل‌اجرا برای اثبات کارکرد کامل قابلیت (US1–US6) را فهرست می‌کند. جزئیات مدل
داده در [data-model.md](./data-model.md) و قرارداد کامل API در
[contracts/openapi.yaml](./contracts/openapi.yaml) است؛ اینجا تکرار نمی‌شوند.

## پیش‌نیازها

- Docker + Docker Compose (برنامه، PostgreSQL ۱۶، ClamAV، پردازشگر پس‌زمینه — طبق `research.md`).
- `docker/docker-compose.yml` بالا باشد: `docker compose up -d`.
- مهاجرت‌های دیتابیس اجراشده: `docker compose exec app python manage.py migrate`.
- در محیط توسعه، `SmsGateway` روی پیاده‌سازی `ConsoleSmsGateway` تنظیم است (کد OTP در لاگ برنامه
  چاپ می‌شود، هرگز در تولید).

## راه‌اندازی داده اولیه

```bash
docker compose exec app python manage.py createsuperuser_staff \
  --username hr.manager --role hr_manager
docker compose exec app python manage.py shell -c \
  "from apps.jobs.models import JobPosition; JobPosition.objects.create(title='توسعه‌دهنده بک‌اند', department='فناوری', location='تهران', status='open')"
```

(فرمان `createsuperuser_staff` معادل همان «فرمان مدیریتی محدود» برای ساخت حساب کارمند طبق
FR-020 است؛ enrollment بعدی TOTP از طریق رابط ورود کارمند انجام می‌شود. در حالت عادی API،
موقعیت تازه با `POST /api/v1/staff/jobs` همیشه `draft` ساخته می‌شود و باید صریحاً با
`PATCH /api/v1/staff/jobs/{id}/status` به `open` منتقل شود — FR-039a.)

## سناریو ۱ — ثبت درخواست (US1)

1. `GET /api/v1/jobs` → موقعیت ایجادشده را (چون `status=open` است) ببینید؛ موقعیت‌های
   `draft`/`closed` در این مسیر عمومی هرگز ظاهر نمی‌شوند.
2. `POST /api/v1/auth/candidate/otp/request` با `{"mobile": "09120000001", "purpose": "register"}`
   → پاسخ ۲۰۲؛ کد OTP را از لاگ کانسول توسعه بخوانید.
3. `POST /api/v1/auth/candidate/otp/verify` با همان موبایل و کد → نشست متقاضی (کوکی) ایجاد می‌شود.
4. `POST /api/v1/candidate/uploads` (multipart، فایل PDF کوچک سالم) → `scan_status: pending` سپس
   پس از چند ثانیه (کار `run_worker`) → `GET /api/v1/candidate/uploads/{id}` باید `clean` برگرداند.
5. `POST /api/v1/candidate/applications` با هدر `Idempotency-Key: demo-key-1` و بدنه معتبر شامل
   `resume_upload_id` از گام ۴ → ۲۰۱ با `tracking_code`.
6. **انتظار**: `GET /api/v1/candidate/applications` همان یک درخواست با وضعیت `new` را نشان دهد.

### تأیید idempotency و رقابت (FR-009)

- همان درخواست گام ۵ را دوباره با همان `Idempotency-Key: demo-key-1` و همان بدنه بفرستید →
  باید ۲۰۰ با همان `tracking_code` بازگردد (نه رکورد جدید).
- همان `Idempotency-Key` را با بدنه متفاوت بفرستید → باید ۴۰۹ بازگردد.
- (تست خودکار) دو درخواست همزمان با همان `candidate`/`job_position` اما کلیدهای متفاوت را به‌صورت
  موازی ارسال کنید → فقط یکی باید ۲۰۱ بگیرد، دیگری ۴۰۹ با پیام درخواست فعال تکراری (FR-008)؛ این
  آزمون باید روی PostgreSQL واقعی اجرا شود، نه SQLite.

### تأیید قرنطینه فایل آلوده (FR-010)

- یک فایل تست EICAR (یا معادل بی‌خطر شناخته‌شده برای ClamAV) بارگذاری کنید → `scan_status` باید به
  `quarantined` برسد و `POST /candidate/applications` با همان `resume_upload_id` باید ۴۰۰/۴۰۹ (نه
  موفقیت) بازگرداند؛ هیچ مسیر دانلودی نباید این فایل را برگرداند.

## سناریو ۲ — پیگیری (US2)

1. با همان موبایل، `POST /auth/candidate/otp/request` + `verify` با `purpose: track` از یک نشست/
   مرورگر دیگر انجام دهید.
2. `GET /candidate/applications` باید همان درخواست قبلی را نشان دهد.
3. **انتظار امنیتی**: تلاش برای `GET /candidate/applications/{id}` با شناسه یک درخواست متعلق به
   موبایل دیگر باید ۴۰۳/۴۰۴ بدهد (نه داده فرد دیگر).

## سناریو ۳ تا ۴ — بررسی، ارجاع، یادداشت و گردش وضعیت (US3/US4)

1. با `hr.manager` وارد شوید: `POST /auth/staff/login` سپس `POST /auth/staff/mfa/verify` (کد TOTP
   از enrollment).
2. `PATCH /staff/applications/{id}/assignments` با `reviewer_id` یک کارمند نقش `recruiter` →
   موفق (اولین ارجاع باید کارشناس باشد).
3. با کاربر کارشناس جذب وارد شوید؛ `GET /staff/applications` باید فقط همین پرونده را نشان دهد؛
   `GET /staff/applications` با کاربر بدون ارجاع نباید این پرونده را نشان دهد (FR-019/FR-040).
4. `POST /staff/applications/{id}/notes` با متن یادداشت → ۲۰۱.
5. با `hr.manager`، `PATCH /staff/applications/{id}/assignments` با `reviewer_id` یک کاربر نقش
   `hiring_manager` → ارجاع کارشناس باید بلافاصله باطل شود (FR-041 به‌روزشده).
6. **انتظار**: کارشناس قبلی دیگر `GET /staff/applications/{id}` یا دانلود رزومه را نتواند انجام
   دهد (۴۰۳/۴۰۴).
7. با `hr.manager`: `PATCH /staff/applications/{id}/status` با `to_status: phone`،
   `expected_version` درست → ۲۰۰؛ تکرار همان درخواست با `expected_version` قدیمی → ۴۰۹.
8. `to_status: rejected` بدون `reason` → ۴۰۰؛ با `reason` → ۲۰۰، و `GET /candidate/applications/{id}`
   نباید این دلیل را نشان دهد.

## سناریو ۵ — خروجی (US5)

1. با `hr.manager`: `POST /staff/exports` با `format: csv`، فیلتر دلخواه، `columns` مجاز → فایل
   CSV با BOM؛ ستون موبایل/شناسه به‌صورت متن در Excel باز شود بدون از دست‌دادن صفر ابتدایی در XLSX.
2. یک مقدار آزمایشی `=SUM(1+1)` در فیلد `city` یک درخواست تست قرار دهید (از طریق فرمان مدیریتی
   تست، نه فرم واقعی) و خروجی بگیرید → مقدار در فایل باید خنثی‌شده باشد (با `'` ابتدایی)، نه یک
   فرمول فعال.
3. با کاربر نقش `recruiter` همان درخواست خروجی را بفرستید → باید ۴۰۳ بگیرد، حتی اگر به همان
   پرونده‌ها دسترسی مشاهده داشته باشد (FR-036).
4. بیش از ۱۰٬۰۰۰ ردیف منطبق با فیلتر بسازید (یا فیلتر را در تست به‌گونه‌ای شبیه‌سازی کنید که آستانه
   عبور کند) → ۴۱۳ با پیام محدودکردن فیلتر.

## سناریو ۶ — مدیریت موقعیت و ارجاع (US6)

1. `POST /staff/jobs` موقعیت جدید → ۲۰۱؛ `PATCH /staff/jobs/{id}` با `status: closed` → ۲۰۰.
2. تلاش ثبت درخواست جدید برای همان موقعیت بسته (سناریو ۱) → رد شود؛ پرونده‌های قبلی همان موقعیت
   همچنان در `GET /staff/applications` با فیلتر آن موقعیت قابل مشاهده بمانند.
3. تلاش حذف فیزیکی موقعیت دارای درخواست (در صورت وجود چنین مسیری در پنل مدیریت) → مجاز نباشد؛ فقط
   بستن/بایگانی ممکن باشد.

## اعتبارسنجی غیرکارکردی (نمونه)

- **بار**: با `locust` روی محیط پیش‌تولید با داده مصنوعی ۱۰۰٬۰۰۰ درخواست و ۲۰ کاربر هم‌زمان،
  صدک ۹۵ پاسخ `GET /staff/applications` باید زیر ۱ ثانیه (بدون شبکه) باشد (SC-002)؛ نرخ ۵xx زیر
  ۱٪ (SC-003).
- **پشتیبان/بازیابی**: پشتیبان PostgreSQL را روی محیط آزمایشی بازیابی کنید؛ یک رزومه شناخته‌شده را
  دانلود و حجم/`sha256` آن را با مقدار اصلی مقایسه کنید.
- **دسترسی‌پذیری/RTL**: تست مرورگری Playwright فرم ثبت و داشبورد HR را در اندازه صفحه موبایل و
  چیدمان راست‌به‌چپ اجرا و برچسب‌های متصل به ورودی و فوکوس پنجره خطا را بررسی کند.

## معیار پایان صحت‌سنجی

همه سناریوهای بالا باید بدون نیاز به دخالت دستی در دیتابیس (جز راه‌اندازی اولیه) و بدون هیچ لینک
عمومی/مستقیم به فایل رزومه قابل تکرار باشند؛ هر مسیر خطا (۴۰۰/۴۰۱/۴۰۳/۴۰۴/۴۰۹/۴۱۳/۴۱۵/۴۲۹) باید
دقیقاً طبق جدول کدهای خطا در `contracts/openapi.yaml` رفتار کند.
