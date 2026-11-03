# تصویر برنامه — مشترک بین سرویس‌های web و worker.
# فقط requirements/base.txt نصب می‌شود؛ ابزارهای تست (pytest/playwright) در تصویر تولید جایی ندارند.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /code

# curl فقط برای healthcheck سرویس‌ها لازم است.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/ requirements/
# تایم‌اوت و تلاش دوباره صریح: روی شبکه‌های کند (مثل سرورهای داخلی) مقدار پیش‌فرض ۱۵ ثانیه‌ای
# pip برای بسته‌های بزرگ (psycopg-binary حدود ۵ مگابایت) کافی نیست و بیلد بی‌دلیل شکست می‌خورد.
RUN pip install --no-cache-dir \
    --timeout 120 --retries 10 \
    -r requirements/base.txt gunicorn==23.0.0

COPY . .

# پایگاه‌داده، میزبان و کلید راز همه از env_file می‌آیند (هیچ مقدار ثابتی اینجا نیست).
ENV DJANGO_SETTINGS_MODULE=config.settings.dev

EXPOSE 8000

# پیش‌فرض توسعه؛ سرویس web آن را با gunicorn بازنویسی می‌کند.
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
