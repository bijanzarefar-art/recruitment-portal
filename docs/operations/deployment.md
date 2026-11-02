# استقرار در محیط اجرا (Production)

راهنمای عملی برای بردن این پروژه از محیط توسعه به یک سرور واقعی.

> **مهم:** این سند بر اساس **خواندن واقعی کد این مخزن** نوشته شده، نه فرض. هر جا چیزی در کد
> آماده نبوده، صریحاً با ⚠️ علامت‌گذاری شده است — آن‌ها را قبل از اولین استقرار حل کنید.

---

## ۰. تصویر کلی: چه چیزهایی باید اجرا شوند

| سرویس | چیست | الزامی؟ |
|---|---|---|
| **web** | Django (WSGI: gunicorn + Nginx) | حتماً |
| **db** | PostgreSQL 16 | حتماً |
| **worker** | `manage.py run_worker` — اسکن رزومهٔ آپلودشده | حتماً (وگرنه ثبت درخواست گیر می‌کند) |
| **clamav** | سرویس ClamAV برای اسکن فایل | حتماً |

### چرا worker حتماً لازم است — با جزئیات از کد

فرم ثبت درخواست رزومه را آپلود می‌کند و بعد تا `scan_status` فایل `clean` نشود، ثبت نهایی انجام
نمی‌شود (`static/js/candidate_apply.js`، تابع `pollUploadStatus`). خودِ اسکن را **جدا** از
هنگام درخواست وب انجام می‌دهد (`apps/operations/management/commands/run_worker.py`) که کار را از
جدول `BackgroundJob` با `SELECT ... FOR UPDATE SKIP LOCKED` برمی‌دارد.

**اگر worker بالا نباشد:** هر متقاضی پیام «بررسی فایل بیش از حد انتظار طول کشید» می‌بیند و
**هیچ درخواستی ثبت نمی‌شود**. این را در همین نشست عملاً دیدم — بدون worker، دکمهٔ ثبت نهایی هیچ
پاسخی نمی‌داد.

### ⚠️ شمارنده‌های محدودسازی نرخ worker لازم ندارند

`ExportRateCounter`، `StaffLoginRateCounter` و `TrackingLookupRateCounter` شمارنده‌های اتمی
**دیتابیسی** هستند که در همان درخواست وب به‌روز می‌شوند (نه پس‌زمینه). پس نیازی به Redis/Celery
ندارند — عمداً این‌طور طراحی شده تا پشته ساده بماند.

---

## ۱. پیش‌نیاز دیسک/سرور

- Python 3.12 (تصویر پایهٔ `docker/Dockerfile` همین است).
- PostgreSQL 16 (در `docker/docker-compose.yml` از `postgres:16` استفاده شده).
- Nginx (یا پراکسی معکوس معادل) برای TLS و سرو کردن فایل‌های استاتیک.

---

## ۲. تنظیمات تولید

`config/settings/prod.py` این‌ها را فعال می‌کند و **اجرا را متوقف می‌کند** اگر کلید راز پیش‌فرض
بماند:

```python
DEBUG = False
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True      # ← یعنی حتماً باید پشت HTTPS باشید
SECURE_HSTS_SECONDS = 31536000
```

یعنی: **قبل از اولین درخواست، گواهی TLS و پراکسی معکوس باید آماده باشد**، وگرنه کل ترافیک
HTTP به HTTPS ریدایرکت می‌شود و چیزی کار نمی‌کند.

### متغیرهای محیطی که باید تنظیم شوند

| متغیر | توضیح | نکته |
|---|---|---|
| `DJANGO_SETTINGS_MODULE` | `config.settings.prod` | ⚠️ پیش‌فرض پروژه `dev` است |
| `DJANGO_SECRET_KEY` | کلید راز | اگر `insecure-dev-key-change-me` بماند، اجرا **بالا نمی‌آید** |
| `DJANGO_ALLOWED_HOSTS` | دامنهٔ واقعی، با کاما | بدون آن همهٔ درخواست‌ها `400` می‌گیرند |
| `POSTGRES_DB` / `_USER` / `_PASSWORD` / `_HOST` / `_PORT` | اتصال دیتابیس | `_HOST` پیش‌فرض `db` (نام سرویس در compose) |
| `CLAMD_HOST` / `CLAMD_PORT` | آدرس ClamAV | پیش‌فرض `clamav:3310` |

قالب کامل و صحیح در `.env.example` هست — آن را کپی و مقادیر واقعی را جایگزین کنید.
**⚠️ هیچ‌وقت `.env` واقعی را در گیت نگذارید؛ در `.gitignore` هست، همان‌طور بگذارید.**

---

## ۳. گام‌به‌گام

### گام ۱ — دیتابیس

یک PostgreSQL 16 با نام کاربری/پایگاه‌دادهٔ دلخواه بسازید. برای جداسازی نقش migrate از runtime
به `docs/operations/db-roles.sql` مراجعه کنید.

> ⚠️ **بازِ ثبت‌شده:** جدول‌های فهرست‌شده در `db-roles.sql` **قدیمی‌اند** و هنوز شامل
> `candidates_trackinglookupratecounter`، `jobs_jobposition.requirements` (فیلد جدید) نیستند و
> برعکس، جدول‌های حذف‌شدهٔ `candidates_otpchallenge`، `candidates_otpratecounter`،
> `accounts_staffrecoverycode` و `otp_totp_totpdevice` هنوز در آن فهرست هستند (چون OTP و MFA در
> این نسخه کامل حذف شده‌اند). **پیش از اعمال آن روی محیط واقعی، فهرست را از روی
> `manage.py showmigrations` و جداول واقعی بازبینی کنید.**

### گام ۲ — کد و وابستگی‌ها

```bash
git clone <repo> /srv/reqruitment
cd /srv/reqruitment
python3.12 -m venv .venv
.venv/bin/pip install -r requirements/base.txt
```

> ⚠️ **فقط `requirements/base.txt` را نصب کنید، نه `dev.txt`.** `docker/Dockerfile` فعلی
> `dev.txt` را نصب می‌کند (pytest، playwright، locust…) — برای تولید مناسب نیست؛ اگر خودتان
> تصویر می‌سازید از `base.txt` استفاده کنید.

> ⚠️ **gunicorn در هیچ‌کدام از دو فایل requirements نیست.** برای تولید باید جداگانه نصبش کنید:
> ```bash
> .venv/bin/pip install gunicorn
> ```
> (نسخه را پین کنید و به `requirements/base.txt` اضافه کنید.)

### گام ۳ — متغیرهای محیطی

```bash
cp .env.example .env
# مقادیر واقعی را جایگزین کنید: کلید راز، دامنه، اعتبارنامهٔ دیتابیس
```

⚠️ **`.env` خودکار خوانده نمی‌شود.** هیچ `load_dotenv` یا `env_file` در کد نیست؛ متغیرها باید
در محیط شل/سرویس سیستم تعریف شوند. برای systemd از `EnvironmentFile=`, برای Docker از
`env_file:` استفاده کنید. خودِ `docker/docker-compose.yml` این را انجام می‌دهد.

### گام ۴ — مایگریشن

```bash
export DJANGO_SETTINGS_MODULE=config.settings.prod
.venv/bin/python manage.py migrate
```

> **نکتهٔ مهم:** اگر دیتابیس از نسخهٔ قدیمی با `is_published` ارتقا می‌یابد، مایگریشن
> `jobs.0002_preflight_job_status_mapping` **عامداً متوقف می‌شود** اگر ردیفی با ترکیب تأییدنشده
> داشته باشد، و راه‌حل را در پیام خطا می‌گوید. جزئیات کامل در
> `docs/operations/migrations.md`.

### گام ۵ — ساخت اولین حساب ادمین

هیچ کاربری به‌صورت پیش‌فرض ساخته نمی‌شود (عمدی — `docs/operations/secrets.md`). اولین
`hr_manager` را با فرمان مدیریتی بسازید:

```bash
.venv/bin/python manage.py createsuperuser_staff --username admin --role hr_manager
```

رمز را تعاملی می‌پرسد. از همان ابتدا نقش را `hr_manager` بدهید تا بتوانید بقیهٔ کارکنان را از
صفحهٔ «مدیریت کاربران» بسازید.

> نکتهٔ امنیتی: نقش `hr_manager` می‌تواند کاربر بسازد. اولین کاربر را دستی بسازید؛ بقیه از پنل
> ساخته شوند.

### گام ۶ — فایل‌های استاتیک

```bash
.venv/bin/python manage.py collectstatic --noinput
```

> ⚠️ **`.venv` هیچ `whitenoise` ندارد** و `STATIC_URL = "static/"` (بدون اسلش ابتدایی) است.
> Django در `DEBUG=False` فایل استاتیک را **سرو نمی‌کند**. یعنی باید Nginx هم `staticfiles/` را
> **و** `static/` را (فایل‌های خودِ پروژه که `STATICFILES_DIRS` تعریف می‌کند) سرو کند. اگر یکی را
> جا بیندازید، صفحهٔ سفید بدون CSS/JS می‌گیرید. نمونه:

```nginx
location /static/ {
    alias /srv/reqruitment/staticfiles/;
}
```

(و مطمئن شوید `static/` اصلی هم در `STATIC_ROOT` جمع شده — `collectstatic` این کار را می‌کند.)

### گام ۷ — اجرای web

```bash
.venv/bin/gunicorn config.wsgi:application \
  --bind 127.0.0.1:8000 \
  --workers 3
```

### گام ۸ — اجرای worker (حداقل یک نمونه، همیشه بالا)

```bash
.venv/bin/python manage.py run_worker
```

این فرمان **حلقهٔ بی‌پایان** است؛ باید به‌صورت سرویس مدیریت‌شده (systemd / `restart: always` در
compose) اجرا شود تا اگر کرش کرد دوباره بالا بیاید. نمونهٔ systemd:

```ini
[Unit]
Description=Reqruitment scan worker
After=network.target postgresql.service

[Service]
WorkingDirectory=/srv/reqruitment
EnvironmentFile=/srv/reqruitment/.env
ExecStart=/srv/reqruitment/.venv/bin/python manage.py run_worker
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### گام ۹ — ClamAV

سرویس ClamAV سرور را بالا بیاورید (در compose سرویس `clamav` هست) و `CLAMD_HOST`/`CLAMD_PORT`
را به آن تنظیم کنید. اولیهٔ دیتابیس ویروس ClamAV معمولاً چند دقیقه طول می‌کشد و در آن بازه
اسکن‌ها `scan_failed` می‌شوند — این حالت عمداً fail-closed است، نه «clean».

---

## ۴. کارهای دوره‌ای (cron)

این‌ها خودکار **نیستند** — هر کدام باید به cron یا systemd timer وصل شوند:

| کار | دستور | هر چند وقت |
|---|---|---|
| پاک‌سازی آپلودهای یتیم (بدون درخواست، >۲۴ ساعت) | `manage.py cleanup_uploads` | روزانه |
| اعمال سیاست نگهداری | `manage.py enforce_retention` | ماهانه |
| پشتیبان‌گیری | `scripts/backup.sh` | روزانه |
| چرخش پشتیبان ۱۲ماهه | `scripts/backup_rotate.sh` | ماهانه |

> ⚠️ **`enforce_retention` به‌طور پیش‌فرض هیچ کاری نمی‌کند.** `RETENTION_OPERATIONAL_ENABLED=False`
> است (`config/settings/base.py`)، پس فرمان با خطا متوقف می‌شود — عمداً. برای فعال‌سازی،
> فقط بعد از تصمیم صریح ذی‌نفع، `RETENTION_OPERATIONAL_ENABLED = True` را در
> **تنظیمات همان محیط** روشن کنید. سوابق حسابرسی (`AuditEvent`) هرگز حذف نمی‌شوند.

**مثال crontab:**

```cron
0 2 * * *  cd /srv/reqruitment && set -a && . ./.env && set +a && .venv/bin/python manage.py cleanup_uploads >> /var/log/reqruitment/cleanup.log 2>&1
0 3 * * *  cd /srv/reqruitment && set -a && . ./.env && set +a && ./scripts/backup.sh >> /var/log/reqruitment/backup.log 2>&1
```

---

## ۵. چک‌لیست پیش از تحویل به کاربر

هرکدام را روی محیط واقعی (نه اینجا) اجرا/بررسی کنید:

- [ ] `manage.py check --deploy` با `DJANGO_SETTINGS_MODULE=config.settings.prod` بدون هشدار
- [ ] `DJANGO_SECRET_KEY` واقعی (نه مقدار پیش‌فرض) تنظیم شده
- [ ] `DJANGO_ALLOWED_HOSTS` شامل دامنهٔ واقعی است
- [ ] HTTPS کار می‌کند و `SECURE_SSL_REDIRECT` حلقه ایجاد نمی‌کند (پراکسی `X-Forwarded-Proto` را درست بدهد)
- [ ] `SECURE_PROXY_SSL_HEADER` — ⚠️ **در `prod.py` تنظیم نشده.** اگر پشت Nginx/ALB هستید، احتمالاً لازمش دارید وگرنه امکان حلقهٔ ریدایرکت نامتناهی وجود دارد. این را روی محیط واقعی تست کنید.
- [ ] `migrate` بدون خطا اجرا شد
- [ ] `collectstatic` اجرا شد و CSS/JS در مرورگر لود می‌شوند (نه ۴۰۴)
- [ ] **worker بالا و `Restart=always` است** — با یک آپلود واقعی تست کنید
- [ ] ClamAV متصل است و یک فایل تمیز به `clean` می‌رسد
- [ ] ثبت درخواست آشناس (بدون ورود) واقعاً کار می‌کند و کد پیگیری برمی‌گردد
- [ ] پیگیری با کد کار می‌کند
- [ ] ورود کارمند + ساختن یک موقعیت شغلی + ارجاع به یک کارمند دیگر کار می‌کند
- [ ] یک خروجی CSV واقعی دانلود می‌شود
- [ ] `backup.sh` موفق شد و فایل با `sha256` تأیید شد
- [ ] لاگ‌های `password=`/`authorization:` در فایل لاگ `[REDACTED]` هستند (فیلتر `RedactSensitiveDataFilter`)
- [ ] پشتیبان روی دیسک/سرور **مستقل** است، نه روی همان میزبان (`scripts/backup.sh` بررسی می‌کند)
- [ ] `docs/operations/db-roles.sql` با فهرست جداول **فعلی** بازبینی و اصلاح شده (مورد ⚠️ بالا)

---

## ۶. مسائلی که عمداً حل نشده‌اند (باز)

این‌ها در `docs/operations/secrets.md`، `monitoring.md` و `db-roles.sql` هم ثبت شده‌اند:

1. **مدیر راز واقعی** (Vault / AWS Secrets Manager / …) انتخاب نشده — کد فقط انتظار دارد از محیط بیاید.
2. **پایش/هشدار** (Sentry / Prometheus / …) پیکربندی نشده.
3. **نقش‌های کمترین‌مجوز PostgreSQL** طراحی شده ولی فعلاً با superuser اجرا می‌شود.
4. **پایش صف `BackgroundJob`** — اگر worker بمیرد و cron اعلانی نداشته باشیم، فقط متقاضی متوجه می‌شود.

مورد ۴ عملاً مهم‌ترین است: **یک هشدار روی «سن قدیمی‌ترین `BackgroundJob` با `status=pending`»
تنظیم کنید**، چون تنها نشانهٔ خاموش شدن worker از دید کاربر، گیر کردن ثبت درخواست است.
