# اجرا با Docker Compose

کل پشته (دیتابیس، ClamAV، web، worker) با یک فایل بالا می‌آید.

## شروع سریع

```bash
cp .env.example .env      # سپس DJANGO_SECRET_KEY و POSTGRES_PASSWORD را عوض کنید
docker compose -f docker/docker-compose.yml up -d --build
```

سپس اولین حساب مدیر را بسازید:

```bash
docker compose -f docker/docker-compose.yml exec web \
  python manage.py createsuperuser_staff --username admin --role hr_manager
```

آدرس: <http://127.0.0.1:8000> (یا پورت دلخواه با `APP_PORT=9000`).

## سرویس‌ها

| سرویس | نقش |
|---|---|
| `db` | PostgreSQL 16، داده در volume `pgdata` |
| `clamav` | اسکن بدافزار رزومه‌ها |
| `migrate` | یک‌بار اجرا می‌شود و خارج می‌شود؛ web و worker پس از موفقیتش بالا می‌آیند |
| `web` | gunicorn روی پورت داخلی ۸۰۰۰ |
| `worker` | `run_worker` — **الزامی**، جلوگیری از گیر کردن ثبت درخواست |

`web` و `worker` از یک تصویر ساخته می‌شوند و فقط دستورشان فرق دارد.

## حالت توسعه در برابر تولید

پیش‌فرض `.env.example` روی `config.settings.dev` است: کد از میزبان مانت می‌شود، `DEBUG=True`
و `ALLOWED_HOSTS=["*"]`.

> **نکتهٔ مهم:** در حالت `dev`، مقدار `DJANGO_ALLOWED_HOSTS` **هیچ اثری ندارد** —
> `config/settings/dev.py` آن را با `["*"]` بازنویسی می‌کند. یعنی هر دامنه‌ای پذیرفته می‌شود.

برای اجرای «مثل تولید» (که در آن دامنهٔ `recru.milanpars.com` و CSRF واقعاً اعمال می‌شوند):

```bash
# در .env:
DJANGO_SETTINGS_MODULE=config.settings.prod
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,recru.milanpars.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://recru.milanpars.com
```

در این حالت `prod` این‌ها را فعال می‌کند: `SECURE_SSL_REDIRECT`, `HSTS`,
`SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`. پس **باید پشت یک پراکسی TLS باشید**، وگرنه
هر درخواست ریدایرکت می‌شود.

`SECURE_PROXY_SSL_HEADER` از قبل در `docker-compose.yml` تنظیم شده (`HTTP_X_FORWARDED_PROTO, https`)
تا پراکسی معکوس درست تشخیص داده شود. اگر مستقیم و بدون پراکسی سرو می‌کنید، `SECURE_SSL_REDIRECT`
را خاموش کنید، وگرنه حلقهٔ ریدایرکت می‌گیرید.

## نکات

- **تگ ClamAV:** فقط `latest` منتشر می‌شود؛ `clamav/clamav:1.3` در رجیستری وجود ندارد و باعث شکست
  `docker compose up` می‌شد.
- **دستور ClamAV:** تصویر رسمی پیش‌فرض `hello-world` دارد (چاپ و خروج). `entrypoint: ["/init"]`
  در کامپوز آن را به اجرای واقعی `clamd` برمی‌گرداند. بدون آن سلامت سرویس هرگز سبز نمی‌شود.
- **اولین اجرا:** بارگذاری دیتابیس ویروس چند دقیقه طول می‌کشد (`start_period: 180s`). در این بازه
  اسکن‌ها `scan_failed` می‌شوند — عمداً fail-closed است، نه `clean`.
- **مانت کد:** `volumes: ..:/code` فقط برای راحتی توسعه است. برای اجرای تولیدی حذفش کنید تا
  کد داخل تصویر سوار باشد و `--build` واقعاً اثر کند.

## دستورهای متداول

```bash
docker compose -f docker/docker-compose.yml ps
docker compose -f docker/docker-compose.yml logs -f web
docker compose -f docker/docker-compose.yml logs -f worker
docker compose -f docker/docker-compose.yml exec web python manage.py migrate
docker compose -f docker/docker-compose.yml exec web python manage.py collectstatic --noinput
docker compose -f docker/docker-compose.yml down          # توقف، داده حفظ می‌شود
docker compose -f docker/docker-compose.yml down -v       # ⚠️ حذف کامل داده‌ها
```
