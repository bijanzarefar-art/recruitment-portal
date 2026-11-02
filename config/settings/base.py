"""
تنظیمات پایه مشترک بین توسعه و تولید.
اصل II (مرجعیت سرور)، V (نشست/CSRF)، VII (عدم اعتماد به ورودی) را اینجا اجرا می‌کنیم.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "insecure-dev-key-change-me")
DEBUG = False
ALLOWED_HOSTS = [
    h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if h.strip()
]
# دیجانگو ۴+ درخواست‌های تغییردهنده از مبدأ ناشناس را با ۴۰۳ رد می‌کند؛ دامنه‌ای که پشت HTTPS
# منتشر می‌شود باید اینجا فهرست شود (اصل V).
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "apps.common",
    "apps.accounts",
    "apps.candidates",
    "apps.jobs",
    "apps.applications",
    "apps.attachments",
    "apps.reporting",
    "apps.audit",
    "apps.operations",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "apps.accounts.middleware.StaffSessionIdleTimeoutMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "recruitment"),
        "USER": os.environ.get("POSTGRES_USER", "recruitment"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "recruitment"),
        "HOST": os.environ.get("POSTGRES_HOST", "db"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# بومی‌سازی فارسی/راست‌به‌چپ و زمان — اصل XII، FR-057/058
LANGUAGE_CODE = "fa"
TIME_ZONE = "UTC"  # ذخیره همیشه UTC؛ نمایش شمسی/Asia-Tehran فقط در لایه قالب (apps/common)
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "accounts.StaffUser"

# --- نشست و امنیت (FR-045, FR-046, FR-048؛ اصل V) ---
SESSION_COOKIE_NAME = "staff_sessionid"  # نشست کارمند؛ متقاضی اصلاً نشست/کوکی ندارد (اصل V نسخهٔ ۲.۰.۰)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = False  # در prod.py به True override می‌شود
SESSION_COOKIE_AGE = 60 * 60 * 8  # ۸ ساعت سقف مطلق نشست کارمند (FR-045)
SESSION_SAVE_EVERY_REQUEST = True  # برای اجرای صحیح idle-timeout ۳۰ دقیقه‌ای کنار SESSION_COOKIE_AGE
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

STAFF_SESSION_IDLE_TIMEOUT_SECONDS = 60 * 30
STAFF_SESSION_ABSOLUTE_TIMEOUT_SECONDS = 60 * 60 * 8

CSRF_COOKIE_HTTPONLY = False  # باید توسط جاوااسکریپت fetch خوانده شود
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = False  # در prod.py به True override می‌شود

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# CSP محدودکننده؛ بدون اسکریپت درون‌خطی در تولید (اصل VII)
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'",)
CSP_STYLE_SRC = ("'self'",)
CSP_IMG_SRC = ("'self'", "data:")

# --- اسکن (رابط قابل‌تعویض — research.md §۴) ---
# apps.notifications/SmsGateway کامل حذف شد (اصل V نسخهٔ ۲.۰.۰، D8 در docs/decisions.md):
# دیگر هیچ OTP پیامکی در سامانه وجود ندارد.
SCANNER_BACKEND = os.environ.get(
    "SCANNER_BACKEND", "apps.attachments.scanning.clamd_client.ClamdScannerClient"
)
CLAMD_HOST = os.environ.get("CLAMD_HOST", "clamav")
CLAMD_PORT = int(os.environ.get("CLAMD_PORT", "3310"))

# --- محدودیت‌های رزومه و فرم (FR-005, FR-004) ---
RESUME_MAX_SIZE_BYTES = 5 * 1024 * 1024  # 5 MiB
RESUME_ALLOWED_EXTENSIONS = (".pdf", ".doc", ".docx")
RESUME_ALLOWED_MIME_TYPES = (
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
)

# FR-043 — محدودسازی نرخ جست‌وجوی کد پیگیری بر اساس IP. **مصوب مالک پروژه** (D9 در
# docs/decisions.md): ۲۰ تلاش در هر IP در هر ۱۰ دقیقه (اصل V نسخهٔ ۲.۰.۰).
TRACKING_LOOKUP_IP_LIMIT = 20
TRACKING_LOOKUP_IP_WINDOW_SECONDS = 10 * 60

# FR-047 — محدودسازی نرخ ورود کارمند. **مصوب مالک پروژه** (D6 در docs/decisions.md):
#   حساب: ۵ تلاش در ۱۵ دقیقه      IP: ۱۵ تلاش در ۲۰ دقیقه (پنجره‌ها مستقل‌اند).
STAFF_LOGIN_ACCOUNT_LIMIT = 5
STAFF_LOGIN_ACCOUNT_WINDOW_SECONDS = 15 * 60
STAFF_LOGIN_IP_LIMIT = 15
STAFF_LOGIN_IP_WINDOW_SECONDS = 20 * 60

# اعتماد به هدر `X-Forwarded-For`: **پیش‌فرض هیچ پراکسی‌ای مورد اعتماد نیست**. اگر برنامه پشت
# پراکسی معکوس معتبر قرار دارد، تعداد هاپ‌های قابل‌اعتماد را از انتهای زنجیره صریح تنظیم کنید
# (نه از ابتدا — هدر از سمت کلاینت قابل‌جعل است).
# مقدار ۰ یعنی: هدر نادیده گرفته می‌شود و فقط REMOTE_ADDR استفاده می‌شود.
TRUSTED_PROXY_COUNT = 0

EXPORT_MAX_ROWS = 10_000
UPLOAD_ORPHAN_CLEANUP_AFTER_HOURS = 24

# --- سیاست نگهداری داده (FR-061) — fail-closed با دو کلید مستقل ---
# دو مفهوم جدا که هر دو باید هم‌زمان برقرار باشند تا حذف رخ دهد (اصل X، اصل XI):
#   ۱) RETENTION_POLICY_APPROVED — تأیید **سیاست کسب‌وکار** توسط ذی‌نفع (T069).
#   ۲) RETENTION_OPERATIONAL_ENABLED — فعال‌سازی **عملیاتی** حذف در این محیط.
# جدا نگه داشتنشان عمدی است: تصویب سیاست نباید به‌طور خودکار حذف را در هر محیطی روشن کند، و
# فعال‌سازی عملیاتی بدون سیاست مصوب نیز مجاز نیست.
#
# **سیاست مصوب مالک پروژه (D5)**: نگهداری ۱۲ ماه؛ **سوابق حسابرسی (`AuditEvent`) هرگز مشمول
# حذف نیستند** (این در کد نیز تضمین شده: `enforce_retention` هیچ عملیاتی روی آن جدول انجام نمی‌دهد).
RETENTION_POLICY_APPROVED = True
RETENTION_OPERATIONAL_ENABLED = False  # فعال‌سازی عملیاتی هر محیط: تصمیم جدا و مستقل
DATA_RETENTION_MONTHS = 12
RETENTION_AUDIT_RECORDS_EXCLUDED = True  # D5 — سوابق حسابرسی از حذف مستثنا

# --- لاگ ساختاریافته بدون داده حساس (FR-055، اصل VIII) ---
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "format": '{"level": "%(levelname)s", "time": "%(asctime)s", "logger": "%(name)s", "message": "%(message)s"}',
        },
    },
    "filters": {
        "redact_sensitive": {
            "()": "apps.common.logging_filters.RedactSensitiveDataFilter",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "filters": ["redact_sensitive"],
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "apps.common.pagination.DefaultPagination",
    "PAGE_SIZE": 25,
    "EXCEPTION_HANDLER": "apps.common.errors.envelope_exception_handler",
}
